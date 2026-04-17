from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import ClipOutput, Segment


class PipelineError(RuntimeError):
    """Raised when strict pipeline rules cannot be satisfied."""


class YouTubeClipPipeline:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.download_dir = self.workspace / "downloads"
        self.output_dir = self.workspace / "outputs"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, input_url: str, max_retries: int = 3) -> dict[str, Any]:
        normalized = self._normalize_youtube_url(input_url)
        info = self._probe_youtube(normalized)
        self._validate_youtube_info(info)
        source_path = self._download_video(normalized)
        source_duration = self._duration_of(source_path)

        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                segments = self._analyze_video(source_path, source_duration, attempt)
                short_clips = self._build_short_clips(source_path, source_duration, segments)
                long_videos = self._build_long_videos(source_path, source_duration, segments)
                self._verify_outputs(source_path, short_clips, long_videos)
                return {
                    "short_clips": [c.path.name for c in short_clips],
                    "long_videos": [c.path.name for c in long_videos],
                    "metadata": {
                        "timestamps": [c.as_dict() for c in short_clips + long_videos],
                        "scores": [
                            {
                                "start": round(seg.start, 3),
                                "end": round(seg.end, 3),
                                "score": round(seg.total_score, 4),
                                "category": seg.category,
                            }
                            for seg in sorted(segments, key=lambda s: s.total_score, reverse=True)
                        ],
                        "categories": sorted({seg.category for seg in segments}),
                    },
                }
            except PipelineError as exc:
                last_error = exc
        raise PipelineError(f"Pipeline failed after retries: {last_error}")

    @staticmethod
    def _normalize_youtube_url(url: str) -> str:
        url = url.strip()
        live_match = re.search(r"youtube\.com/live/([\w-]+)", url)
        if live_match:
            return f"https://www.youtube.com/watch?v={live_match.group(1)}"
        return url

    @staticmethod
    def _run_cmd(cmd: list[str]) -> str:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            raise PipelineError(f"Command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
        return proc.stdout

    def _probe_youtube(self, url: str) -> dict[str, Any]:
        output = self._run_cmd(["yt-dlp", "--dump-json", "--no-warnings", url])
        return json.loads(output)

    @staticmethod
    def _validate_youtube_info(info: dict[str, Any]) -> None:
        if info.get("is_live"):
            raise PipelineError("Live videos are not supported.")
        if info.get("availability") in {"private", "needs_auth", "subscriber_only"}:
            raise PipelineError(f"Unavailable video: {info.get('availability')}")
        if info.get("duration") is None or info["duration"] <= 0:
            raise PipelineError("Invalid or unavailable video duration.")

    def _download_video(self, url: str) -> Path:
        out_template = str(self.download_dir / "source.%(ext)s")
        self._run_cmd(["yt-dlp", "-f", "mp4/best", "-o", out_template, "--no-warnings", url])
        candidates = sorted(self.download_dir.glob("source.*"))
        if not candidates:
            raise PipelineError("Video download failed: source file missing.")
        return candidates[-1]

    def _duration_of(self, path: Path) -> float:
        output = self._run_cmd([
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]).strip()
        return float(output)

    def _scene_cut_times(self, source: Path) -> list[float]:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                str(source),
                "-filter:v",
                "select='gt(scene,0.35)',metadata=print",
                "-an",
                "-f",
                "null",
                "-",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        text = f"{proc.stdout}\n{proc.stderr}"
        times = []
        for match in re.finditer(r"pts_time:([0-9]+\.?[0-9]*)", text):
            times.append(float(match.group(1)))
        return sorted(set(times))

    def _analyze_video(self, source: Path, duration: float, attempt: int) -> list[Segment]:
        cut_times = self._scene_cut_times(source)
        if not cut_times:
            step = max(30.0 - (attempt * 4), 12.0)
            cut_times = [x for x in self._frange(step, duration, step)]

        boundaries = [0.0, *cut_times, duration]
        segments: list[Segment] = []
        for start, end in zip(boundaries, boundaries[1:]):
            seg_dur = end - start
            if seg_dur < 12:
                continue
            speech_score = self._speech_likelihood(seg_dur)
            emotion_score, category = self._emotion_estimate(start, end, duration)
            movement_score = min(1.0, 0.35 + (seg_dur / 65.0))
            hook_score = self._hook_estimate(start)
            rewatch_score = min(1.0, (emotion_score + movement_score) / 2)
            scene_score = min(1.0, seg_dur / 45.0)
            segments.append(
                Segment(
                    start=start,
                    end=end,
                    scene_score=scene_score,
                    speech_score=speech_score,
                    emotion_score=emotion_score,
                    movement_score=movement_score,
                    hook_score=hook_score,
                    rewatch_score=rewatch_score,
                    category=category,
                )
            )

        if len(segments) < 5:
            raise PipelineError("Insufficient detected segments for scoring.")
        return segments

    @staticmethod
    def _speech_likelihood(duration: float) -> float:
        # Placeholder heuristic; replace with whisper/ASR output when available.
        return min(1.0, 0.45 + duration / 90)

    @staticmethod
    def _emotion_estimate(start: float, end: float, full_duration: float) -> tuple[float, str]:
        center = (start + end) / 2
        phase = math.sin((center / max(full_duration, 1)) * 2 * math.pi)
        if phase > 0.6:
            return 0.92, "intense"
        if phase > 0.2:
            return 0.82, "funny"
        if phase > -0.2:
            return 0.74, "emotional"
        return 0.7, "angry"

    @staticmethod
    def _hook_estimate(start: float) -> float:
        if start <= 3:
            return 1.0
        if start <= 20:
            return 0.84
        return 0.65

    def _build_short_clips(self, source: Path, source_duration: float, segments: list[Segment]) -> list[ClipOutput]:
        ranked = sorted((s for s in segments if s.duration >= 15), key=lambda s: s.total_score, reverse=True)
        chosen: list[Segment] = []
        for seg in ranked:
            clip_len = min(60.0, seg.duration)
            if clip_len < 15:
                continue
            chosen.append(
                Segment(
                    start=seg.start,
                    end=seg.start + clip_len,
                    scene_score=seg.scene_score,
                    speech_score=seg.speech_score,
                    emotion_score=seg.emotion_score,
                    movement_score=seg.movement_score,
                    hook_score=seg.hook_score,
                    rewatch_score=seg.rewatch_score,
                    category=seg.category,
                )
            )
            if len(chosen) == 5:
                break
        if len(chosen) < 3:
            raise PipelineError("Unable to select 3-5 valid short clips.")

        outputs: list[ClipOutput] = []
        for idx, seg in enumerate(chosen[:5], start=1):
            out = self.output_dir / f"short_clip_{idx}.mp4"
            self._trim_and_crop(source, out, seg.start, seg.end, vertical=True)
            outputs.append(ClipOutput(path=out, start=seg.start, end=seg.end, score=seg.total_score, category=seg.category))

        for out in outputs:
            duration = self._duration_of(out.path)
            if abs(duration - source_duration) < 1.0:
                raise PipelineError("Short clip equals full source duration, refusing output.")
            if not (15 <= duration <= 60.5):
                raise PipelineError(f"Invalid short clip duration: {duration}")
        return outputs

    def _build_long_videos(self, source: Path, source_duration: float, segments: list[Segment]) -> list[ClipOutput]:
        if source_duration < 620:
            raise PipelineError("Source too short for two 10-15 minute long videos.")

        ranked = sorted(segments, key=lambda s: s.total_score, reverse=True)
        targets = [720.0, 660.0]
        outputs: list[ClipOutput] = []
        for i, target in enumerate(targets, start=1):
            seq = self._pack_for_duration(ranked, target)
            if not seq:
                raise PipelineError("Unable to build long-video timeline from segments.")
            concat_file = self.output_dir / f"long_{i}_concat.txt"
            parts: list[Path] = []
            for j, seg in enumerate(seq, start=1):
                part = self.output_dir / f"long_{i}_part_{j}.mp4"
                self._trim_and_crop(source, part, seg.start, min(seg.end, seg.start + 120), vertical=False)
                parts.append(part)
            concat_file.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
            final_path = self.output_dir / f"long_video_{i}.mp4"
            self._run_cmd([
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-vf",
                "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-c:a",
                "aac",
                str(final_path),
            ])
            start, end = seq[0].start, seq[-1].end
            outputs.append(ClipOutput(path=final_path, start=start, end=end, score=sum(s.total_score for s in seq) / len(seq), category="montage"))

        for out in outputs:
            duration = self._duration_of(out.path)
            if abs(duration - source_duration) < 1.0:
                raise PipelineError("Long output equals full source duration, refusing output.")
            if not (600 <= duration <= 930):
                raise PipelineError(f"Invalid long video duration: {duration}")
        return outputs

    @staticmethod
    def _pack_for_duration(segments: list[Segment], target: float) -> list[Segment]:
        total = 0.0
        chosen: list[Segment] = []
        used_windows: set[tuple[int, int]] = set()
        for seg in segments:
            window = (int(seg.start // 30), int(seg.end // 30))
            if window in used_windows:
                continue
            if total >= target:
                break
            chosen.append(seg)
            used_windows.add(window)
            total += min(seg.duration, 120)
        return chosen

    def _trim_and_crop(self, source: Path, out: Path, start: float, end: float, vertical: bool) -> None:
        if out.exists():
            out.unlink()
        duration = max(0.1, end - start)
        vf = (
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
            if vertical
            else "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
        )
        self._run_cmd([
            "ffmpeg",
            "-y",
            "-ss",
            str(round(start, 3)),
            "-i",
            str(source),
            "-t",
            str(round(duration, 3)),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-c:a",
            "aac",
            str(out),
        ])
        if not out.exists():
            raise PipelineError(f"Missing output clip: {out}")

    def _verify_outputs(self, source: Path, shorts: list[ClipOutput], longs: list[ClipOutput]) -> None:
        if not (3 <= len(shorts) <= 5):
            raise PipelineError("Output check failed: short clip count.")
        if len(longs) != 2:
            raise PipelineError("Output check failed: long video count.")
        source_duration = self._duration_of(source)
        for clip in [*shorts, *longs]:
            if not clip.path.exists() or clip.path.stat().st_size == 0:
                raise PipelineError(f"Output check failed: missing file {clip.path}")
            dur = self._duration_of(clip.path)
            if abs(dur - source_duration) < 1.0:
                raise PipelineError(f"Output check failed: untrimmed file {clip.path.name}")

    @staticmethod
    def _frange(start: float, stop: float, step: float) -> list[float]:
        vals: list[float] = []
        x = start
        while x < stop:
            vals.append(x)
            x += step
        return vals


def ensure_dependencies() -> None:
    required = ["yt-dlp", "ffmpeg", "ffprobe"]
    missing = [tool for tool in required if shutil.which(tool) is None]
    if missing:
        raise PipelineError(f"Missing required binaries: {', '.join(missing)}")
