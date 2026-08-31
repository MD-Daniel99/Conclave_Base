from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate
from jinja2 import Environment, StrictUndefined
from sqlalchemy.orm import Session

from app import crud, models

STORAGE_DIR = os.environ.get("STORAGE_DIR", "/app/storage")

# One registry is deliberately used even while there is only one document.
# Adding another TSR later means adding a template file + one entry here; the
# API/UI do not need to be redesigned.
MTZ_TEMPLATES: dict[str, dict[str, str]] = {
    "mtz_8_1_07_14": {
        "filename": "mtz_8_1_07_14.docx",
        "label": "8(1)-07-14 · Протез голени модульный с микропроцессорной стопой",
        "tsr_code": "8(1)-07-14",
        "file_prefix": "МТЗ 8(1)-07-14",
    },
}


def list_mtz_templates() -> list[dict[str, str]]:
    return [
        {
            "value": key,
            "label": item["label"],
            "tsr_code": item["tsr_code"],
        }
        for key, item in MTZ_TEMPLATES.items()
    ]


def _template_path(filename: str) -> Path:
    app_dir = Path(__file__).resolve().parents[1]
    candidates = [
        app_dir / "templates" / filename,
        Path("/app/app/templates") / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(filename)


def _format_date_ru(value: Any) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).strftime("%d.%m.%Y")
        except ValueError:
            continue
    return raw


def _safe_part(value: str, fallback: str = "документ") -> str:
    clean = re.sub(r"[^0-9A-Za-zА-Яа-яЁё()_. -]+", "_", value or "")
    clean = re.sub(r"\s+", " ", clean).strip(" ._")
    return clean[:96] or fallback


def _latest_passport(passports: list[dict[str, Any]]) -> dict[str, Any]:
    if not passports:
        return {}
    return max(
        passports,
        key=lambda item: (
            int(item.get("version") or 0),
            str(item.get("created_at") or ""),
        ),
    )


def generate_mtz(db: Session, client_id, payload) -> models.Document:
    client = crud.get_client(db, client_id)
    if not client:
        raise ValueError("Клиент не найден")

    template_key = str(getattr(payload, "template_type", "") or "mtz_8_1_07_14").strip()
    config = MTZ_TEMPLATES.get(template_key)
    if not config:
        raise ValueError("Неизвестный шаблон МТЗ")

    full_name = " ".join(
        part.strip()
        for part in (
            str(client.get("last_name") or ""),
            str(client.get("first_name") or ""),
            str(client.get("middle_name") or ""),
        )
        if part and part.strip()
    )
    passport = _latest_passport(list(client.get("passports") or []))
    phones = list(client.get("phones") or [])
    phone = str(phones[0].get("number") or "") if phones else ""

    context = {
        "mtz_number": str(payload.mtz_number).strip(),
        "document_date": _format_date_ru(payload.document_date),
        "full_name": full_name,
        "birth_date": _format_date_ru(passport.get("birth_date")),
        "disability_group_reason": str(payload.disability_group_reason).strip(),
        "certificate_reference": str(payload.certificate_reference).strip(),
        "diagnosis": str(payload.diagnosis).strip(),
        "phone": phone,
        "amputation_level": str(payload.amputation_level).strip(),
        "weight_kg": str(payload.weight_kg).strip(),
    }

    template = DocxTemplate(str(_template_path(config["filename"])))
    template.render(context, jinja_env=Environment(undefined=StrictUndefined, autoescape=True))

    storage = Path(STORAGE_DIR)
    storage.mkdir(parents=True, exist_ok=True)
    date_part = _safe_part(context["document_date"].replace(".", "-"), "без-даты")
    patient_part = _safe_part(str(client.get("last_name") or full_name), "пациент")
    filename = f'{config["file_prefix"]}_{date_part}_{patient_part}.docx'
    stored_name = f"{uuid.uuid4()}_{filename}"
    save_path = storage / stored_name
    template.save(str(save_path))

    document = models.Document(
        client_id=client_id,
        filename=filename,
        storage_path=str(save_path),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size=save_path.stat().st_size,
        document_type=template_key,
        document_number=context["mtz_number"],
        contract_total=None,
        certificate_amount=None,
        certificate_id=None,
        # The manually entered medical details are deliberately NOT stored in
        # CLIENT or DOCUMENT metadata. They live only long enough to render the
        # DOCX, as requested. Metadata keeps only non-medical template identity.
        contract_metadata={
            "template_type": template_key,
            "template_label": config["label"],
            "tsr_code": config["tsr_code"],
        },
    )
    db.add(document)
    try:
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        db.rollback()
        try:
            save_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise
