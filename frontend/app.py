import streamlit as st
import utils
import time

# 1. Настройка
st.set_page_config(page_title="CRM System", layout="wide")

# 2. Инициализация сессии
if "token" not in st.session_state:
    st.session_state["token"] = None
    st.session_state["role"] = None
    st.session_state["username"] = None
    st.session_state["user_id"] = None 

# 3. Выход
def logout():
    st.session_state["token"] = None
    st.session_state["role"] = None
    st.session_state["username"] = None
    st.session_state["user_id"] = None
    st.rerun()


# НАВИГАЦИЯ

if not st.session_state["token"]:
    pg = st.navigation([
        st.Page("views/login.py", title="Вход в систему", icon="🔐")
    ])
else:
    # Общие страницы
    pages_list = [
        st.Page("views/Clients.py", title="Клиенты", icon="👥"),
        st.Page("views/Agents.py", title="Агенты", icon="🕵️"),
        st.Page("views/Warehouse.py", title="Склад", icon="📦"),
        # Личный кабинет доступен всем
        st.Page("views/Settings.py", title="Настройки профиля", icon="⚙️"),
    ]

    # Админка
    if str(st.session_state.get("role")).lower() == "admin":
        pages_list.append(st.Page("views/Admin.py", title="Управление пользователями", icon="🛡️"))

    pg = st.navigation({
        "CRM Меню": pages_list
    })

    with st.sidebar:
        st.info(f"👤 **{st.session_state.get('username')}**")
        if st.button("Выйти", use_container_width=True):
            logout()

pg.run()