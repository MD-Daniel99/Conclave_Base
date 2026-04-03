import streamlit as st
import pandas as pd
import re
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import utils

if not st.session_state.get("token"):
    st.stop()

st.title("💰 Бухгалтерия и Финансы")

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def parse_price(val):
    if not val: return 0.0
    # Убираем пробелы и неразрывные пробелы
    s = str(val).replace(" ", "").replace("\xa0", "")
    # Меняем запятую на точку
    s = s.replace(",", ".")
    # Если точек больше одной (например 1.500.000.00), удаляем все, кроме последней
    parts = s.split(".")
    if len(parts) > 2:
        s = "".join(parts[:-1]) + "." + parts[-1]
    # Оставляем только цифры и точку
    cleaned = re.sub(r'[^\d.]', '', s)
    try:
        return float(cleaned) if cleaned else 0.0
    except:
        return 0.0

# Функция автосохранения изменений из таблицы
def save_accounting_edits():
    changes = st.session_state.accounting_editor.get("edited_rows", {})
    if not changes: return
    
    for row_idx, edit_dict in changes.items():
        # Достаем реальный ID клиента из скрытой карты
        cid = st.session_state.acc_row_map.get(int(row_idx))
        if not cid: continue
        patch_data = {}
        
        # Проверяем, какие именно колонки изменил пользователь
        if "ЗП Протезиста" in edit_dict: patch_data["prosthetist_salary"] = edit_dict["ЗП Протезиста"]
        if "ЗП Агента" in edit_dict: patch_data["agent_salary"] = edit_dict["ЗП Агента"]
        if "ЗП Поддержки" in edit_dict: patch_data["support_salary"] = edit_dict["ЗП Поддержки"]
        
        # Отправляем запрос на сервер
        if patch_data:
            utils.patch_client(cid, patch_data)
            
    # Сбрасываем кэш, чтобы загрузить свежие данные и пересчитать прибыль
    utils.clear_caches()
    st.toast("✅ Зарплаты успешно сохранены!", icon="💰")

# --- ПАНЕЛЬ НАСТРОЕК ---
with st.expander("⚙️ Настройки, проценты и фильтры", expanded=True):
    st.caption("Изменение процентов мгновенно пересчитает всю таблицу")
    col_tax, col_acq, col_filter = st.columns(3)
    
    tax_percent = col_tax.number_input("Налог (%)", value=6.0, step=0.5, format="%.1f")
    acq_percent = col_acq.number_input("Эквайринг (%)", value=1.0, step=0.5, format="%.1f")
    
    # Галочка скрытия отмененных клиентов
    hide_fails = col_filter.checkbox("Скрыть статусы 'Отказ' и 'Отложен'", value=True)
    
    st.divider()
    
    # Динамический выбор колонок (пожелание клиента)
    ALL_COLUMNS =[
        "ФИО", "Агент", "Дата пробития", "Стоимость серт.", 
        "Налог", "Стоимость модулей", "ЗП Протезиста", 
        "ЗП Агента", "ЗП Поддержки", "Эквайринг", "Прибыль"
    ]
    
    selected_columns = st.multiselect(
        "Отображаемые столбцы", 
        options=ALL_COLUMNS, 
        default=ALL_COLUMNS
    )

# --- ЗАГРУЗКА И ОБРАБОТКА ДАННЫХ ---
try:
    clients = utils.fetch_clients(limit=100000)
except Exception as e:
    st.error(f"Ошибка загрузки данных: {e}")
    clients =[]

data_rows =[]
total_revenue = 0.0
total_profit = 0.0
total_taxes = 0.0

