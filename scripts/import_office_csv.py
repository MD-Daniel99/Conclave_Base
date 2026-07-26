#!/usr/bin/env python3
"""Безопасный импорт офисных CSV в DB CRM.

По умолчанию выполняется только dry-run: CSV разбираются, строится план импорта,
но база данных не изменяется. Для реального запуска нужны одновременно флаги
``--execute`` и ``--confirm-reset ERASE_BUSINESS_DATA``.

Пример из корня проекта:

    python scripts/import_office_csv.py --csv-dir /path/to/csv

    python scripts/import_office_csv.py --csv-dir /path/to/csv \
        --execute --confirm-reset ERASE_BUSINESS_DATA

Скрипт очищает бизнес-данные и заново заполняет STATUS/STAGE, но намеренно
сохраняет USERS, чтобы после импорта оставалась возможность войти в приложение.
Файлы из storage не удаляются; старые записи DOCUMENT удаляются из базы.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from uuid import uuid4


PROBITO_FILE_MARKER = "пробито"
PATIENTS_FILE_MARKER = "пациенты"
MONITORING_FILE_MARKER = "мониторинг поставок"
WAREHOUSE_FILE_MARKER = "склад"

PROBITO_NAME = "ФИО пациента"
PROBITO_DATE = "Дата пробития ЭС (выставляем дату ТОЛЬКО по данным из чека)"
PROBITO_TSR = (
    "Номер вида ТСР и Наименование товара (Необходимо писать номер ТСР, "
    "затем полное наименование протеза (как в чеке). Позиции пишутся через + "
    "с пробелами по обеим сторонам)"
)
PROBITO_AMOUNT = "Сумма ЭС (Необходимо писать через = и каждую сумму за отдельную единицу складывать)"
PROBITO_AGENT = "Агент\n(Указывает Михаил)"
PROBITO_ORG = "Наименование организации (проставлять согласно чеку!)"
PROBITO_CONTRACT = "Статус договора"
PROBITO_ACTS = "Статус актов (актуализируем после каждого этапа)"
PROBITO_AGENT_PAYMENT = "Расчет с агентом (колонка для Георгия)"
PROBITO_COMMENT = "Комментарии Георгий"

TSR_START_RE = re.compile(r"(?<!\d)(\d{1,2}(?:\(\d+\))?-\d{2}(?:-\d{2})?)(?=\s|[А-ЯЁA-Z])")
PHONE_RE = re.compile(r"\d")
QUANTITY_RE = re.compile(r"\(\s*(\d+)\s*шт", re.IGNORECASE)

DEFAULT_STATUSES = (
    ("new", "Новый"),
    ("work", "В работе"),
    ("success", "Успешно завершен"),
    ("fail", "Отказ"),
    ("hold", "Отложен"),
)
DEFAULT_STAGES = (
    ("contact", "Первичный контакт"),
    ("meeting", "Встреча/Переговоры"),
    ("kp", "Отправлено КП"),
    ("contract", "Договор"),
    ("prepay", "Предоплата"),
    ("production", "В производстве"),
    ("shipping", "Отгрузка"),
    ("done", "Закрытие актов"),
)


@dataclass
class TsrItem:
    code: str
    description: str

    @property
    def full_value(self) -> str:
        return f"{self.code} {self.description}".strip()


@dataclass
class ClientPlan:
    source_row: int
    full_name: str
    last_name: str
    first_name: str
    middle_name: str | None
    check_date: date
    deadline: date | None
    agent: str
    status_code: str
    current_stage: str
    certificate_price: float
    prosthesis_type: str | None
    tsr_items: list[TsrItem]
    phone: str | None
    snils: str | None
    notes: str
    monitoring_rows: list[dict[str, str]] = field(default_factory=list, repr=False)


@dataclass
class ModulePlan:
    source: str
    source_row: int
    owner_name: str | None
    tsr_code: str | None
    module_name_index: str
    supplier: str
    quantity: int
    cost: float
    price: float
    ordered: int
    received: int
    pending: int
    prosthetist_keep: int
    order_data: str
    size: str | None
    stiffness: str | None
    side: str | None
    properties: str
    notes: str | None


@dataclass
class ImportPlan:
    clients: list[ClientPlan]
    modules: list[ModulePlan]
    tsr_catalog: list[TsrItem]
    warnings: list[str]
    stats: dict[str, int]


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ").strip())


def clip(value: Any, length: int, fallback: str = "") -> str:
    """Нормализует текст под ограничения String(N) в текущих ORM-моделях."""
    return (clean(value) or fallback)[:length]


def person_key(value: Any) -> str:
    base = clean(value).split("(", 1)[0].casefold()
    return re.sub(r"[^а-яёa-z0-9]", "", base)


def parse_date(value: Any) -> date | None:
    raw = clean(value)
    if not raw or raw in {"-", "—"}:
        return None
    raw = raw.split(" ", 1)[0]
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
            if 2000 <= parsed.year <= 2100:
                return parsed
        except ValueError:
            continue
    return None


def parse_money(value: Any) -> float:
    raw = clean(value)
    if not raw:
        return 0.0
    normalized = raw.replace(" ", "").replace(",", ".").replace("−", "-")
    normalized = re.sub(r"[^0-9.\-]", "", normalized)
    if normalized.count(".") > 1:
        parts = normalized.split(".")
        normalized = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(normalized)
    except ValueError:
        return 0.0


def parse_quantity(value: Any, default: int = 1) -> int:
    match = re.search(r"\d+", clean(value))
    if not match:
        return default
    return max(1, int(match.group()))


def count_from_marker(value: Any, quantity: int) -> int:
    """Возвращает количество только для непустой отметки, не сохраняя артикул как число."""
    marker = clean(value)
    if not marker or not marker.strip("-—_"):
        return 0
    if re.fullmatch(r"\d+", marker):
        return max(0, int(marker))
    return max(0, quantity)


def normalize_phone(value: Any) -> str | None:
    raw = clean(value)
    digits = "".join(PHONE_RE.findall(raw))
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    if not (10 <= len(digits) <= 15):
        return None
    return "+" + digits


def normalize_snils(value: Any) -> str | None:
    digits = re.sub(r"\D", "", clean(value))
    if len(digits) != 11:
        return None
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}"


def split_person_name(value: Any) -> tuple[str, str, str | None]:
    parts = clean(value).split()
    if not parts:
        return "Без фамилии", "", None
    if len(parts) == 1:
        return parts[0], "", None
    return parts[0], parts[1], " ".join(parts[2:]) or None


def normalize_tsr_code(code: str) -> str:
    parts = code.strip().split("-")
    first = parts[0]
    match = re.fullmatch(r"0*(\d+)(\(\d+\))?", first)
    if match:
        first = str(int(match.group(1))) + (match.group(2) or "")
    return "-".join([first, *parts[1:]])


def normalize_description(value: str) -> str:
    value = re.sub(r"^[+;,\s]+|[+;,\s]+$", "", value)
    return clean(value)


def extract_tsr_items(value: Any) -> list[TsrItem]:
    raw = str(value or "").replace("\n", " ")
    matches = list(TSR_START_RE.finditer(raw))
    result: list[TsrItem] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        description = normalize_description(raw[match.end():end])
        if len(description) < 4 or not re.search(r"[а-яёa-z]", description, re.IGNORECASE):
            continue
        result.append(TsrItem(normalize_tsr_code(match.group(1)), description))
    return result


def choose_tsr_catalog(probito_rows: Sequence[dict[str, str]], warnings: list[str]) -> list[TsrItem]:
    by_code: dict[str, Counter[str]] = defaultdict(Counter)
    original: dict[tuple[str, str], str] = {}
    for row in probito_rows:
        for item in extract_tsr_items(row.get(PROBITO_TSR)):
            description_key = clean(item.description).casefold()
            by_code[item.code][description_key] += 1
            original[(item.code, description_key)] = item.description

    catalog: list[TsrItem] = []
    for code in sorted(by_code, key=tsr_sort_key):
        variants = by_code[code]
        best_key = sorted(variants, key=lambda key: (-variants[key], -len(key), key))[0]
        if len(variants) > 1:
            warnings.append(
                f"ТСР {code}: найдено {len(variants)} вариантов названия; выбран наиболее частый вариант."
            )
        catalog.append(TsrItem(code, original[(code, best_key)]))
    return catalog


def tsr_sort_key(code: str) -> tuple[Any, ...]:
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"[-()]", code) if part != "")


def find_csv(csv_dir: Path, marker: str) -> Path:
    matches = [path for path in csv_dir.glob("*.csv") if marker in path.name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"Ожидался один CSV с фрагментом '{marker}', найдено: {len(matches)}")
    return matches[0]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def index_rows(rows: Iterable[dict[str, str]], column: str) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = person_key(row.get(column))
        if key:
            result[key].append(row)
    return result


def closest_patient_rows(rows: Sequence[dict[str, str]], target_date: date) -> list[dict[str, str]]:
    def distance(row: dict[str, str]) -> tuple[int, int]:
        row_date = parse_date(row.get("Дата Пробития"))
        return (abs((row_date - target_date).days), 0) if row_date else (10**9, 1)
    return sorted(rows, key=distance)


def first_valid(rows: Sequence[dict[str, str]], column: str, parser: Any) -> Any:
    for row in rows:
        parsed = parser(row.get(column))
        if parsed is not None:
            return parsed
    return None


def select_status(contract: str, acts: str) -> tuple[str, str]:
    text = f"{contract} {acts}".casefold()
    if any(token in text for token in ("отказ", "расторг", "отмен")):
        return "fail", "contact"
    if any(token in text for token in ("отлож", "приостанов")):
        return "hold", "contact"
    if "договор" in text and any(token in text for token in ("нет", "без")):
        return "new", "contact"
    if "подписан" in contract.casefold() and "подписан" in acts.casefold():
        return "success", "done"
    if any(token in text for token in ("подпис", "договор", "акт")):
        return "work", "contract"
    return "work", "contact"


def choose_prosthesis(patient_rows: Sequence[dict[str, str]], tsr_items: Sequence[TsrItem]) -> str | None:
    for row in patient_rows:
        raw = clean(row.get("Данные прот."))
        if raw and raw not in {"-", "—"}:
            items = extract_tsr_items(raw)
            return items[0].description if items else raw.split(" + ", 1)[0]
    return tsr_items[0].description if tsr_items else None


def choose_monitoring_rows(rows: Sequence[dict[str, str]], target_date: date) -> list[dict[str, str]]:
    if not rows:
        return []
    dated = [(parse_date(row.get("Пробитие дата")), row) for row in rows]
    exact = [row for row_date, row in dated if row_date == target_date]
    if exact:
        return exact
    valid = [(abs((row_date - target_date).days), row) for row_date, row in dated if row_date]
    if valid:
        return [min(valid, key=lambda pair: pair[0])[1]]
    return list(rows[:1])


def build_client_notes(row: dict[str, str], patient_rows: Sequence[dict[str, str]]) -> str:
    parts = [
        "Импортировано из CSV «Пробито».",
        f"Организация: {clean(row.get(PROBITO_ORG)) or 'не указана'}.",
        f"Статус договора: {clean(row.get(PROBITO_CONTRACT)) or 'не указан'}.",
        f"Статус актов: {clean(row.get(PROBITO_ACTS)) or 'не указан'}.",
    ]
    payment = clean(row.get(PROBITO_AGENT_PAYMENT))
    comment = clean(row.get(PROBITO_COMMENT))
    if payment:
        parts.append(f"Расчёт с агентом: {payment}.")
    if comment:
        parts.append(f"Комментарий: {comment}")
    invalid_phones = sorted({clean(item.get("Телефон")) for item in patient_rows if clean(item.get("Телефон")) and not normalize_phone(item.get("Телефон"))})
    if invalid_phones:
        parts.append("Неперенесённые значения колонки «Телефон»: " + "; ".join(invalid_phones) + ".")
    return "\n".join(parts)


def build_clients(
    probito_rows: Sequence[dict[str, str]],
    patient_rows: Sequence[dict[str, str]],
    monitoring_rows: Sequence[dict[str, str]],
    tsr_catalog: Sequence[TsrItem],
    organization: str,
    limit: int,
    warnings: list[str],
) -> list[ClientPlan]:
    patients_by_name = index_rows(patient_rows, "а")
    monitoring_by_name = index_rows(monitoring_rows, "6")
    probito_by_name = index_rows(probito_rows, PROBITO_NAME)
    canonical_tsr = {item.code: item for item in tsr_catalog}
    candidates: list[tuple[date, int, dict[str, str]]] = []
    for row_number, row in enumerate(probito_rows, start=2):
        if clean(row.get(PROBITO_ORG)).casefold() != clean(organization).casefold():
            continue
        check_date = parse_date(row.get(PROBITO_DATE))
        if not check_date:
            warnings.append(f"Пробито, строка {row_number}: пропущена запись без корректной даты.")
            continue
        candidates.append((check_date, row_number, row))
    candidates.sort(key=lambda item: (-item[0].toordinal(), item[1]))

    clients: list[ClientPlan] = []
    seen_people: set[str] = set()
    for check_date, row_number, row in candidates:
        full_name = clean(row.get(PROBITO_NAME))
        key = person_key(full_name)
        if not key or key in seen_people:
            continue
        seen_people.add(key)
        related_patients = closest_patient_rows(patients_by_name.get(key, []), check_date)
        related_monitoring = choose_monitoring_rows(monitoring_by_name.get(key, []), check_date)
        phone = first_valid(related_patients, "Телефон", normalize_phone)
        snils = first_valid(related_patients, "СНИЛС", normalize_snils)
        deadline = first_valid(related_patients, "Дата След.Обращения", parse_date)
        raw_tsr_items: list[TsrItem] = []
        # Берём коды из выбранной строки и дополняем другими строками того же
        # клиента: в свежей строке код иногда пропущен, хотя он есть в истории.
        for related_row in [row, *probito_by_name.get(key, [])]:
            raw_tsr_items.extend(extract_tsr_items(related_row.get(PROBITO_TSR)))
        tsr_items = []
        seen_tsr_codes: set[str] = set()
        for tsr in raw_tsr_items:
            if tsr.code in seen_tsr_codes:
                continue
            seen_tsr_codes.add(tsr.code)
            tsr_items.append(canonical_tsr.get(tsr.code, tsr))
        agent = clean(row.get(PROBITO_AGENT)) or "Агент не указан"
        status_code, current_stage = select_status(
            clean(row.get(PROBITO_CONTRACT)), clean(row.get(PROBITO_ACTS))
        )
        last_name, first_name, middle_name = split_person_name(full_name)
        clients.append(ClientPlan(
            source_row=row_number,
            full_name=full_name,
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name,
            check_date=check_date,
            deadline=deadline,
            agent=agent,
            status_code=status_code,
            current_stage=current_stage,
            certificate_price=parse_money(row.get(PROBITO_AMOUNT)),
            # ТСР и вид протеза — разные сущности. Импорт ТСР не должен
            # автоматически заполнять справочник/поле вида протеза.
            prosthesis_type=None,
            tsr_items=tsr_items,
            phone=phone,
            snils=snils,
            notes=build_client_notes(row, related_patients),
            monitoring_rows=related_monitoring,
        ))
        if not related_patients:
            warnings.append(f"{full_name}: строка в «Пациенты» не найдена.")
        if not phone:
            warnings.append(f"{full_name}: валидный телефон не найден.")
        if not related_monitoring:
            warnings.append(f"{full_name}: комплектующие в «Мониторинге поставок» не найдены.")
        if not tsr_items:
            warnings.append(f"{full_name}: в строке нет ТСР с распознаваемым числовым кодом.")
        if len(clients) >= limit:
            break
    if len(clients) < limit:
        raise RuntimeError(f"Для организации {organization!r} найдено только {len(clients)} уникальных клиентов с датой.")
    return clients


CONFUSABLES = str.maketrans({"а": "a", "в": "b", "с": "c", "е": "e", "н": "h", "к": "k", "м": "m", "о": "o", "р": "p", "т": "t", "х": "x"})


def catalog_key(value: Any) -> str:
    raw = clean(value).casefold().translate(CONFUSABLES)
    raw = QUANTITY_RE.sub("", raw)
    raw = re.split(r"\s+-\s+(?:оттобок|метиз|витоорта|оссур|ottobock|ossur)\b", raw, maxsplit=1)[0]
    return re.sub(r"[^a-z0-9а-яё]", "", raw)


def split_lines(value: Any) -> list[str]:
    return [clean(line) for line in str(value or "").splitlines() if clean(line)]


def module_label(name: str, catalogue: str) -> str:
    if catalogue and name:
        return f"{catalogue} — {name}"[:128]
    return (catalogue or name or "Комплектующая без наименования")[:128]


def infer_side(size: str) -> str | None:
    value = clean(size).upper()
    if value.endswith("L") or " LEFT" in value:
        return "L"
    if value.endswith("R") or " RIGHT" in value:
        return "R"
    return None


def prepare_warehouse(rows: Sequence[dict[str, str]], warnings: list[str]) -> tuple[list[ModulePlan], dict[str, list[dict[str, str]]]]:
    plans: list[ModulePlan] = []
    index: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row_number, row in enumerate(rows, start=2):
        name = clean(row.get("НАИМЕНОВАНИЕ МОДУЛЯ"))
        catalogue = clean(row.get("ИНДЕКС ПО КАТАЛОГУ"))
        if not name and not catalogue:
            continue
        key = catalog_key(catalogue)
        if key:
            index[key].append(row)
        quantity = parse_quantity(row.get("КОЛ-ВО"))
        total_cost = parse_money(row.get("СТОИМОСТЬ"))
        total_price = parse_money(row.get("СТОИМОСТЬ ПРАЙС"))
        if not total_cost:
            total_cost = parse_money(row.get("ЦЕНА")) * quantity
        if not total_price:
            total_price = parse_money(row.get("ЦЕНА ПРАЙС")) * quantity
        plans.append(ModulePlan(
            source="СКЛАД",
            source_row=row_number,
            owner_name=None,
            tsr_code=None,
            module_name_index=module_label(name, catalogue),
            supplier=clean(row.get("ОТКУДА")) or "Не указан",
            quantity=quantity,
            cost=total_cost,
            price=total_price,
            ordered=0,
            received=quantity,
            pending=0,
            prosthetist_keep=0,
            order_data=clean(row.get("ПРИХОД")) or "-",
            size=clean(row.get("РАЗМЕР")) or None,
            stiffness=clean(row.get("ЖЕСТКОСТЬ")) or None,
            side=infer_side(clean(row.get("РАЗМЕР"))),
            properties=clean(row.get("СОСТОЯНИЕ")) or "Склад",
            notes="; ".join(filter(None, [
                "Комплектующая без владельца, импортирована из CSV «СКЛАД»",
                f"Уход: {clean(row.get('УХОД'))}" if clean(row.get("УХОД")) else "",
                f"Источник, строка {row_number}",
            ])),
        ))
    duplicate_keys = [key for key, values in index.items() if len(values) > 1]
    if duplicate_keys:
        warnings.append(f"СКЛАД: {len(duplicate_keys)} каталожных индексов встречаются более одного раза; совпадение выбирается только при однозначной строке.")
    return plans, index


def find_warehouse_match(raw_index: str, warehouse_index: dict[str, list[dict[str, str]]]) -> dict[str, str] | None:
    key = catalog_key(raw_index)
    exact = warehouse_index.get(key, []) if key else []
    if len(exact) == 1:
        return exact[0]
    if len(key) >= 4:
        possible = [row for candidate, rows in warehouse_index.items() if key in candidate or candidate in key for row in rows]
        if len(possible) == 1:
            return possible[0]
    return None


def choose_module_tsr_code(tsr_items: Sequence[TsrItem], module_text: str) -> str | None:
    """Подбирает ТСР комплектующей только когда связь выводится из названия.

    Для деталей протеза базовым вариантом считается модульный протез; лайнеры
    и оболочки получают отдельный ТСР, если такой код есть у клиента.
    """
    if not tsr_items:
        return None
    if len(tsr_items) == 1:
        return tsr_items[0].code

    text_value = clean(module_text).casefold()
    rules = (
        (("лайнер", "чехол", "силикон", "сополимер"), ("чехол на культю", "полимерного материала")),
        (("оболочк",), ("косметическая оболочка",)),
        (("купан", "водостой"), ("для купания",)),
        (("кист",), ("протез кисти",)),
        (("предплеч",), ("протез предплечья",)),
        (("плеч",), ("протез плеча",)),
        (("бедр", "колен"), ("протез бедра",)),
        (("голен", "стоп", "адаптер", "замок", "клапан"), ("протез голени модульный",)),
    )
    for module_tokens, description_tokens in rules:
        if not any(token in text_value for token in module_tokens):
            continue
        for item in tsr_items:
            description = item.description.casefold()
            if any(token in description for token in description_tokens):
                return item.code

    for item in tsr_items:
        if "модульн" in item.description.casefold():
            return item.code
    return tsr_items[0].code


def monitoring_module_plans(clients: Sequence[ClientPlan], warehouse_index: dict[str, list[dict[str, str]]], warnings: list[str]) -> list[ModulePlan]:
    plans: list[ModulePlan] = []
    for client in clients:
        for monitoring in client.monitoring_rows:
            names = split_lines(monitoring.get("ЗАПЧАСТИ"))
            indexes = split_lines(monitoring.get("ИНДЕКС ПО КАТАЛОГУ"))
            ordered_lines = str(monitoring.get("ЗАКАЗАНО") or "").splitlines()
            received_lines = str(monitoring.get("ИНДЕКС ОТГРУЖЕНОГО НА СКЛАД ") or "").splitlines()
            pending_lines = str(monitoring.get("Ожидаем") or monitoring.get("НАДО ЗАКАЗАТЬ") or "").splitlines()
            count = max(len(names), len(indexes))
            if not count:
                continue
            if len(names) != len(indexes):
                warnings.append(f"{client.full_name}: число названий комплектующих ({len(names)}) не равно числу индексов ({len(indexes)}).")
            total_monitoring_cost = parse_money(monitoring.get("ЗАТРАТЫ"))
            for pos in range(count):
                name = names[pos] if pos < len(names) else "Комплектующая без наименования"
                raw_index = indexes[pos] if pos < len(indexes) else ""
                catalogue = re.sub(r"\s*\(\s*\d+\s*шт.*$", "", raw_index, flags=re.IGNORECASE).strip()
                match = find_warehouse_match(catalogue, warehouse_index)
                quantity_match = QUANTITY_RE.search(raw_index)
                quantity = int(quantity_match.group(1)) if quantity_match else 1
                module_tsr = choose_module_tsr_code(client.tsr_items, f"{name} {raw_index}")
                supplier = clean(match.get("ОТКУДА")) if match else clean(monitoring.get("ПОСТАВЩИК"))
                cost = parse_money(match.get("СТОИМОСТЬ")) if match else 0.0
                price = parse_money(match.get("СТОИМОСТЬ ПРАЙС")) if match else 0.0
                size = clean(match.get("РАЗМЕР")) if match else ""
                stiffness = clean(match.get("ЖЕСТКОСТЬ")) if match else ""
                notes = [
                    f"Назначено клиенту из CSV «Мониторинг поставок»: {client.full_name}",
                    f"Исходный индекс: {raw_index or 'не указан'}",
                    f"Общие затраты строки мониторинга: {total_monitoring_cost:.2f}",
                    "Найдено соответствие в CSV «СКЛАД»." if match else "Точное соответствие в CSV «СКЛАД» не найдено.",
                ]
                plans.append(ModulePlan(
                    source="Мониторинг поставок",
                    source_row=client.source_row,
                    owner_name=client.full_name,
                    tsr_code=module_tsr,
                    module_name_index=module_label(name, catalogue),
                    supplier=supplier or "Не указан",
                    quantity=max(1, quantity),
                    cost=cost,
                    price=price,
                    ordered=count_from_marker(ordered_lines[pos] if pos < len(ordered_lines) else "", quantity),
                    received=count_from_marker(received_lines[pos] if pos < len(received_lines) else "", quantity),
                    pending=count_from_marker(pending_lines[pos] if pos < len(pending_lines) else "", quantity),
                    prosthetist_keep=0,
                    order_data=clean(monitoring.get("ДАТА ЗАКАЗА + № СЧЕТА")) or "-",
                    size=size or None,
                    stiffness=stiffness or None,
                    side=infer_side(size),
                    properties=clean(match.get("СОСТОЯНИЕ")) if match else (clean(monitoring.get("Статус")) or "Назначен клиенту"),
                    notes="\n".join(notes),
                ))
    return plans


def build_plan(csv_dir: Path, organization: str, client_limit: int) -> ImportPlan:
    warnings: list[str] = []
    probito_rows = read_csv(find_csv(csv_dir, PROBITO_FILE_MARKER))
    patient_rows = read_csv(find_csv(csv_dir, PATIENTS_FILE_MARKER))
    monitoring_rows = read_csv(find_csv(csv_dir, MONITORING_FILE_MARKER))
    warehouse_rows = read_csv(find_csv(csv_dir, WAREHOUSE_FILE_MARKER))

    tsr_catalog = choose_tsr_catalog(probito_rows, warnings)
    clients = build_clients(
        probito_rows, patient_rows, monitoring_rows, tsr_catalog, organization, client_limit, warnings
    )
    warehouse_modules, warehouse_index = prepare_warehouse(warehouse_rows, warnings)
    assigned_modules = monitoring_module_plans(clients, warehouse_index, warnings)
    modules = assigned_modules + warehouse_modules
    stats = {
        "clients": len(clients),
        "clients_with_phone": sum(client.phone is not None for client in clients),
        "clients_with_snils": sum(client.snils is not None for client in clients),
        "clients_with_monitoring": sum(bool(client.monitoring_rows) for client in clients),
        "assigned_modules": len(assigned_modules),
        "unassigned_warehouse_modules": len(warehouse_modules),
        "unique_tsr_codes": len(tsr_catalog),
        "warnings": len(warnings),
    }
    return ImportPlan(clients, modules, tsr_catalog, warnings, stats)


def plan_to_json(plan: ImportPlan) -> dict[str, Any]:
    def convert(value: Any) -> Any:
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, list):
            return [convert(item) for item in value]
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        return value

    clients = []
    for client in plan.clients:
        payload = asdict(client)
        payload.pop("monitoring_rows", None)
        clients.append(convert(payload))
    return {
        "stats": plan.stats,
        "clients": clients,
        "modules": convert([asdict(module) for module in plan.modules]),
        "tsr_catalog": convert([asdict(item) | {"full_value": item.full_value} for item in plan.tsr_catalog]),
        "warnings": plan.warnings,
    }


def print_preview(plan: ImportPlan) -> None:
    print("\n=== ПЛАН ИМПОРТА (DRY-RUN) ===")
    print(json.dumps(plan.stats, ensure_ascii=False, indent=2))
    print("\nКлиенты в порядке даты пробития:")
    for index, client in enumerate(plan.clients, start=1):
        print(
            f"{index:>2}. {client.check_date.isoformat()} | {client.full_name} | "
            f"агент={client.agent} | телефон={'да' if client.phone else 'нет'} | "
            f"СНИЛС={'да' if client.snils else 'нет'} | ТСР={len(client.tsr_items)}"
        )
    if plan.warnings:
        print("\nПредупреждения:")
        for warning in plan.warnings:
            print("-", warning)


def reset_business_data(db: Any, models: Any, delete: Any, text: Any) -> None:
    ordered_models = (
        models.AuditLog,
        models.AccountingFieldValue,
        models.AccountingCustomField,
        models.ContractAccounting,
        models.Document,
        models.Phone,
        models.Passport,
        models.Snils,
        models.Reminder,
        models.Module,
        models.Client,
        models.Agent,
        models.ProsthesisRef,
        models.TstCodeRef,
        models.ModuleNameIndex,
        models.Status,
        models.Stage,
    )
    for model in ordered_models:
        db.execute(delete(model))
    db.execute(text("ALTER SEQUENCE IF EXISTS agent_external_id_seq RESTART WITH 1"))
    db.execute(text("ALTER SEQUENCE IF EXISTS client_external_id_seq RESTART WITH 1"))
    db.add_all([models.Status(status_code=code, description=description) for code, description in DEFAULT_STATUSES])
    db.add_all([models.Stage(stage_code=code, description=description) for code, description in DEFAULT_STAGES])
    db.flush()


def execute_import(plan: ImportPlan) -> None:
    try:
        from sqlalchemy import delete, text
        from app import models
        from app.db import SessionLocal
    except ImportError as exc:
        raise RuntimeError(
            "Для --execute запускайте скрипт из корня проекта в окружении приложения с установленными requirements.txt."
        ) from exc

    with SessionLocal() as db:
        try:
            reset_business_data(db, models, delete, text)

            tsr_by_code: dict[str, Any] = {}
            for item in plan.tsr_catalog:
                model = models.TstCodeRef(full_tsr_code=item.full_value)
                db.add(model)
                tsr_by_code[item.code] = model

            agents: dict[str, Any] = {}
            for name in sorted({client.agent for client in plan.clients}, key=str.casefold):
                last_name, first_name, middle_name = split_person_name(name)
                model = models.Agent(last_name=last_name, first_name=first_name, middle_name=middle_name)
                db.add(model)
                agents[name] = model
            db.flush()

            client_by_name: dict[str, Any] = {}
            for item in plan.clients:
                client = models.Client(
                    last_name=item.last_name,
                    first_name=item.first_name,
                    middle_name=item.middle_name,
                    status_code=item.status_code,
                    current_stage=item.current_stage,
                    agent_id=agents[item.agent].agent_id,
                    deadline=datetime.combine(item.deadline, time.min, tzinfo=timezone.utc) if item.deadline else None,
                    check_date=item.check_date,
                    prosthesis_type=None,
                    certificate_price=f"{item.certificate_price:.2f}",
                    tsr_code="\n".join(tsr.full_value for tsr in item.tsr_items) or None,
                    notes=item.notes,
                )
                db.add(client)
                db.flush()
                client_by_name[item.full_name] = client
                if item.phone:
                    db.add(models.Phone(client_id=client.client_id, number=item.phone))
                if item.snils:
                    db.add(models.Snils(client_id=client.client_id, number=item.snils, issued_date=None, version=1))

            name_index_models: dict[str, Any] = {}
            for name in sorted({module.module_name_index for module in plan.modules}, key=str.casefold):
                model = models.ModuleNameIndex(name_index=name)
                db.add(model)
                name_index_models[name] = model
            db.flush()

            for item in plan.modules:
                tsr_model = tsr_by_code.get(item.tsr_code) if item.tsr_code else None
                owner = client_by_name.get(item.owner_name) if item.owner_name else None
                db.add(models.Module(
                    client_id=owner.client_id if owner else None,
                    tsr_id=tsr_model.tsr_id if tsr_model else None,
                    module_name_index=item.module_name_index,
                    supplier=clip(item.supplier, 64, "Не указан"),
                    ordered=item.ordered,
                    order_date_acc_num=clip(item.order_data, 64, "-"),
                    quantity=item.quantity,
                    size=clip(item.size, 64) or None,
                    stiffness=clip(item.stiffness, 64) or None,
                    side=clip(item.side, 64) or None,
                    cost=item.cost,
                    price=item.price,
                    recd=item.received,
                    pending=item.pending,
                    prosthetist_keep=item.prosthetist_keep,
                    properties=clip(item.properties, 64, "Импорт"),
                    notes=item.notes,
                ))

            run_id = uuid4()
            db.add(models.AuditLog(
                entity="system",
                entity_id=run_id,
                action="office_csv.import",
                user_id="system-import",
                details={"stats": plan.stats, "run_id": str(run_id)},
            ))
            db.commit()
        except Exception:
            db.rollback()
            raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Импорт офисных CSV в DB CRM (по умолчанию dry-run).")
    parser.add_argument("--csv-dir", type=Path, required=True, help="Каталог с четырьмя CSV-файлами.")
    parser.add_argument("--organization", default="ОООСД", help="Значение колонки организации (по умолчанию ОООСД).")
    parser.add_argument("--client-limit", type=int, default=10, help="Число последних уникальных клиентов (по умолчанию 10).")
    parser.add_argument("--report", type=Path, help="Сохранить полный JSON-предпросмотр.")
    parser.add_argument("--execute", action="store_true", help="Выполнить очистку и импорт.")
    parser.add_argument("--confirm-reset", help="Для выполнения требуется точное значение ERASE_BUSINESS_DATA.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.client_limit < 1:
        raise SystemExit("--client-limit должен быть больше нуля")
    plan = build_plan(args.csv_dir.resolve(), args.organization, args.client_limit)
    print_preview(plan)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(plan_to_json(plan), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nПолный отчёт сохранён: {args.report}")
    if not args.execute:
        print("\nБаза не изменена. Для импорта добавьте --execute --confirm-reset ERASE_BUSINESS_DATA")
        return 0
    if args.confirm_reset != "ERASE_BUSINESS_DATA":
        print("ОТКАЗ: неверное подтверждение очистки. База не изменена.", file=sys.stderr)
        return 2
    execute_import(plan)
    print("\nИмпорт успешно завершён одной транзакцией.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
