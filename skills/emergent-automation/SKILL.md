---
name: emergent-automation
description: Build and operate a fully automated pipeline that takes one YouTube URL and produces validated short viral clips and long edited videos with strict failure handling. Use when asked to automate ingest, analysis, scoring, trimming, format conversion, captioning, export verification, and auto-retry for real video outputs only.
---

# Emergent Automation Skill

## Execute the mandatory workflow
1. Validate the input URL and normalize `/live/<id>` to `watch?v=<id>`.
2. Reject live/private/unavailable videos before downloading.
3. Download only the provided video. Stop on failure.
4. Analyze the video and speech (Hindi/Marathi/English) and detect emotional moments.
5. Score candidate segments for hook, emotion intensity, movement/action, and rewatch potential.
6. Select top non-overlapping 15–60 second segments for 3–5 shorts.
7. Cut clips with timestamp-based FFmpeg trimming; fail if output equals full duration.
8. Convert shorts to vertical 9:16 and long videos to horizontal 16:9.
9. Add synced captions; add meme overlays as best effort without blocking output.
10. Build two 10–15 minute long edits from top-scoring segments.
11. Validate every output file exists, is trimmed, and has expected duration.
12. Auto-retry by adjusting segmentation/scoring thresholds up to a bounded attempt count.

## Enforce strict integrity rules
- Never return full original duration as output.
- Never generate synthetic/random fallback videos.
- Never process links other than the provided URL.
- If pipeline checks fail after retries, return a real error with stage and reason.

## Return schema
Return exactly:

```json
{
  "short_clips": ["clip1.mp4", "clip2.mp4", "clip3.mp4"],
  "long_videos": ["video1.mp4", "video2.mp4"],
  "metadata": {
    "timestamps": [],
    "scores": [],
    "categories": []
  }
}
```
