"""Display-name collision handling; storage names remain UUID-prefixed."""
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models


def next_document_filename(db: Session, client_id: UUID, proposed: str) -> str:
    existing = set(db.execute(
        select(models.Document.filename).where(models.Document.client_id == client_id)
    ).scalars().all())
    if proposed not in existing:
        return proposed
    path = Path(proposed)
    index = 2
    while True:
        candidate = f"{path.stem} ({index}){path.suffix}"
        if candidate not in existing:
            return candidate
        index += 1
