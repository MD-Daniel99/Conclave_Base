import streamlit as st
import utils
import time

# 1. Настройка
st.set_page_config(page_title="CRM System", layout="wide")

# В начало app.py, сразу после st.set_page_config
st.markdown("""
<style>
    /* ===== ОСНОВНЫЕ НАСТРОЙКИ ===== */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e7eb 100%);
    }
    
    /* Убираем лишние отступы */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* ===== ЗАГОЛОВКИ ===== */
    h1 {
        color: #5E81AC !important;
        font-size: 2.8rem !important;
        font-weight: 800 !important;
        margin-bottom: 1.5rem !important;
        padding-bottom: 15px;
        border-bottom: 3px solid #88C0D0;
        background: linear-gradient(90deg, #5E81AC, #81A1C1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-align: center;
    }
    
    h2 {
        color: #4C566A !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
        margin-top: 2rem !important;
        padding-left: 15px;
        border-left: 4px solid #5E81AC;
    }
    
    h3 {
        color: #4C566A !important;
        font-size: 1.5rem !important;
        font-weight: 600 !important;
        margin-top: 1.5rem !important;
    }
    
    /* ===== ТАБЛИЦЫ (DATAFRAME) ===== */
    [data-testid="stDataFrame"] {
        border: 1px solid #D8DEE9 !important;
        border-radius: 10px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
    }
    
    /* Заголовки таблиц */
    [data-testid="stDataFrame"] th {
        background: linear-gradient(90deg, #5E81AC, #81A1C1) !important;
        color: white !important;
        font-weight: 600 !important;
        padding: 12px 8px !important;
    }
    
    /* Чередование строк */
    [data-testid="stDataFrame"] tbody tr:nth-child(even) {
        background-color: #F8F9FA !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:hover {
        background-color: rgba(136, 192, 208, 0.1) !important;
    }
    
    /* ===== КНОПКИ ===== */
    .stButton > button {
        background: linear-gradient(90deg, #5E81AC, #81A1C1) !important;
        color: white !important;
        border: none !important;
        padding: 10px 24px !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 4px rgba(94, 129, 172, 0.3) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 8px rgba(94, 129, 172, 0.4) !important;
        background: linear-gradient(90deg, #81A1C1, #5E81AC) !important;
    }
    
    /* Primary кнопки */
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #88C0D0, #8FBCBB) !important;
        box-shadow: 0 2px 4px rgba(136, 192, 208, 0.3) !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(90deg, #8FBCBB, #88C0D0) !important;
        box-shadow: 0 4px 8px rgba(136, 192, 208, 0.4) !important;
    }
    
    /* ===== SIDEBAR ===== */
    section[data-testid="stSidebar"] > div {
        background: linear-gradient(180deg, #ECEFF4 0%, #E5E9F0 100%) !important;
        border-right: 1px solid #D8DEE9 !important;
        padding: 2rem 1rem !important;
    }
    
    /* Элементы в sidebar */
    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        margin: 6px 0;
        background: white !important;
        color: #4C566A !important;
        border: 2px solid #D8DEE9 !important;
        box-shadow: none !important;
    }
    
    section[data-testid="stSidebar"] .stButton > button:hover {
        border-color: #5E81AC !important;
        background: rgba(94, 129, 172, 0.05) !important;
        transform: translateX(5px) !important;
    }
    
    /* ===== КАРТОЧКИ И КОНТЕЙНЕРЫ ===== */
    .stExpander {
        border: 1px solid #D8DEE9 !important;
        border-radius: 10px !important;
        margin-bottom: 1rem !important;
    }
    
    .stExpander summary {
        background: linear-gradient(90deg, #F8F9FA, #FFFFFF) !important;
        border-radius: 10px 10px 0 0 !important;
        padding: 1rem !important;
        font-weight: 600 !important;
        color: #4C566A !important;
    }
    
    /* Формы в expander */
    .stExpander .stForm {
        background: white !important;
        border-radius: 0 0 10px 10px !important;
        padding: 1.5rem !important;
    }
    
    /* ===== ПОЛЯ ВВОДА ===== */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > div,
    .stDateInput > div > div > input,
    .stTextArea > textarea {
        border: 2px solid #D8DEE9 !important;
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stSelectbox > div > div > div:focus,
    .stDateInput > div > div > input:focus,
    .stTextArea > textarea:focus {
        border-color: #5E81AC !important;
        box-shadow: 0 0 0 3px rgba(94, 129, 172, 0.1) !important;
    }
    
    /* ===== РАДИО-КНОПКИ И ЧЕКБОКСЫ ===== */
    .stRadio > div {
        background: white;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #D8DEE9;
    }
    
    .stCheckbox {
        background: white;
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px solid #D8DEE9;
        margin: 4px 0;
    }
    
    /* ===== ВКЛАДКИ (TABS) ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background-color: #F8F9FA;
        padding: 4px;
        border-radius: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 10px 20px !important;
        color: #4C566A !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, #5E81AC, #81A1C1) !important;
        color: white !important;
        box-shadow: 0 2px 4px rgba(94, 129, 172, 0.3) !important;
    }
    
    /* ===== УВЕДОМЛЕНИЯ ===== */
    .stAlert {
        border-radius: 10px !important;
        border-left: 4px solid !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
    }
    
    /* Success */
    .stAlert [data-testid="stMarkdownContainer"]:has(svg[aria-label="success"]) {
        border-left-color: #4CAF50 !important;
        background: linear-gradient(90deg, rgba(76, 175, 80, 0.1), white) !important;
    }
    
    /* Info */
    .stAlert [data-testid="stMarkdownContainer"]:has(svg[aria-label="info"]) {
        border-left-color: #2196F3 !important;
        background: linear-gradient(90deg, rgba(33, 150, 243, 0.1), white) !important;
    }
    
    /* Warning */
    .stAlert [data-testid="stMarkdownContainer"]:has(svg[aria-label="warning"]) {
        border-left-color: #FF9800 !important;
        background: linear-gradient(90deg, rgba(255, 152, 0, 0.1), white) !important;
    }
    
    /* Error */
    .stAlert [data-testid="stMarkdownContainer"]:has(svg[aria-label="error"]) {
        border-left-color: #F44336 !important;
        background: linear-gradient(90deg, rgba(244, 67, 54, 0.1), white) !important;
    }
    
    /* ===== МЕТРИКИ ===== */
    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: #5E81AC !important;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 1rem !important;
        color: #4C566A !important;
        font-weight: 500 !important;
    }
    
    /* ===== РАЗДЕЛИТЕЛИ ===== */
    hr {
        margin: 2rem 0 !important;
        height: 2px !important;
        background: linear-gradient(90deg, transparent, #D8DEE9, transparent) !important;
        border: none !important;
    }
    
    /* ===== СЛАЙДЕР ===== */
    .stSlider > div > div > div {
        background: linear-gradient(90deg, #5E81AC, #81A1C1) !important;
    }
    
    /* ===== ПРОГРЕСС-БАР ===== */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #88C0D0, #8FBCBB) !important;
    }
    
    /* ===== ВЫПАДАЮЩИЕ СПИСКИ (SELECTBOX) ===== */
    [data-baseweb="select"] > div {
        border-radius: 8px !important;
        border: 2px solid #D8DEE9 !important;
    }
    
    /* ===== КАРТОЧКИ В ТАБЛИЦЕ (для Clients, Warehouse и т.д.) ===== */
    /* Создаем эффект карточек для строк таблицы */
    [data-testid="stDataFrame"] td {
        padding: 12px 8px !important;
        border-bottom: 1px solid #ECEFF4 !important;
    }
    
    /* ===== КНОПКИ В ТАБЛИЦАХ ===== */
    .stDataFrame .stButton > button {
        padding: 6px 12px !important;
        font-size: 0.9rem !important;
    }
    
    /* ===== ИКОНКИ ===== */
    h1::before {
        content: "✨ ";
    }
    
    h2::before {
        content: "📌 ";
    }
    
    /* ===== АДАПТИВНОСТЬ ===== */
    @media (max-width: 768px) {
        h1 {
            font-size: 2rem !important;
        }
        
        h2 {
            font-size: 1.5rem !important;
        }
        
        .stButton > button {
            padding: 8px 16px !important;
        }
    }
    
    /* ===== АНИМАЦИИ ===== */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .stDataFrame, .stExpander, .stForm {
        animation: fadeIn 0.5s ease-out;
    }
    
    /* ===== СКРОЛЛБАР ===== */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #F8F9FA;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #88C0D0;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #5E81AC;
    }
</style>
""", unsafe_allow_html=True)


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