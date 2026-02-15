import os
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from app.websocket.manager import session_jobs

router = APIRouter()
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, session: str):
    return templates.TemplateResponse(
        "upload.html",
        {"request": request, "session": session}
    )

@router.post("/upload")
async def handle_upload(
    session: str = Form(...),
    file: UploadFile = File(...),
    copies: int = Form(...),
    color: str = Form(...)
):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    session_jobs[session] = {
        "file_path": file_path,
        "copies": copies,
        "color": color
    }

    return {"message": "Job submitted successfully"}
