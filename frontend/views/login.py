import streamlit as st
import utils
import time

def show_login_page():
    st.header("🔐 Вход в систему")

    with st.form("login_form"):
        username = st.text_input("Имя пользователя", key="login_user")
        password = st.text_input("Пароль", type="password", key="login_pass")
        submit = st.form_submit_button("Войти", use_container_width=True)
        
        if submit:
            try:
                data = utils.login_user(username, password)
                    
                # Сохраняем данные
                st.session_state["token"] = data["access_token"]
                st.session_state["role"] = data["role"]
                st.session_state["username"] = data["username"]
                st.session_state["user_id"] = data["user_id"] # <--- ВАЖНО
                
                st.success("Вход выполнен!")
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка входа: {e}")

show_login_page()