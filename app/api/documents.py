# app/api/documents.py
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import os

from app import crud, models, schemas
from app.api.deps import get_current_user
from app.db import get_db
from app.services import contracts, mtz
from app.services.audit import log_action, snapshot

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
CONTRACT_DOCUMENT_TYPES = frozenset({"llc_contract", "dmk_contract", "sdv_contract"})


@router.post("/clients/{client_id}/upload", response_model=schemas.DocumentRead)
def upload_file(
    client_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")
    if getattr(file, "size", None) is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large")
    try:
        document = crud.upload_document(db, client_id, file, file.filename, file.content_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Upload failed: {e}")
    log_action(db, entity="client", entity_id=client_id, action="document.upload", user=current_user, after=document)
    return document


@router.get("/clients/{client_id}/list", response_model=List[schemas.DocumentRead])
def list_client_files(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not crud.get_client(db, client_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return crud.list_documents(db, client_id)


@router.get("/contract_templates")
def list_contract_templates(
    current_user: models.User = Depends(get_current_user),
):
    return contracts.list_contract_templates()


@router.get("/contracts/next_number")
def next_contract_number(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return {"number": contracts.get_next_contract_number(db)}


@router.get("/mtz_templates")
def list_mtz_templates(
    current_user: models.User = Depends(get_current_user),
):
    return mtz.list_mtz_templates()


@router.patch("/{document_id}/status", response_model=schemas.DocumentRead)
def update_document_status(
    document_id: UUID,
    payload: schemas.DocumentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = crud.get_document(db, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if doc.document_type not in CONTRACT_DOCUMENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Статусы доступны только для договоров")
    before = snapshot(doc)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(doc, key, value)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    log_action(db, entity="client", entity_id=doc.client_id, action="document.status.update", user=current_user, before=before, after=doc)
    return doc


@router.get("/download/{document_id}")
def download_file(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = crud.get_document(db, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on disk")
    return FileResponse(path=doc.storage_path, filename=doc.filename, media_type=doc.content_type)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = crud.get_document(db, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    client_id = doc.client_id
    before = snapshot(doc)
    if not crud.delete_document(db, document_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    log_action(db, entity="client", entity_id=client_id, action="document.delete", user=current_user, before=before)
    return None


@router.post("/clients/{client_id}/generate_contract", response_model=schemas.DocumentRead)
def gen_contract(
    client_id: UUID,
    payload: schemas.ContractGeneration,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        contract = contracts.generate_contract(db, client_id, payload)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Template file missing on server")
    except ValueError as e:
        message = str(e)
        code = status.HTTP_404_NOT_FOUND if "Клиент" in message else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=message)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Generation failed: {e}")
    log_action(
        db,
        entity="client",
        entity_id=client_id,
        action="document.generate_contract",
        user=current_user,
        after=contract,
        details={
            "template_type": payload.template_type,
            "document_number": contract.document_number,
        },
    )
    return contract


@router.post("/clients/{client_id}/generate_mtz", response_model=schemas.DocumentRead)
def gen_mtz(
    client_id: UUID,
    payload: schemas.MtzGeneration,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        document = mtz.generate_mtz(db, client_id, payload)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Шаблон МТЗ отсутствует на сервере")
    except ValueError as e:
        message = str(e)
        code = status.HTTP_404_NOT_FOUND if "Клиент" in message else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=message)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"MTZ generation failed: {e}")

    log_action(
        db,
        entity="client",
        entity_id=client_id,
        action="document.generate_mtz",
        user=current_user,
        after=document,
        details={
            "template_type": payload.template_type,
            "document_number": document.document_number,
        },
    )
    return document
