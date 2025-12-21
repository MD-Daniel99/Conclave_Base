import streamlit as st
import pandas as pd
import sys
import os
import io
import time
from datetime import datetime, date, time as dt_time
import requests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import utils

MIN_DATE = date(1900, 1, 1)

# --- AUTH ---
if not st.session_state.get("token"):
    st.stop()

# --- STATE MANAGEMENT ---
if "cli_active_id" not in st.session_state:
    st.session_state.cli_active_id = None

# --- HELPERS ---
def reset_state():
    st.session_state.cli_active_id = None
    st.rerun()

def to_date(iso_str):
    """Конвертирует ISO строку (YYYY-MM-DD) в объект date для st.date_input"""
    if not iso_str: return None
    try: 
        return date.fromisoformat(str(iso_str)[:10])
    except: 
        return None

# Загрузка справочников
try:
    statuses = utils.fetch_statuses()
    stages = utils.fetch_stages()
    agents = utils.fetch_agents(limit=1000)
except:
    statuses, stages, agents = [], [], []

statuses_map = {s["status_code"]: s["description"] for s in statuses}
stages_map = {s["stage_code"]: s["description"] for s in stages}
agents_map = {f"{a['last_name']} {a['first_name']}": a['agent_id'] for a in agents}
statuses_map_rev = {v: k for k, v in statuses_map.items()}
stages_map_rev = {v: k for k, v in stages_map.items()}
agents_map_rev = {k: v for k, v in agents_map.items()}

# --- EXPORT FUNCTION (CACHED) ---
@st.cache_data(ttl=60)
def get_clients_csv():
    try:
        all_data = utils.fetch_clients(limit=100000)
        if not all_data: return None
        
        export_rows = []
        for c in all_data:
            aname = ""
            if c.get("agent"): aname = f"{c['agent']['last_name']} {c['agent']['first_name']}"
            
            export_rows.append({
                "Фамилия": c['last_name'],
                "Имя": c['first_name'],
                "Отчество": c['middle_name'],
                "Дата пробития": c.get('check_date'),
                "Вид протеза": c.get('prosthesis_type'),
                "Стоимость сертификата": c.get('certificate_price'),
                "Статус": statuses_map.get(c['status_code'], c['status_code']),
                "Этап": stages_map.get(c['current_stage'], c['current_stage']),
                "Агент": aname,
                "Повторное обращение": c['deadline'],
                "Заметки": c['notes'],
            })
        return pd.DataFrame(export_rows).to_csv(index=False).encode('utf-8-sig')
    except Exception as e:
        return None

# ... (функция get_clients_csv остается как была) ...

@st.cache_data(ttl=60)
def get_clients_excel():
    try:
        all_data = utils.fetch_clients(limit=100000)
        if not all_data: return None
        
        export_rows = []
        for c in all_data:
            aname = ""
            if c.get("agent"): aname = f"{c['agent']['last_name']} {c['agent']['first_name']}"
            
            export_rows.append({
                "Фамилия": c['last_name'],
                "Имя": c['first_name'],
                "Отчество": c['middle_name'],
                "Дата пробития": c.get('check_date'),
                "Вид протеза": c.get('prosthesis_type'),
                "Стоимость сертификата": c.get('certificate_price'),
                "Статус": statuses_map.get(c['status_code'], c['status_code']),
                "Этап": stages_map.get(c['current_stage'], c['current_stage']),
                "Агент": aname,
                "Повторное обращение": c['deadline'],
                "Заметки": c['notes'],
            })
        
        df = pd.DataFrame(export_rows)
        
        # Запись в буфер памяти вместо диска
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Clients')
        
        return buffer.getvalue()
    except Exception:
        return None

