---
name: emergent-video-automation
description: Build or update an automated pipeline that turns one YouTube URL into trimmed viral shorts and edited long videos with strict failure handling, timestamped ffmpeg cutting, scoring-based segment selection, and output validation/retries. Use when tasks involve YouTube ingestion, clip generation, AI-assisted highlight scoring, multilingual captioning, or batch export guarantees.
---

# Emergent Video Automation

Implement a strict, no-fake-output pipeline.

## Workflow

1. Validate URL input.
2. Normalize `youtube.com/live/<id>` into `youtube.com/watch?v=<id>`.
3. Reject live/private/unavailable videos before download.
4. Download only the provided URL and stop on failure.
5. Analyze scenes, speech signals, and emotion cues.
6. Score segments for hook, emotion, action, and rewatch potential.
7. Select 3–5 short segments (15–60s).
8. Cut with ffmpeg using exact timestamps.
9. Convert short clips to 9:16 and long videos to 16:9.
10. Export 2 long videos (10–15m), validate files, durations, and trimming.
11. Auto-retry with adjusted segmentation if any check fails.

## Non-Negotiable Rules

- Never output the full original source as a final artifact.
- Never fabricate outputs if processing fails.
- Never replace user input with demo videos.
- Always return a real error when a dependency or step fails.

## Command Recipes

Use `scripts/run_pipeline.sh` for local execution.

```bash
bash skills/emergent-video-automation/scripts/run_pipeline.sh "https://www.youtube.com/watch?v=<id>"
```

Use `references/output-schema.json` as the canonical response format.

## Adaptation Guidance

- Prefer deterministic ffmpeg/ffprobe checks over optimistic assumptions.
- Keep retries bounded and explicit.
- If ASR or emotion models are unavailable, fail or fallback with explicit metadata labels.
- Treat duration and trim checks as hard gates before returning success.
