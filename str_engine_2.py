# str_engine_2.py
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

def patch_phone(phone_id: int, payload: Dict[str, Any]):
    resp = requests.patch(f"{API_BASE}/phones/{phone_id}", json=payload, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def delete_passport(passport_id: str):
    resp = requests.delete(f"{API_BASE}/passports/{passport_id}", headers=HEADERS, timeout=10)
    resp.raise_for_status()

def delete_snils(snils_id: str):
    resp = requests.delete(f"{API_BASE}/snils/{snils_id}", headers=HEADERS, timeout=10)
    resp.raise_for_status()

# Modules 
@st.cache_data(ttl=60)
def fetch_all_modules(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    params = {"skip": skip, "limit": limit}
    # Обращается к общему списку модулей
    resp = requests.get(f"{API_BASE}/modules/", params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

# ФУНКЦИЯ №1: Создает модуль БЕЗ привязки к клиенту в URL
# Используется на странице "Склад"
def create_module(payload: Dict[str, Any]):
    # Теперь мы всегда обращаемся к /modules/
    # client_id уже должен лежать внутри payload (или быть None)
    resp = requests.post(f"{API_BASE}/modules/", json=payload, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

# ФУНКЦИЯ №2: Создает модуль ДЛЯ КОНКРЕТНОГО КЛИЕНТА
# Используется внутри досье клиента
def create_module_for_client_wrapper(client_id: str, payload: Dict[str, Any]):
    # Просто добавляем ID в словарь и шлем на общий эндпоинт
    payload['client_id'] = client_id
    return create_module(payload)


def patch_module(module_id: str, payload: Dict[str, Any]):
    resp = requests.patch(f"{API_BASE}/modules/{module_id}", json=payload, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def delete_module(module_id: str):
    resp = requests.delete(f"{API_BASE}/modules/{module_id}", headers=HEADERS, timeout=10)
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
    
    event = st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True, 
        on_select="rerun", 
        selection_mode="single-row"
    )

    selected_rows = event.selection.rows
    if selected_rows:
        selected_index = selected_rows[0]
        selected_client_id = df.iloc[selected_index]['client_id']
        selected_client_name = f"{df.iloc[selected_index]['first_name']} {df.iloc[selected_index]['last_name']}"

        st.divider()
        st.write(f"Выбран клиент: **{selected_client_name}**")
        
        if st.button(f"Просмотреть / Редактировать клиента"):
            st.session_state['selected_client_id'] = selected_client_id
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
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["Просмотр", "Редактирование", "Документы", "Телефоны", "Модули"])

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
                    
                    agents_list = fetch_agents()
                    agent_options_map = {f"{a.get('external_id') or ''} — {a.get('last_name')} {a.get('first_name')}": a["agent_id"] for a in agents_list}
                    current_agent = client_detail.get("agent", {})
                    current_agent_display = f"{current_agent.get('external_id', '')} — {current_agent.get('last_name', '')} {current_agent.get('first_name', '')}".strip()
                    agent_display_options = list(agent_options_map.keys())
                    try:
                        current_agent_index = agent_display_options.index(current_agent_display)
                    except ValueError:
                        current_agent_index = 0
                    selected_agent_display = c2.selectbox("Агент", options=agent_display_options, index=current_agent_index)
                    selected_agent_id = agent_options_map[selected_agent_display]

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
                            "notes": notes,
                            "agent_id": selected_agent_id,
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

                            c3, c4 = st.columns(2)
                            if c3.form_submit_button("Обновить паспорт"):
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
                            
                            if c4.form_submit_button("Удалить паспорт", type="secondary"):
                                try:
                                    delete_passport(passport['passport_id'])
                                    st.success("Паспорт удален!")
                                    clear_caches(); st.rerun()
                                except Exception as e: st.error(f"Ошибка удаления: {e}")
                
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
                            
                            c1, c2 = st.columns(2)
                            if c1.form_submit_button("Обновить СНИЛС"):
                                payload = {"number": number, "issued_date": issued_date.isoformat() if issued_date else None}
                                try:
                                    patch_snils(snils['snils_id'], payload)
                                    st.success("СНИЛС обновлен!")
                                    clear_caches(); st.rerun()
                                except Exception as e: st.error(f"Ошибка: {e}")
                            
                            if c2.form_submit_button("Удалить СНИЛС", type="secondary"):
                                try:
                                    delete_snils(snils['snils_id'])
                                    st.success("СНИЛС удален!")
                                    clear_caches(); st.rerun()
                                except Exception as e: st.error(f"Ошибка удаления: {e}")

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
                    with st.form(key=f"phone_form_{phone['phone_id']}"):
                        new_number = st.text_input("Номер телефона", value=phone['number'])
                        
                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Сохранить"):
                            try:
                                patch_phone(phone['phone_id'], {"number": new_number})
                                st.success("Номер телефона обновлен!")
                                clear_caches(); st.rerun()
                            except Exception as e: st.error(f"Ошибка обновления: {e}")

                        if c2.form_submit_button("Удалить", type="secondary"):
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
            
            
            # ПРАВИЛЬНЫЙ БЛОК ДЛЯ str_engine_2.py
            with tab5:
                st.markdown("##### Модули, закрепленные за клиентом")
                for module_data in client_detail.get('modules', []):
                    with st.expander(f"Модуль: {module_data.get('module_name', '')} ({module_data.get('catalogue_index', '')})"):
                        with st.form(f"edit_module_{module_data['module_id']}"):
                            
                            st.text_input("Пациент", value=f"{client_detail.get('first_name')} {client_detail.get('last_name')}", disabled=True, key=f"patient_{module_data['module_id']}")
                            
                            c1, c2 = st.columns(2)
                            module_name = c1.text_input("Название модуля", value=module_data.get('module_name', ''), key=f"mod_name_{module_data['module_id']}")
                            catalogue_index = c1.text_input("Индекс в каталоге", value=module_data.get('catalogue_index', ''), key=f"mod_cat_idx_{module_data['module_id']}")
                            supplier = c1.text_input("Поставщик", value=module_data.get('supplier', ''), key=f"mod_supplier_{module_data['module_id']}")
                            ordered = c2.text_input("Заказано", value=module_data.get('ordered', ''), key=f"mod_ordered_{module_data['module_id']}")
                            order_date_acc_num = c2.text_input("Номер счета, дата заказа", value=module_data.get('order_date_acc_num', ''), key=f"mod_order_date_{module_data['module_id']}")
                            
                            c3, c4 = st.columns(2)
                            cost = c3.number_input("Стоимость", value=float(module_data.get('cost', 0.0)), key=f"mod_cost_{module_data['module_id']}")
                            price = c4.number_input("Цена", value=float(module_data.get('price', 0.0)), key=f"mod_price_{module_data['module_id']}")
                            
                            c5, c6 = st.columns(2)
                            pending = c5.text_input("В ожидании", value=module_data.get('pending', ''), key=f"mod_pending_{module_data['module_id']}")
                            recd = c6.text_input("Получено (Recd)", value=module_data.get('recd', ''), key=f"mod_recd_edit_{module_data['module_id']}")

                            properties = st.text_input("Характеристики", value=module_data.get('properties', ''), key=f"mod_props_{module_data['module_id']}")
                            notes = st.text_area("Заметки", value=module_data.get('notes', ''), key=f"mod_notes_edit_{module_data['module_id']}")

                            c7, c8 = st.columns(2)
                            if c7.form_submit_button("Обновить модуль"):
                                payload = {
                                    "module_name": module_name, "catalogue_index": catalogue_index,
                                    "supplier": supplier, "ordered": ordered,
                                    "order_date_acc_num": order_date_acc_num, "cost": cost,
                                    "price": price, "pending": pending, "recd": recd,
                                    "properties": properties, "notes": notes,
                                }
                                try:
                                    patch_module(module_data['module_id'], payload)
                                    st.success("Модуль обновлен!")
                                    clear_caches(); st.rerun()
                                except Exception as e:
                                    st.error(f"Ошибка обновления модуля: {e}")

                            if c8.form_submit_button("Удалить модуль", type="secondary"):
                                try:
                                    delete_module(module_data['module_id'])
                                    st.success("Модуль удален!")
                                    clear_caches(); st.rerun()
                                except Exception as e:
                                    st.error(f"Ошибка удаления модуля: {e}")

                with st.expander("Добавить новый модуль для клиента"):
                    with st.form("add_module_form"):
                        st.write("Заполните информацию о новом модуле")
                        c1, c2 = st.columns(2)
                        new_module_name = c1.text_input("Название модуля *", key="add_mod_name")
                        new_catalogue_index = c1.text_input("Индекс в каталоге *", key="add_mod_cat_idx")
                        new_supplier = c1.text_input("Поставщик *", key="add_mod_supplier")
                        new_ordered = c2.text_input("Заказано (кол-во) *", key="add_mod_ordered", value="0")
                        new_order_date_acc_num = c2.text_input("Номер счета, дата заказа *", key="add_mod_order_date")
                        new_cost = c2.number_input("Стоимость *", key="add_mod_cost", value=0.0)
                        new_price = c2.number_input("Цена *", key="add_mod_price", value=0.0)
                        
                        c3, c4 = st.columns(2)
                        new_pending = c3.text_input("В ожидании (кол-во) *", key="add_mod_pending", value="0")
                        new_recd = c4.text_input("Получено (Recd) *", key="add_mod_recd", value="0")
                        
                        new_properties = st.text_input("Характеристики *", key="add_mod_props")
                        new_notes = st.text_area("Заметки по модулю", key="add_mod_notes")

                        if st.form_submit_button("Сохранить модуль"):
                            if all([new_module_name, new_catalogue_index, new_supplier]):
                                payload = {
                                    "module_name": new_module_name,
                                    "catalogue_index": new_catalogue_index,
                                    "supplier": new_supplier, "ordered": new_ordered,
                                    "order_date_acc_num": new_order_date_acc_num, "cost": new_cost,
                                    "price": new_price, "pending": new_pending, "recd": new_recd,
                                    "properties": new_properties, "notes": new_notes,
                                }
                                try:
                                    create_module_for_client_wrapper(client_id, payload)
                                    st.success("Модуль успешно добавлен!")
                                    clear_caches(); st.rerun()
                                except Exception as e:
                                    st.error(f"Ошибка добавления модуля: {e}")
                            else:
                                st.warning("Поля 'Название модуля', 'Индекс в каталоге' и 'Поставщик' обязательны.")

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
    
    event = st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    selected_rows = event.selection.rows
    if selected_rows:
        selected_index = selected_rows[0]
        selected_agent_id = df.iloc[selected_index]['agent_id']
        selected_agent_name = f"{df.iloc[selected_index]['first_name']} {df.iloc[selected_index]['last_name']}"

        st.divider()
        st.write(f"Выбран агент: **{selected_agent_name}**")

        if st.button("Просмотреть / Редактировать агента"):
            st.session_state['selected_agent_id'] = selected_agent_id
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

def warehouse_page():
    st.title("Склад модулей")
    st.write("Здесь отображается полный список всех модулей в системе.")

    # Инициализация состояния для редактирования (локально для этой страницы)
    if 'editing_module_id' not in st.session_state:
        st.session_state['editing_module_id'] = None

    # --- БЛОК 1: ФОРМА ДОБАВЛЕНИЯ НОВОГО МОДУЛЯ ---
    with st.expander("Добавить новый модуль на склад"):
        with st.form("warehouse_add_module_form", clear_on_submit=True):
            st.write("Заполните информацию о новом модуле")
            
            # Загрузка списка клиентов для привязки
            try:
                clients = fetch_clients(limit=1000)
                # Опция "На склад (ничей)" имеет значение None
                client_map = {"На склад (ничей)": None}
                # Добавляем реальных клиентов
                client_map.update({f"{c['first_name']} {c['last_name']} ({c.get('external_id', 'No ID')})": c['client_id'] for c in clients})
                
                selected_client_display = st.selectbox("Привязать к клиенту", options=list(client_map.keys()))
                selected_client_id = client_map[selected_client_display]
            except Exception:
                selected_client_id = None
                st.warning("Не удалось загрузить список клиентов. Модуль будет добавлен без привязки.")

            # Поля ввода (все поля из модели)
            c1, c2 = st.columns(2)
            new_module_name = c1.text_input("Название модуля *", key="wh_add_mod_name")
            new_catalogue_index = c1.text_input("Индекс в каталоге *", key="wh_add_mod_cat_idx")
            new_supplier = c1.text_input("Поставщик *", key="wh_add_mod_supplier")
            new_ordered = c2.text_input("Заказано (кол-во) *", key="wh_add_mod_ordered", value="0")
            new_order_date_acc_num = c2.text_input("Номер счета, дата заказа *", key="wh_add_mod_order_date")
            # Используем number_input для числовых полей во избежание ошибок валидации
            new_cost = c2.number_input("Стоимость *", key="wh_add_mod_cost", value=0.0, min_value=0.0)
            new_price = c2.number_input("Цена *", key="wh_add_mod_price", value=0.0, min_value=0.0)
            
            c3, c4, c5 = st.columns(3)
            new_received_stored = c3.text_input("На складе (кол-во) *", key="wh_add_mod_stored", value="0")
            new_pending = c4.text_input("В ожидании (кол-во) *", key="wh_add_mod_pending", value="0")
            new_recd = c5.text_input("Получено (Recd) *", key="wh_add_mod_recd", value="0")
            
            new_properties = st.text_input("Характеристики *", key="wh_add_mod_props")
            new_notes = st.text_area("Заметки по модулю", key="wh_add_mod_notes")

            if st.form_submit_button("Сохранить новый модуль"):
                if all([new_module_name, new_catalogue_index, new_supplier]):
                    payload = {
                        "client_id": selected_client_id, # Может быть UUID или None
                        "module_name": new_module_name,
                        "catalogue_index": new_catalogue_index,
                        "supplier": new_supplier,
                        "ordered": new_ordered,
                        "order_date_acc_num": new_order_date_acc_num,
                        "cost": new_cost,
                        "price": new_price,
                        "received_stored": new_received_stored,
                        "pending": new_pending,
                        "recd": new_recd,
                        "properties": new_properties,
                        "notes": new_notes,
                    }
                    try:
                        create_module(payload)
                        st.success("Модуль успешно создан!")
                        clear_caches(); st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка создания модуля: {e}")
                else:
                    st.warning("Поля 'Название модуля', 'Индекс в каталоге' и 'Поставщик' обязательны.")

    st.divider()
    
    # --- БЛОК 2: ОТОБРАЖЕНИЕ ТАБЛИЦЫ ---
    try:
        all_modules = fetch_all_modules(limit=1000)
    except Exception as e:
        st.error(f"Не удалось загрузить данные со склада: {e}")
        return
    
    if not all_modules:
        st.info("На складе пока нет ни одного модуля.")
        return

    # Подготовка данных для таблицы
    df_raw = pd.DataFrame(all_modules)
    
    # Формирование красивого имени владельца
    df_raw['Владелец'] = df_raw['client'].apply(
        lambda c: f"{c['first_name']} {c['last_name']}" if c else "На складе"
    )

    # Словарь переименования колонок
    column_rename_map = {
        "module_name": "Название модуля",
        "catalogue_index": "Индекс в каталоге",
        "supplier": "Поставщик",
        "ordered": "Заказано",
        "order_date_acc_num": "№ счета / Дата заказа",
        "cost": "Стоимость",
        "price": "Цена",
        "recd": "Получено",
        "pending": "В ожидании",
        "properties": "Характеристики",
        "notes": "Заметки",
    }

    df_processed = df_raw.rename(columns=column_rename_map)

    # Выбор колонок для отображения
    columns_to_show = [
        "Владелец", 
        "Название модуля",
        "Индекс в каталоге",
        "Поставщик",
        "Стоимость",
        "Цена",
        "Заказано",
        "Получено",
        "В ожидании",
        "Заметки",
    ]

    # Отображение таблицы с возможностью выбора
    st.write("Нажмите на строку, чтобы отредактировать модуль.")
    # Проверяем, есть ли нужные колонки в датафрейме (на случай пустых данных)
    final_cols = [c for c in columns_to_show if c in df_processed.columns]
    
    event = st.dataframe(
        df_processed[final_cols], 
        on_select="rerun", 
        selection_mode="single-row", 
        use_container_width=True, 
        hide_index=True
    )
    
    # Логика обработки выбора строки
    selected_rows = event.selection.rows
    if selected_rows:
        selected_index = selected_rows[0]
        # Берем ID из сырого датафрейма, так как порядок строк совпадает
        module_id_selected = df_raw.iloc[selected_index]['module_id']
        
        # Сохраняем ID в сессию и перезагружаем, чтобы открыть форму редактирования
        if st.session_state['editing_module_id'] != module_id_selected:
            st.session_state['editing_module_id'] = module_id_selected
            st.rerun()

    # --- БЛОК 3: ФОРМА РЕДАКТИРОВАНИЯ (ПОЯВЛЯЕТСЯ ПРИ ВЫБОРЕ) ---
    if st.session_state.get('editing_module_id'):
        module_id_to_edit = st.session_state['editing_module_id']
        # Находим полные данные модуля по ID
        selected_module = next((m for m in all_modules if m['module_id'] == module_id_to_edit), None)
        
        if selected_module:
            st.divider()
            st.markdown(f"#### Редактирование модуля: {selected_module.get('module_name', 'Без названия')}")
            
            with st.container(border=True):
                with st.form(f"wh_edit_module_form_{module_id_to_edit}"):
                    # 1. Выбор владельца (включая "На склад")
                    try:
                        clients = fetch_clients(limit=1000)
                        client_map = {"На склад (ничей)": None}
                        client_map.update({f"{c['first_name']} {c['last_name']} ({c.get('external_id', 'No ID')})": c['client_id'] for c in clients})
                        
                        # Определение текущего владельца для установки значения по умолчанию
                        current_client_id = selected_module.get('client_id')
                        
                        # Ищем индекс текущего владельца в списке ключей
                        default_index = 0
                        client_options = list(client_map.keys())
                        
                        if current_client_id:
                            for idx, (name, cid) in enumerate(client_map.items()):
                                if cid == current_client_id:
                                    default_index = idx
                                    break
                        
                        selected_owner_display = st.selectbox("Владелец", options=client_options, index=default_index)
                        new_owner_id = client_map[selected_owner_display]
                        
                    except Exception:
                        new_owner_id = selected_module.get('client_id')
                        st.warning("Не удалось загрузить список клиентов для смены владельца.")

                    # 2. Поля для редактирования данных
                    c1, c2 = st.columns(2)
                    edit_module_name = c1.text_input("Название модуля", value=selected_module.get('module_name', ''))
                    edit_catalogue_index = c1.text_input("Индекс в каталоге", value=selected_module.get('catalogue_index', ''))
                    edit_supplier = c1.text_input("Поставщик", value=selected_module.get('supplier', ''))
                    edit_ordered = c2.text_input("Заказано", value=selected_module.get('ordered', ''))
                    edit_order_date_acc_num = c2.text_input("Номер счета, дата заказа", value=selected_module.get('order_date_acc_num', ''))
                    
                    # Важно: используем float() для number_input
                    edit_cost = c2.number_input("Стоимость", value=float(selected_module.get('cost', 0.0)), min_value=0.0)
                    edit_price = c2.number_input("Цена", value=float(selected_module.get('price', 0.0)), min_value=0.0)
                    
                    c3, c4, c5 = st.columns(3)
                    edit_received_stored = c3.text_input("На складе", value=selected_module.get('received_stored', ''))
                    edit_pending = c4.text_input("В ожидании", value=selected_module.get('pending', ''))
                    edit_recd = c5.text_input("Получено (Recd)", value=selected_module.get('recd', ''))

                    edit_properties = st.text_input("Характеристики", value=selected_module.get('properties', ''))
                    edit_notes = st.text_area("Заметки", value=selected_module.get('notes', ''))

                    # Кнопки действий
                    col_save, col_del = st.columns([1, 1])
                    
                    # Кнопка Сохранить
                    if col_save.form_submit_button("Сохранить изменения", type="primary"):
                        payload = {
                            "client_id": new_owner_id, # Обновляем владельца (или None)
                            "module_name": edit_module_name,
                            "catalogue_index": edit_catalogue_index,
                            "supplier": edit_supplier,
                            "ordered": edit_ordered,
                            "order_date_acc_num": edit_order_date_acc_num,
                            "cost": edit_cost,
                            "price": edit_price,
                            "received_stored": edit_received_stored,
                            "pending": edit_pending,
                            "recd": edit_recd,
                            "properties": edit_properties,
                            "notes": edit_notes,
                        }
                        try:
                            patch_module(module_id_to_edit, payload)
                            st.success("Модуль успешно обновлен!")
                            st.session_state['editing_module_id'] = None # Закрываем форму
                            clear_caches(); st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка обновления: {e}")

                    # Кнопка Удалить
                    if col_del.form_submit_button("Удалить модуль", type="secondary"):
                        try:
                            delete_module(module_id_to_edit)
                            st.success("Модуль удален!")
                            st.session_state['editing_module_id'] = None # Закрываем форму
                            clear_caches(); st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка удаления: {e}")

            # Кнопка отмены редактирования (вне формы)
            if st.button("Отмена / Скрыть форму"):
                st.session_state['editing_module_id'] = None
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

mode = st.sidebar.radio("Меню", ["Клиенты", "Агенты", "Склад", "Добавить клиента", "Добавить агента"])

if mode == "Клиенты":
    clients_page()
elif mode == "Агенты":
    agents_page()
elif mode == "Склад":
    warehouse_page()
elif mode == "Добавить клиента":
    add_client_page()
elif mode == "Добавить агента":
    add_agent_page()