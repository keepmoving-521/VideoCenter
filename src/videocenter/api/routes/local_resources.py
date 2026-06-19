from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.models.media import LocalResource, Media
from videocenter.schemas.media import LocalResourceRead, LocalScanRequest, LocalScanResult
from videocenter.services.local_library import scan_local_library

router = APIRouter()


@router.get("", response_model=list[LocalResourceRead])
def list_resources(db: Session = Depends(get_db)):
    return db.scalars(select(LocalResource).order_by(LocalResource.id.desc())).all()


@router.post("/scan", response_model=LocalScanResult)
def scan_resources(payload: LocalScanRequest, db: Session = Depends(get_db)):
    if payload.media_id is not None and not db.get(Media, payload.media_id):
        raise HTTPException(status_code=404, detail="影视条目不存在")
    try:
        return scan_local_library(db, payload.path, payload.media_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
