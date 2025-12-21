import os
import re
from num2words import num2words
from docxtpl import DocxTemplate
from sqlalchemy.orm import Session
from app import models, crud
import uuid

# Папка для сохранения готовых документов
STORAGE_DIR = "/app/storage"

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

def generate_contract(db: Session, client_id: uuid.UUID, payload):
    # 1. Получаем данные
    client = crud.get_client(db, client_id) 
    if not client:
        raise ValueError("Клиент не найден")

    # 2. Подготовка данных
    passport = {}
    if client.get("passports") and len(client["passports"]) > 0:
        last_passport = sorted(client["passports"], key=lambda x: x.get("created_at") or "", reverse=True)[0]
        passport = last_passport

    phone = ""
    if client.get("phones") and len(client["phones"]) > 0:
        phone = client["phones"][0]["number"]

    modules = client.get("modules", [])

    total_sum = sum(float(m.get("price") or 0) for m in modules)

    raw_sn = passport.get('series_number') or ""
    clean_sn = raw_sn.replace(" ", "").replace("-", "")

    series = clean_sn[:4]
    number = clean_sn[4:]
    
    # Форматирование: 1 250.00 (пробел как разделитель)
    sum_formatted = f"{total_sum:,.2f}".replace(",", " ")

    context = {
        "НомерДоговора": payload.contract_number,
        "ДатаДоговора": payload.contract_date,
        "ДатаПлана": payload.plan_date,

        "ФИОЗаказчика": f"{client['last_name']} {client['first_name']} {client['middle_name'] or ''}".strip(),
        "ДатаРожденияЗаказчика": passport.get('birth_date') if passport.get('birth_date') else "__________",
        "ПаспортСерия": series,
        "ПаспортНомер": number,
        "КемВыданПаспорт": passport.get('issued_by', "________"),
        "ДатаВыдачиПаспорта": passport.get("issue_date", "________"),
        "КодПодразделения": passport.get("department_code", "______"),
        "АдресРегистрацииЗаказчика": passport.get("registration_address", "__________________"),
        "Телефон_заказчика": phone,

        "Сумма": sum_formatted,
        "СуммаПрописью": rub_to_words(total_sum),
        "ИнициалыЗаказчикаКратко": get_initials(client['last_name'], client['first_name'], client['middle_name']),
        
        "ВерхнихилиНижнихконечностей": client.get('prosthesis_type', ' ')
    }

    # Заполнение модулей ТСР
    for i in range(1, 5):
        idx = i - 1
        if idx < len(modules):
            module = modules[idx]
            tsr_full = module.get('tsr_code') or "Не указан ТСР"
            tsr_code = extract_tsr_numeric(tsr_full)
            qty = module.get("quantity", " ")
            price = float(module.get("price", 0))
            price_fmt = f"{price:,.2f}".replace(",", " ")

            context[f"Наименование{i}_ТСР_И_ЕГО_КОД"] = tsr_full
            context[f"Количество_{i}_ТСР"] = str(qty)
            context[f"Цена{i}_ТСР_И_ЕГО_КОД"] = price_fmt
        
        else:
            context[f"Наименование{i}_ТСР_И_ЕГО_КОД"] = "—"
            context[f"Количество_{i}_ТСР"] = "—"
            context[f"Цена{i}_ТСР_И_ЕГО_КОД"] = "—"

    # --- ЛОГИКА ПОИСКА ПУТИ (ПЕРЕНЕСЕНА ВНУТРЬ ФУНКЦИИ) ---
    POSSIBLE_PATHS = [
        "/app/app/templates/contract_template.docx",  # Путь, который выдал find
        "/app/templates/contract_template.docx",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "contract_template.docx"),
    ]
    
    real_template_path = None
    for path in POSSIBLE_PATHS:
        if os.path.exists(path):
            real_template_path = path
            break
            
    if not real_template_path:
        # Логируем ошибку в консоль Docker
        print(f"CRITICAL ERROR: Шаблон не найден. Искали здесь: {POSSIBLE_PATHS}", flush=True)
        print(f"CWD: {os.getcwd()}", flush=True)
        # Пытаемся показать содержимое папки для отладки
        try:
            print(f"Content of /app/app/templates: {os.listdir('/app/app/templates')}", flush=True)
        except Exception as e:
            print(f"Cannot list dir: {e}", flush=True)
            
        raise FileNotFoundError(f"Файл шаблона не найден. Проверьте логи сервера.")

    # -----------------------------------------------------

    doc = DocxTemplate(real_template_path)
    doc.render(context)

    # Чистим имя файла от слэшей, чтобы путь не сломался
    safe_contract_num = str(payload.contract_number).replace("/", "-").replace("\\", "-")
    filename = f"Договор_{safe_contract_num}_{client['last_name']}.docx"
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