# ==========================================
# UI: LIST (Список клиентов)
# ==========================================
if st.session_state.cli_active_id is None:
    st.title("👥 Клиенты")

    # --- IMPORT / EXPORT SECTION ---
    with st.expander("📂 Импорт / Экспорт (CSV)"):
        tab_ex, tab_im = st.tabs(["Экспорт (Скачать)", "Импорт (Загрузить)"])
        
        with tab_ex:
            st.write("Выберите формат для скачивания:")
            col1, col2 = st.columns(2)
            
            # CSV
            with col1:
                csv_data = get_clients_csv()
                if csv_data:
                    st.download_button(
                        label="📥 Скачать CSV",
                        data=csv_data,
                        file_name=f"clients_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.warning("Нет данных (CSV)")
            
            # EXCEL
            with col2:
                excel_data = get_clients_excel()
                if excel_data:
                    st.download_button(
                        label="📥 Скачать Excel (.xlsx)",
                        data=excel_data,
                        file_name=f"clients_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                else:
                    st.warning("Нет данных (Excel)")

        # ИМПОРТ
        with tab_im:
            st.info("Загрузите CSV файл. Обязательные колонки: Фамилия, Имя, Агент (ФИО в точности как в базе), Статус, Этап.")
            
            # Генерация шаблона
            template_data = pd.DataFrame([
                {"Фамилия": "Иванов", "Имя": "Иван", "Отчество": "Иванович", 
                 "Агент": list(agents_map.keys())[0] if agents_map else "Фамилия Агента",
                 "Статус": list(statuses_map.values())[0] if statuses_map else "Новый",
                 "Этап": list(stages_map.values())[0] if stages_map else "Первичный контакт",
                 "Заметки": "Импорт"}
            ])
            csv_template = template_data.to_csv(index=False).encode('utf-8-sig')
            st.download_button("Скачать шаблон CSV", csv_template, "clients_template.csv", "text/csv")

            uploaded_file = st.file_uploader("Выбрать файл", type=["csv"])
            
            if uploaded_file is not None:
                if st.button("Начать загрузку"):
                    try:
                        df_im = pd.read_csv(uploaded_file)
                        progress_bar = st.progress(0)
                        success_count = 0
                        error_count = 0
                        errors_log = []

                        total = len(df_im)
                        for i, row in df_im.iterrows():
                            try:
                                # Маппинг значений
                                ag_name = str(row.get("Агент", "")).strip()
                                st_name = str(row.get("Статус", "")).strip()
                                sg_name = str(row.get("Этап", "")).strip()

                                # Поиск ID
                                ag_id = agents_map_rev.get(ag_name)
                                st_code = statuses_map_rev.get(st_name)
                                sg_code = stages_map_rev.get(sg_name)

                                # Если не нашли по имени, берем дефолт (первый попавшийся) или пропускаем
                                if not ag_id:
                                    raise ValueError(f"Агент '{ag_name}' не найден")
                                if not st_code: 
                                    st_code = st_name if st_name in statuses_map else list(statuses_map.keys())[0]
                                if not sg_code:
                                    sg_code = sg_name if sg_name in stages_map else list(stages_map.keys())[0]

                                pl = {
                                    "last_name": row.get("Фамилия"),
                                    "first_name": row.get("Имя"),
                                    "middle_name": row.get("Отчество") if pd.notna(row.get("Отчество")) else None,
                                    "status_code": st_code,
                                    "current_stage": sg_code,
                                    "agent_id": ag_id,
                                    "notes": row.get("Заметки") if pd.notna(row.get("Заметки")) else None
                                }
                                
                                utils.create_client(pl)
                                success_count += 1
                            
                            except Exception as e:
                                error_count += 1
                                errors_log.append(f"Строка {i+1}: {e}")
                            
                            progress_bar.progress((i + 1) / total)

                        st.success(f"Завершено! Добавлено: {success_count}, Ошибок: {error_count}")
                        if errors_log:
                            with st.expander("Показать ошибки"):
                                for err in errors_log: st.write(err)
                        
                        time.sleep(2)
                        utils.clear_caches()
                        st.rerun()

                    except Exception as e:
                        st.error(f"Ошибка чтения файла: {e}")

    # 1. ФИЛЬТРЫ
    with st.expander("🔍 Фильтры и поиск", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        q = c1.text_input("Поиск (ФИО)")
        st_filter = c2.selectbox("Статус", ["(Все)"] + list(statuses_map.keys()), format_func=lambda x: statuses_map.get(x, x))
        sg_filter = c3.selectbox("Этап", ["(Все)"] + list(stages_map.keys()), format_func=lambda x: stages_map.get(x, x))
        ag_filter = c4.selectbox("Агент", ["(Все)"] + list(agents_map.keys()))
        
        c5, c6 = st.columns([1, 5])
        limit = c5.number_input("На стр.", 5, 200, 20)
        page = c6.number_input("Страница", 1, 100, 1)
        skip = (page - 1) * limit

    # 2. ТАБЛИЦА
    real_st = st_filter if st_filter != "(Все)" else None
    real_sg = sg_filter if sg_filter != "(Все)" else None
    real_ag = agents_map.get(ag_filter) if ag_filter != "(Все)" else None

    try:
        clients = utils.fetch_clients(skip, limit, q, real_st, real_ag, real_sg)
    except Exception as e:
        st.error(f"Ошибка сервера: {e}")
        clients = []

    if clients:
        rows = []
        for c in clients:
            agent_name = "-"
            if c.get("agent"): 
                agent_name = f"{c['agent']['last_name']} {c['agent']['first_name']}"
            
            created_dt = c.get("created_at")[:10] if c.get("created_at") else "-"
            updated_dt = c.get("updated_at")[:10] if c.get("updated_at") else "-"
            deadline_dt = c.get("deadline")[:10] if c.get("deadline") else "-"
            check_dt = c.get("check_date") if c.get("check_date") else "-"
            cert_price = c.get("certificate_price") if c.get("certificate_price") is not None else "-"
            
            rows.append({
                "ID": c["client_id"],
                "ФИО": f"{c['last_name']} {c['first_name']} {c['middle_name'] or ''}",
                "Вид протеза": c.get("prosthesis_type") or "-",
                "Дата пробития": check_dt,                     
                "Стоимость серт.": cert_price,
                "Статус": statuses_map.get(c["status_code"], c["status_code"]),
                "Этап": stages_map.get(c["current_stage"], c["current_stage"]),
                "Агент": agent_name,
                "Повторное обращение": deadline_dt,
                "Создан": created_dt,       
                "Обновлен": updated_dt
            })
        
        df = pd.DataFrame(rows)

        df.insert(0, "№", range(skip + 1, skip + len(df) + 1))
        
        event = st.dataframe(
            df, 
            use_container_width=True, 
            hide_index=True, 
            selection_mode="single-row", 
            on_select="rerun",
            column_config={
                "ID": None, 
                "№": st.column_config.NumberColumn("№", width="small")
            }
        )
        
        if event.selection.rows:
            idx = event.selection.rows[0]
            st.session_state.cli_active_id = df.iloc[idx]["ID"]
            st.rerun()
    else:
        st.info("Клиенты не найдены.")

    st.divider()
    with st.expander("➕ Создать нового клиента"):
        with st.form("new_client_form"):
            c1, c2 = st.columns(2)
            nl = c1.text_input("Фамилия *")
            nf = c1.text_input("Имя *")
            nm = c1.text_input("Отчество")
            
            nst = c2.selectbox("Статус *", list(statuses_map.keys()), format_func=lambda x: statuses_map.get(x))
            nsg = c2.selectbox("Этап *", list(stages_map.keys()), format_func=lambda x: stages_map.get(x))
            nag = c2.selectbox("Агент *", list(agents_map.keys()))
            st.divider()
            st.subheader("Сертификат и вид протеза")
            d1, d2, d3 = st.columns(3)
            n_prosthesis = d1.text_area("Виды протезов (каждый с новой строки)", height=100)
            n_check_date = d2.date_input("Дата пробития", value=None)
            n_price = d3.number_input("Стоимость сертификата", min_value=0.0, step=1.0, format="%.2f")
            ndead = st.date_input("Повторное обращение", value=None)
            nnotes = st.text_area("Заметки", key="new_client_notes")
            
            if st.form_submit_button("Создать"):
                if nl and nf and nag:
                    pl = {
                        "last_name": nl, "first_name": nf, "middle_name": nm,
                        "prosthesis_type": n_prosthesis,
                        "check_date": n_check_date.isoformat() if n_check_date else None,
                        "certificate_price": n_price,
                        "status_code": nst, "current_stage": nsg,
                        "agent_id": agents_map[nag],
                        "deadline": datetime.combine(ndead, dt_time.min).isoformat() if ndead else None,
                        "notes": nnotes
                    }
                    try:
                        utils.create_client(pl)
                        st.success("Создан!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
                else:
                    st.warning("Заполните обязательные поля")

# ==========================================
# UI: EDIT MODE (Карточка клиента)
# ==========================================
# ==========================================

else:
    cid = st.session_state.cli_active_id

    if st.button("⬅️ Вернуться к списку"):
        reset_state()

    try:
        detail = utils.fetch_client_detail(cid)
    except:
        st.error("Не удалось загрузить данные клиента")
        if st.button("Сброс"): reset_state()
        st.stop()

    st.header(f"👤 {detail['last_name']} {detail['first_name']}")

    # ---------- TAB CONTROL (с сохранением в session_state) ----------
    TAB_NAMES = ["✏️ Редактирование", "📄 Документы", "👤 Личные данные", "📦 Модули", "📎 Файлы"]
    if "cli_active_tab" not in st.session_state:
        # по умолчанию открываем Модули (или 0 если хотите Редактирование)
        st.session_state.cli_active_tab = 3

    # радиопереключатель сохраняет выбор между rerun'ами
    sel = st.radio("Client menu", TAB_NAMES, index=st.session_state.cli_active_tab, horizontal=True, key=f"client_tab_radio_{cid}", label_visibility="collapsed")
    st.session_state.cli_active_tab = TAB_NAMES.index(sel)

    # --- TAB 1: ОСНОВНОЕ ---
    if sel == "✏️ Редактирование":
        with st.form("edit_main"):
            c1, c2 = st.columns(2)
            el = c1.text_input("Фамилия", detail['last_name'])
            ef = c1.text_input("Имя", detail['first_name'])
            em = c1.text_input("Отчество", detail['middle_name'])

            idx_st = list(statuses_map.keys()).index(detail['status_code']) if detail['status_code'] in statuses_map else 0
            est = c2.selectbox("Статус", list(statuses_map.keys()), index=idx_st, format_func=lambda x: statuses_map.get(x))

            idx_sg = list(stages_map.keys()).index(detail['current_stage']) if detail['current_stage'] in stages_map else 0
            esg = c2.selectbox("Этап", list(stages_map.keys()), index=idx_sg, format_func=lambda x: stages_map.get(x))

            st.divider()
            st.caption("Данные протезирования")

            pd1, pd2, pd3 = st.columns(3)
            e_prosthesis = pd1.text_area("Виды протезов", value=detail.get('prosthesis_type') or "", height=100)
            e_check_date = pd2.date_input("Дата пробития", value=to_date(detail.get('check_date')))

            curr_price = detail.get('certificate_price') or 0.0
            e_price = pd3.number_input("Стоимость сертификата", min_value=0.0, value=float(curr_price), step=1.0, format="%.2f")

            st.divider()

            cur_ag_id = detail['agent_id']
            ag_name = next((k for k, v in agents_map.items() if v == cur_ag_id), list(agents_map.keys())[0])
            idx_ag = list(agents_map.keys()).index(ag_name)
            eag = c2.selectbox("Агент", list(agents_map.keys()), index=idx_ag)

            c3, c4 = st.columns(2)
            edead = c3.date_input("Повторное обращение", value=to_date(detail.get('deadline')))
            enotes = st.text_area("Заметки", detail['notes'])

            if st.form_submit_button("Сохранить изменения"):
                pl = {
                    "last_name": el, "first_name": ef, "middle_name": em,
                    "prosthesis_type": e_prosthesis,
                    "check_date": e_check_date.isoformat() if e_check_date else None,
                    "certificate_price": e_price,
                    "status_code": est, "current_stage": esg,
                    "agent_id": agents_map[eag],
                    "deadline": datetime.combine(edead, dt_time.min).isoformat() if edead else None,
                    "notes": enotes
                }
                utils.patch_client(cid, pl)
                st.success("Сохранено")
                utils.clear_caches()
                #del st.session_state["cli_active_id"]
                st.rerun()

        if st.button("Удалить клиента", type="primary"):
            utils.delete_client(cid)
            reset_state()

    # --- TAB 2: ДОКУМЕНТЫ ---
    elif sel == "📄 Документы":
        # ПАСПОРТА
        st.subheader("Паспорта")
        for p in detail.get("passports", []):
            with st.expander(f"📘 {p.get('series_number', 'Без номера')} — {p.get('full_name', '')}"):
                with st.form(key=f"edit_pass_{p['passport_id']}"):
                    pc1, pc2 = st.columns(2)
                    e_p_sn = pc1.text_input("Серия/Номер", value=p.get('series_number'))
                    e_p_fn = pc2.text_input("ФИО", value=p.get('full_name'))

                    pc3, pc4 = st.columns(2)
                    e_p_by = pc3.text_input("Кем выдан", value=p.get('issued_by'))
                    e_p_code = pc4.text_input("Код подразделения", value=p.get('department_code'))

                    pc5, pc6 = st.columns(2)
                    e_p_date = pc5.date_input("Дата выдачи", value=to_date(p.get('issue_date')), min_value=MIN_DATE)
                    #e_p_exp = pc6.date_input("Действителен до", value=to_date(p.get('expiry_date')))

                    st.divider()
                    pc7, pc8 = st.columns(2)
                    e_p_bp = pc7.text_input("Место рождения", value=p.get('birth_place'))
                    e_p_bd = pc8.date_input("Дата рождения", value=to_date(p.get('birth_date')), min_value=MIN_DATE)
                    e_p_addr = st.text_area("Адрес прописки", value=p.get('registration_address'))

                    col_save, col_del = st.columns([1, 1])
                    if col_save.form_submit_button("💾 Сохранить паспорт", use_container_width=True):
                        pl = {
                            "full_name": e_p_fn, "series_number": e_p_sn, "issued_by": e_p_by, "department_code": e_p_code,
                            "issue_date": e_p_date.isoformat() if e_p_date else None,
                            #"expiry_date": e_p_exp.isoformat() if e_p_exp else None,
                            "birth_place": e_p_bp, "birth_date": e_p_bd.isoformat() if e_p_bd else None,
                            "registration_address": e_p_addr
                        }
                        try:
                            utils.patch_passport(p['passport_id'], pl)
                            st.success("Паспорт обновлен!")
                            st.rerun()
                        except Exception as e: st.error(f"Ошибка: {e}")

                if st.button("🗑️ Удалить этот паспорт", key=f"del_p_{p['passport_id']}"):
                    utils.delete_passport(p['passport_id'])
                    st.rerun()

        # ДОБАВЛЕНИЕ ПАСПОРТА
        with st.popover("➕ Добавить новый паспорт"):
            with st.form("new_pass"):
                st.write("Заполните данные паспорта")
                n_sn = st.text_input("Серия/Номер *")
                n_fn = st.text_input("ФИО *")
                n_bd = st.date_input("Дата рождения", value=None, min_value=MIN_DATE)
                n_by = st.text_input("Кем выдан")
                n_code = st.text_input("Код подразделения", max_chars=7, help="Формат 000-000")
                n_dt = st.date_input("Дата выдачи *", value=None, min_value=MIN_DATE)
                n_bp = st.text_input("Место рождения")
                n_addr = st.text_area("Прописка")

                if st.form_submit_button("Добавить"):
                    if n_sn and n_fn and n_dt:
                        pl = {
                            "full_name": n_fn, 
                            "series_number": n_sn,
                            "issued_by": n_by, 
                            "issue_date": n_dt.isoformat(),
                            "registration_address": n_addr, 
                            "birth_place": n_bp,
                            "department_code": n_code, 
                            #"expiry_date": None
                            "birth_date": n_bd.isoformat() if n_bd else None
                        }
                        try:
                            utils.post_passport(cid, pl)
                            st.success("Добавлено")
                            st.rerun()
                        except Exception as e: st.error(f"{e}")
                    else:
                        st.warning("Заполните обязательные поля (*)")

        st.divider()

        c_snils, c_ipra = st.columns(2)

        # --- ЛЕВАЯ КОЛОНКА: СНИЛС ---
        with c_snils:
            st.subheader("СНИЛС")
            for s in detail.get("snils", []):
                with st.expander(f"📗 {s.get('number')}"):
                    with st.form(key=f"edit_snils_{s['snils_id']}"):
                        e_s_num = st.text_input("Номер", value=s['number'])
                        e_s_dt = st.date_input("Дата выдачи", value=to_date(s.get('issued_date')), min_value=MIN_DATE)
                        
                        if st.form_submit_button("Сохранить"):
                            pl = {"number": e_s_num, "issued_date": e_s_dt.isoformat() if e_s_dt else None}
                            utils.patch_snils(s['snils_id'], pl)
                            st.success("Обновлено")
                            st.rerun()
                    
                    if st.button("Удалить СНИЛС", key=f"del_s_{s['snils_id']}"):
                        utils.delete_snils(s['snils_id'])
                        st.rerun()

            with st.popover("➕ Добавить СНИЛС"):
                with st.form("new_snils"):
                    s_num = st.text_input("Номер")
                    s_dt = st.date_input("Дата выдачи", value=None, min_value=MIN_DATE)
                    
                    if st.form_submit_button("Сохранить"):
                        if s_num:
                            utils.post_snils(cid, {"number": s_num, "issued_date": s_dt.isoformat() if s_dt else None})
                            st.rerun()
                        else:
                            st.warning("Введите номер")

        # --- ПРАВАЯ КОЛОНКА: ИПРА ---
        with c_ipra:
            st.subheader("ИПРА")
            # Получаем текущее значение из объекта клиента
            current_ipra = detail.get("ipra_code") or ""
            
            with st.form("edit_ipra_form"):
                new_ipra = st.text_input("Номер ИПРА", value=current_ipra)
                
                if st.form_submit_button("Сохранить ИПРА"):
                    # ИПРА - это поле самого клиента, поэтому обновляем через patch_client
                    utils.patch_client(cid, {"ipra_code": new_ipra})
                    st.success("Сохранено!")
                    utils.clear_caches()
                    st.rerun()

    # --- TAB 3: ТЕЛЕФОНЫ ---
    # --- TAB 3: ЛИЧНЫЕ ДАННЫЕ (ТЕЛЕФОНЫ И АДРЕС) ---
    elif sel == "👤 Личные данные":
        
        col_phones, col_addr = st.columns([1, 1])

        # ЛЕВАЯ КОЛОНКА: ТЕЛЕФОНЫ
        with col_phones:
            st.subheader("Телефоны")
            
            # Список существующих телефонов
            for ph in detail.get("phones", []):
                # Форма для каждого телефона
                with st.form(key=f"edit_ph_{ph['phone_id']}"):
                    # Поле ввода
                    new_num = st.text_input("Номер", value=ph['number'], label_visibility="collapsed")
                    
                    # Кнопки в ряд (КАК ВЫ ПРОСИЛИ)
                    c_save, c_del = st.columns(2)
                    
                    # Кнопка Сохранить
                    if c_save.form_submit_button("💾 Сохранить", use_container_width=True):
                        utils.patch_phone(ph['phone_id'], {"number": new_num})
                        st.success("OK")
                        st.rerun()
                    
                    # Кнопка Удалить (Теперь внутри формы и красная)
                    if c_del.form_submit_button("🗑️ Удалить", type="primary", use_container_width=True):
                        utils.delete_phone(ph['phone_id'])
                        st.rerun()
            
            # Добавление нового телефона
            st.write("---")
            with st.form("new_phone"):
                st.caption("Добавить новый номер")
                pn = st.text_input("Номер")
                if st.form_submit_button("Добавить", use_container_width=True):
                    if pn:
                        utils.add_phone(cid, pn)
                        st.rerun()
                    else:
                        st.warning("Введите номер")

        # ПРАВАЯ КОЛОНКА: МЕСТО ЖИТЕЛЬСТВА
        with col_addr:
            st.subheader("Место жительства")
            
            # Получаем текущее значение
            # (Если после применения патча БД и рестарта сервера не работает - проверьте schemas.py еще раз)
            current_addr = detail.get("place_of_residence") or ""
            
            with st.form("edit_address_form"):
                new_addr = st.text_area("Адрес", value=current_addr, height=150, help="Фактический адрес проживания")
                
                # Кнопки в одну строку
                c_save, c_del = st.columns(2)
                
                # Кнопка сохранения
                if c_save.form_submit_button("💾 Сохранить", use_container_width=True):
                    utils.patch_client(cid, {"place_of_residence": new_addr})
                    st.success("Сохранено!")
                    utils.clear_caches()
                    st.rerun()
                
                # Кнопка удаления (Очистки)
                if c_del.form_submit_button("🗑️ Удалить адрес", type="primary", use_container_width=True):
                    utils.patch_client(cid, {"place_of_residence": None})
                    st.success("Удалено!")
                    utils.clear_caches()
                    st.rerun()

    # --- TAB 4: МОДУЛИ (Синхронизировано со Складом) ---
    elif sel == "📦 Модули":
        st.info("Модули, созданные или измененные здесь, автоматически синхронизируются со Складом.")

        # 1. СПИСОК СУЩЕСТВУЮЩИХ МОДУЛЕЙ
        # СОРТИРОВКА — важно для детерминированности виджет-дерева
        modules = sorted(detail.get("modules", []) or [], key=lambda m: m['module_id'])
        if modules:
            for m in modules:
                mid = m['module_id']
                # Заголовок экспандера
                label = f"📦 {m['module_name']}"
                if m.get('catalogue_index'): label += f" ({m['catalogue_index']})"

                with st.expander(label):
                    # --- БЕЗ ST.FORM (Для авто-пересчета) ---

                    # 1. ОСНОВНОЕ
                    st.caption("Основные данные")
                    c1, c2, c3 = st.columns(3)
                    mn = c1.text_input("Название", value=m['module_name'], key=f"nm_{mid}")
                    mi = c2.text_input("Индекс в каталоге", value=m['catalogue_index'], key=f"idx_{mid}")
                    tsr = c3.text_input("Код и название ТСР", value = m['tsr_code'], key = f"tsr_{mid}")

                    c3, c4 = st.columns(2)
                    ms = c3.text_input("Поставщик", value=m['supplier'], key=f"sup_{mid}")
                    c4.text_input("Владелец", value="Текущий клиент", disabled=True, key=f"own_{mid}")

                    st.divider()

                    # 2. ФИНАНСЫ (С ПЕРЕСЧЕТОМ)
                    st.caption("Финансы (Авто-пересчет)")

                    db_qty = int(m.get('quantity') or 1)
                    db_cost = float(m.get('cost') or 0.0)
                    db_price = float(m.get('price') or 0.0)

                    init_uc = db_cost / db_qty if db_qty > 0 else 0.0
                    init_up = db_price / db_qty if db_qty > 0 else 0.0

                    f1, f2, f3, f4, f5 = st.columns(5)

                    mq = f1.number_input("Кол-во", min_value=1, value=db_qty, key=f"qty_{mid}")
                    mc_unit = f2.number_input("Себест. (ед)", min_value=0.0, value=init_uc, step=10.0, key=f"uc_{mid}")
                    mp_unit = f3.number_input("Цена (ед)", min_value=0.0, value=init_up, step=10.0, key=f"up_{mid}")

                    m_total_cost = mc_unit * mq
                    m_total_price = mp_unit * mq

                    f4.metric("ИТОГО Cost", f"{m_total_cost:.2f}")
                    f5.metric("ИТОГО Price", f"{m_total_price:.2f}")

                    st.divider()

                    # 3. ХАРАКТЕРИСТИКИ (НОВОЕ)
                    st.caption("Характеристики")
                    h1, h2, h3 = st.columns(3)
                    m_size = h1.text_input("Размер", value=m.get('size') or "", key=f"sz_{mid}")
                    m_stiff = h2.text_input("Жесткость", value=m.get('stiffness') or "", key=f"st_{mid}")
                    m_side = h3.text_input("Сторона", value=m.get('side') or "", key=f"sd_{mid}")

                    st.divider()

                    # 4. СТАТУСЫ И ДЕТАЛИ
                    st.caption("Статусы и Детали")
                    s1, s2, s3 = st.columns(3)
                    m_ord = s1.text_input("Ordered", value=m.get('ordered', '0'), key=f"ord_{mid}")
                    m_recd = s2.text_input("Recd", value=m.get('recd', '0'), key=f"rcd_{mid}")
                    m_pend = s3.text_input("Pending", value=m.get('pending', '0'), key=f"pnd_{mid}")

                    d1, d2 = st.columns(2)
                    m_acc = d1.text_input("Номер счёта и дата заказа", value=m.get('order_date_acc_num', '-'), key=f"acc_{mid}")
                    m_prop = d2.text_input("Доп. св-ва", value=m.get('properties', '-'), key=f"prp_{mid}")

                    m_notes = st.text_area("Заметки", value=m.get('notes') or "", key=f"nts_{mid}")

                    # КНОПКИ
                    col_save, col_del = st.columns([1, 4])

                    if col_save.button("💾", key=f"save_{mid}", help="Сохранить изменения"):
                        pl = {
                            "module_name": mn, "catalogue_index": mi, "supplier": ms,
                            "quantity": mq,
                            "cost": m_total_cost,   # ИТОГ
                            "price": m_total_price, # ИТОГ
                            "ordered": m_ord, "recd": m_recd, "pending": m_pend,
                            "order_date_acc_num": m_acc, "properties": m_prop, "notes": m_notes,
                            # Новые поля
                            "size": m_size, "stiffness": m_stiff, "side": m_side,
                            "tsr_code": tsr,
                        }
                        try:
                            utils.patch_module(mid, pl)
                            st.success("ОК")
                            st.rerun()
                        except Exception as e: st.error(f"Ошибка: {e}")

                    if col_del.button("🗑️ Удалить", key=f"del_{mid}"):
                        utils.delete_module(mid)
                        st.rerun()
        else:
            st.write("Нет привязанных модулей.")

        st.divider()

        # 2. СОЗДАНИЕ НОВОГО МОДУЛЯ
        with st.expander("➕ Создать модуль для этого клиента", expanded=False):

            st.caption("Основные данные")
            c1, c2, c3 = st.columns(3)
            nn = c1.text_input("Название *", key=f"new_cl_mn_{cid}")
            create_tsr = c3.text_input("Код и название ТСР", key=f"new_cl_tsr_{cid}")
            ni = c2.text_input("Индекс в каталоге*", key=f"new_cl_mi_{cid}")

            c3, c4 = st.columns(2)
            ns = c3.text_input("Поставщик *", key=f"new_cl_ms_{cid}")
            c4.text_input("Владелец", value="Текущий клиент", disabled=True, key=f"new_cl_own_{cid}")

            st.divider()

            st.caption("Финансы (Авто-пересчет)")
            f1, f2, f3, f4, f5 = st.columns(5)
            nq = f1.number_input("Кол-во", min_value=1, value=1, key=f"new_cl_qty_{cid}")
            nuc = f2.number_input("Себест. (ед)", 0.0, step=10.0, key=f"new_cl_uc_{cid}")
            nup = f3.number_input("Цена (ед)", 0.0, step=10.0, key=f"new_cl_up_{cid}")

            n_total_cost = nuc * nq
            n_total_price = nup * nq

            f4.metric("ИТОГО Cost", f"{n_total_cost:.2f}")
            f5.metric("ИТОГО Price", f"{n_total_price:.2f}")

            st.divider()
            st.caption("Характеристики")
            h1, h2, h3 = st.columns(3)
            n_size = h1.text_input("Размер", key=f"new_cl_sz_{cid}")
            n_stiff = h2.text_input("Жесткость", key=f"new_cl_st_{cid}")
            n_side = h3.text_input("Сторона", key=f"new_cl_sd_{cid}")

            st.divider()
            st.caption("Статусы")
            s1, s2, s3 = st.columns(3)
            no = s1.text_input("Ordered", "0", key=f"new_cl_ord_{cid}")
            nr = s2.text_input("Recd", "0", key=f"new_cl_rcd_{cid}")
            npe = s3.text_input("Pending", "0", key=f"new_cl_pend_{cid}")

            d1, d2 = st.columns(2)
            na = d1.text_input("Номер счёта и дата заказа", "-", key=f"new_cl_acc_{cid}")
            npr = d2.text_input("Доп. св-ва", "-", key=f"new_cl_prop_{cid}")

            n_notes = st.text_area("Заметки", key=f"new_cl_nts_{cid}")

            if st.button("Создать модуль", type="primary", key=f"btn_create_cl_mod_{cid}"):
                if nn and ni and ns:
                    pl = {
                        "module_name": nn, "catalogue_index": ni, "supplier": ns,
                        "client_id": cid, # Привязка
                        "quantity": nq, "cost": n_total_cost, "price": n_total_price,
                        "ordered": no, "recd": nr, "pending": npe,
                        "order_date_acc_num": na, "properties": npr, "notes": n_notes,
                        "size": n_size, "stiffness": n_stiff, "side": n_side,
                        "tsr_code": create_tsr,
                    }
                    try:
                        utils.create_module(pl)
                        st.success("Модуль создан!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка создания: {e}")
                else:
                    st.warning("Заполните поля со *")

    # --- TAB 5: ФАЙЛЫ ---
    elif sel == "📎 Файлы":
        st.info("Здесь хранятся сканы документов, фото и PDF.")

        with st.expander("📝 Генерация договора", expanded=False):
            st.write("Автоматическое создание договора по шаблону на основе данных клиента и модулей.")
            
            with st.form("contract_gen_form"):
                gc1, gc2 = st.columns(2)
                c_num = gc1.text_input("Номер договора", value=f"{datetime.now().strftime('%y-%m')}/01")
                c_date = gc2.date_input("Дата договора", value=datetime.now())
                
                gc3, gc4 = st.columns(2)
                p_date = gc3.date_input("Дата Плана/Акта", value=datetime.now())
                #l_type = gc4.selectbox("Тип конечности", ["нижних конечностей", "верхних конечностей"])
                
                # Кнопка подтверждения внутри формы
                if st.form_submit_button("🚀 Сформировать договор", type="primary"):
                    if c_num:
                        payload = {
                            "contract_number": c_num,
                            "contract_date": c_date.isoformat(),
                            "plan_date": p_date.isoformat(),
                            #"limb_type": l_type
                        }
                        try:
                            utils.generate_contract(cid, payload)
                            st.success("Договор успешно создан и добавлен в список файлов!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка генерации: {e}")
                    else:
                        st.warning("Укажите номер договора")

        st.divider()

        # 1. Загрузка
        with st.form("upload_form", clear_on_submit=True):
            uploaded_file = st.file_uploader("Выберите файл (PDF, JPG, PNG)", type=["pdf", "png", "jpg", "jpeg"])
            if st.form_submit_button("Загрузить на сервер"):
                if uploaded_file:
                    try:
                        utils.upload_client_file(cid, uploaded_file)
                        st.success("Файл загружен!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка загрузки: {e}")
                else:
                    st.warning("Файл не выбран")

        st.divider()

        # 2. Список файлов
        try:
            files = utils.fetch_client_files(cid)
        except:
            files = []

        if files:
            for f in files:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 2, 1])

                    # Иконка по типу
                    icon = "📄"
                    if "pdf" in f['content_type']: icon = "📕"
                    elif "image" in f['content_type']: icon = "🖼️"

                    c1.write(f"**{icon} {f['filename']}**")
                    c1.caption(f"Загружено: {f['created_at'][:10]} | Размер: {f['size'] // 1024} KB")

                    try:
                        # Запрашиваем файл
                        url = utils.get_download_url(f['document_id'])
                        r = requests.get(url, headers=utils.get_headers())

                        if r.status_code == 200:
                            c2.download_button(
                                "⬇️ Скачать",
                                data=r.content,
                                file_name=f['filename'],
                                key=f"dl_{f['document_id']}"
                            )
                        else:
                            c2.error(f"Err {r.status_code}")
                    except Exception as e:
                        c2.error(f"Ex: {e}")

                    if c3.button("🗑️", key=f"rm_file_{f['document_id']}"):
                        utils.delete_file(f['document_id'])
                        st.rerun()
        else:
            st.write("Файлов пока нет.")
