from app.websocket.manager import send_job_to_shop


async def dispatch_job_to_agent(job):

    printer = job.assigned_printer

    if not printer:
        return False

    if not job.files:
        return False

    file = job.files[0]

    job_payload = {

        "job_id":
            str(job.job_id),

        "file_id":
            str(file.file_id),

        "download_url": (
            f"http://localhost:8000"
            f"/download/job/{job.job_id}/file/{file.file_id}"
        ),

        "stored_filename":
            file.stored_filename,

        "printer_id":
            str(printer.printer_id),

        "printer_name":
            printer.printer_name,

        "file_type":
            file.file_type,

        "page_count":
            file.page_count or 1,

        "copies":
            file.copies or 1,

        "paper_size":
            (
                file.paper_size.value
                if file.paper_size
                else "A4"
            ),

        "orientation":
            (
                file.orientation.value
                if file.orientation
                else "PORTRAIT"
            ),

        "duplex":
            bool(file.duplex),

        "print_type":
            (
                file.print_type.value
                if file.print_type
                else "BW"
            ),

        "color_mode":
            file.color_mode or "AUTO",

        "page_ranges":
            file.page_ranges
    }

    # send_job_to_shop() already creates:
    # {
    #     "type": "job",
    #     "data": job_payload
    # }
    #
    # Therefore pass job_payload directly.

    return await send_job_to_shop(
        str(job.owner_id),
        job_payload
    )
