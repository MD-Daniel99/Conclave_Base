import os
import requests
import streamlit as st
from datetime import datetime, date
from typing import List, Dict, Any, Optional


# --- CONFIG ---
def get_secret(key: str, default=None):
    v = os.environ.get(key)
    if v: return v
    try: return st.secrets.get(key, default)
    except: return default

API_BASE = get_secret("API_BASE", "http://127.0.0.1:8000")

# --- ERROR HANDLER ---
def handle_request(method, url, **kwargs):
    """Обертка для запросов с выводом понятной ошибки"""
    try:
        resp = requests.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}
    except requests.exceptions.HTTPError as e:
        # Пытаемся достать текст ошибки от сервера (FastAPI detail)
        try:
            error_detail = e.response.json().get("detail", e.response.text)
        except:
            error_detail = e.response.text
        
        #logger.error(f"HTTP error: {e}")
        #raise APIException("Ошибка сервера")
        
        # Показываем ошибку в UI
        st.error(f"Ошибка сервера ({e.response.status_code}): {error_detail}")
        raise e # Пробрасываем дальше, чтобы остановить выполнение
    except Exception as e:
        st.error(f"Ошибка соединения: {e}")
        raise e

# --- AUTH ---
def login_user(username, password):
    return handle_request("POST", f"{API_BASE}/auth/login", json={"username": username, "password": password})

def register_user(username, password, role="user"):
    return handle_request("POST", f"{API_BASE}/auth/register", json={"username": username, "password": password, "role": role})

def get_users():
    return handle_request("GET", f"{API_BASE}/auth/users")

def patch_user(user_id, role=None, is_active=None, username=None, password=None):
    payload = {}
    if role: payload["role"] = role
    if is_active is not None: payload["is_active"] = is_active
    if username: payload["username"] = username
    if password: payload["password"] = password
    
    handle_request("PATCH", f"{API_BASE}/auth/users/{user_id}", json=payload, headers=get_headers())
    st.cache_data.clear()

def delete_user(user_id):
    handle_request("DELETE", f"{API_BASE}/auth/users/{user_id}", headers=get_headers())
    st.cache_data.clear()

# --- HELPERS ---
def get_headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}

def clear_caches():
    st.cache_data.clear()

def safe_iso_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str: return None
    try: return date.fromisoformat(date_str)
    except: return None

# --- API WRAPPERS ---

# CLIENTS
@st.cache_data(ttl=60)
def fetch_clients(skip=0, limit=50, q=None, status=None, agent_id=None, current_stage=None):
    params = {"skip": skip, "limit": limit}
    if q: params["q"] = q
    if status: params["status"] = status
    if agent_id: params["agent_id"] = agent_id
    if current_stage: params["current_stage"] = current_stage
    resp = requests.get(f"{API_BASE}/clients/", params=params, headers=get_headers())
    resp.raise_for_status()
    return resp.json()

@st.cache_data(ttl=60)
def fetch_client_detail(client_id: str):
    resp = requests.get(f"{API_BASE}/clients/{client_id}", headers=get_headers())
    resp.raise_for_status()
    return resp.json()

def create_client(payload):
    handle_request("POST", f"{API_BASE}/clients/", json=payload, headers=get_headers())
    st.cache_data.clear()

def patch_client(client_id, payload):
    handle_request("PATCH", f"{API_BASE}/clients/{client_id}", json=payload, headers=get_headers())
    st.cache_data.clear()

def delete_client(client_id):
    handle_request("DELETE", f"{API_BASE}/clients/{client_id}", headers=get_headers())
    st.cache_data.clear()

# AGENTS
@st.cache_data(ttl=300)
def fetch_agents(skip=0, limit=50, q=None):
    params = {"skip": skip, "limit": limit, "q": q}
    resp = requests.get(f"{API_BASE}/agents/", params=params, headers=get_headers())
    resp.raise_for_status()
    return resp.json()

@st.cache_data(ttl=300)
def fetch_agent_detail(agent_id):
    resp = requests.get(f"{API_BASE}/agents/{agent_id}", headers=get_headers())
    resp.raise_for_status()
    return resp.json()

def create_agent(payload):
    handle_request("POST", f"{API_BASE}/agents/", json=payload, headers=get_headers())
    st.cache_data.clear()

def patch_agent(agent_id, payload):
    handle_request("PATCH", f"{API_BASE}/agents/{agent_id}", json=payload, headers=get_headers())
    st.cache_data.clear()

def delete_agent(agent_id):
    handle_request("DELETE", f"{API_BASE}/agents/{agent_id}", headers=get_headers())
    st.cache_data.clear()

# MODULES
@st.cache_data(ttl=60)
def fetch_modules(skip=0, limit=100, q=None, supplier=None, client_id=None):
    params = {"skip": skip, "limit": limit}
    if q: params["q"] = q
    if supplier: params["supplier"] = supplier
    if client_id: params["client_id"] = client_id
    resp = requests.get(f"{API_BASE}/modules/", params=params, headers=get_headers())
    resp.raise_for_status()
    return resp.json()

def fetch_module_detail(module_id):
    return handle_request("GET", f"{API_BASE}/modules/{module_id}", headers=get_headers())

