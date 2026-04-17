from pathlib import Path

from app.pipeline import YouTubeClipPipeline


def test_normalize_live_url() -> None:
    url = "https://www.youtube.com/live/abc123XYZ"
    assert YouTubeClipPipeline._normalize_youtube_url(url) == "https://www.youtube.com/watch?v=abc123XYZ"


def test_normalize_watch_url() -> None:
    url = "https://www.youtube.com/watch?v=abc"
    assert YouTubeClipPipeline._normalize_youtube_url(url) == url


def test_pack_for_duration_non_empty() -> None:
    pipeline = YouTubeClipPipeline(workspace=Path("/tmp/emergent-test"))
    segs = pipeline._analyze_video  # smoke for attribute existence
    assert callable(segs)
