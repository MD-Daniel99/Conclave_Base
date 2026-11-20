"""Approved medical-technical conclusions (one DOCX per TSR).

Only fields explicitly approved for the current form are dynamic. The medical
specification, letterhead, headers, and signature blocks remain in the DOCX.
"""
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
from app.services.document_filenames import next_document_filename

STORAGE_DIR = os.environ.get("STORAGE_DIR", "/app/storage")

MTZ_TEMPLATES: dict[str, dict[str, str]] = {
    "mtz_zet_thigh_mpu": {
        "filename": "mtz_zet_thigh_mpu_approved.docx",
        "label": "8(1)-07-12 · Протез бедра модульный с микропроцессорным управлением · Движение ЗЕТ",
        "tsr_code": "8(1)-07-12",
        "file_prefix": "МТЗ ЗЕТ 8(1)-07-12",
    },
}

DISABILITY_REASONS = (
    "I Группа, Военная травма",
    "II Группа, Военная травма",
    "III Группа, Военная травма",
)

DIAGNOSIS_OPTIONS = (
    "Амп. Культя правого и левого плеча",
    "Амп. Культя правого плеча",
    "Амп. Культя левого плеча",
    "Амп. пальцев правой и левой руки",
    "Амп. пальцев правой руки",
    "Амп. пальцев левой руки",
    "Амп. Культя правого и левого предплечья",
    "Амп. Культя правого предплечья",
    "Амп. Культя левого предплечья",
    "Амп. Культя правой и левой кисти",
    "Амп. Культя правой кисти",
    "Амп. Культя левой кисти",
    "Амп. Культя правого и левого бедра",
    "Амп. Культя правого бедра",
    "Амп. Культя левого бедра",
    "Амп. Культя правой и левой голени",
    "Амп. Культя правой голени",
    "Амп. Культя левой голени",
)

# Codes in the approved DOCX are copied from its existing choice for each
# classification. No assumptions about clinical diagnoses are made here.
STUMP_CODES = {"Функциональная": "1.2.1", "Нефункциональная": "1.2.2"}
ACTIVITY_CODES = {"2-3": "1.3.2", "3-4": "1.3.3"}


def list_mtz_templates() -> list[dict[str, str]]:
    return [
        {"value": key, "label": item["label"], "tsr_code": item["tsr_code"]}
        for key, item in MTZ_TEMPLATES.items()
    ]


def _template_path(filename: str) -> Path:
    app_dir = Path(__file__).resolve().parents[1]
    for location in [app_dir / "templates" / filename, Path("/app/app/templates") / filename]:
        if location.is_file():
            return location
    raise FileNotFoundError(filename)


def _format_date(value: Any) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).strftime("%d.%m.%Y")
        except ValueError:
            pass
    return raw


def _safe_part(value: str, fallback: str = "документ") -> str:
    clean = re.sub(r"[^0-9A-Za-zА-Яа-яЁё()_. -]+", "_", value or "")
    return re.sub(r"\s+", " ", clean).strip(" ._")[:96] or fallback


def _latest_passport(passports: list[dict[str, Any]]) -> dict[str, Any]:
    return max(passports, key=lambda item: (int(item.get("version") or 0), str(item.get("created_at") or ""))) if passports else {}


