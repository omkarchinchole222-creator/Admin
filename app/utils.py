import json
import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse


YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def run_cmd(cmd: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{proc.stderr}")
    return proc.stdout


def normalize_youtube_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.netloc not in YOUTUBE_HOSTS:
        raise ValueError("Only YouTube URLs are supported.")

    if "youtu.be" in parsed.netloc:
        video_id = parsed.path.strip("/")
        return f"https://www.youtube.com/watch?v={video_id}"

    if parsed.path.startswith("/live/"):
        video_id = parsed.path.split("/live/")[-1].strip("/")
        return f"https://www.youtube.com/watch?v={video_id}"

    if parsed.path.startswith("/watch"):
        query = parse_qs(parsed.query)
        video_id = query.get("v", [None])[0]
        if not video_id:
            raise ValueError("Invalid YouTube watch URL; missing video id.")
        return f"https://www.youtube.com/watch?v={video_id}"

    raise ValueError("Unsupported YouTube URL format.")


def fetch_video_metadata(url: str) -> dict:
    output = run_cmd(["yt-dlp", "--dump-single-json", "--no-download", url])
    data = json.loads(output)

    if data.get("is_live") or data.get("live_status") in {"is_live", "post_live"}:
        raise ValueError("Live videos are not supported.")
    if data.get("availability") in {"private", "unlisted", "subscriber_only"}:
        raise ValueError("Video is private/unavailable for processing.")

    return data


def download_video(url: str, workdir: Path) -> Path:
    out_tpl = workdir / "input.%(ext)s"
    run_cmd(
        [
            "yt-dlp",
            "-f",
            "bestvideo+bestaudio/best",
            "--merge-output-format",
            "mp4",
            "-o",
            str(out_tpl),
            url,
        ]
    )
    candidates = sorted(workdir.glob("input.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError("Video download failed. No file created.")
    return candidates[0]


def ffprobe_duration(path: Path) -> float:
    out = run_cmd(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    ).strip()
    return float(out)
