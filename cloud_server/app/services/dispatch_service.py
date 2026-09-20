from app.core.config import BASE_URL
from app.websocket.manager import send_job_to_agent, send_job_to_shop
from app.utils.logger import logger


async def dispatch_job_to_agent(job):
    """
    Dispatch a print job (with all files) to the selected printer's connected agent.
    """
    printer = job.assigned_printer

    if not printer:
        logger.error(f"Cannot dispatch job {job.job_id}: No assigned printer.")
        return False

    if not job.files:
        logger.error(f"Cannot dispatch job {job.job_id}: Job has no files.")
        return False

    # Build files list for multi-file print job dispatch
    files_payload = []
    for file in job.files:
        files_payload.append({
            "file_id": str(file.file_id),
            "original_filename": file.original_filename,
            "stored_filename": file.stored_filename,
            "download_url": f"{BASE_URL}/download/job/{job.job_id}/file/{file.file_id}",
            "file_type": file.file_type,
            "page_count": file.page_count or 1,
            "copies": file.copies or 1,
            "paper_size": (file.paper_size.value if file.paper_size else "A4"),
            "orientation": (file.orientation.value if file.orientation else "PORTRAIT"),
            "duplex": bool(file.duplex),
            "print_type": (file.print_type.value if file.print_type else "BW"),
            "color_mode": file.color_mode or "AUTO",
            "page_ranges": file.page_ranges
        })

    # Legacy/first file shortcut for single-file compatibility
    primary_file = files_payload[0]

    job_payload = {
        "job_id": str(job.job_id),
        "owner_id": str(job.owner_id),
        "printer_id": str(printer.printer_id),
        "printer_name": printer.printer_name,
        "agent_id": printer.agent_id,
        "total_files": len(files_payload),
        "files": files_payload,
        # Top-level backward compatibility fields
        "file_id": primary_file["file_id"],
        "download_url": primary_file["download_url"],
        "stored_filename": primary_file["stored_filename"],
        "file_type": primary_file["file_type"],
        "page_count": primary_file["page_count"],
        "copies": primary_file["copies"],
        "paper_size": primary_file["paper_size"],
        "orientation": primary_file["orientation"],
        "duplex": primary_file["duplex"],
        "print_type": primary_file["print_type"],
        "color_mode": primary_file["color_mode"],
        "page_ranges": primary_file["page_ranges"]
    }

    # First attempt routing to the specific agent registered for this printer
    dispatched = False
    if printer.agent_id:
        dispatched = await send_job_to_agent(printer.agent_id, job_payload)

    # Fallback to shop-level routing if agent_id routing was not connected
    if not dispatched:
        dispatched = await send_job_to_shop(str(job.owner_id), job_payload)

    if dispatched:
        logger.info(f"Dispatched Job {job.job_id} ({len(files_payload)} file(s)) to printer '{printer.printer_name}'")
    else:
        logger.warning(f"Could not dispatch Job {job.job_id}: Agent not connected.")

    return dispatched
