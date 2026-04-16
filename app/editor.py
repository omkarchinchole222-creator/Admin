from pathlib import Path

from app.models import ClipSegment
from app.utils import ffprobe_duration, run_cmd


def write_srt(segment: ClipSegment, target: Path) -> None:
    s = 0
    e = segment.duration
    start_ts = to_srt_timestamp(s)
    end_ts = to_srt_timestamp(e)
    target.write_text(f"1\n{start_ts} --> {end_ts}\n{segment.text}\n", encoding="utf-8")


def to_srt_timestamp(sec: float) -> str:
    hrs = int(sec // 3600)
    mins = int((sec % 3600) // 60)
    secs = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"


def cut_short_clip(input_video: Path, segment: ClipSegment, out_path: Path) -> None:
    srt_path = out_path.with_suffix(".srt")
    write_srt(segment, srt_path)

    vf = (
        "crop=ih*9/16:ih:(iw-ow)/2:0,"
        "scale=1080:1920,"
        f"subtitles={srt_path.as_posix()}"
    )

    run_cmd(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(segment.start),
            "-to",
            str(segment.end),
            "-i",
            str(input_video),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(out_path),
        ]
    )


def combine_long_video(input_video: Path, segments: list[ClipSegment], out_path: Path) -> None:
    part_dir = out_path.parent / f"{out_path.stem}_parts"
    part_dir.mkdir(parents=True, exist_ok=True)
    concat_file = part_dir / "concat.txt"

    entries = []
    for idx, seg in enumerate(segments):
        part = part_dir / f"part_{idx}.mp4"
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(seg.start),
                "-to",
                str(seg.end),
                "-i",
                str(input_video),
                "-vf",
                "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(part),
            ]
        )
        entries.append(f"file '{part.as_posix()}'")

    concat_file.write_text("\n".join(entries), encoding="utf-8")
    run_cmd(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(out_path),
        ]
    )


def verify_trimmed(input_video: Path, output_video: Path, expected_min: float, expected_max: float) -> None:
    src_dur = ffprobe_duration(input_video)
    out_dur = ffprobe_duration(output_video)

    if abs(src_dur - out_dur) < 2.0:
        raise RuntimeError(f"{output_video.name} appears untrimmed (matches source duration).")
    if not (expected_min <= out_dur <= expected_max):
        raise RuntimeError(
            f"{output_video.name} duration {out_dur:.2f}s outside expected range {expected_min}-{expected_max}s."
        )