def create_module(payload):
    handle_request("POST", f"{API_BASE}/modules/", json=payload, headers=get_headers())
    st.cache_data.clear()

def patch_module(module_id, payload):
    handle_request("PATCH", f"{API_BASE}/modules/{module_id}", json=payload, headers=get_headers())
    st.cache_data.clear()

def delete_module(module_id):
    handle_request("DELETE", f"{API_BASE}/modules/{module_id}", headers=get_headers())
    st.cache_data.clear()

# REFS
@st.cache_data(ttl=300)
def fetch_statuses():
    return handle_request("GET", f"{API_BASE}/status/", headers=get_headers())

@st.cache_data(ttl=300)
def fetch_stages():
    return handle_request("GET", f"{API_BASE}/stages/", headers=get_headers())

# DOCS
def post_passport(cid, pl):
    handle_request("POST", f"{API_BASE}/clients/{cid}/passports", json=pl, headers=get_headers())
    st.cache_data.clear()

def patch_passport(pid, pl):
    handle_request("PATCH", f"{API_BASE}/passports/{pid}", json=pl, headers=get_headers())
    st.cache_data.clear()

def delete_passport(pid):
    handle_request("DELETE", f"{API_BASE}/passports/{pid}", headers=get_headers())
    st.cache_data.clear()

def post_snils(cid, pl):
    handle_request("POST", f"{API_BASE}/clients/{cid}/snils", json=pl, headers=get_headers())
    st.cache_data.clear()

def patch_snils(sid, pl):
    handle_request("PATCH", f"{API_BASE}/snils/{sid}", json=pl, headers=get_headers())
    st.cache_data.clear()

def delete_snils(sid):
    handle_request("DELETE", f"{API_BASE}/snils/{sid}", headers=get_headers())
    st.cache_data.clear()

def add_phone(cid, num):
    handle_request("POST", f"{API_BASE}/clients/{cid}/phones", json={"number": num}, headers=get_headers())
    st.cache_data.clear()

def patch_phone(pid, pl):
    handle_request("PATCH", f"{API_BASE}/phones/{pid}", json=pl, headers=get_headers())
    st.cache_data.clear()

def delete_phone(pid):
    handle_request("DELETE", f"{API_BASE}/phones/{pid}", headers=get_headers())
    st.cache_data.clear()

# --- Documents API ---
def upload_client_file(client_id, file_obj):
    # Для отправки файлов requests использует параметр 'files'
    # file_obj - это объект BytesIO от Streamlit
    files = {"file": (file_obj.name, file_obj, file_obj.type)}
    resp = requests.post(f"{API_BASE}/documents/clients/{client_id}/upload", files=files, headers=get_headers())
    resp.raise_for_status()
    st.cache_data.clear()

def fetch_client_files(client_id):
    return handle_request("GET", f"{API_BASE}/documents/clients/{client_id}/list", headers=get_headers())

def delete_file(document_id):
    handle_request("DELETE", f"{API_BASE}/documents/{document_id}", headers=get_headers())
    st.cache_data.clear()

# Функция для получения прямой ссылки (для скачивания)
def get_download_url(document_id):
    return f"{API_BASE}/documents/download/{document_id}"

def generate_contract(client_id, payload):
    handle_request(
        "POST", 
        f"{API_BASE}/documents/clients/{client_id}/generate_contract", 
        json=payload, 
        headers=get_headers()
    )
    st.cache_data.clear()

# --- REFERENCES ---
@st.cache_data(ttl=60)
def get_ref_prosthesis():
    return handle_request("GET", f"{API_BASE}/references/prosthesis", headers=get_headers())

def add_ref_prosthesis(name):
    handle_request("POST", f"{API_BASE}/references/prosthesis", json={"name": name}, headers=get_headers())
    st.cache_data.clear()

def delete_ref_prosthesis(rid):
    get_ref_prosthesis.clear()
    handle_request("DELETE", f"{API_BASE}/references/prosthesis/{rid}", headers=get_headers())

@st.cache_data(ttl=60)
def get_ref_tsr():
    return handle_request("GET", f"{API_BASE}/references/tsr", headers=get_headers())

def add_ref_tsr(text):
    handle_request("POST", f"{API_BASE}/references/tsr", json={"full_tsr_code": text}, headers=get_headers())
    st.cache_data.clear()

def delete_ref_tsr(rid):
    get_ref_tsr.clear()
    handle_request("DELETE", f"{API_BASE}/references/tsr/{rid}", headers=get_headers())

# --- MODULE NAME INDEX ---
@st.cache_data(ttl=60)
def get_ref_module_name_index():
    return handle_request("GET", f"{API_BASE}/references/name_index", headers=get_headers())

def add_ref_module_name_index(name_index: str):
    handle_request("POST", f"{API_BASE}/references/name_index", json={"name_index": name_index}, headers=get_headers())
    st.cache_data.clear()

def delete_ref_module_name_index(name_index_id: str):
    get_ref_module_name_index.clear()
    handle_request("DELETE", f"{API_BASE}/references/name_index/{name_index_id}", headers=get_headers())
