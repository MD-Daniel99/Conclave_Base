import os
import re
from num2words import num2words
from docxtpl import DocxTemplate
from sqlalchemy.orm import Session
from app import models, crud
import uuid

# Папка для сохранения готовых документов
STORAGE_DIR = "/app/storage"

TEMPLATES_CONFIG = {
    "llc_contract": {
        "filename": "contract_template.docx",
        "doc_type_name": "ООО Соц. фонд Движение",
    },
    "DMK_contract": {
        "filename": "ДМК_Шаблон_Договор.docx",
        "doc_type_name": "ИП ДМК Договор" ,
    },
    "SDV_contract": {
        "filename": "СДВ_Шаблон_Договор.docx",
        "doc_type_name": "ИП СДВ Договор",
    },
    "DMK_instrument": {
        "filename": "ДМК_Шаблон_Акт.docx",
        "doc_type_name": "ИП ДМК Акт",
    },
    "SDV_instrument": {
        "filename": "СДВ_Шаблон_Акт.docx",
        "doc_type_name": "ИП СДВ Акт", 
    },
}

def rub_to_words(amount: float) -> str:
    """Конвертация числа в сумму прописью"""
    try:
        text = num2words(amount, lang='ru', to='currency', currency='RUB')
        return text.capitalize()
    except:
        return str(amount)
    
def get_initials(last_name, first_name, middle_name):
    f = first_name[0].upper() + "." if first_name else ""
    m = middle_name[0].upper() + "." if middle_name else ""
    return f"{last_name} {f} {m}".strip()

def extract_tsr_numeric(tsr_code):
    if not tsr_code: return ""
    match = re.search(r'\d{1,2}-\d{2}-\d{2}', tsr_code)
    return match.group(0) if match else ""

def extract_tsr_literals(tsr_code):
    if not tsr_code: return ""
    text_part = re.sub(r'\d{1,2}-\d{2}-\d{2}', '', tsr_code)
    return text_part.strip(' .,- ')


def get_template_path(filename):
    POSSIBLE_PATHS = [
        f"/app/app/templates/{filename}",
        f"/app/templates/{filename}",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", filename),
    ]
    for path in POSSIBLE_PATHS:
        if os.path.exists(path):
            return path
    # Логируем ошибку, если не нашли
    print(f"CRITICAL ERROR: Шаблон {filename} не найден. Искали здесь: {POSSIBLE_PATHS}", flush=True)
    raise FileNotFoundError(f"Файл шаблона {filename} не найден.")

