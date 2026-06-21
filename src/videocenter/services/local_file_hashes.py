import hashlib
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.models.media import LocalResource

HASH_CHUNK_SIZE = 1024 * 1024


def calculate_sha256(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(HASH_CHUNK_SIZE):
            checksum.update(chunk)
    return checksum.hexdigest()


def find_duplicate_local_resources(db: Session) -> list[list[LocalResource]]:
    resources = db.scalars(
        select(LocalResource)
        .where(
            LocalResource.checksum_sha256.is_not(None),
            LocalResource.is_available.is_(True),
        )
        .order_by(LocalResource.id)
    ).all()
    grouped: dict[str, list[LocalResource]] = defaultdict(list)
    for resource in resources:
        grouped[resource.checksum_sha256].append(resource)
    return [group for group in grouped.values() if len(group) > 1]
