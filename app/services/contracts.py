import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from docxtpl import DocxTemplate
from jinja2 import Environment, StrictUndefined
from num2words import num2words
from sqlalchemy.orm import Session

from app import crud, models

STORAGE_DIR = os.environ.get("STORAGE_DIR", "/app/storage")

TEMPLATES_CONFIG: dict[str, dict[str, str]] = {
    "llc_contract": {
        "filename": "llc_contract.docx",
        "label": "ООО Смарт Движение · Договор",
        "file_prefix": "ООО Договор",
    },
    "dmk_contract": {
        "filename": "dmk_contract.docx",
        "label": "ИП ДМК · Договор",
        "file_prefix": "ДМК Договор",
    },
    "dmk_instrument": {
        "filename": "dmk_instrument.docx",
        "label": "ИП ДМК · Акт",
        "file_prefix": "ДМК Акт",
    },
}

TEMPLATE_ALIASES = {
    "DMK_contract": "dmk_contract",
    "DMK_instrument": "dmk_instrument",
    "contract_original": "llc_contract",
    "contract_template": "llc_contract",
    "sdv_contract": "llc_contract",
    "SDV_contract": "llc_contract",
}


def list_contract_templates() -> list[dict[str, str]]:
    return [
        {"value": key, "label": config["label"]}
        for key, config in TEMPLATES_CONFIG.items()
    ]


def normalize_template_key(raw_key: str | None) -> str:
    key = (raw_key or "llc_contract").strip()
    key = TEMPLATE_ALIASES.get(key, key)
    if key not in TEMPLATES_CONFIG:
        allowed = ", ".join(TEMPLATES_CONFIG)
        raise ValueError(f"Неизвестный шаблон: {raw_key}. Доступны: {allowed}")
    return key


def format_date_ru(value: Any) -> str:
    if not value:
        return "__________"

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return "__________"
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw[:10], fmt).strftime("%d.%m.%Y")
            except ValueError:
                pass
        return raw

    try:
        return value.strftime("%d.%m.%Y")
    except Exception:
        return str(value)