for c in clients:
    status = c.get("status_code", "")
    stage = c.get("current_stage", "")
    
    # Фильтрация отмененных (статусы fail/hold или какие-либо отмененные этапы)
    if hide_fails and (status in["fail", "hold"] or "отменен" in stage.lower()):
        continue
        
    # Парсинг данных
    cert_price = parse_price(c.get("certificate_price"))
    modules_cost = sum([float(m.get("cost", 0.0)) for m in c.get("modules", [])])
    
    # Расчет налогов и эквайринга
    tax_amount = cert_price * (tax_percent / 100.0)
    acq_amount = cert_price * (acq_percent / 100.0)
    
    # Зарплаты
    p_sal = float(c.get("prosthetist_salary") or 0.0)
    a_sal = float(c.get("agent_salary") or 0.0)
    s_sal = float(c.get("support_salary") or 0.0)
    
    # ПРИБЫЛЬ
    if modules_cost == 0:
        profit = 0
    else:
        profit = cert_price - tax_amount - acq_amount - modules_cost - p_sal - a_sal - s_sal
    
    # Сводные метрики
    total_revenue += cert_price
    total_profit += profit
    total_taxes += tax_amount
    
    # Форматирование имени агента
    ag_name = f"{c['agent']['last_name']} {c['agent']['first_name']}" if c.get("agent") else "—"
    
    data_rows.append({
        "ID": c["client_id"], # Скрытая колонка для автосохранения
        "ФИО": f"{c.get('last_name','')} {c.get('first_name','')}".strip(),
        "Агент": ag_name,
        "Дата пробития": c.get("check_date", "—"),
        "Стоимость серт.": cert_price,
        "Налог": tax_amount,
        "Стоимость модулей": modules_cost,
        "ЗП Протезиста": p_sal,
        "ЗП Агента": a_sal,
        "ЗП Поддержки": s_sal,
        "Эквайринг": acq_amount,
        "Прибыль": profit
    })

# --- ИНТЕРФЕЙС И ТАБЛИЦА ---
if data_rows:
    df = pd.DataFrame(data_rows)
    
    # Метрики наверху
    m1, m2, m3 = st.columns(3)
    m1.metric("Общая сумма сертификатов", f"{total_revenue:,.2f} ₽".replace(",", " "))
    m2.metric("Общая чистая прибыль", f"{total_profit:,.2f} ₽".replace(",", " "))
    m3.metric("Уплачено налогов", f"{total_taxes:,.2f} ₽".replace(",", " "))
    
    st.write("💡 *Подсказка: Можно редактировать ячейки зарплат прямо в таблице - они сохранятся автоматически*")

    # Сохраняем карту ID строк для коллбека сохранения
    st.session_state.acc_row_map = df["ID"].to_dict()
    
    # Оставляем только скрытый ID и выбранные колонки
    df_display = df[["ID"] + selected_columns]

    # Какие колонки запрещено редактировать
    disabled_cols =[col for col in df_display.columns if col not in["ЗП Протезиста", "ЗП Агента", "ЗП Поддержки"]]

    # Отрисовка интерактивной таблицы
    st.data_editor(
        df_display,
        key="accounting_editor",
        on_change=save_accounting_edits,
        disabled=disabled_cols,
        hide_index=True,
        use_container_width=True,
        column_config={
            "ID": None, # Полностью прячем колонку ID
            "Стоимость серт.": st.column_config.NumberColumn("Стоимость серт.", format="%,.2f ₽"),
            "Налог": st.column_config.NumberColumn("Налог", format="%,.2f ₽"),
            "Стоимость модулей": st.column_config.NumberColumn("Стоимость модулей", format="%,.2f ₽"),
            "Эквайринг": st.column_config.NumberColumn("Эквайринг", format="%,.2f ₽"),
            "Прибыль": st.column_config.NumberColumn("Прибыль", format="%,.2f ₽"),
            
            "ЗП Протезиста": st.column_config.NumberColumn("ЗП Протезиста ✏️", format="%,.2f ₽", min_value=0.0),
            "ЗП Агента": st.column_config.NumberColumn("ЗП Агента ✏️", format="%,.2f ₽", min_value=0.0),
            "ЗП Поддержки": st.column_config.NumberColumn("ЗП Поддержки ✏️", format="%,.2f ₽", min_value=0.0),
        }
    )
else:
    st.info("Нет данных для отображения. Возможно, у всех клиентов стоит статус 'Отказ'.")