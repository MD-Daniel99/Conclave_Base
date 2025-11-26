import streamlit as st
import pandas as pd
import sys
import os
import time
from datetime import datetime 

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import utils

if not st.session_state.get("token"):
    st.stop()

# --- STATE ---
if "wh_active_id" not in st.session_state:
    st.session_state.wh_active_id = None

def reset_wh():
    st.session_state.wh_active_id = None
    st.rerun()

# --- LOAD DATA ---
try:
    clients_raw = utils.fetch_clients(limit=1000)
    # Карта: "Фамилия Имя" -> ID
    clients_map = {f"{c['last_name']} {c['first_name']}": c['client_id'] for c in clients_raw}
    # Для фильтра добавляем опцию "На складе" (None)
    clients_filter = {"(Все)": None}
    clients_filter.update(clients_map)
except:
    clients_map = {}
    clients_filter = {}

# --- EXPORT FUNCTION (CACHED) ---
@st.cache_data(ttl=60)
def get_warehouse_csv():
    mods = utils.fetch_modules(limit=100000)
    if not mods:
        return None
    
    ex_rows = []
    for m in mods:
        own = ""
        if m.get("client"): own = f"{m['client']['last_name']} {m['client']['first_name']}"
        
        ex_rows.append({
            "Название": m['module_name'],
            "Индекс": m['catalogue_index'],
            "Поставщик": m['supplier'],
            "Владелец": own,
            "Количество": m['quantity'],
            "Цена": m['price'],
            "Себестоимость": m['cost'],
            "Ordered": m['ordered'],
            "Recd": m['recd'],
            "Pending": m['pending'],
            "Счет": m['order_date_acc_num'],
            "Заметки": m['notes']
        })
    
    return pd.DataFrame(ex_rows).to_csv(index=False).encode('utf-8-sig')

st.title("📦 Склад")