def generate_contract(db: Session, client_id: uuid.UUID, payload):
    template_key = getattr(payload, "template_type", "contract_original")

    templates_config = TEMPLATES_CONFIG.get(template_key, TEMPLATES_CONFIG["llc_contract"])
    template_filename = templates_config["filename"]

    # 1. Получаем данные
    client = crud.get_client(db, client_id) 
    if not client:
        raise ValueError("Клиент не найден")

    # 2. Паспорт, телефон, снилс
    passport = {}
    if client.get("passports") and len(client["passports"]) > 0:
        last_passport = sorted(client["passports"], key=lambda x: x.get("created_at") or "", reverse=True)[0]
        passport = last_passport

    phone = ""
    if client.get("phones") and len(client["phones"]) > 0:
        phone = client["phones"][0]["number"]

    snils = ""
    if client.get("snils") and len(client["snils"]) > 0:
        snils = client["snils"][0]["number"]

     # Серия/номер паспорта
    raw_sn = passport.get('series_number', "")
    clean_sn = raw_sn.replace(" ", "").replace("-", "")
    series = clean_sn[:4]
    number = clean_sn[4:]

    # Место рождения
    birth_place = passport.get("birth_place", "")

    # Цены
    modules = client.get("modules", [])
    total_sum = sum(float(m.get("price") or 0) for m in modules)
 
    # Цена с чехлом
    cover_price_standalone = 0.0
    for m in modules:
        m_name = m.get("module_name", "").lower()
        if "чехол" in m_name:
            added_price = float(m.get("price") or 0)
            cover_price_standalone += added_price
        
        total_sum_with_cover = total_sum + cover_price_standalone

    
    # Форматирование: 1 250.00 
    sum_formatted = f"{total_sum:,.2f}".replace(",", " ")
    sum_with_cover_formatted = f"{total_sum_with_cover:,.2f}".replace(",", " ")

    context = {
        "НомерДоговора": payload.document_number,
        "ДатаДоговора": payload.document_date,
        "ДатаПлана": payload.plan_date,
        "Название акта": payload.document_number,

        "ФИОЗаказчика": f"{client['last_name']} {client['first_name']} {client['middle_name'] or ''}".strip(),
        "ДатаРожденияЗаказчика": passport.get('birth_date') if passport.get('birth_date') else "__________",
        "ПаспортСерия": series,
        "ПаспортНомер": number,
        "КемВыданПаспорт": passport.get('issued_by', "________"),
        "ДатаВыдачиПаспорта": passport.get("issue_date", "________"),
        "КодПодразделения": passport.get("department_code", "______"),
        "АдресРегистрацииЗаказчика": passport.get("registration_address", "__________________"),
        "МестоРожденияЗаказчика": birth_place,
        "Телефон_заказчика": phone,
        "СНИЛСЗаказчика": snils,
        "СуммаСЧехлом": sum_with_cover_formatted,
        "СуммаПрописьюСЧехлом": rub_to_words(total_sum_with_cover),

        "Сумма": sum_formatted,
        "СуммаПрописью": rub_to_words(total_sum),
        "ИнициалыЗаказчикаКратко": get_initials(client['last_name'], client['first_name'], client['middle_name']),
        
        "ВерхнихилиНижнихконечностей": client.get('prosthesis_type', ' ')
    }

    # 1. Получаем строку с кодами из клиента и превращаем её в список строк
    raw_tsr_source = client.get('tsr_code') or ""
    # Разбиваем текст по переносам строки (\n) и убираем пустые пробелы
    tsr_names_list = [line.strip() for line in raw_tsr_source.split('\n') if line.strip()]

    # АГРЕГАЦИЯ ДЛЯ НОВЫХ ДОГОВОРОВ / АКТОВ


    names = []
    codes = []
    quantities = []
    description_parts = []

    items_count = max(len(tsr_names_list), len(modules))

    for idx in range(items_count):
        if idx < len(tsr_names_list):
            tsr_full = tsr_names_list[idx]
            tsr_code = extract_tsr_numeric(tsr_full)
            tsr_name = extract_tsr_literals(tsr_full)
        else:
            continue

        if idx < len(modules):
            qty = modules[idx].get("quantity", 1)
        else:
            qty = 1

        names.append(tsr_name)
        codes.append(tsr_code)
        quantities.append(str(qty))
        description_parts.append(f"{tsr_code} {tsr_name}")

    # КЛЮЧЕВОЙ МОМЕНТ — ДОБАВЛЯЕМ В CONTEXT
    context.update({
        "Наименованиетовара": "; ".join(names),
        "КодТовара": "; ".join(codes),
        "КолТовара": "; ".join(quantities),
        "ОписаниеТовара": "; ".join(description_parts),
    })

    # Заполнение таблицы (идем по строкам шаблона от 1 до 4)
    for i in range(1, 5):
        idx = i - 1
        
        # --- ШАГ А: Ищем Название ТСР (в списке из клиента) ---
        if idx < len(tsr_names_list):
            tsr_full = tsr_names_list[idx]
            tsr_numeric = extract_tsr_numeric(tsr_full) 
            tsr_literal = extract_tsr_literals(tsr_full)
        else:
            tsr_full = "—"
            tsr_numeric = ""

        # --- ШАГ Б: Ищем Цену и Количество (в списке модулей) ---
        # Мы предполагаем, что порядок строк в ТСР совпадает с порядком модулей
        if idx < len(modules):
            mod = modules[idx]
            qty = mod.get("quantity", 1)
            price = float(mod.get("price", 0))
            price_fmt = f"{price:,.2f}".replace(",", " ")
        else:
            qty = 1 # Если модуля нет, но название есть - ставим 1 шт по умолчанию
            price_fmt = "—"

        # --- ШАГ В: Формируем строку количества ---
        # Если есть название ТСР, но нет модуля -> "1 шт 8-07..."
        # Если нет названия ТСР -> прочерки
        if tsr_full != "—":
            qty = f"{qty}".strip()
        else:
            qty_str = "—"
            price_fmt = "—" # Если нет названия, то и цены нет

        # Записываем в контекст
        context[f"Наименование{i}_ТСР_И_ЕГО_КОД"] = tsr_full
        context[f"Количество_{i}_ТСР"] = qty
        context[f"Цена{i}_ТСР_И_ЕГО_КОД"] = price_fmt

    # --- ЛОГИКА ПОИСКА ПУТИ ---
   
    
    template_key = getattr(payload, "template_type", "llc_contract")

    if template_key not in TEMPLATES_CONFIG:
        template_key = "llc_contract"

    template_config = TEMPLATES_CONFIG[template_key]
    template_filename = template_config["filename"]

    real_template_path = get_template_path(template_filename)

    # -----------------------------------------------------

    doc = DocxTemplate(real_template_path)
    doc.render(context)

    if template_key == "llc_contract":
        file_prefix = "ООО Договор"
    elif template_key == "DMK_contract":
        file_prefix = "ДМК Договор"
    elif template_key == "DMK_instrument":
        file_prefix = "ДМК Акт"
    elif template_key == "SDV_contract":
        file_prefix = "СДВ Договор"
    elif template_key == "SDV_instrument":
        file_prefix = "СДВ Акт"
    else:
        file_prefix = "Документ"

    # 2. Форматируем дату (меняем точки на дефисы, чтобы Windows не ругался)
    # payload.document_date приходит в формате "DD.MM.YYYY"
    safe_date = str(payload.document_date).replace(".", "-").replace("/", "-")

    # 3. Собираем имя: "Префикс_Дата_Фамилия.docx"
    filename = f"{file_prefix}_{safe_date}_{client['last_name']}.docx"
    
    # Генерируем уникальное имя для хранилища (чтобы файлы не перезаписывались)
    unique_name = f"{uuid.uuid4()}_{filename}"
    
    save_path = os.path.join(STORAGE_DIR, unique_name)

    os.makedirs(STORAGE_DIR, exist_ok=True)
    doc.save(save_path)

    file_size = os.path.getsize(save_path)

    db_doc = models.Document(
        client_id=client_id,
        filename=filename,
        storage_path=save_path,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size=file_size
    )

    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    return db_doc