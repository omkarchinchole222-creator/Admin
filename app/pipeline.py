import json
from pathlib import Path

from app.analysis import build_candidate_windows, score_windows, transcribe_audio
from app.editor import combine_long_video, cut_short_clip, verify_trimmed
from app.models import ClipSegment
from app.utils import download_video, fetch_video_metadata, normalize_youtube_url


def select_non_overlapping(segments: list[ClipSegment], target_count: int) -> list[ClipSegment]:
    selected: list[ClipSegment] = []
    for seg in segments:
        overlaps = any(not (seg.end <= s.start or seg.start >= s.end) for s in selected)
        if not overlaps:
            selected.append(seg)
        if len(selected) >= target_count:
            break
    return selected


def create_long_segment_plan(sorted_segments: list[ClipSegment], min_total: int = 600, max_total: int = 900) -> list[ClipSegment]:
    plan: list[ClipSegment] = []
    total = 0.0
    for seg in sorted_segments:
        if total >= max_total:
            break
        plan.append(seg)
        total += seg.duration
    if total < min_total:
        raise RuntimeError("Not enough high-scoring material to build a 10-15 minute long video.")
    return plan


def process_youtube_video(url: str) -> dict:
    normalized = normalize_youtube_url(url)

    out_root = Path("outputs")
    out_root.mkdir(exist_ok=True)
    run_dir = out_root / normalized.split("v=")[-1]
    run_dir.mkdir(parents=True, exist_ok=True)

    metadata = fetch_video_metadata(normalized)
    input_video = download_video(normalized, run_dir)

    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            transcript = transcribe_audio(input_video)
            windows = build_candidate_windows(transcript)
            scored = score_windows(windows)

            short_segments = select_non_overlapping(scored, target_count=5)
            if len(short_segments) < 3:
                raise RuntimeError("Unable to select at least 3 short segments.")

            short_paths = []
            for i, seg in enumerate(short_segments[:5], start=1):
                clip = run_dir / f"short_clip_{i}.mp4"
                cut_short_clip(input_video, seg, clip)
                verify_trimmed(input_video, clip, expected_min=15, expected_max=60)
                short_paths.append(str(clip))

            long1_plan = create_long_segment_plan(scored, min_total=600, max_total=900)
            long2_plan = create_long_segment_plan(list(reversed(scored)), min_total=600, max_total=900)
            long_paths = []
            for idx, plan in enumerate([long1_plan, long2_plan], start=1):
                out = run_dir / f"long_video_{idx}.mp4"
                combine_long_video(input_video, plan, out)
                verify_trimmed(input_video, out, expected_min=600, expected_max=900)
                long_paths.append(str(out))

            details = {
                "video_id": metadata.get("id"),
                "title": metadata.get("title"),
                "timestamps": [{"start": s.start, "end": s.end} for s in short_segments],
                "scores": [s.score for s in short_segments],
                "categories": [s.emotion for s in short_segments],
                "attempt": attempt,
            }
            (run_dir / "metadata.json").write_text(json.dumps(details, indent=2), encoding="utf-8")

            return {
                "short_clips": short_paths,
                "long_videos": long_paths,
                "metadata": details,
            }
        except Exception as exc:
            last_err = exc

    raise RuntimeError(f"Processing failed after retries: {last_err}")
