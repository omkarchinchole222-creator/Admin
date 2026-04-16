import json
import os
from pathlib import Path

from openai import OpenAI
from scenedetect import ContentDetector, SceneManager, open_video

from app.models import ClipSegment
from app.utils import run_cmd


PROMPT = """
You are scoring virality from transcript windows.
For each item, return JSON array entries with keys:
index, emotion (funny|emotional|angry|intense|neutral),
hook_score (0-1), emotion_intensity (0-1), movement_action (0-1),
rewatch_potential (0-1), total_score (0-100), category.
Prefer Hindi/Marathi/English-aware understanding.
"""


def detect_scenes(video_path: Path) -> list[tuple[float, float]]:
    video = open_video(str(video_path))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=27.0))
    manager.detect_scenes(video)
    scenes = []
    for start, end in manager.get_scene_list():
        scenes.append((start.get_seconds(), end.get_seconds()))
    return scenes


def transcribe_audio(video_path: Path) -> list[dict]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for transcription and AI analysis.")
    client = OpenAI(api_key=api_key)

    audio_path = video_path.with_suffix(".wav")
    run_cmd([
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(audio_path),
    ])

    with audio_path.open("rb") as af:
        tr = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=af,
            response_format="verbose_json",
        )

    segments = tr.segments if hasattr(tr, "segments") else []
    return [
        {
            "start": float(s.start),
            "end": float(s.end),
            "text": s.text,
        }
        for s in segments
    ]


def build_candidate_windows(transcript_segments: list[dict], min_len: int = 15, max_len: int = 60) -> list[dict]:
    windows: list[dict] = []
    n = len(transcript_segments)
    for i in range(n):
        start = transcript_segments[i]["start"]
        text_parts = []
        for j in range(i, n):
            end = transcript_segments[j]["end"]
            dur = end - start
            text_parts.append(transcript_segments[j]["text"])
            if dur > max_len:
                break
            if min_len <= dur <= max_len:
                windows.append({"start": start, "end": end, "text": " ".join(text_parts)})
    if not windows:
        raise RuntimeError("No valid transcript windows between 15 and 60 seconds.")
    return windows


def score_windows(windows: list[dict]) -> list[ClipSegment]:
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)

    payload = [{"index": i, **w} for i, w in enumerate(windows[:120])]
    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    txt = resp.output_text
    try:
        scores = json.loads(txt)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse AI scoring response: {txt}") from exc

    by_idx = {s["index"]: s for s in scores}
    out: list[ClipSegment] = []
    for i, w in enumerate(payload):
        s = by_idx.get(i)
        if not s:
            continue
        out.append(
            ClipSegment(
                start=w["start"],
                end=w["end"],
                text=w["text"],
                emotion=s.get("emotion", "neutral"),
                score=float(s.get("total_score", 0.0)),
            )
        )
    out.sort(key=lambda x: x.score, reverse=True)
    return out