def date_sort_value(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        raw = value.strip()
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(raw[:19], fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    return datetime.min.replace(tzinfo=timezone.utc)


def parse_money(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace("\u00a0", " ").replace("\u202f", " ")
    text = text.replace(" ", "").replace("−", "-").replace(",", ".")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]

    try:
        return float(cleaned) if cleaned not in {"", "-", "."} else 0.0
    except ValueError:
        return 0.0


def format_money(amount: float) -> str:
    return f"{amount:,.2f}".replace(",", " ")


def rub_to_words(amount: float) -> str:
    try:
        return num2words(amount, lang="ru", to="currency", currency="RUB").capitalize()
    except Exception:
        return format_money(amount)


def get_initials(last_name: str | None, first_name: str | None, middle_name: str | None) -> str:
    last = (last_name or "").strip()
    first = (first_name or "").strip()
    middle = (middle_name or "").strip()
    first_initial = f"{first[0].upper()}." if first else ""
    middle_initial = f"{middle[0].upper()}." if middle else ""
    return f"{last} {first_initial}{middle_initial}".strip()


def extract_tsr_numeric(tsr_code: str | None) -> str:
    if not tsr_code:
        return ""
    match = re.search(r"\d{1,2}-\d{2}[-.\d]*", tsr_code)
    return match.group(0) if match else ""


def extract_tsr_literals(tsr_code: str | None) -> str:
    if not tsr_code:
        return ""
    text_part = re.sub(r"\d{1,2}-\d{2}[-.\d]*", "", tsr_code)
    return text_part.strip(" .,-")


def split_document_number(full_number: str, prefix: str | None = None, suffix: str | None = None) -> tuple[str, str]:
    clean_prefix = (prefix or "").strip().upper()
    clean_suffix = (suffix or "").strip()

    if clean_prefix or clean_suffix:
        return clean_prefix, clean_suffix

    full = (full_number or "").strip()
    match = re.match(r"^([^0-9]*)([0-9].*)$", full)
    if match:
        return match.group(1).strip().upper(), match.group(2).strip()
    return "", full


def get_template_path(filename: str) -> str:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    possible_paths = [
        os.path.join(base_dir, "templates", filename),
        os.path.join("/app/app/templates", filename),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    checked = ", ".join(possible_paths)
    raise FileNotFoundError(f"Файл шаблона {filename} не найден. Проверенные пути: {checked}")


def latest_by_created(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {}
    return sorted(items, key=lambda item: date_sort_value(item.get("created_at")), reverse=True)[0]


def build_passport_full(passport: dict[str, Any], series: str, number: str) -> str:
    parts: list[str] = []
    if series or number:
        parts.append(f"{series} {number}".strip())
    if passport.get("issued_by"):
        parts.append(f"выдан {passport['issued_by']}")
    issue_date = format_date_ru(passport.get("issue_date"))
    if issue_date != "__________":
        parts.append(issue_date)
    if passport.get("department_code"):
        parts.append(f"код подразделения {passport['department_code']}")
    return ", ".join(parts)


def build_contract_items(client: dict[str, Any], modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Legacy positional TSR mapping used only by the untouched IP templates."""
    tsr_lines = [line.strip() for line in str(client.get("tsr_code") or "").splitlines() if line.strip()]
    max_len = max(len(tsr_lines), len(modules), 1)
    items: list[dict[str, Any]] = []

    for index in range(max_len):
        tsr_full = tsr_lines[index] if index < len(tsr_lines) else ""
        code = extract_tsr_numeric(tsr_full)
        name = extract_tsr_literals(tsr_full)
        module = modules[index] if index < len(modules) else {}
        module_name = str(module.get("module_name_index") or "").strip()
        description = " ".join(part for part in [code, name or module_name] if part).strip()

        if not description and not module:
            continue

        raw_quantity = parse_money(module.get("quantity") if module else 1)
        quantity = int(raw_quantity) if raw_quantity else 1
        price = parse_money(module.get("price"))
        items.append({
            "number": code or str(index + 1),
            "description": description or module_name or "__________",
            "quantity": quantity,
            "price": format_money(price) if price else "",
            "raw_price": price,
        })

    return items


def build_llc_contract_items(modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build reliable LLC rows from the explicit Module -> TSR relation."""
    items: list[dict[str, Any]] = []
    for index, module in enumerate(modules, start=1):
        tsr = module.get("tsr") or {}
        tsr_full = str(tsr.get("full_tsr_code") or "").strip()
        if not tsr_full:
            raise ValueError(f"У модуля «{module.get('module_name_index') or index}» не выбран ТСР")

        code = extract_tsr_numeric(tsr_full)
        name = extract_tsr_literals(tsr_full) or tsr_full
        quantity = max(1, int(parse_money(module.get("quantity")) or 1))
        total_price = parse_money(module.get("price"))
        unit_price = total_price / quantity if quantity else total_price
        component_names = [
            str(component.get("component_index") or "").strip()
            for component in (module.get("components") or [])
            if str(component.get("component_index") or "").strip()
        ]
        items.append({
            "number": code or tsr_full,
            "description": name,
            "name_and_code": "\n".join(part for part in (code or tsr_full, name) if part),
            "quantity": quantity,
            "price": format_money(unit_price),
            "raw_price": unit_price,
            "total_price": format_money(total_price),
            "raw_total_price": total_price,
            "module_name": str(module.get("module_name_index") or ""),
            "components_text": ", ".join(component_names),
        })
    return items


def select_llc_modules(client: dict[str, Any], payload: Any) -> list[dict[str, Any]]:
    modules = client.get("modules") or []
    selected_ids = {str(value) for value in (getattr(payload, "selected_module_ids", None) or [])}
    if not selected_ids:
        raise ValueError("Для договора ООО выберите хотя бы один модуль клиента")

    selected = [module for module in modules if str(module.get("module_id")) in selected_ids]
    if len(selected) != len(selected_ids):
        raise ValueError("Один или несколько выбранных модулей не принадлежат клиенту")
    return selected


def build_context(client: dict[str, Any], payload: Any, template_key: str = "llc_contract") -> dict[str, Any]:
    passport = latest_by_created(client.get("passports") or [])
    snils = latest_by_created(client.get("snils") or [])
    phones = client.get("phones") or []
    modules = select_llc_modules(client, payload) if template_key == "llc_contract" else (client.get("modules") or [])

    raw_series_number = str(passport.get("series_number", "")).replace("-", " ")
    compact_series_number = re.sub(r"\D", "", raw_series_number)
    passport_series = compact_series_number[:4]
    passport_number = compact_series_number[4:]
    if not passport_number and " " in raw_series_number:
        parts = raw_series_number.split()
        passport_series = parts[0] if parts else passport_series
        passport_number = " ".join(parts[1:])

    document_number = str(getattr(payload, "document_number", "") or "").strip()
    prefix, suffix = split_document_number(
        document_number,
        getattr(payload, "document_number_prefix", None),
        getattr(payload, "document_number_suffix", None),
    )
    full_document_number = document_number or f"{prefix}{suffix}".strip()

    document_date = format_date_ru(getattr(payload, "document_date", None))
    plan_date = format_date_ru(getattr(payload, "plan_date", None) or getattr(payload, "document_date", None))
    appendix_date = format_date_ru(
        getattr(payload, "appendix_date", None)
        or getattr(payload, "plan_date", None)
        or getattr(payload, "document_date", None)
    )
    appendix_number = str(getattr(payload, "appendix_number", None) or full_document_number or "1")

    prosthesis_type = str(client.get("prosthesis_type") or "").strip()
    clean_prosthesis_type = re.sub(r"(?i)^протез\s+", "", prosthesis_type)
    contract_items = (
        build_llc_contract_items(modules)
        if template_key == "llc_contract"
        else build_contract_items(client, modules)
    )

    module_sum = sum(parse_money(module.get("price")) for module in modules)
    certificate_sum = parse_money(client.get("certificate_price"))
    total_sum = module_sum if template_key == "llc_contract" else (module_sum or certificate_sum)

    full_name = f"{client.get('last_name', '')} {client.get('first_name', '')} {client.get('middle_name') or ''}".strip()
    phone = phones[0].get("number", "") if phones else ""
    snils_number = snils.get("number", "") if snils else ""
    passport_issue_date = format_date_ru(passport.get("issue_date"))
    passport_full = build_passport_full(passport, passport_series, passport_number)

    context: dict[str, Any] = {
        "НомерДоговора": full_document_number,
        "НомерДоговораБуквы": prefix,
        "НомерДоговораЧисло": suffix,
        "ДатаДоговора": document_date,
        "ДатаПлана": plan_date,
        "ДатаПриложения": appendix_date,
        "НомерАкта": appendix_number,
        "ДатаАкта": appendix_date,
        "НазваниеАкта": full_document_number,
        "Название акта": full_document_number,
        "ФИОЗаказчика": full_name,
        "ДатаРожденияЗаказчика": format_date_ru(passport.get("birth_date")),
        "ПаспортСерия": passport_series,
        "ПаспортНомер": passport_number,
        "ПаспортПолностью": passport_full,
        "КемВыданПаспорт": passport.get("issued_by", "________"),
        "ДатаВыдачиПаспорта": passport_issue_date,
        "КодПодразделения": passport.get("department_code", "______"),
        "АдресРегистрацииЗаказчика": passport.get("registration_address", "__________________"),
        "МестоРожденияЗаказчика": passport.get("birth_place", ""),
        "Телефон_заказчика": phone,
        "СНИЛСЗаказчика": snils_number,
        "НомерИПРА": client.get("ipra_code") or "",
        "ДатаВыдачиИПРА": format_date_ru(snils.get("issued_date") if snils else None),
        "Сумма": format_money(total_sum),
        "СуммаПрописью": rub_to_words(total_sum),
        "СуммаСЧехлом": format_money(total_sum),
        "СуммаПрописьюСЧехлом": rub_to_words(total_sum),
        "ИнициалыЗаказчикаКратко": get_initials(client.get("last_name"), client.get("first_name"), client.get("middle_name")),
        "ВерхнихилиНижнихконечностей": clean_prosthesis_type,
        "contract_items": contract_items,
        "act_items": contract_items,
        "ИтогоКоличество": sum(int(item.get("quantity") or 0) for item in contract_items),
        "ИтогоСтоимость": format_money(total_sum),
    }

    total_quantity = 0
    act_descriptions: list[str] = []
    for index in range(1, 5):
        item = contract_items[index - 1] if index - 1 < len(contract_items) else {}
        number = str(item.get("number", ""))
        description = str(item.get("description", ""))
        quantity = item.get("quantity", "")
        if quantity:
            total_quantity += int(quantity)
        context[f"КодТовара{index}"] = number
        context[f"Наименованиетовара{index}"] = description.replace(number, "", 1).strip() if number else description
        context[f"КолТовара{index}"] = str(quantity) if quantity else ""
        if description:
            act_descriptions.append(description)

    final_act_description = "; ".join(act_descriptions)
    context["КодТовара"] = extract_tsr_numeric(final_act_description) or final_act_description
    context["Наименованиетовара"] = extract_tsr_literals(final_act_description) or final_act_description
    context["КолТовара"] = str(total_quantity)
    context["ОписаниеТовара"] = final_act_description

    return context


def make_safe_filename(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "-", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or "Документ"


def validate_template_context(doc: DocxTemplate, context: dict[str, Any]) -> None:
    required = doc.get_undeclared_template_variables()
    missing = sorted(name for name in required if name not in context)
    if missing:
        raise ValueError(f"В шаблоне есть переменные без значения: {', '.join(missing)}")


def generate_contract(db: Session, client_id: uuid.UUID, payload: Any):
    template_key = normalize_template_key(getattr(payload, "template_type", "llc_contract"))
    template_config = TEMPLATES_CONFIG[template_key]
    template_path = get_template_path(template_config["filename"])

    client = crud.get_client(db, client_id)
    if not client:
        raise ValueError("Клиент не найден")

    context = build_context(client, payload, template_key)
    doc = DocxTemplate(template_path)
    validate_template_context(doc, context)
    doc.render(context, jinja_env=Environment(undefined=StrictUndefined))

    safe_date = make_safe_filename(str(getattr(payload, "document_date", "")).replace(".", "-").replace("/", "-"))
    client_last_name = make_safe_filename(str(client.get("last_name") or "Клиент"))
    filename = make_safe_filename(f"{template_config['file_prefix']}_{safe_date}_{client_last_name}.docx")
    unique_name = f"{uuid.uuid4()}_{filename}"

    os.makedirs(STORAGE_DIR, exist_ok=True)
    save_path = os.path.join(STORAGE_DIR, unique_name)
    doc.save(save_path)

    db_doc = models.Document(
        client_id=client_id,
        filename=filename,
        storage_path=save_path,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size=os.path.getsize(save_path),
        document_type=template_key,
        document_number=str(getattr(payload, "document_number", "") or "").strip(),
        contract_total=parse_money(context.get("Сумма")),
        certificate_amount=parse_money(client.get("certificate_price")),
        contract_metadata={
            "selected_modules": [
                {
                    "module_id": str(module.get("module_id")),
                    "module_name": module.get("module_name_index"),
                    "tsr": (module.get("tsr") or {}).get("full_tsr_code"),
                    "price": parse_money(module.get("price")),
                }
                for module in (
                    select_llc_modules(client, payload)
                    if template_key == "llc_contract"
                    else (client.get("modules") or [])
                )
            ],
            "document_date": str(getattr(payload, "document_date", "") or ""),
        },
    )
    db.add(db_doc)
    db.flush()
    if template_key in {"llc_contract", "dmk_contract"}:
        db.add(models.ContractAccounting(document_id=db_doc.document_id))
    db.commit()
    db.refresh(db_doc)
    return db_doc
