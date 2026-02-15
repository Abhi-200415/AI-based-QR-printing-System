import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from app.core.job_store import print_jobs
from app.websocket.manager import broadcast_job

router = APIRouter()

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session: str = Form(...)
):
    try:
        file_id = str(uuid.uuid4())
        filename = f"{file_id}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        # Save file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Create job
        job = {
            "id": file_id,
            "filename": filename,
            "file_url": f"/uploads/{filename}",
            "status": "pending"
        }

        # Store job
        print_jobs.append(job)

        # Broadcast job to connected printers
        await broadcast_job(job)

        return JSONResponse({"message": "Job submitted successfully"})

    except Exception as e:
        return JSONResponse({"error": str(e)})


@router.post("/mark_printed/{job_id}")
def mark_printed(job_id: str):
    for job in print_jobs:
        if job["id"] == job_id:
            job["status"] = "printed"
            return {"message": "Marked as printed"}
    return {"error": "Job not found"}
