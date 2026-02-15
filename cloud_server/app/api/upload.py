import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.websocket.manager import broadcast_job

router = APIRouter()
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ✅ STEP 1 — Show upload page (GET)
@router.get("/upload/{session_id}", response_class=HTMLResponse)
async def upload_page(request: Request, session_id: str):
    return templates.TemplateResponse(
        "mobile.html",
        {
            "request": request,
            "session_id": session_id
        }
    )


# ✅ STEP 2 — Handle file upload (POST)
@router.post("/upload/{session_id}")
async def handle_upload(
    session_id: str,
    file: UploadFile = File(...)
):
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Send job to printer
    await broadcast_job({
        "file_id": file_id,
        "filename": file.filename,
        "path": file_path
    })

    return {"message": "Job submitted successfully"}
