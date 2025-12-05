import streamlit as st
import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import utils

# --- AUTH CHECK ---
if not st.session_state.get("token"):
    st.stop()

# --- STATE MANAGEMENT ---
if "ag_active_id" not in st.session_state:
    st.session_state.ag_active_id = None

def reset_state():
    st.session_state.ag_active_id = None
    st.rerun()

# ==========================================
# UI: LIST (Список агентов)
# ==========================================
if st.session_state.ag_active_id is None:
    st.title("🕵️ Агенты")

    # 1. ФИЛЬТРЫ
    with st.expander("🔍 Поиск и настройки", expanded=True):
        c1, c2 = st.columns([2, 1])
        q = c1.text_input("Поиск (ФИО агента или клиента)", placeholder="Введите имя...")
        
        # Пагинация
        c3, c4 = st.columns([1, 4])
        limit = c3.number_input("На стр.", 5, 100, 20)
        page = c4.number_input("Страница", 1, 100, 1)
        skip = (page - 1) * limit

    # 2. ТАБЛИЦА
    try:
        agents = utils.fetch_agents(skip, limit, q)
    except Exception as e:
        st.error(f"Ошибка: {e}")
        agents = []

    if agents:
        rows = []
        for a in agents:
            rows.append({
                "ID": a["agent_id"],
                "ФИО": f"{a['last_name']} {a['first_name']} {a['middle_name'] or ''}".strip(),
                "ИНН": a["inn"],
                "БИК": a["bic"],
                #"Юр. адрес": a["legal_address"]
                "ОГРНИП": a["ogrnip"],
                "Расчетный счет": a["account_number"]

            })
        
        df = pd.DataFrame(rows)
        
        event = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun"
        )
        
        if event.selection.rows:
            idx = event.selection.rows[0]
            st.session_state.ag_active_id = df.iloc[idx]["ID"]
            st.rerun()
    else:
        st.info("Агенты не найдены")

    # 3. СОЗДАНИЕ (В отдельном экспандере, с красивой формой)
    st.divider()
    with st.expander("➕ Добавить нового агента"):
        with st.form("create_agent_form"):
            st.subheader("Новый агент")
            
            st.caption("Персональные данные")
            c1, c2, c3 = st.columns(3)
            nl = c1.text_input("Фамилия *")
            nf = c2.text_input("Имя *")
            nm = c3.text_input("Отчество")
            
            st.divider()
            st.caption("Реквизиты")
            r1, r2, r3 = st.columns(3)
            ni = r1.text_input("ИНН")
            no = r2.text_input("ОГРНИП")
            nb = r3.text_input("БИК")
            
            na = st.text_input("Расчетный счет")
            nc = st.text_input("Корр. счет")
            
            st.divider()
            st.caption("Адреса")
            a1, a2 = st.columns(2)
            nla = a1.text_area("Юридический адрес", height=100)
            naa = a2.text_area("Фактический адрес", height=100)
            
            if st.form_submit_button("Создать агента"):
                if nl and nf:
                    pl = {
                        "last_name": nl, "first_name": nf,
                        "inn": ni, "ogrnip": no, "bic": nb, 
                        "account_number": na, "correspondent_account": nc,
                        "legal_address": nla, "actual_address": naa,
                        "inn": ni if ni else None,
                        "ogrnip": no if no else None,
                        "bic": nb if nb else None,
                        "account_number": na if na else None,
                        "correspondent_account": nc if nc else None,
                        "legal_address": nla if nla else None,
                        "actual_address": naa if naa else None
                    }
                    try:
                        utils.create_agent(pl)
                        st.success("Агент создан!")
                        st.rerun()
                    except Exception as e: st.error(f"Ошибка: {e}")
                else:
                    st.warning("Заполните поля, отмеченные *")

# ==========================================
# UI: EDIT MODE (Карточка агента)
# ==========================================
else:
    aid = st.session_state.ag_active_id
    
    if st.button("⬅️ Вернуться к списку"):
        reset_state()

    try:
        detail = utils.fetch_agent_detail(aid)
    except:
        st.error("Не удалось загрузить данные агента")
        if st.button("Сброс"): reset_state()
        st.stop()

    st.header(f"🕵️ {detail['last_name']} {detail['first_name']}")

    tab1, tab2 = st.tabs(["✏️ Редактирование", "👥 Связанные клиенты"])

    # --- TAB 1: РЕДАКТИРОВАНИЕ ---
    with tab1:
        with st.form("edit_agent_form"):
            st.caption("Персональные данные")
            c1, c2, c3 = st.columns(3)
            el = c1.text_input("Фамилия", value=detail['last_name'])
            ef = c2.text_input("Имя", value=detail['first_name'])
            em = c3.text_input("Отчество", value=detail['middle_name'] or "")
            
            st.divider()
            st.caption("Реквизиты")
            r1, r2, r3 = st.columns(3)
            ei = r1.text_input("ИНН", value=detail['inn'])
            eo = r2.text_input("ОГРНИП", value=detail['ogrnip'])
            eb = r3.text_input("БИК", value=detail['bic'])
            
            ea = st.text_input("Расчетный счет", value=detail['account_number'])
            ec = st.text_input("Корр. счет", value=detail['correspondent_account'] or "")
            
            st.divider()
            st.caption("Адреса")
            a1, a2 = st.columns(2)
            ela = a1.text_area("Юридический адрес", value=detail['legal_address'])
            eaa = a2.text_area("Фактический адрес", value=detail['actual_address'])
            
            if st.form_submit_button("Сохранить изменения"):
                pl = {
                    "last_name": el, "first_name": ef, "middle_name": em,
                    "inn": ei, "ogrnip": eo, "bic": eb,
                    "account_number": ea, "correspondent_account": ec,
                    "legal_address": ela, "actual_address": eaa
                }
                try:
                    utils.patch_agent(aid, pl)
                    st.success("Сохранено!")
                    utils.clear_caches()
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {e}")

        st.divider()
        if st.button("🗑️ Удалить агента", type="primary"):
            try:
                utils.delete_agent(aid)
                st.success("Агент удален")
                reset_state()
            except Exception as e:
                st.error(f"Не удалось удалить (возможно, есть привязанные клиенты): {e}")

    # --- TAB 2: СВЯЗАННЫЕ КЛИЕНТЫ ---
    with tab2:
        st.info("Список клиентов, привязанных к этому агенту.")
        try:
            # Используем фильтр agent_id в fetch_clients
            linked_clients = utils.fetch_clients(limit=1000, agent_id=aid)
            if linked_clients:
                # Простая таблица для просмотра
                client_rows = []
                for c in linked_clients:
                    client_rows.append({
                        "ФИО": f"{c['last_name']} {c['first_name']}",
                        "Статус": c.get("status", {}).get("description", "-"),
                        "Дедлайн": c.get("deadline")
                    })
                st.dataframe(pd.DataFrame(client_rows), use_container_width=True)
            else:
                st.write("У этого агента пока нет клиентов.")
        except Exception as e:
            st.error(f"Ошибка загрузки клиентов: {e}")