def _parse_passport_number(value: str) -> tuple[str, str]:
    # Current passport serializer stores the Russian four-digit series and
    # six-digit number as one value. Do not silently truncate other formats.
    digits = re.sub(r"\D", "", value)
    if len(digits) == 10:
        return digits[:4], digits[4:]
    # Preserve arbitrary legacy passport values rather than inventing a series.
    parts = value.strip().rsplit(" ", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else ("", value.strip())


def prepare_mtz_context(client: dict[str, Any], payload: Any) -> dict[str, str]:
    """Pure, testable validation and data binding; no DB or filesystem writes."""
    full_name = " ".join(str(client.get(part) or "").strip() for part in ("last_name", "first_name", "middle_name")).strip()
    full_name = re.sub(r"\s+", " ", full_name)
    passport = _latest_passport(list(client.get("passports") or []))
    series, number = _parse_passport_number(str(passport.get("series_number") or ""))
    mse = str(client.get("mse_reference") or "").strip()
    if not mse:
        raise ValueError("Заполните справку МСЭ в карточке пациента, в разделе СНИЛС / ИПРА / МСЭ")
    if not all((full_name, passport.get("birth_date"), series, number, passport.get("issued_by"), passport.get("issue_date"), passport.get("department_code"))):
        raise ValueError("Для МТЗ необходимо заполнить ФИО, дату рождения и паспортные данные пациента")

    diagnoses = list(payload.diagnoses)
    if not diagnoses or any(value not in DIAGNOSIS_OPTIONS for value in diagnoses):
        raise ValueError("Выберите один или несколько диагнозов из перечня")
    if payload.disability_group_reason not in DISABILITY_REASONS:
        raise ValueError("Выберите группу и причину инвалидности")
    if payload.stump_condition not in STUMP_CODES or payload.activity_level not in ACTIVITY_CODES:
        raise ValueError("Выберите состояние культи и уровень активности")
    raw_weight = str(payload.weight_kg).strip().replace(",", ".")
    try:
        weight = float(raw_weight)
    except ValueError as exc:
        raise ValueError("Укажите корректный вес пациента") from exc
    if not (0 < weight <= 500):
        raise ValueError("Вес пациента должен быть больше 0 и не превышать 500 кг")

    return {
        "full_name": full_name,
        "birth_date": _format_date(passport["birth_date"]),
        "passport_series": series,
        "passport_number": number,
        "passport_issuer": str(passport["issued_by"]).strip(),
        "passport_issue_date": _format_date(passport["issue_date"]),
        "passport_department": str(passport["department_code"]).strip(),
        "mse_reference": mse,
        "disability_group_reason": str(payload.disability_group_reason).strip(),
        "diagnosis": "; ".join(dict.fromkeys(diagnoses)),
        "amputation_level": str(payload.amputation_level).strip(),
        "stump_condition": payload.stump_condition,
        "stump_condition_code": STUMP_CODES[payload.stump_condition],
        "activity_level": payload.activity_level,
        "activity_level_code": ACTIVITY_CODES[payload.activity_level],
        "weight_kg": format(weight, "g").replace(".", ","),
    }



def _compact_long_mtz_signatures(path: Path) -> None:
    """Prevent the final signature from appearing alone on a third page.

    The approved form contains three empty spacer paragraphs above the first
    signature and three between signatories. Only for long diagnosis lists we
    remove these spacers, leaving all fonts, tables, and written content intact.
    """
    from docx import Document

    document = Document(path)
    paragraphs = document.paragraphs
    doctor_at = next((i for i, p in enumerate(paragraphs) if p.text.strip() == "Врач-хирург"), None)
    director_at = next((i for i, p in enumerate(paragraphs) if p.text.strip().startswith("Генеральный директор")), None)
    if doctor_at is None or director_at is None or director_at <= doctor_at:
        return

    def removable(paragraph) -> bool:
        return not paragraph.text.strip() and not paragraph._element.xpath('.//w:drawing | .//w:pict | .//w:br')

    preceding = [p for p in paragraphs[max(0, doctor_at - 3):doctor_at] if removable(p)]
    between = [p for p in paragraphs[doctor_at + 1:director_at] if removable(p)]
    if not preceding and not between:
        return
    for paragraph in preceding + between:
        paragraph._element.getparent().remove(paragraph._element)
    document.save(path)

def generate_mtz(db: Session, client_id, payload) -> models.Document:
    client = crud.get_client(db, client_id)
    if not client:
        raise ValueError("Пациент не найден")
    template_key = str(payload.template_type).strip()
    config = MTZ_TEMPLATES.get(template_key)
    if config is None:
        raise ValueError("Неизвестный или устаревший шаблон МТЗ")
    context = prepare_mtz_context(client, payload)
    template = DocxTemplate(str(_template_path(config["filename"])))
    template.render(context, jinja_env=Environment(undefined=StrictUndefined, autoescape=True))
    storage = Path(STORAGE_DIR)
    storage.mkdir(parents=True, exist_ok=True)
    patient_part = _safe_part(str(client.get("last_name") or context["full_name"]), "пациент")
    filename = next_document_filename(db, client_id, f'{config["file_prefix"]}_{patient_part}.docx')
    stored_path = storage / f"{uuid.uuid4()}_{filename}"
    template.save(str(stored_path))
    if len(context["diagnosis"]) > 200 or len(context["mse_reference"]) > 100:
        _compact_long_mtz_signatures(stored_path)

    document = models.Document(
        client_id=client_id,
        filename=filename,
        storage_path=str(stored_path),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size=stored_path.stat().st_size,
        document_type=template_key,
        document_number=None,  # Intentionally completed by hand after printing.
        contract_total=None,
        certificate_amount=None,
        certificate_id=None,
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
        stored_path.unlink(missing_ok=True)
        raise
