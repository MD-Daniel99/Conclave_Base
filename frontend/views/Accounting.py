import streamlit as st
import pandas as pd
import re
import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import utils

if not st.session_state.get("token"):
    st.stop()

user_id = st.session_state.get("user_id")

saved_settings = {}
if user_id:
    try:
        saved_settings = utils.fetch_user_settings(user_id) or {}
    except:
        saved_settings = {}

default_tax = saved_settings.get("tax_percent", 6.0)
default_acq = saved_settings.get("acq_percent", 1.0)

if "tax_percent" not in st.session_state:
    st.session_state.tax_percent = default_tax
if "acq_percent" not in st.session_state:
    st.session_state.acq_percent = default_acq

st.title("💰 Бухгалтерия и Финансы")

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def parse_price(val):
    if not val: return 0.0
    s = str(val).replace(" ", "").replace("\xa0", "")
    s = s.replace(",", ".")
    parts = s.split(".")
    if len(parts) > 2:
        s = "".join(parts[:-1]) + "." + parts[-1]
    cleaned = re.sub(r'[^\d.]', '', s)
    try:
        return float(cleaned) if cleaned else 0.0
    except:
        return 0.0

if "saving_in_progress" not in st.session_state:
    st.session_state.saving_in_progress = False

# Функция автосохранения изменений из таблицы
def save_accounting_edits():
    if st.session_state.saving_in_progress:
        return
        
    changes = st.session_state.accounting_editor.get("edited_rows", {})
    if not changes: return
    
    # NEW: Получаем список кастомных полей для определения типа
    custom_fields = st.session_state.get("custom_fields_list", [])
    field_map = {f["field_id"]: f for f in custom_fields}
    
    for row_idx, edit_dict in changes.items():
        cid = st.session_state.acc_row_map.get(int(row_idx))
        if not cid: continue
        
        patch_data = {}
        custom_updates = []
        
        for col_name, new_val in edit_dict.items():
            if col_name == "ЗП Протезиста":
                patch_data["prosthetist_salary"] = new_val
            elif col_name == "ЗП Агента":
                patch_data["agent_salary"] = new_val
            elif col_name == "ЗП Поддержки":
                patch_data["support_salary"] = new_val
            else:
                # NEW: Обработка кастомных полей
                # Ищем поле по имени в field_map
                field_id = None
                for fid, f in field_map.items():
                    if f["field_name"] == col_name:
                        field_id = fid
                        break
                if field_id:
                    custom_updates.append({"field_id": field_id, "value": new_val})
        
        if patch_data:
            utils.patch_client(cid, patch_data)
        if custom_updates:
            utils.patch_client_custom_values(cid, custom_updates)
            
    utils.clear_caches()
    st.toast("✅ Изменения сохранены!", icon="💰")
   

# --- ЗАГРУЗКА КАСТОМНЫХ ПОЛЕЙ (NEW) ---
try:
    custom_fields = utils.fetch_custom_fields()
except Exception as e:
    st.error(f"Ошибка загрузки кастомных полей: {e}")
    custom_fields = []
st.session_state.custom_fields_list = custom_fields  # сохраняем для использования в save_accounting_edits

if st.session_state.get("saving_in_progress"):
    st.session_state.saving_in_progress = False
    
