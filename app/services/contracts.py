import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from docxtpl import DocxTemplate
from jinja2 import Environment, StrictUndefined
from num2words import num2words
from sqlalchemy import select, text
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


def get_next_contract_number(db: Session) -> str:
    """Return the next number in the new PREFIX/NNN contract series.

    Legacy test documents used date-like numbers without a slash. They are not
    part of the new global 001, 002, ... sequence requested for contracts.
    """
    existing_numbers = db.execute(
        select(models.Document.document_number)
        .where(models.Document.document_type.in_(("llc_contract", "dmk_contract")))
    ).scalars().all()
    contract_count = sum(
        1
        for raw_number in existing_numbers
        if re.fullmatch(r"\s*[^/]+/\d+\s*", str(raw_number or ""))
    )
    return f"{contract_count + 1:03d}"


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
        rubles = int(amount)
        kopecks = int(round((amount - rubles) * 100))
        if kopecks == 100:
            rubles += 1
            kopecks = 0
        words = num2words(rubles, lang="ru").capitalize()
        return f"{words} {kopecks:02d}/100" if kopecks else words
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


def group_llc_components_by_tsr(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group client components by their explicit TSR relation."""
    groups: dict[str, dict[str, Any]] = {}
    ordered_components = sorted(
        components,
        key=lambda component: (
            str((component.get("tsr") or {}).get("full_tsr_code") or "").casefold(),
            str(component.get("module_name_index") or "").casefold(),
            str(component.get("module_id") or ""),
        ),
    )

    for index, component in enumerate(ordered_components, start=1):
        tsr = component.get("tsr") or {}
        tsr_full = str(tsr.get("full_tsr_code") or "").strip()
        if not tsr_full:
            raise ValueError(
                f"У комплектующей «{component.get('module_name_index') or index}» не выбран ТСР"
            )

        group_key = str(component.get("client_tsr_id") or component.get("tsr_id") or tsr.get("id") or tsr_full)
        if group_key not in groups:
            groups[group_key] = {
                "key": group_key,
                "client_tsr_id": str(component.get("client_tsr_id") or ""),
                "tsr_id": str(component.get("tsr_id") or tsr.get("id") or ""),
                "tsr_full": tsr_full,
                "components": [],
            }
        groups[group_key]["components"].append(component)

    return list(groups.values())


def build_llc_contract_items(
    components: list[dict[str, Any]],
    client_tsr_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build one LLC contract row per selected client TSR.

    A TSR remains selectable even before components are attached. Components
    are supplemental details; the contractual price is always the certificate
    price stored on the client↔TSR link.
    """
    components_by_assignment: dict[str, list[dict[str, Any]]] = {}
    legacy_components_by_tsr: dict[str, list[dict[str, Any]]] = {}
    for component in components:
        client_tsr_id = str(component.get("client_tsr_id") or "")
        tsr_id = str(component.get("tsr_id") or (component.get("tsr") or {}).get("id") or "")
        if client_tsr_id:
            components_by_assignment.setdefault(client_tsr_id, []).append(component)
        if tsr_id:
            legacy_components_by_tsr.setdefault(tsr_id, []).append(component)

    items: list[dict[str, Any]] = []
    for client_tsr in client_tsr_items:
        tsr = client_tsr.get("tsr") or {}
        client_tsr_id = str(client_tsr.get("client_tsr_id") or "")
        tsr_id = str(client_tsr.get("tsr_id") or tsr.get("id") or "")
        tsr_full = str(tsr.get("full_tsr_code") or "").strip()
        if not tsr_full:
            raise ValueError("У выбранного ТСР отсутствует код в справочнике")
        code = extract_tsr_numeric(tsr_full)
        name = extract_tsr_literals(tsr_full) or tsr_full
        group_components = sorted(
            components_by_assignment.get(client_tsr_id, [])
            if client_tsr_id
            else legacy_components_by_tsr.get(tsr_id, []),
            key=lambda component: (
                str(component.get("module_name_index") or "").casefold(),
                str(component.get("module_id") or ""),
            ),
        )
        certificate_price = parse_money(client_tsr.get("certificate_price"))
        if certificate_price <= 0:
            raise ValueError(f"Для ТСР «{tsr_full}» укажите стоимость сертификата")
        component_names: list[str] = []
        for component_index, component in enumerate(group_components, start=1):
            component_name = str(component.get("module_name_index") or "").strip() or "Без названия"
            component_quantity = max(1, int(parse_money(component.get("quantity")) or 1))
            quantity_suffix = f" — {component_quantity} шт." if component_quantity != 1 else ""
            component_names.append(f"{component_index}. {component_name}{quantity_suffix}")

        items.append({
            "number": code or tsr_full,
            "description": name,
            "name_and_code": "\n".join(part for part in (code or tsr_full, name) if part),
            # Одна строка — один выбранный ТСР (протез), а не количество его деталей.
            "quantity": 1,
            # Цена договора по ТСР — стоимость электронного сертификата,
            # а не сумма отпускных цен комплектующих.
            "price": format_money(certificate_price),
            "raw_price": certificate_price,
            "total_price": format_money(certificate_price),
            "raw_total_price": certificate_price,
            "certificate_price": certificate_price,
            "check_date": format_date_ru(client_tsr.get("check_date")),
            "module_name": ", ".join(
                str(component.get("module_name_index") or "")
                for component in group_components
                if str(component.get("module_name_index") or "").strip()
            ),
            "components_text": "\n".join(component_names),
        })
    return items


def select_llc_modules(client: dict[str, Any], payload: Any) -> list[dict[str, Any]]:
    modules = client.get("modules") or []
    selected_ids = {str(value) for value in (getattr(payload, "selected_module_ids", None) or [])}
    if not selected_ids:
        return []

    selected = [module for module in modules if str(module.get("module_id")) in selected_ids]
    if len(selected) != len(selected_ids):
        raise ValueError("Одна или несколько выбранных комплектующих не принадлежат клиенту")
    return selected


def select_llc_tsr_items(
    client: dict[str, Any],
    payload: Any,
    selected_modules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    attached_items = client.get("tsr_items") or []
    attached_by_assignment_id = {
        str(item.get("client_tsr_id") or ""): item
        for item in attached_items
        if str(item.get("client_tsr_id") or "")
    }
    selected_assignment_ids = {
        str(value)
        for value in (getattr(payload, "selected_client_tsr_ids", None) or [])
        if str(value)
    }
    selected_tsr_ids = {
        str(value) for value in (getattr(payload, "selected_tsr_ids", None) or []) if str(value)
    }

    # Backward compatibility with an older frontend that sent only TSR or
    # component IDs. New clients select the concrete client↔TSR instance.
    if not selected_assignment_ids and not selected_tsr_ids:
        selected_assignment_ids = {
            str(module.get("client_tsr_id") or "")
            for module in selected_modules
            if str(module.get("client_tsr_id") or "")
        }
        if not selected_assignment_ids:
            selected_tsr_ids = {
                str(module.get("tsr_id") or (module.get("tsr") or {}).get("id") or "")
                for module in selected_modules
                if str(module.get("tsr_id") or (module.get("tsr") or {}).get("id") or "")
            }
    if not selected_assignment_ids and not selected_tsr_ids:
        raise ValueError("Для договора ООО выберите один сертификат пациента")

    if len(selected_assignment_ids) > 1 or len(selected_tsr_ids) > 1:
        raise ValueError("Один договор можно сформировать только по одному сертификату")

    if selected_assignment_ids:
        missing_ids = selected_assignment_ids.difference(attached_by_assignment_id)
        if missing_ids:
            raise ValueError("Один или несколько выбранных ТСР не прикреплены к клиенту")
        selected_items = [
            item for item in attached_items
            if str(item.get("client_tsr_id") or "") in selected_assignment_ids
        ]
    else:
        attached_tsr_ids = {
            str(item.get("tsr_id") or (item.get("tsr") or {}).get("id") or "")
            for item in attached_items
        }
        missing_ids = selected_tsr_ids.difference(attached_tsr_ids)
        if missing_ids:
            raise ValueError("Один или несколько выбранных ТСР не прикреплены к клиенту")
        selected_items = [
            item for item in attached_items
            if str(item.get("tsr_id") or (item.get("tsr") or {}).get("id") or "") in selected_tsr_ids
        ]
        if len(selected_items) != 1:
            raise ValueError(
                "У пациента есть несколько одинаковых ТСР. Выберите конкретный сертификат по дате пробития"
            )

    if len(selected_items) != 1:
        raise ValueError("Один договор можно сформировать только по одному сертификату")

    selected_item_ids = {str(item.get("client_tsr_id") or "") for item in selected_items}
    selected_item_tsr_ids = {
        str(item.get("tsr_id") or (item.get("tsr") or {}).get("id") or "")
        for item in selected_items
    }
    for module in selected_modules:
        module_assignment_id = str(module.get("client_tsr_id") or "")
        module_tsr_id = str(module.get("tsr_id") or (module.get("tsr") or {}).get("id") or "")
        if module_assignment_id:
            if module_assignment_id not in selected_item_ids:
                raise ValueError("Выбранная комплектующая относится к ТСР, который не включён в договор")
        elif module_tsr_id not in selected_item_tsr_ids:
            raise ValueError("Выбранная комплектующая относится к ТСР, который не включён в договор")

    return selected_items


def build_context(client: dict[str, Any], payload: Any, template_key: str = "llc_contract") -> dict[str, Any]:
    passport = latest_by_created(client.get("passports") or [])
    snils = latest_by_created(client.get("snils") or [])
    phones = client.get("phones") or []
    modules = select_llc_modules(client, payload) if template_key == "llc_contract" else (client.get("modules") or [])
    selected_client_tsr_items = (
        select_llc_tsr_items(client, payload, modules)
        if template_key == "llc_contract"
        else []
    )

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
        build_llc_contract_items(modules, selected_client_tsr_items)
        if template_key == "llc_contract"
        else build_contract_items(client, modules)
    )

    module_sum = sum(parse_money(module.get("price")) for module in modules)
    certificate_sum = parse_money(client.get("certificate_price"))
    total_sum = (
        sum(parse_money(item.get("raw_total_price")) for item in contract_items)
        if template_key == "llc_contract"
        else (module_sum or certificate_sum)
    )

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


def _metadata_certificate_ids(metadata: Any) -> set[str]:
    if not isinstance(metadata, dict):
        return set()
    ids: set[str] = set()
    direct_id = str(metadata.get("certificate_id") or "").strip()
    if direct_id:
        ids.add(direct_id)
    snapshots = metadata.get("selected_tsr_components")
    if isinstance(snapshots, list):
        for snapshot in snapshots:
            if isinstance(snapshot, dict):
                value = str(snapshot.get("client_tsr_id") or "").strip()
                if value:
                    ids.add(value)
    return ids


def _document_matches_certificate(
    document: models.Document,
    certificate: dict[str, Any],
) -> bool:
    certificate_id = str(certificate.get("client_tsr_id") or "").strip()
    if not certificate_id:
        return False
    if document.certificate_id and str(document.certificate_id) == certificate_id:
        return True
    if certificate_id in _metadata_certificate_ids(document.contract_metadata):
        return True

    # Compatibility for documents generated before CLIENT_TSR ids were stored.
    metadata = document.contract_metadata if isinstance(document.contract_metadata, dict) else {}
    snapshots = metadata.get("selected_tsr_components")
    if not isinstance(snapshots, list) or len(snapshots) != 1 or not isinstance(snapshots[0], dict):
        return False
    snapshot = snapshots[0]
    certificate_tsr_id = str(certificate.get("tsr_id") or (certificate.get("tsr") or {}).get("id") or "")
    snapshot_tsr_id = str(snapshot.get("tsr_id") or "")
    if certificate_tsr_id and snapshot_tsr_id and certificate_tsr_id != snapshot_tsr_id:
        return False
    snapshot_date = str(snapshot.get("check_date") or "")[:10]
    certificate_date = str(certificate.get("check_date") or "")[:10]
    if snapshot_date and certificate_date and snapshot_date != certificate_date:
        return False
    snapshot_amount = parse_money(snapshot.get("certificate_price") or document.certificate_amount)
    certificate_amount = parse_money(certificate.get("certificate_price"))
    return snapshot_amount > 0 and abs(snapshot_amount - certificate_amount) < 0.01


def _accounting_snapshot(document: models.Document) -> dict[str, Any] | None:
    row = document.contract_accounting
    if not row:
        return None
    return {
        "prosthetist_work": row.prosthetist_work,
        "patient_travel": row.patient_travel,
        "patient_accommodation": row.patient_accommodation,
        "patient_meals": row.patient_meals,
        "patient_payment": row.patient_payment,
        "other_expenses": row.other_expenses,
        "agency_expenses": row.agency_expenses,
        "custom_values": dict(row.custom_values or {}),
    }


def generate_contract(db: Session, client_id: uuid.UUID, payload: Any):
    template_key = normalize_template_key(getattr(payload, "template_type", "llc_contract"))
    template_config = TEMPLATES_CONFIG[template_key]
    template_path = get_template_path(template_config["filename"])

    client = crud.get_client(db, client_id)
    if not client:
        raise ValueError("Клиент не найден")

    selected_document_components = (
        select_llc_modules(client, payload)
        if template_key == "llc_contract"
        else (client.get("modules") or [])
    )
    selected_document_tsr_items = (
        select_llc_tsr_items(client, payload, selected_document_components)
        if template_key == "llc_contract"
        else []
    )
    selected_certificate = selected_document_tsr_items[0] if selected_document_tsr_items else None
    certificate_id = (
        uuid.UUID(str(selected_certificate.get("client_tsr_id")))
        if selected_certificate and selected_certificate.get("client_tsr_id")
        else None
    )

    if template_key in {"llc_contract", "dmk_contract"}:
        # Serialize number allocation inside the current DB transaction. The UI
        # only previews the next number; the server remains the source of truth.
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(73921001)"))
        number_suffix = get_next_contract_number(db)
        number_prefix = str(getattr(payload, "document_number_prefix", None) or "СД").strip().upper()
        payload.document_number_prefix = number_prefix
        payload.document_number_suffix = number_suffix
        payload.document_number = f"{number_prefix}/{number_suffix}"

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

    component_snapshot = [
        {
            "component_id": str(component.get("module_id")),
            "component_name": component.get("module_name_index"),
            "client_tsr_id": str(component.get("client_tsr_id") or ""),
            "tsr_id": str(component.get("tsr_id") or (component.get("tsr") or {}).get("id") or ""),
            "tsr": (component.get("tsr") or {}).get("full_tsr_code"),
            "quantity": max(1, int(parse_money(component.get("quantity")) or 1)),
            "price": parse_money(component.get("price")),
            "cost": parse_money(component.get("cost")),
        }
        for component in selected_document_components
    ]
    components_by_client_tsr: dict[str, list[dict[str, Any]]] = {}
    for component in selected_document_components:
        component_key = str(
            component.get("client_tsr_id")
            or component.get("tsr_id")
            or (component.get("tsr") or {}).get("id")
            or ""
        )
        components_by_client_tsr.setdefault(component_key, []).append(component)
    tsr_component_snapshot = [
        {
            "client_tsr_id": str(item.get("client_tsr_id") or ""),
            "tsr_id": str(item.get("tsr_id") or (item.get("tsr") or {}).get("id") or ""),
            "tsr": (item.get("tsr") or {}).get("full_tsr_code"),
            "certificate_price": parse_money(item.get("certificate_price")),
            "check_date": str(item.get("check_date") or ""),
            "components": [
                {
                    "component_id": str(component.get("module_id")),
                    "component_name": component.get("module_name_index"),
                    "quantity": max(1, int(parse_money(component.get("quantity")) or 1)),
                    "price": parse_money(component.get("price")),
                    "cost": parse_money(component.get("cost")),
                }
                for component in components_by_client_tsr.get(
                    str(
                        item.get("client_tsr_id")
                        or item.get("tsr_id")
                        or (item.get("tsr") or {}).get("id")
                        or ""
                    ),
                    [],
                )
            ],
        }
        for item in selected_document_tsr_items
    ] if template_key == "llc_contract" else []

    components_cost = sum(parse_money(component.get("cost")) for component in selected_document_components)
    certificate_amount = (
        parse_money(selected_certificate.get("certificate_price"))
        if selected_certificate
        else parse_money(context.get("Сумма"))
    )

    old_documents: list[models.Document] = []
    old_paths: list[str] = []
    preserved_accounting: dict[str, Any] | None = None
    if selected_certificate:
        candidates = (
            db.query(models.Document)
            .filter(
                models.Document.client_id == client_id,
                models.Document.document_type.in_(("llc_contract", "dmk_contract", "sdv_contract")),
            )
            .order_by(models.Document.created_at.desc(), models.Document.document_id.desc())
            .all()
        )
        old_documents = [
            candidate for candidate in candidates
            if _document_matches_certificate(candidate, selected_certificate)
        ]
        for old_document in old_documents:
            if preserved_accounting is None:
                preserved_accounting = _accounting_snapshot(old_document)
            if old_document.storage_path:
                old_paths.append(old_document.storage_path)
            db.delete(old_document)
        if old_documents:
            db.flush()

    db_doc = models.Document(
        client_id=client_id,
        filename=filename,
        storage_path=save_path,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size=os.path.getsize(save_path),
        document_type=template_key,
        document_number=str(getattr(payload, "document_number", "") or "").strip(),
        contract_total=components_cost,
        certificate_amount=certificate_amount,
        certificate_id=certificate_id,
        contract_metadata={
            "certificate_id": str(certificate_id or ""),
            "selected_components": component_snapshot,
            "selected_tsr_components": tsr_component_snapshot,
            "components_cost": components_cost,
            # Обратная совместимость с ранее сформированными отчётами/выгрузками.
            "selected_modules": [
                {
                    "module_id": str(component.get("module_id")),
                    "module_name": component.get("module_name_index"),
                    "tsr": (component.get("tsr") or {}).get("full_tsr_code"),
                    "price": parse_money(component.get("price")),
                    "cost": parse_money(component.get("cost")),
                }
                for component in selected_document_components
            ],
            "document_date": str(getattr(payload, "document_date", "") or ""),
        },
    )
    db.add(db_doc)
    try:
        db.flush()
        if template_key in {"llc_contract", "dmk_contract"}:
            db.add(models.ContractAccounting(
                document_id=db_doc.document_id,
                **(preserved_accounting or {}),
            ))
        db.commit()
        db.refresh(db_doc)
    except Exception:
        db.rollback()
        try:
            os.remove(save_path)
        except OSError:
            pass
        raise

    # Remove replaced files only after the database transaction succeeded.
    for old_path in old_paths:
        if old_path == save_path:
            continue
        try:
            os.remove(old_path)
        except OSError:
            pass
    return db_doc

