from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.pipeline import process_youtube_video

app = FastAPI(title="Viral Clip Generator")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/process")
def process(youtube_url: str = Form(...)):
    try:
        result = process_youtube_video(youtube_url)
        return JSONResponse(result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/health")
def health_check():
    return {"status": "ok", "outputs_dir": str(Path("outputs").resolve())}