# --- ПАНЕЛЬ НАСТРОЕК ---
with st.expander("⚙️ Настройки, проценты и фильтры", expanded=True):
    st.caption("Изменение процентов мгновенно пересчитает всю таблицу")
    col_tax, col_acq, col_save = st.columns([1,1,1])
    tax_percent = col_tax.number_input("Налог (%)", value=st.session_state.tax_percent, step=0.1, format="%.1f", key="tax_input")
    acq_percent = col_acq.number_input("Эквайринг (%)", value=st.session_state.acq_percent, step=0.1, format="%.1f", key="acq_input")
    if col_save.button("💾 Сохранить проценты", use_container_width=True, key="save_percents"):
        if user_id:
            try:
                utils.patch_user_settings(user_id, {"tax_percent": tax_percent, "acq_percent": acq_percent})
                st.session_state.tax_percent = tax_percent
                st.session_state.acq_percent = acq_percent
                st.success("Проценты сохранены!")
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка сохранения: {e}")
        else:
            st.warning("Не удалось определить пользователя")
    
    col_date1, col_date2 = st.columns(2)
    start_date = col_date1.date_input("Дата пробития с", value=None, key="start_date_filter")
    end_date = col_date2.date_input("Дата пробития по", value=None, key="end_date_filter")
    
    hide_fails = st.checkbox("Скрыть статусы 'Отказ' и 'Отложен'", value=True)
    
    st.divider()
    
    # --- УПРАВЛЕНИЕ КАСТОМНЫМИ ПОЛЯМИ (NEW) ---
    with st.expander("🛠️ Управление кастомными полями", expanded=False):
        st.markdown("**Добавить новое поле**")
        col_new_name, col_new_type, col_new_btn = st.columns([3,1,1])
        with col_new_name:
            new_field_name = st.text_input("Имя поля", key="new_cf_name")
        with col_new_type:
            new_field_type = st.selectbox("Тип", ["number", "text"], key="new_cf_type")
        with col_new_btn:
            st.write("")  # для выравнивания
            if st.button("➕ Создать", key="create_cf_btn"):
                if new_field_name:
                    try:
                        utils.create_custom_field(new_field_name, new_field_type)
                        st.success(f"Поле '{new_field_name}' создано!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
                else:
                    st.warning("Введите имя поля")
        
        if custom_fields:
            st.markdown("**Существующие кастомные поля**")
            for cf in custom_fields:
                col_cf, col_del = st.columns([5,1])
                col_cf.write(f"• **{cf['field_name']}** ({cf['field_type']})")
                if col_del.button("🗑️", key=f"del_cf_{cf['field_id']}"):
                    try:
                        utils.delete_custom_field(cf['field_id'])
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка удаления: {e}")
    
    st.divider()
    
    # Динамический выбор колонок (включая кастомные)
    ALL_COLUMNS = [
        "ФИО", "Агент", "Дата пробития", "Стоимость серт.", 
        "Налог", "Стоимость модулей", "ЗП Протезиста", 
        "ЗП Агента", "ЗП Поддержки", "Эквайринг", "Прибыль"
    ]
    # NEW: Добавляем имена кастомных полей
    custom_field_names = [cf["field_name"] for cf in custom_fields]
    ALL_COLUMNS.extend(custom_field_names)
    
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
    clients = []

data_rows = []
total_revenue = 0.0
total_profit = 0.0
total_taxes = 0.0

# NEW: Собираем map field_name -> field_type для быстрого доступа
field_type_map = {cf["field_name"]: cf["field_type"] for cf in custom_fields}

for c in clients:
    status = c.get("status_code", "")
    stage = c.get("current_stage", "")
    
    if hide_fails and (status in ["fail", "hold"] or "отменен" in stage.lower()):
        continue

    # --- ФИЛЬТР ПО ДАТЕ ПРОБИТИЯ ---
    check_date_str = c.get("check_date")
    if check_date_str:
        try:
            check_date_str = str(check_date_str).split("T")[0].split()[0]
            check_date_obj = datetime.strptime(check_date_str, "%Y-%m-%d").date()
        except Exception as e:
            # Для отладки: раскомментируйте, чтобы увидеть проблемные даты
            #бка парсинга даты для {c.get('last_name')}: {check_date_str} - {e}")
            check_date_obj = None

    if start_date and (not check_date_obj or check_date_obj < start_date):
        continue
    if end_date and (not check_date_obj or check_date_obj > end_date):
        continue
        
    cert_price = parse_price(c.get("certificate_price"))
    cashing_date = c.get("check_date")
    modules_cost = sum([float(m.get("cost", 0.0)) for m in c.get("modules", [])])
    
    tax_amount = cert_price * (tax_percent / 100.0)
    acq_amount = cert_price * (acq_percent / 100.0)
    
    p_sal = float(c.get("prosthetist_salary") or 0.0)
    a_sal = float(c.get("agent_salary") or 0.0)
    s_sal = float(c.get("support_salary") or 0.0)
    
    # NEW: Сумма числовых кастомных полей (расходы)
    custom_numeric_sum = 0.0
    custom_fields_values = c.get("custom_fields", {})
    for fname, fval in custom_fields_values.items():
        if field_type_map.get(fname) == "number" and fval is not None:
            try:
                custom_numeric_sum += float(fval)
            except:
                pass
    
    # ПРИБЫЛЬ (MODIFIED: вычитаем custom_numeric_sum)
    if modules_cost == 0 and cashing_date == None:
        profit = 0
    else:
        profit = cert_price - tax_amount - acq_amount - modules_cost - p_sal - a_sal - s_sal - custom_numeric_sum
    
    total_revenue += cert_price
    total_profit += profit
    total_taxes += tax_amount
    
    ag_name = f"{c['agent']['last_name']} {c['agent']['first_name']}" if c.get("agent") else "—"
    
    row = {
        "ID": c["client_id"],
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
    }
    # NEW: Добавляем значения кастомных полей
    for fname in custom_field_names:
        val = custom_fields_values.get(fname)
        if field_type_map.get(fname) == "number":
            # Для числовых полей используем 0.0 вместо None, иначе data_editor не позволит редактировать
            row[fname] = float(val) if val is not None and val != "" else 0.0
        else:
            row[fname] = str(val) if val is not None else ""
    
    data_rows.append(row)

# --- ИНТЕРФЕЙС И ТАБЛИЦА ---
if data_rows:
    df = pd.DataFrame(data_rows)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Общая сумма сертификатов", f"{total_revenue:,.2f} ₽".replace(",", " "))
    m2.metric("Общая чистая прибыль", f"{total_profit:,.2f} ₽".replace(",", " "))
    m3.metric("Уплачено налогов", f"{total_taxes:,.2f} ₽".replace(",", " "))
    
    st.write("💡 *Подсказка: Можно редактировать ячейки зарплат и кастомных полей прямо в таблице - они сохранятся автоматически*")

    st.session_state.acc_row_map = df["ID"].to_dict()
    
    df_display = df[["ID"] + selected_columns]

    # Какие колонки разрешено редактировать
    editable_cols = ["ЗП Протезиста", "ЗП Агента", "ЗП Поддержки"] + custom_field_names
    disabled_cols = [col for col in df_display.columns if col not in editable_cols]

    # Настройка форматов колонок
    column_config = {
        "ID": None,
        "Стоимость серт.": st.column_config.NumberColumn("Стоимость серт.", format="%,.2f ₽"),
        "Налог": st.column_config.NumberColumn("Налог", format="%,.2f ₽"),
        "Стоимость модулей": st.column_config.NumberColumn("Стоимость модулей", format="%,.2f ₽"),
        "Эквайринг": st.column_config.NumberColumn("Эквайринг", format="%,.2f ₽"),
        "Прибыль": st.column_config.NumberColumn("Прибыль", format="%,.2f ₽"),
        "ЗП Протезиста": st.column_config.NumberColumn("ЗП Протезиста ✏️", format="%,.2f ₽", min_value=0.0),
        "ЗП Агента": st.column_config.NumberColumn("ЗП Агента ✏️", format="%,.2f ₽", min_value=0.0),
        "ЗП Поддержки": st.column_config.NumberColumn("ЗП Поддержки ✏️", format="%,.2f ₽", min_value=0.0),
        "Дата пробития": st.column_config.DateColumn("Дата пробития", format="DD.MM.YYYY"),
    }
    # NEW: Добавляем конфигурацию для кастомных полей
    for cf in custom_fields:
        if cf["field_type"] == "number":
            column_config[cf["field_name"]] = st.column_config.NumberColumn(
                f"{cf['field_name']} ✏️", format="%,.2f ₽", min_value=0.0
            )
        else:
            column_config[cf["field_name"]] = st.column_config.TextColumn(f"{cf['field_name']} ✏️")

    # Флаг для принудительного обновления после сохранения
    if "force_refresh" not in st.session_state:
        st.session_state.force_refresh = False

    editor_result = st.data_editor(
        df_display,
        key="accounting_editor",
        disabled=disabled_cols,
        hide_index=True,
        use_container_width=True,
        column_config=column_config
    )

    # Проверяем изменения и сохраняем
    if st.session_state.accounting_editor.get("edited_rows") and not st.session_state.force_refresh:
        save_accounting_edits()
        st.session_state.force_refresh = True
        st.rerun()
    elif st.session_state.force_refresh:
        st.session_state.force_refresh = False
