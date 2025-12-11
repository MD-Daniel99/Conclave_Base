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
            "Стоимость": m['cost'],
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
            # добавление данных в датафрейм
            rows.append({
                "ID": m["module_id"],
                "Название": m["module_name"],
                "Индекс": m["catalogue_index"],
                "Цена": m["price"],
                "Стоимость": m["cost"],
                "Заказано": m.get("ordered", "0"),
                "Получено": m.get("recd", "0"),
                "В ожидании": m.get("pending", "0"),
                "У протезиста": m.get("prosthetist_keep", "0"),
                "Размер": m.get("size", ""),
                "Жесткость": m.get("stiffness", ""),
                "Сторона": m.get("side", ""),
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
    with st.expander("➕ Создать модуль (с авто-расчетом)", expanded=False):
        # УБРАЛИ st.form! Теперь работает пересчет.
        st.subheader("Основные данные")
        c1, c2 = st.columns(2)
        # Добавляем key, чтобы не терять фокус
        nn = c1.text_input("Название *", key="new_n")
        ni = c2.text_input("Индекс в каталоге *", key="new_i")
        
        c3, c4 = st.columns(2)
        ns = c3.text_input("Поставщик *", key="new_s")
        no = c4.selectbox("Привязать к", ["На склад"] + list(clients_map.keys()), key="new_o")

        st.divider()
        st.subheader("Финансы")
        f1, f2, f3, f4, f5 = st.columns(5)

        # Ввод (с ключами!)
        n_qty = f1.number_input("Кол-во", min_value=1, value=1, key="new_q")
        n_unit_cost = f2.number_input("Себест. (ед)", 0.0, step=10.0, key="new_uc")
        n_unit_price = f3.number_input("Цена (ед)", 0.0, step=10.0, key="new_up")
    
        # Расчет (мгновенный, т.к. нет формы)
        n_total_cost = n_unit_cost * n_qty
        n_total_price = n_unit_price * n_qty
    
        f4.metric("ИТОГО стоимость", f"{n_total_cost:.2f}")
        f5.metric("ИТОГО цена", f"{n_total_price:.2f}")

        st.divider()
        st.subheader("Характеристики")
        ch1, ch2, ch3 = st.columns(3)
        n_size = ch1.text_input("Размер", key="new_size")
        n_stiff = ch2.text_input("Жесткость", key="new_stiff")
        n_side = ch3.text_input("Сторона", key="new_side")

        st.divider()
        st.subheader("Статусы")
        s1, s2, s3, s4 = st.columns(4)
        n_ord = s1.text_input("Заказано", "0", key="new_ord")
        n_recd = s2.text_input("Получено", "0", key="new_recd")
        n_pend = s3.text_input("Ожидается", "0", key="new_pend")
        n_pr_keep = s4.text_input("У протезиста", "0", key="new_pr_keep")

        d1, d2 = st.columns(2)
        n_acc = d1.text_input("Счет", "-", key="new_acc")
        n_props = d2.text_input("Хар-ки", "-", key="new_props")
        
        n_notes = st.text_area("Заметки", key="new_notes")
        
        # Кнопка теперь просто button
        if st.button("Создать модуль", type="primary"):
            if nn and ni and ns:
                cid_target = clients_map.get(no)
                pl = {
                    "module_name": nn, "catalogue_index": ni, "supplier": ns, "client_id": cid_target,
                    "quantity": n_qty, "cost": n_total_cost, "price": n_total_price,
                    "ordered": n_ord, "recd": n_recd, "pending": n_pend,
                    "order_date_acc_num": n_acc, "properties": n_props, "notes": n_notes,
                    "size": n_size, "stiffness": n_stiff, "side": n_side, "prosthetist_keep": n_pr_keep,
                }
                try:
                    utils.create_module(pl)
                    st.success("Создано!")
                    st.rerun()
                except Exception as e: st.error(f"Ошибка: {e}")
            else:
                st.warning("Заполните поля со *")

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

    # УБИРАЕМ with st.form!
    
    # --- РАЗДЕЛ 1: ОСНОВНОЕ ---
    st.caption("Основные данные")
    c1, c2 = st.columns(2)
    en = c1.text_input("Название", value=mod_detail['module_name'], key="edit_n")
    ei = c2.text_input("Индекс в каталоге", value=mod_detail['catalogue_index'], key="edit_i")
    
    c3, c4 = st.columns(2)
    es = c3.text_input("Поставщик", value=mod_detail['supplier'], key="edit_s")
    
    # Владелец
    curr_cid = mod_detail.get('client_id')
    owner_options = ["На склад (Ничей)"] + list(clients_map.keys())
    default_idx = 0
    if curr_cid:
        found_name = next((name for name, uid in clients_map.items() if uid == curr_cid), None)
        if found_name: default_idx = owner_options.index(found_name)
    
    eo = c4.selectbox("Владелец", owner_options, index=default_idx, key="edit_o")
    
    st.divider()
    
    # --- РАЗДЕЛ 2: ФИНАНСЫ ---
    st.caption("Финансы (Авто-пересчет)")

    # ИСПРАВЛЕНИЕ: Используем mod_detail, а не mod
    db_qty = int(mod_detail.get('quantity') or 1)
    db_tot_cost = float(mod_detail.get('cost') or 0.0)
    db_tot_price = float(mod_detail.get('price') or 0.0)
    
    # Вычисляем unit price для начального значения
    init_uc = db_tot_cost / db_qty if db_qty > 0 else 0.0
    init_up = db_tot_price / db_qty if db_qty > 0 else 0.0

    f1, f2, f3, f4, f5 = st.columns(5)
    # ВАЖНО: key обязателен
    eq = f1.number_input("Кол-во", min_value=1, value=db_qty, key="edit_q")
    e_unit_cost = f2.number_input("Себест. (ед)", 0.0, value=init_uc, step=10.0, key="edit_uc")
    e_unit_price = f3.number_input("Цена (ед)", 0.0, value=init_up, step=10.0, key="edit_up")
    
    # ПЕРЕСЧЕТ
    e_total_cost = e_unit_cost * eq
    e_total_price = e_unit_price * eq
    
    f4.metric("ИТОГО стоимость", f"{e_total_cost:.2f}")
    f5.metric("ИТОГО цена", f"{e_total_price:.2f}")

    st.divider()
    st.caption("Характеристики")
    ch1, ch2, ch3 = st.columns(3)
    e_size = ch1.text_input("Размер", value=mod_detail.get('size') or "", key="e_size")
    e_stiff = ch2.text_input("Жесткость", value=mod_detail.get('stiffness') or "", key="e_stiff")
    e_side = ch3.text_input("Сторона", value=mod_detail.get('side') or "", key="e_side")

    st.divider()
    # --- РАЗДЕЛ 3: СТАТУСЫ ---
    s1, s2, s3, s4 = st.columns(4)
    e_ord = s1.text_input("Заказано", value=mod_detail.get('ordered', '0'), key="edit_ord")
    e_recd = s2.text_input("Получено", value=mod_detail.get('recd', '0'), key="edit_recd")
    e_pend = s3.text_input("В ожидании", value=mod_detail.get('pending', '0'), key="edit_pend")
    e_pr_keep = s4.text_input("У протезиста", value=mod_detail.get('prosthetist_keep', '0') or "", key="e_pr_keep")

    d1, d2 = st.columns(2)
    e_acc = d1.text_input("Счет", value=mod_detail.get('order_date_acc_num', '-'), key="edit_acc")
    e_props = d2.text_input("Хар-ки", value=mod_detail.get('properties', '-'), key="edit_prop")
    
    e_notes = st.text_area("Заметки", value=mod_detail.get('notes') or "", key="edit_notes")
    
    # --- СОХРАНЕНИЕ (Обычная кнопка) ---
    if st.button("Сохранить изменения", type="primary"):
        cid_target = clients_map.get(eo)
        
        pl = {
            "module_name": en, "catalogue_index": ei, "supplier": es, "client_id": cid_target,
            "quantity": eq, 
            "cost": e_total_cost, # Сохраняем ИТОГ
            "price": e_total_price,
            "ordered": e_ord, "recd": e_recd, "pending": e_pend,
            "order_date_acc_num": e_acc, "properties": e_props, "notes": e_notes,
            "size": e_size,
            "stiffness": e_stiff,
            "side": e_side,
            "prosthetist_keep": e_pr_keep,
        }
        
        try:
            utils.patch_module(mid, pl)
            st.success("Обновлено!")
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка обновления: {e}")
            
    st.divider()
    if st.button("🗑️ Удалить модуль"):
        try:
            utils.delete_module(mid)
            st.success("Удалено")
            reset_wh()
        except Exception as e:
            st.error(f"Ошибка удаления: {e}")