# ==========================================
# VIEW MODE (Список)
# ==========================================
if st.session_state.wh_active_id is None:

    # --- IMPORT / EXPORT ---
    with st.expander("📂 Импорт / Экспорт (CSV)"):
        tab_ex, tab_im = st.tabs(["Экспорт", "Импорт"])
        
        with tab_ex:
            # ОДНА КНОПКА: Данные готовятся на лету (кэшируются)
            csv_data = get_warehouse_csv()
            if csv_data:
                st.download_button(
                    label="📥 Скачать таблицу Склад (CSV)",
                    data=csv_data,
                    file_name=f"warehouse_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("Нет данных для экспорта")

        with tab_im:
            st.info("При импорте модули без владельца будут помечены как 'На складе'.")
            template = pd.DataFrame([{"Название": "Тест", "Индекс": "123", "Поставщик": "ООО", "Владелец": "", "Количество": 1, "Цена": 100}])
            csv_t = template.to_csv(index=False).encode('utf-8-sig')
            st.download_button("Скачать шаблон", csv_t, "warehouse_template.csv", "text/csv")
            
            up = st.file_uploader("CSV файл", type=["csv"])
            if up and st.button("Загрузить"):
                try:
                    df_im = pd.read_csv(up)
                    prog = st.progress(0)
                    tot = len(df_im)
                    
                    for i, row in df_im.iterrows():
                        owner_str = str(row.get("Владелец", "")).strip()
                        cid = clients_map_rev.get(owner_str)
                        
                        pl = {
                            "module_name": str(row.get("Название", "Без названия")),
                            "catalogue_index": str(row.get("Индекс", "-")),
                            "supplier": str(row.get("Поставщик", "-")),
                            "client_id": cid,
                            "quantity": int(row.get("Количество", 1)),
                            "price": float(row.get("Цена", 0)),
                            "cost": float(row.get("Себестоимость", 0)),
                            "ordered": str(row.get("Ordered", "0")),
                            "recd": str(row.get("Recd", "0")),
                            "pending": str(row.get("Pending", "0")),
                            "order_date_acc_num": str(row.get("Счет", "-")),
                            "notes": str(row.get("Заметки", "")),
                            "properties": "-"
                        }
                        utils.create_module(pl)
                        prog.progress((i + 1) / tot)
                    
                    st.success("Готово!")
                    time.sleep(1)
                    utils.clear_caches()
                    st.rerun()
                except Exception as e: st.error(f"Ошибка: {e}")
    
    # 1. ФИЛЬТРЫ
    with st.expander("🔍 Поиск", expanded=True):
        c1, c2, c3 = st.columns(3)
        q = c1.text_input("Название")
        sup = c2.text_input("Поставщик")
        owner_sel = c3.selectbox("Владелец", list(clients_filter.keys()))
        
        c4, c5 = st.columns([1, 4])
        limit = c4.number_input("Лимит", 10, 200, 50)
        page = c5.number_input("Страница", 1, 100, 1)
        skip = (page - 1) * limit

    # 2. TABLE
    # Получаем ID для фильтрации
    cid_filter = clients_filter.get(owner_sel)
    
    try:
        modules = utils.fetch_modules(skip, limit, q, sup, cid_filter)
    except Exception as e:
        st.error(f"Ошибка: {e}")
        modules = []

    if modules:
        rows = []
        for m in modules:
            own = "—"
            # Бэкенд возвращает объект client внутри модуля (благодаря selectinload)
            if m.get("client"): 
                own = f"{m['client']['last_name']} {m['client']['first_name']}"
            
            rows.append({
                "ID": m["module_id"],
                "Название": m["module_name"],
                "Индекс": m["catalogue_index"],
                "Поставщик": m["supplier"],
                "Владелец": own
            })
        
        df = pd.DataFrame(rows)
        
        event = st.dataframe(
            df, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun"
        )
        
        if event.selection.rows:
            idx = event.selection.rows[0]
            # Сохраняем ID и переходим в режим редактирования
            st.session_state.wh_active_id = df.iloc[idx]["ID"]
            st.rerun()
    else:
        st.info("Пусто")

    # 3. CREATE
    st.divider()
    with st.expander("➕ Создать модуль", expanded=False):
        with st.form("new_mod"):
            st.subheader("Основные данные")
            c1, c2 = st.columns(2)
            nn = c1.text_input("Название *")
            ni = c2.text_input("Индекс в каталоге *")
            
            c3, c4 = st.columns(2)
            ns = c3.text_input("Поставщик *")
            no = c4.selectbox("Привязать к", ["На склад"] + list(clients_map.keys()))

            st.divider()
            st.subheader("Финансы и Количество")
            f1, f2, f3 = st.columns(3)
            n_qty = f1.number_input("Количество (шт)", min_value=0, value=1, step=1)
            n_cost = f2.number_input("Себестоимость", min_value=0.0, value=0.0, step=10.0)
            n_price = f3.number_input("Цена продажи", min_value=0.0, value=0.0, step=10.0)

            st.divider()
            st.subheader("Статусы и Детали")
            # Эти поля в вашей базе строковые (String), поэтому используем text_input
            s1, s2, s3 = st.columns(3)
            n_ord = s1.text_input("Заказано (Ordered)", value="0")
            n_recd = s2.text_input("Получено (Recd)", value="0")
            n_pend = s3.text_input("Ожидается (Pending)", value="0")

            d1, d2 = st.columns(2)
            n_acc = d1.text_input("№ Счета / Дата заказа", value="-")
            n_props = d2.text_input("Характеристики", value="-")
            
            n_notes = st.text_area("Заметки")
            
            submit_btn = st.form_submit_button("Создать модуль", use_container_width=True)

            if submit_btn:
                if nn and ni and ns:
                    # Определяем ID клиента (или None)
                    cid_target = clients_map.get(no)
                    
                    pl = {
                        # Обязательные
                        "module_name": nn, 
                        "catalogue_index": ni, 
                        "supplier": ns,
                        "client_id": cid_target,
                        
                        # Числовые
                        "quantity": n_qty,
                        "cost": n_cost,
                        "price": n_price,
                        
                        # Строковые статусы
                        "ordered": n_ord,
                        "recd": n_recd,
                        "pending": n_pend,
                        "order_date_acc_num": n_acc,
                        "properties": n_props,
                        
                        # Опциональные
                        "notes": n_notes if n_notes else None
                    }
                    
                    try:
                        utils.create_module(pl)
                        st.success("Модуль успешно создан!")
                        st.rerun()
                    except Exception as e: 
                        st.error(f"Ошибка создания: {e}")
                else:
                    st.warning("Поля, отмеченные *, обязательны к заполнению")

# ==========================================
# EDIT MODE (Если выбран модуль)
# ==========================================
# ==========================================
# EDIT MODE (Если выбран модуль)
# ==========================================
else:
    mid = st.session_state.wh_active_id
    
    if st.button("⬅️ Назад к списку"):
        reset_wh()

    # 1. Загружаем данные модуля по ID
    try:
        mod_detail = utils.fetch_module_detail(mid)
    except Exception as e:
        st.error(f"Ошибка загрузки модуля: {e}")
        if st.button("Сбросить выбор"): reset_wh()
        st.stop()

    st.subheader(f"Редактирование: {mod_detail['module_name']}")

    with st.form("edit_wh_mod"):
        # --- РАЗДЕЛ 1: ОСНОВНОЕ ---
        st.caption("Основные данные")
        c1, c2 = st.columns(2)
        en = c1.text_input("Название", value=mod_detail['module_name'])
        ei = c2.text_input("Индекс в каталоге", value=mod_detail['catalogue_index'])
        
        c3, c4 = st.columns(2)
        es = c3.text_input("Поставщик", value=mod_detail['supplier'])
        
        # ЛОГИКА ВЫБОРА ВЛАДЕЛЬЦА (восстановленная)
        curr_cid = mod_detail.get('client_id')
        owner_options = ["На склад (Ничей)"] + list(clients_map.keys())
        
        default_idx = 0
        if curr_cid:
            # Ищем имя по ID в clients_map
            found_name = next((name for name, uid in clients_map.items() if uid == curr_cid), None)
            if found_name:
                default_idx = owner_options.index(found_name)
        
        eo = c4.selectbox("Владелец", owner_options, index=default_idx)
        
        st.divider()
        
        # --- РАЗДЕЛ 2: ФИНАНСЫ ---
        st.caption("Финансы и Количество")
        f1, f2, f3 = st.columns(3)
        # Используем get() or 0, чтобы не упало, если придет None
        qty_val = mod_detail.get('quantity') or 0
        cost_val = mod_detail.get('cost') or 0.0
        price_val = mod_detail.get('price') or 0.0
        
        eq = f1.number_input("Количество (шт)", min_value=0, value=int(qty_val), step=1)
        ec = f2.number_input("Себестоимость", min_value=0.0, value=float(cost_val), step=10.0)
        ep = f3.number_input("Цена продажи", min_value=0.0, value=float(price_val), step=10.0)

        st.divider()

        # --- РАЗДЕЛ 3: СТАТУСЫ И ДЕТАЛИ ---
        st.caption("Статусы и Детали")
        s1, s2, s3 = st.columns(3)
        e_ord = s1.text_input("Заказано (Ordered)", value=mod_detail.get('ordered', '0'))
        e_recd = s2.text_input("Получено (Recd)", value=mod_detail.get('recd', '0'))
        e_pend = s3.text_input("Ожидается (Pending)", value=mod_detail.get('pending', '0'))

        d1, d2 = st.columns(2)
        e_acc = d1.text_input("№ Счета / Дата заказа", value=mod_detail.get('order_date_acc_num', '-'))
        e_props = d2.text_input("Характеристики", value=mod_detail.get('properties', '-'))
        
        e_notes = st.text_area("Заметки", value=mod_detail.get('notes') or "")
        
        # --- СОХРАНЕНИЕ ---
        if st.form_submit_button("Сохранить изменения", use_container_width=True):
            # Определяем новый ID клиента
            cid_target = None
            if eo != "На склад (Ничей)":
                cid_target = clients_map[eo]
            
            pl = {
                "module_name": en, 
                "catalogue_index": ei, 
                "supplier": es,
                "client_id": cid_target, # Перепривязка
                
                "quantity": eq,
                "cost": ec,
                "price": ep,
                
                "ordered": e_ord,
                "recd": e_recd,
                "pending": e_pend,
                "order_date_acc_num": e_acc,
                "properties": e_props,
                "notes": e_notes
            }
            
            try:
                utils.patch_module(mid, pl)
                st.success("Обновлено!")
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка обновления: {e}")
            
    st.divider()
    if st.button("🗑️ Удалить модуль", type="primary"):
        try:
            utils.delete_module(mid)
            st.success("Удалено")
            reset_wh()
        except Exception as e:
            st.error(f"Ошибка удаления: {e}")