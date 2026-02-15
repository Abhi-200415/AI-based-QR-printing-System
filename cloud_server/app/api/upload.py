import uuid
import qrcode
import os
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/session", response_class=HTMLResponse)
async def create_session(request: Request):
    session_id = str(uuid.uuid4())

    os.makedirs("static", exist_ok=True)

    base_url = str(request.base_url).rstrip("/")

    # ✅ FIXED HERE
    upload_url = f"{base_url}/upload/{session_id}"

    qr = qrcode.make(upload_url)
    qr_path = f"static/{session_id}.png"
    qr.save(qr_path)

    return templates.TemplateResponse(
        "session.html",
        {
            "request": request,
            "qr_path": f"/{qr_path}",
            "session_id": session_id
        }
    )
