import streamlit as st
import utils
import time

# 1. Настройка
st.set_page_config(layout="wide", page_title="CRM System")

# ==============================================================================
# 2. ПОЛУЧЕНИЕ ЦВЕТОВ ИЗ CONFIG.TOML
# ==============================================================================
try:
    primary_color = st.get_option("theme.primaryColor")
    background_color = st.get_option("theme.backgroundColor")
    secondary_background_color = st.get_option("theme.secondaryBackgroundColor")
    text_color = st.get_option("theme.textColor")
except:
    primary_color = "#2E8B57"
    background_color = "#FFFFFF"
    secondary_background_color = "#F1F8E9"
    text_color = "#2D3748"

# Внедряем переменные
st.markdown(f"""
<style>
    :root {{
        --prim: {primary_color};
        --bg: {background_color};
        --sec: {secondary_background_color};
        --txt: {text_color};
    }}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. ОСНОВНЫЕ СТИЛИ
# ==============================================================================
st.markdown("""
<style>
    /* Базовая настройка */
    .stApp {
        background: var(--bg) !important;
    }
    
    /* Основной контейнер */
    .main .block-container {
        background: #FFFFFF !important;
        border-radius: 20px !important;
        padding: 2rem !important;
        max-width: 1600px !important;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.08) !important;
        border: 1px solid rgba(0,0,0,0.05) !important;
    }

    /* ===========================
       САЙДБАР
       =========================== */
    section[data-testid="stSidebar"] {
        background-color: var(--prim) !important;
        background-image: linear-gradient(180deg, var(--prim) 0%, rgba(0,0,0,0.2) 100%) !important;
        border-right: 1px solid rgba(0,0,0,0.1);
    }
    
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
        gap: 1rem;
    }

    /* Блок профиля */
    section[data-testid="stSidebar"] [data-testid="stAlert"] {
        background-color: rgba(255, 255, 255, 0.95) !important;
        border: none !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
        padding: 0.5rem !important;
    }

    section[data-testid="stSidebar"] [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
        color: var(--prim) !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        text-align: center;
        margin: 0 !important;
    }
    
    section[data-testid="stSidebar"] [data-testid="stAlert"] svg {
        fill: var(--prim) !important;
    }

    /* Кнопка Выход */
    section[data-testid="stSidebar"] [data-testid="stButton"] button {
        background: transparent !important;
        border: 1px solid rgba(255, 255, 255, 0.6) !important;
        color: #FFFFFF !important;
        width: 100%;
        border-radius: 8px !important;
    }

    section[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
        background: #FFFFFF !important;
        color: var(--prim) !important;
        border-color: #FFFFFF !important;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    
    section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span {
        color: #FFFFFF !important;
    }

    /* ===========================
       ПОЛЯ ВВОДА
       =========================== */
    .stTextInput input, 
    .stNumberInput input,
    .stTextArea textarea,
    .stDateInput input,
    div[data-baseweb="select"] > div {
        background-color: var(--sec) !important;
        color: var(--txt) !important;
        border: 1px solid rgba(0,0,0,0.1) !important;
        border-radius: 8px !important;
    }
    
    div[data-baseweb="select"] span {
        color: var(--txt) !important;
    }
    
    div[data-baseweb="menu"] {
        background-color: #FFFFFF !important;
        border: 1px solid var(--sec) !important;
    }

    /* Фокус */
    .stTextInput input:focus, 
    .stNumberInput input:focus, 
    .stTextArea textarea:focus, 
    .stDateInput input:focus,
    div[data-baseweb="select"] > div:focus-within {
        background-color: #FFFFFF !important;
        border-color: #2D3748 !important;
        box-shadow: 0 0 0 2px rgba(45, 55, 72, 0.2) !important;
    }

    /* ===========================
       ОСТАЛЬНОЙ ДИЗАЙН
       =========================== */
    
    /* H1 - Главный заголовок */
    h1 {
        color: var(--txt) !important;
        font-weight: 800 !important;
        text-align: center;
        background: linear-gradient(135deg, var(--sec), #FFFFFF) !important;
        border: 2px solid #cbd5e1 !important; 
        border-radius: 16px !important;
        padding: 1.5rem !important;
        margin-bottom: 2rem !important;
    }

    /* H2 - Подзаголовки (Имена агентов, разделы) */
    /* ИЗМЕНЕНО: теперь берется var(--txt), а не var(--prim) */
    h2 {
        color: var(--txt) !important; 
        border-left: 5px solid #2D3748 !important;
        padding-left: 15px;
        background: linear-gradient(90deg, var(--sec), transparent);
        font-weight: 600 !important;
    }

    /* Таблицы */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--sec) !important;
        border-radius: 12px !important;
        overflow: hidden;
    }
    [data-testid="stDataFrame"] th {
        background: var(--prim) !important;
        color: #FFFFFF !important;
    }
    [data-testid="stDataFrame"] td {
        background: #FFFFFF !important;
        color: var(--txt) !important;
        border-bottom: 1px solid var(--sec) !important;
    }

    /* Кнопки */
    .stButton > button[kind="primary"] {
        background: var(--prim) !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.15) !important;
    }
    
    .stButton > button[kind="secondary"] {
        background: #FFFFFF !important;
        border: 1px solid var(--prim) !important;
        color: var(--prim) !important;
    }

    /* Карточки */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important;
        border: 1px solid var(--sec) !important;
        border-radius: 16px !important;
        padding: 1.5rem !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05) !important;
    }

    /* Метрики */
    [data-testid="stMetricValue"] {
        color: var(--prim) !important;
    }

    /* ВКЛАДКИ (TABS) */
    .stTabs [data-baseweb="tab-list"] {
        background-color: var(--sec);
        border-radius: 10px;
        padding: 5px;
        gap: 5px;
    }
    
    /* Неактивная вкладка - теперь цвет текста (серый), а не бирюзовый */
    /* ИЗМЕНЕНО: color: var(--txt) */
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 8px;
        color: var(--txt) !important; 
        font-weight: 500;
    }
    
    /* Активная вкладка - остается бирюзовой с белым текстом */
    .stTabs [aria-selected="true"] {
        background-color: #2D3748 !important;
        color: #FFFFFF !important;
    }
</style>
""", unsafe_allow_html=True)


# 4. Инициализация сессии
if "token" not in st.session_state:
    st.session_state["token"] = None
    st.session_state["role"] = None
    st.session_state["username"] = None
    st.session_state["user_id"] = None 

# 5. Выход
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
    pages_list = [
        st.Page("views/Clients.py", title="Клиенты", icon="👥"),
        st.Page("views/Agents.py", title="Агенты", icon="🕵️"),
        st.Page("views/Warehouse.py", title="Склад", icon="📦"),
        st.Page("views/Settings.py", title="Настройки профиля", icon="⚙️"),
    ]

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