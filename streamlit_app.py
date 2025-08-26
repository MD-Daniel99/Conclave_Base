# streamlit_app.py
from __future__ import annotations
import os
import streamlit as st
from typing import List, Dict, Any, Optional
import requests
import pandas as pd
from datetime import datetime, date, time

PAGE_SIZE = 50

# -------------------------------
# Secrets / Settings
# -------------------------------
def get_secret(key: str, default=None):
    v = os.environ.get(key)
    if v:
        return v
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

API_BASE = get_secret("API_BASE", "http://127.0.0.1:8000")
API_TOKEN = get_secret("API_TOKEN", None)
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}

def clear_caches():
    """Очистка всех кешей для обновления данных."""
    st.cache_data.clear()

# -------------------------------
# API helpers (cached)
# -------------------------------
@st.cache_data(ttl=60)
def fetch_clients(skip: int = 0, limit: int = 100, q: str = None, status: str = None, agent_id: str = None, current_stage: str = None) -> List[Dict[str, Any]]:
    params = {"skip": skip, "limit": limit}
    if q: params["q"] = q
    if status: params["status"] = status
    if agent_id: params["agent_id"] = agent_id
    if current_stage: params["current_stage"] = current_stage
    resp = requests.get(f"{API_BASE}/clients/", params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

@st.cache_data(ttl=60)
def fetch_client_detail(client_id: str) -> Dict[str, Any]:
    resp = requests.get(f"{API_BASE}/clients/{client_id}", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

@st.cache_data(ttl=300)
def fetch_agents(q: str = None) -> List[Dict[str, Any]]:
    params = {"limit": 1000}
    if q: params["q"] = q
    resp = requests.get(f"{API_BASE}/agents/", params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

@st.cache_data(ttl=300)
def fetch_agent_detail(agent_id: str) -> Dict[str, Any]:
    resp = requests.get(f"{API_BASE}/agents/{agent_id}", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

@st.cache_data(ttl=300)
def fetch_statuses() -> List[Dict[str, Any]]:
    resp = requests.get(f"{API_BASE}/status/", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

@st.cache_data(ttl=300)
def fetch_stages() -> List[Dict[str, Any]]:
    resp = requests.get(f"{API_BASE}/stages/", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def create_client(payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(f"{API_BASE}/clients/", json=payload, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def create_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(f"{API_BASE}/agents/", json=payload, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def post_passport(client_id: str, passport_payload: Dict[str, Any]):
    resp = requests.post(f"{API_BASE}/clients/{client_id}/passports", json=passport_payload, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def post_snils(client_id: str, snils_payload: Dict[str, Any]):
    resp = requests.post(f"{API_BASE}/clients/{client_id}/snils", json=snils_payload, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def patch_client(client_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.patch(f"{API_BASE}/clients/{client_id}", json=payload, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def patch_agent(agent_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.patch(f"{API_BASE}/agents/{agent_id}", json=payload, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def patch_passport(passport_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.patch(f"{API_BASE}/passports/{passport_id}", json=payload, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def patch_snils(snils_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.patch(f"{API_BASE}/snils/{snils_id}", json=payload, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def delete_client(client_id: str):
    resp = requests.delete(f"{API_BASE}/clients/{client_id}", headers=HEADERS, timeout=10)
    resp.raise_for_status()

def delete_agent(agent_id: str):
    resp = requests.delete(f"{API_BASE}/agents/{agent_id}", headers=HEADERS, timeout=10)
    if resp.status_code == 400:
        raise ValueError(resp.json().get("detail", "Не удалось удалить агента."))
    resp.raise_for_status()

def add_phone(client_id: str, number: str):
    resp = requests.post(f"{API_BASE}/clients/{client_id}/phones", json={"number": number}, headers=HEADERS, timeout=10)
    resp.raise_for_status()

def delete_phone(phone_id: int):
    resp = requests.delete(f"{API_BASE}/phones/{phone_id}", headers=HEADERS, timeout=10)
    resp.raise_for_status()

# -------------------------------
# Helpers
# -------------------------------
def flatten_client(c: Dict[str, Any]) -> Dict[str, Any]:
    agent = c.get("agent") or {}
    agent_display = f"{agent.get('external_id') or ''} — {agent.get('last_name')} {agent.get('first_name') or ''}".strip() if agent else c.get("agent_id")
    phones = ", ".join([p["number"] for p in (c.get("phones") or [])])
    snils_display = ", ".join([s["number"] for s in (c.get("snils") or [])])
    passport_display = ", ".join([p["series_number"] for p in (c.get("passports") or [])])

    return {
        "external_id": c.get("external_id"), "client_id": c.get("client_id"),
        "last_name": c.get("last_name"), "first_name": c.get("first_name"), "middle_name": c.get("middle_name"),
        "status_code": c.get("status_code"), "current_stage": c.get("current_stage"),
        "agent": agent_display, "phones": phones, "snils": snils_display, "passport": passport_display,
        "deadline": c.get("deadline"), "created_at": c.get("created_at"), "updated_at": c.get("updated_at"),
        "notes": c.get("notes"),
    }

def safe_iso_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return None

# -------------------------------
# UI pages
# -------------------------------
def clients_page():
    st.title("Список клиентов")

    try:
        statuses = fetch_statuses()
        statuses_map = {s["status_code"]: s["description"] for s in statuses}
        stages = fetch_stages()
        stages_map = {s["stage_code"]: s["description"] for s in stages}
    except Exception as e:
        st.sidebar.error(f"Ошибка загрузки справочников: {e}")
        statuses_map, stages_map = {}, {}

    with st.sidebar:
        st.header("Фильтры / Поиск")
        q = st.text_input("Поиск (ФИО)", "")
        status_filter = st.selectbox("Статус", [""] + list(statuses_map.keys()), format_func=lambda x: "(все)" if not x else f"{x} — {statuses_map.get(x, '')}") or None
        stage_filter = st.selectbox("Этап", [""] + list(stages_map.keys()), format_func=lambda x: "(все)" if not x else f"{x} — {stages_map.get(x, '')}") or None

        try:
            agents = fetch_agents()
            agent_map = {f"{a.get('external_id') or ''} — {a.get('last_name')} {a.get('first_name')}": a["agent_id"] for a in agents}
            agent_choice = st.selectbox("Агент", ["(все)"] + list(agent_map.keys()))
            selected_agent_id = agent_map.get(agent_choice) if agent_choice != "(все)" else None
        except Exception:
            selected_agent_id = None

        page_size = st.number_input("Строк на странице", 10, 1000, PAGE_SIZE, 10)

    page = st.number_input("Страница", 1)
    skip = (page - 1) * page_size

    try:
        clients = fetch_clients(skip=skip, limit=page_size, q=q, status=status_filter, agent_id=selected_agent_id, current_stage=stage_filter)
    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        return

    if not clients:
        st.info("Клиенты не найдены.")
        return

    df = pd.DataFrame([flatten_client(c) for c in clients])
    st.dataframe(df, use_container_width=True, hide_index=True)

    client_options = {f"{row['last_name']} {row['first_name']} ({row['client_id']})": row['client_id'] for _, row in df.iterrows()}
    selected_client_display = st.selectbox("Выберите клиента для детального просмотра", client_options.keys())

    if st.button("Просмотреть / Редактировать"):
        st.session_state['selected_client_id'] = client_options[selected_client_display]
        st.session_state['show_modal'] = True
        st.rerun()

    if st.session_state.get('show_modal'):
        client_id = st.session_state.get('selected_client_id')
        if not client_id: return

        try:
            client_detail = fetch_client_detail(client_id)
        except Exception as e:
            st.error(f"Ошибка загрузки деталей клиента: {e}")
            return

        with st.container(border=True):
            st.markdown(f"### Детали клиента: {client_detail.get('last_name')} {client_detail.get('first_name')}")
            tab1, tab2, tab3, tab4 = st.tabs(["Просмотр", "Редактирование", "Документы", "Телефоны"])

            with tab1:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Основная информация**")
                    st.write(f"**ID:** `{client_detail.get('client_id')}`")
                    st.write(f"**External ID:** {client_detail.get('external_id')}")
                    st.write(f"**ФИО:** {client_detail.get('last_name')} {client_detail.get('first_name')} {client_detail.get('middle_name') or ''}")
                    st.write(f"**Статус:** {statuses_map.get(client_detail.get('status_code'), 'Н/Д')}")
                    st.write(f"**Этап:** {stages_map.get(client_detail.get('current_stage'), 'Н/Д')}")
                    st.write(f"**Дедлайн:** {client_detail.get('deadline')}")
                with col2:
                    st.markdown("**Связанные данные**")
                    agent = client_detail.get('agent', {})
                    if agent: st.write(f"**Агент:** {agent.get('last_name')} {agent.get('first_name') or ''}")
                    st.write(f"**Заметки:**")
                    st.text_area("notes_display", client_detail.get('notes', ''), height=150, disabled=True)

            with tab2:
                with st.form("edit_client_form"):
                    c1, c2 = st.columns(2)
                    last_name = c1.text_input("Фамилия", value=client_detail.get("last_name", ""))
                    first_name = c1.text_input("Имя", value=client_detail.get("first_name", ""))
                    middle_name = c1.text_input("Отчество", value=client_detail.get("middle_name", ""))

                    status_options = list(statuses_map.keys())
                    current_status_idx = status_options.index(client_detail.get("status_code")) if client_detail.get("status_code") in status_options else 0
                    selected_status = c2.selectbox("Статус", options=status_options, index=current_status_idx, format_func=lambda x: f"{x} — {statuses_map.get(x, '')}")

                    stage_options = list(stages_map.keys())
                    current_stage_idx = stage_options.index(client_detail.get("current_stage")) if client_detail.get("current_stage") in stage_options else 0
                    selected_stage = c2.selectbox("Этап", options=stage_options, index=current_stage_idx, format_func=lambda x: f"{x} — {stages_map.get(x, '')}")
                    
                    deadline_val = client_detail.get("deadline")
                    deadline_date = datetime.fromisoformat(deadline_val.replace('Z', '+00:00')).date() if deadline_val else None
                    deadline = c2.date_input("Дедлайн", value=deadline_date)

                    notes = st.text_area("Заметки", value=client_detail.get("notes", ""))
                    
                    c3, c4 = st.columns(2)
                    if c3.form_submit_button("Сохранить изменения", use_container_width=True):
                        payload = {
                            "last_name": last_name, "first_name": first_name, "middle_name": middle_name,
                            "status_code": selected_status, "current_stage": selected_stage,
                            "deadline": datetime.combine(deadline, time.min).isoformat() + "Z" if deadline else None,
                            "notes": notes
                        }
                        try:
                            patch_client(client_id, payload)
                            st.success("Данные клиента обновлены!")
                            clear_caches(); st.rerun()
                        except Exception as e: st.error(f"Ошибка: {e}")

                    if c4.form_submit_button("Удалить клиента", type="secondary", use_container_width=True):
                        try:
                            delete_client(client_id)
                            st.success("Клиент удален!")
                            st.session_state['show_modal'] = False
                            clear_caches(); st.rerun()
                        except Exception as e: st.error(f"Ошибка удаления: {e}")
            
            with tab3:
                st.markdown("##### Паспорта")
                for passport in client_detail.get('passports', []):
                    with st.expander(f"Паспорт: {passport.get('series_number', '')}"):
                        with st.form(f"edit_passport_{passport['passport_id']}"):
                            c1, c2 = st.columns(2)
                            full_name = c1.text_input("ФИО", value=passport.get('full_name', ''))
                            birth_date = c1.date_input("Дата рождения", value=safe_iso_date(passport.get('birth_date')))
                            birth_place = c1.text_input("Место рождения", value=passport.get('birth_place', ''))
                            series_number = c2.text_input("Серия и номер", value=passport.get('series_number', ''))
                            department_code = c2.text_input("Код подразделения", value=passport.get('department_code', ''))
                            issue_date = c2.date_input("Дата выдачи", value=safe_iso_date(passport.get('issue_date')))
                            issued_by = st.text_input("Кем выдан", value=passport.get('issued_by', ''))
                            registration_address = st.text_area("Адрес прописки", value=passport.get('registration_address', ''))

                            if st.form_submit_button("Обновить паспорт"):
                                payload = {
                                    "full_name": full_name, "birth_date": birth_date.isoformat() if birth_date else None,
                                    "birth_place": birth_place, "series_number": series_number,
                                    "department_code": department_code, "issue_date": issue_date.isoformat() if issue_date else None,
                                    "issued_by": issued_by, "registration_address": registration_address
                                }
                                try:
                                    patch_passport(passport['passport_id'], payload)
                                    st.success("Паспорт обновлен!")
                                    clear_caches(); st.rerun()
                                except Exception as e: st.error(f"Ошибка: {e}")

                with st.expander("Добавить новый паспорт"):
                    with st.form("add_passport_form"):
                        c1, c2 = st.columns(2)
                        new_full_name = c1.text_input("ФИО")
                        new_birth_date = c1.date_input("Дата рождения", value=None)
                        new_birth_place = c1.text_input("Место рождения")
                        new_series_number = c2.text_input("Серия и номер")
                        new_department_code = c2.text_input("Код подразделения")
                        new_issue_date = c2.date_input("Дата выдачи", value=None)
                        new_issued_by = st.text_input("Кем выдан")
                        new_registration_address = st.text_area("Адрес прописки")

                        if st.form_submit_button("Добавить паспорт"):
                            if all([new_full_name, new_birth_date, new_birth_place, new_series_number, new_issue_date, new_issued_by, new_registration_address]):
                                payload = {
                                    "full_name": new_full_name, "birth_date": new_birth_date.isoformat(),
                                    "birth_place": new_birth_place, "series_number": new_series_number,
                                    "department_code": new_department_code, "issue_date": new_issue_date.isoformat(),
                                    "issued_by": new_issued_by, "registration_address": new_registration_address
                                }
                                try:
                                    post_passport(client_id, payload)
                                    st.success("Паспорт добавлен!")
                                    clear_caches(); st.rerun()
                                except Exception as e: st.error(f"Ошибка: {e}")
                            else: st.warning("Заполните все поля паспорта.")
                
                st.divider()
                st.markdown("##### СНИЛС")
                for snils in client_detail.get('snils', []):
                    with st.expander(f"СНИЛС: {snils.get('number', '')}"):
                        with st.form(f"edit_snils_{snils['snils_id']}"):
                            number = st.text_input("Номер", value=snils.get('number', ''))
                            issued_date = st.date_input("Дата выдачи", value=safe_iso_date(snils.get('issued_date')))
                            if st.form_submit_button("Обновить СНИЛС"):
                                payload = {"number": number, "issued_date": issued_date.isoformat() if issued_date else None}
                                try:
                                    patch_snils(snils['snils_id'], payload)
                                    st.success("СНИЛС обновлен!")
                                    clear_caches(); st.rerun()
                                except Exception as e: st.error(f"Ошибка: {e}")

                with st.expander("Добавить новый СНИЛС"):
                    with st.form("add_snils_form"):
                        new_number = st.text_input("Номер СНИЛС")
                        new_issued_date = st.date_input("Дата выдачи СНИЛС", value=None)
                        if st.form_submit_button("Добавить СНИЛС"):
                            if new_number:
                                payload = {"number": new_number, "issued_date": new_issued_date.isoformat() if new_issued_date else None}
                                try:
                                    post_snils(client_id, payload)
                                    st.success("СНИЛС добавлен!")
                                    clear_caches(); st.rerun()
                                except Exception as e: st.error(f"Ошибка: {e}")
                            else: st.warning("Введите номер СНИЛС.")

            with tab4:
                st.markdown("##### Телефоны")
                for phone in client_detail.get('phones', []):
                    c1, c2 = st.columns([4, 1])
                    c1.text_input("Номер", phone['number'], disabled=True, key=f"phone_{phone['phone_id']}")
                    if c2.button("🗑️", key=f"del_phone_{phone['phone_id']}", help="Удалить телефон"):
                        try:
                            delete_phone(phone['phone_id'])
                            st.success("Телефон удален!")
                            clear_caches(); st.rerun()
                        except Exception as e: st.error(f"Ошибка удаления: {e}")
                
                with st.form("add_phone_form"):
                    new_phone_number = st.text_input("Новый номер телефона")
                    if st.form_submit_button("Добавить телефон"):
                        if new_phone_number:
                            try:
                                add_phone(client_id, new_phone_number)
                                st.success("Телефон добавлен!")
                                clear_caches(); st.rerun()
                            except Exception as e: st.error(f"Ошибка: {e}")
                        else: st.warning("Введите номер.")
            
            if st.button("Закрыть", key="close_modal"):
                st.session_state['show_modal'] = False
                st.rerun()

def agents_page():
    st.title("Список агентов")
    
    try:
        agents = fetch_agents()
    except Exception as e:
        st.error(f"Не удалось загрузить агентов: {e}")
        return
        
    if not agents:
        st.info("Агенты не найдены.")
        return
        
    df = pd.DataFrame(agents)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    agent_options = {f"{row['last_name']} {row['first_name']} ({row['agent_id']})": row['agent_id'] for _, row in df.iterrows()}
    selected_display = st.selectbox("Выберите агента для просмотра/редактирования", options=list(agent_options.keys()))

    if st.button("Просмотреть / Редактировать агента"):
        st.session_state['selected_agent_id'] = agent_options[selected_display]
        st.session_state['show_agent_modal'] = True
        st.rerun()

    if st.session_state.get('show_agent_modal') and st.session_state.get('selected_agent_id'):
        agent_id = st.session_state.selected_agent_id
        try:
            agent_detail = fetch_agent_detail(agent_id)
        except Exception as e:
            st.error(f"Не удалось загрузить детали агента: {e}")
            return
            
        with st.container(border=True):
            st.markdown(f"### Детали агента: {agent_detail.get('last_name')} {agent_detail.get('first_name')}")
            
            with st.form("edit_agent_form"):
                c1, c2 = st.columns(2)
                last_name = c1.text_input("Фамилия", value=agent_detail.get("last_name", ""))
                first_name = c1.text_input("Имя", value=agent_detail.get("first_name", ""))
                middle_name = c1.text_input("Отчество", value=agent_detail.get("middle_name", ""))
                inn = c2.text_input("ИНН", value=agent_detail.get("inn", ""))
                ogrnip = c2.text_input("ОГРНИП", value=agent_detail.get("ogrnip", ""))
                legal_address = st.text_area("Юридический адрес", value=agent_detail.get("legal_address", ""))
                actual_address = st.text_area("Фактический адрес", value=agent_detail.get("actual_address", ""))
                account_number = st.text_input("Расчетный счет", value=agent_detail.get("account_number", ""))
                correspondent_account = st.text_input("Корреспондентский счет", value=agent_detail.get("correspondent_account", ""))
                bic = st.text_input("БИК", value=agent_detail.get("bic", ""))

                if st.form_submit_button("Сохранить изменения"):
                    payload = {
                        "last_name": last_name, "first_name": first_name, "middle_name": middle_name,
                        "inn": inn, "ogrnip": ogrnip, "legal_address": legal_address, "actual_address": actual_address,
                        "account_number": account_number, "correspondent_account": correspondent_account, "bic": bic
                    }
                    try:
                        patch_agent(agent_id, payload)
                        st.success("Данные агента обновлены!")
                        clear_caches(); st.rerun()
                    except Exception as e: st.error(f"Ошибка обновления: {e}")
            
            if st.button("Удалить агента", type="secondary"):
                try:
                    delete_agent(agent_id)
                    st.success("Агент успешно удален!")
                    st.session_state['show_agent_modal'] = False
                    clear_caches(); st.rerun()
                except (ValueError, requests.HTTPError) as e:
                    st.error(str(e))

            if st.button("Закрыть", key="close_agent_modal"):
                st.session_state['show_agent_modal'] = False
                st.rerun()

def add_client_page():
    st.title("➕ Добавить клиента")

    try:
        statuses = fetch_statuses()
        statuses_map = {s["status_code"]: s["description"] for s in statuses}
        stages = fetch_stages()
        stages_map = {s["stage_code"]: s["description"] for s in stages}
        agents = fetch_agents()
        agent_map = {f"{a.get('external_id') or ''} — {a.get('last_name')} {a.get('first_name')}": a["agent_id"] for a in agents}
    except Exception as e:
        st.error(f"Не удалось загрузить справочники: {e}")
        return

    with st.form("add_client_form"):
        st.markdown("**Основная информация**")
        c1, c2 = st.columns(2)
        last_name = c1.text_input("Фамилия *")
        first_name = c1.text_input("Имя *")
        middle_name = c1.text_input("Отчество")
        selected_status = c2.selectbox("Статус *", options=list(statuses_map.keys()), format_func=lambda x: f"{x} — {statuses_map.get(x, '')}")
        selected_stage = c2.selectbox("Этап *", options=list(stages_map.keys()), format_func=lambda x: f"{x} — {stages_map.get(x, '')}")
        selected_agent_display = c2.selectbox("Агент *", options=list(agent_map.keys()))
        deadline = st.date_input("Дедлайн", value=None)
        notes = st.text_area("Заметки")
        
        st.markdown("---")
        phones_raw = st.text_area("Телефоны (каждый с новой строки)")
        
        with st.expander("Добавить паспортные данные (опционально)"):
            c1, c2 = st.columns(2)
            passport_full_name = c1.text_input("ФИО по паспорту")
            passport_birth_date = c1.date_input("Дата рождения", value=None)
            passport_birth_place = c1.text_input("Место рождения")
            passport_series = c2.text_input("Серия и номер")
            passport_department_code = c2.text_input("Код подразделения")
            passport_issue_date = c2.date_input("Дата выдачи", value=None)
            passport_issued_by = st.text_input("Кем выдан")
            passport_registration_address = st.text_area("Адрес прописки")

        with st.expander("Добавить СНИЛС (опционально)"):
            snils_number = st.text_input("Номер СНИЛС")
            snils_issue_date = st.date_input("Дата выдачи СНИЛС", value=None)

        if st.form_submit_button("Сохранить клиента"):
            if not all([last_name.strip(), first_name.strip(), selected_agent_display]):
                st.error("Поля 'Фамилия', 'Имя' и 'Агент' обязательны.")
                return

            client_payload = {
                "last_name": last_name.strip(), "first_name": first_name.strip(),
                "middle_name": middle_name.strip() or None, "status_code": selected_status,
                "current_stage": selected_stage, "agent_id": agent_map.get(selected_agent_display),
                "deadline": datetime.combine(deadline, time.min).isoformat() + "Z" if deadline else None,
                "notes": notes.strip() or None,
                "phones": [{"number": p.strip()} for p in phones_raw.splitlines() if p.strip()],
            }
            
            try:
                created_client = create_client(client_payload)
                client_id = created_client.get("client_id")
                st.success(f"Клиент '{created_client.get('last_name')}' создан!")

                if passport_full_name.strip() and passport_series.strip():
                    passport_payload = {
                        "full_name": passport_full_name,
                        "birth_date": passport_birth_date.isoformat() if passport_birth_date else None,
                        "birth_place": passport_birth_place,
                        "series_number": passport_series,
                        "issued_by": passport_issued_by,
                        "issue_date": passport_issue_date.isoformat() if passport_issue_date else None,
                        "department_code": passport_department_code,
                        "registration_address": passport_registration_address,
                    }
                    try:
                        post_passport(client_id, passport_payload)
                        st.info("Паспортные данные добавлены.")
                    except Exception as e: st.warning(f"Не удалось добавить паспорт: {e}")
                
                if snils_number.strip():
                    snils_payload = {"number": snils_number, "issued_date": snils_issue_date.isoformat() if snils_issue_date else None}
                    try:
                        post_snils(client_id, snils_payload)
                        st.info("СНИЛС добавлен.")
                    except Exception as e: st.warning(f"Не удалось добавить СНИЛС: {e}")
                
                clear_caches()
            except Exception as e:
                st.error(f"Ошибка при создании клиента: {e}")

def add_agent_page():
    st.title("➕ Добавить агента")
    
    with st.form("add_agent_form"):
        st.markdown("**Основная информация**")
        c1, c2 = st.columns(2)
        last_name = c1.text_input("Фамилия *")
        first_name = c1.text_input("Имя *")
        middle_name = c1.text_input("Отчество")
        inn = c2.text_input("ИНН *", help="10 или 12 цифр")
        ogrnip = c2.text_input("ОГРНИП *", help="15 цифр")
        legal_address = st.text_area("Юридический адрес *")
        actual_address = st.text_area("Фактический адрес *")
        account_number = st.text_input("Расчетный счет *", help="20 цифр")
        correspondent_account = st.text_input("Корр. счет", help="20 цифр (если отличается)")
        bic = st.text_input("БИК *", help="9 цифр")

        if st.form_submit_button("Сохранить агента"):
            errors = []
            if not all([last_name, first_name, inn, ogrnip, legal_address, actual_address, account_number, bic]):
                errors.append("Поля, отмеченные *, обязательны.")
            if not inn.isdigit() or not (len(inn) == 10 or len(inn) == 12): errors.append("ИНН должен состоять из 10 или 12 цифр.")
            if not ogrnip.isdigit() or len(ogrnip) != 15: errors.append("ОГРНИП должен состоять из 15 цифр.")
            if not account_number.isdigit() or len(account_number) != 20: errors.append("Расчетный счет должен состоять из 20 цифр.")
            if correspondent_account and (not correspondent_account.isdigit() or len(correspondent_account) != 20): errors.append("Корр. счет должен состоять из 20 цифр.")
            if not bic.isdigit() or len(bic) != 9: errors.append("БИК должен состоять из 9 цифр.")

            if errors:
                for error in errors: st.error(error)
            else:
                payload = {
                    "last_name": last_name.strip(), "first_name": first_name.strip(),
                    "middle_name": middle_name.strip() or None, "inn": inn.strip(),
                    "ogrnip": ogrnip.strip(), "legal_address": legal_address.strip(),
                    "actual_address": actual_address.strip(), "account_number": account_number.strip(),
                    "correspondent_account": correspondent_account.strip() or None, "bic": bic.strip()
                }
                try:
                    create_agent(payload)
                    st.success(f"Агент {last_name} {first_name} успешно создан!")
                    clear_caches()
                except requests.exceptions.HTTPError as e:
                    st.error(f"Ошибка API: {e.response.json().get('detail', e.response.text)}")
                except Exception as e: st.error(f"Произошла ошибка: {e}")

# -------------------------------
# Main
# -------------------------------
st.set_page_config(page_title="CRM Admin UI", layout="wide")

if 'show_modal' not in st.session_state: st.session_state['show_modal'] = False
if 'selected_client_id' not in st.session_state: st.session_state['selected_client_id'] = None
if 'show_agent_modal' not in st.session_state: st.session_state['show_agent_modal'] = False
if 'selected_agent_id' not in st.session_state: st.session_state['selected_agent_id'] = None

mode = st.sidebar.radio("Меню", ["Клиенты", "Агенты", "Добавить клиента", "Добавить агента"])

if mode == "Клиенты":
    clients_page()
elif mode == "Агенты":
    agents_page()
elif mode == "Добавить клиента":
    add_client_page()
elif mode == "Добавить агента":
    add_agent_page()