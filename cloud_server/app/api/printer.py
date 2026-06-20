from fastapi import APIRouter

router = APIRouter(
    prefix="/printer",
    tags=["Printer"]
)


@router.get("/health")
def printer_health():
    return {
        "message": "Printer API Working"
    }