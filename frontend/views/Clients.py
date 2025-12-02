import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime, time, date
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
    try: return date.fromisoformat(iso_str)
    except: return None

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

# ==========================================
# UI: LIST (Список клиентов)
# ==========================================
if st.session_state.cli_active_id is None:
    st.title("👥 Клиенты")

    # --- IMPORT / EXPORT SECTION ---
    with st.expander("📂 Импорт / Экспорт (CSV)"):
        tab_ex, tab_im = st.tabs(["Экспорт (Скачать)", "Импорт (Загрузить)"])
        
        # ЭКСПОРТ (ТЕПЕРЬ ОДНА КНОПКА)
        with tab_ex:
            csv_data = get_clients_csv()
            if csv_data:
                st.download_button(
                    label="📥 Скачать всех клиентов (CSV)",
                    data=csv_data,
                    file_name=f"clients_export_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("Нет данных для экспорта или ошибка соединения.")

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
        
        event = st.dataframe(
            df, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun"
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
            n_prosthesis = d1.text_input("Вид протеза")
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
                        "deadline": datetime.combine(ndead, time.min).isoformat() if ndead else None,
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

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["✏️ Редактирование", "📄 Документы", "📞 Телефоны", "📦 Модули", "📎 Файлы"])

    # --- TAB 1: ОСНОВНОЕ ---
    with tab1:
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
            e_prosthesis = pd1.text_input("Вид протеза", value=detail.get('prosthesis_type') or "")
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
                    "deadline": datetime.combine(edead, time.min).isoformat() if edead else None,
                    "notes": enotes
                }
                utils.patch_client(cid, pl)
                st.success("Сохранено")
                utils.clear_caches()
                del st.session_state["cli_active_id"]
                st.rerun()
        
        if st.button("Удалить клиента", type="primary"):
            utils.delete_client(cid)
            reset_state()

    # --- TAB 2: ДОКУМЕНТЫ ---
    with tab2:
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
                    e_p_exp = pc6.date_input("Действителен до", value=to_date(p.get('expiry_date')))
                    
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
                            "expiry_date": e_p_exp.isoformat() if e_p_exp else None,
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
                n_by = st.text_input("Кем выдан")
                n_dt = st.date_input("Дата выдачи *", value=None, min_value=MIN_DATE)
                n_bp = st.text_input("Место рождения")
                n_addr = st.text_area("Прописка")
                
                if st.form_submit_button("Добавить"):
                    if n_sn and n_fn and n_dt:
                        pl = {
                            "full_name": n_fn, "series_number": n_sn, 
                            "issued_by": n_by, "issue_date": n_dt.isoformat(), 
                            "registration_address": n_addr, "birth_place": n_bp,
                            "department_code": None, "expiry_date": None
                        }
                        try:
                            utils.post_passport(cid, pl)
                            st.success("Добавлено")
                            st.rerun()
                        except Exception as e: st.error(f"{e}")
                    else:
                        st.warning("Заполните обязательные поля (*)")

        st.divider()
        
        # СНИЛС
        st.subheader("СНИЛС")
        for s in detail.get("snils", []):
            with st.expander(f"📗 СНИЛС: {s.get('number')}"):
                with st.form(key=f"edit_snils_{s['snils_id']}"):
                    c1, c2 = st.columns(2)
                    e_s_num = c1.text_input("Номер", value=s['number'])
                    e_s_dt = c2.date_input("Дата выдачи", value=to_date(s.get('issued_date')), min_value=MIN_DATE)
                    
                    if st.form_submit_button("Сохранить СНИЛС"):
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
                        d_val = s_dt.isoformat() if s_dt else None
                        utils.post_snils(cid, {"number": s_num, "issued_date": d_val})
                        st.rerun()
                    else:
                        st.warning("Введите номер")

    # --- TAB 3: ТЕЛЕФОНЫ ---
    with tab3:
        st.subheader("Телефоны")
        for ph in detail.get("phones", []):
            with st.form(key=f"edit_ph_{ph['phone_id']}"):
                c1, c2, c3 = st.columns([3, 1, 1])
                new_num = c1.text_input("Номер", value=ph['number'], label_visibility="collapsed")
                
                if c2.form_submit_button("💾"):
                    utils.patch_phone(ph['phone_id'], {"number": new_num})
                    st.success("OK")
                    st.rerun()
                
            if st.button("Удалить", key=f"del_ph_{ph['phone_id']}"):
                utils.delete_phone(ph['phone_id'])
                st.rerun()
        
        st.write("---")
        with st.form("new_phone"):
            st.write("Новый телефон")
            pn = st.text_input("Номер")
            if st.form_submit_button("Добавить"):
                utils.add_phone(cid, pn)
                st.rerun()

    # --- TAB 4: МОДУЛИ (ПОЛНЫЙ ИНТЕРФЕЙС КАК НА СКЛАДЕ) ---
    with tab4:
        st.info("Модули, созданные или измененные здесь, автоматически синхронизируются со Складом.")
        
        # 1. СПИСОК СУЩЕСТВУЮЩИХ МОДУЛЕЙ
        if detail.get("modules"):
            for m in detail["modules"]:
                with st.expander(f"📦 {m['module_name']} ({m['catalogue_index']})"):
                    with st.form(f"edit_mod_{m['module_id']}"):
                        st.caption("Основные данные")
                        c1, c2 = st.columns(2)
                        mn = c1.text_input("Название", value=m['module_name'])
                        mi = c2.text_input("Индекс в каталоге", value=m['catalogue_index'])
                        
                        c3, c4 = st.columns(2)
                        ms = c3.text_input("Поставщик", value=m['supplier'])
                        # Владелец тут фиксирован (текущий клиент), но можно отобразить
                        c4.text_input("Владелец", value=f"{detail['last_name']} {detail['first_name']}", disabled=True)

                        st.divider()
                        st.caption("Финансы и Количество")
                        f1, f2, f3 = st.columns(3)
                        mq = f1.number_input("Количество (шт)", min_value=0, value=int(m.get('quantity') or 1), step=1)
                        mc = f2.number_input("Себестоимость", min_value=0.0, value=float(m.get('cost') or 0.0), step=10.0)
                        mp = f3.number_input("Цена", min_value=0.0, value=float(m.get('price') or 0.0), step=10.0)

                        st.divider()
                        st.caption("Статусы и Детали")
                        s1, s2, s3 = st.columns(3)
                        m_ord = s1.text_input("Заказано (Ordered)", value=m.get('ordered', '0'))
                        m_recd = s2.text_input("Получено (Recd)", value=m.get('recd', '0'))
                        m_pend = s3.text_input("Ожидается (Pending)", value=m.get('pending', '0'))

                        d1, d2 = st.columns(2)
                        m_acc = d1.text_input("№ Счета / Дата заказа", value=m.get('order_date_acc_num', '-'))
                        m_prop = d2.text_input("Характеристики", value=m.get('properties', '-'))
                        
                        m_notes = st.text_area("Заметки", value=m.get('notes') or "")
                        
                        if st.form_submit_button("Сохранить изменения модуля"):
                            pl = {
                                "module_name": mn, "catalogue_index": mi, "supplier": ms,
                                "quantity": mq, "cost": mc, "price": mp,
                                "ordered": m_ord, "recd": m_recd, "pending": m_pend,
                                "order_date_acc_num": m_acc, "properties": m_prop,
                                "notes": m_notes
                            }
                            utils.patch_module(m['module_id'], pl)
                            st.success("Обновлено!")
                            st.rerun()
                    
                    if st.button("Удалить модуль", key=f"del_mod_{m['module_id']}"):
                        utils.delete_module(m['module_id'])
                        st.rerun()
        else:
            st.write("Нет модулей.")

        st.divider()
        
        # 2. СОЗДАНИЕ НОВОГО МОДУЛЯ
        with st.expander("➕ Создать модуль для этого клиента", expanded=False):
            with st.form("add_client_mod_full"):
                st.subheader("Новый модуль")
                
                st.caption("Основные данные")
                c1, c2 = st.columns(2)
                nn = c1.text_input("Название *")
                ni = c2.text_input("Индекс в каталоге *")
                
                c3, c4 = st.columns(2)
                ns = c3.text_input("Поставщик *")
                c4.text_input("Владелец", value="Будет привязан к текущему клиенту", disabled=True)

                st.divider()
                st.caption("Финансы и Количество")
                f1, f2, f3 = st.columns(3)
                nq = f1.number_input("Количество (шт)", min_value=0, value=1, step=1)
                nc = f2.number_input("Себестоимость", min_value=0.0, value=0.0, step=10.0)
                np = f3.number_input("Цена", min_value=0.0, value=0.0, step=10.0)

                st.divider()
                st.caption("Статусы и Детали")
                s1, s2, s3 = st.columns(3)
                n_ord = s1.text_input("Заказано (Ordered)", value="0")
                n_recd = s2.text_input("Получено (Recd)", value="0")
                n_pend = s3.text_input("Ожидается (Pending)", value="0")

                d1, d2 = st.columns(2)
                n_acc = d1.text_input("№ Счета / Дата заказа", value="-")
                n_prop = d2.text_input("Характеристики", value="-")
                
                n_notes = st.text_area("Заметки")
                
                if st.form_submit_button("Создать модуль"):
                    if nn and ni and ns:
                        pl = {
                            "module_name": nn, 
                            "catalogue_index": ni, 
                            "supplier": ns,
                            "client_id": cid, # Привязка к текущему клиенту
                            
                            "quantity": nq, "cost": nc, "price": np,
                            "ordered": n_ord, "recd": n_recd, "pending": n_pend,
                            "order_date_acc_num": n_acc, "properties": n_prop,
                            "notes": n_notes
                        }
                        try:
                            utils.create_module(pl)
                            st.success("Модуль создан!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка создания: {e}")
                    else:
                        st.warning("Заполните поля со *")

    # --- ФАЙЛЫ ---
    with tab5:
        st.info("Здесь хранятся сканы документов, фото и PDF.")
        
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
                            # ПОКАЗЫВАЕМ РЕАЛЬНУЮ ОШИБКУ
                            c2.error(f"Err {r.status_code}")
                    except Exception as e:
                        c2.error(f"Ex: {e}")

                    if c3.button("🗑️", key=f"rm_file_{f['document_id']}"):
                        utils.delete_file(f['document_id'])
                        st.rerun()
        else:
            st.write("Файлов пока нет.")