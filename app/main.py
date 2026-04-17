from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

from .pipeline import PipelineError, YouTubeClipPipeline, ensure_dependencies


class ProcessRequest(BaseModel):
    youtube_url: HttpUrl


app = FastAPI(title="Emergent Video Automation")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/process")
def process_video(req: ProcessRequest) -> dict:
    try:
        ensure_dependencies()
        pipeline = YouTubeClipPipeline(workspace=Path("workdir"))
        return pipeline.run(str(req.youtube_url))
    except PipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
