from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
import os

from app import schemas, crud
from app.db import get_db

router = APIRouter()

@router.post("/clients/{client_id}/upload", response_model=schemas.DocumentRead)
def upload_file(client_id: UUID, file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        return crud.upload_document(
            db, 
            client_id, 
            file, 
            file.filename, 
            file.content_type
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

@router.get("/clients/{client_id}/list", response_model=List[schemas.DocumentRead])
def list_client_files(client_id: UUID, db: Session = Depends(get_db)):
    # Здесь используем рукописную конвертацию, т.к. Pydantic V2 строгий
    docs = crud.list_documents(db, client_id)
    return docs

@router.get("/download/{document_id}")
def download_file(document_id: UUID, db: Session = Depends(get_db)):
    doc = crud.get_document(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail="File missing on disk")
        
    return FileResponse(
        path=doc.storage_path, 
        filename=doc.filename, 
        media_type=doc.content_type
    )

@router.delete("/{document_id}", status_code=204)
def delete_file(document_id: UUID, db: Session = Depends(get_db)):
    if not crud.delete_document(db, document_id):
        raise HTTPException(status_code=404, detail="File not found")