from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["系统"])
def health() -> dict[str, str]:
    return {"status": "ok"}
