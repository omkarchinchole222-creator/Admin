# AI YouTube Clip Automation

Automated web app that processes a single YouTube URL and generates:
- 3–5 short vertical viral clips (15–60s)
- 2 long edited horizontal videos (10–15m)

## Run

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=...
uvicorn app.main:app --reload
```

## Notes

- Uses `yt-dlp`, `ffmpeg`, and `ffprobe` binaries from system PATH.
- Never exports the full source video: duration checks enforce real trimming.
- Retries processing up to 3 times; surfaces real error if it cannot complete.
