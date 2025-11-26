import streamlit as st
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import utils

if not st.session_state.get("token"):
    st.stop()

st.title("⚙️ Настройки профиля")

current_uid = st.session_state.get("user_id")
current_user = st.session_state.get("username")

# БЛОК 1: Смена Логина
with st.container(border=True):
    st.subheader("Изменить логин")
    with st.form("change_login"):
        new_login = st.text_input("Новый логин", value=current_user)
        
        if st.form_submit_button("Сохранить логин"):
            if new_login and new_login != current_user:
                try:
                    utils.patch_user(current_uid, username=new_login)
                    st.session_state["username"] = new_login
                    st.success("Логин обновлен!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {e}")
            elif new_login == current_user:
                st.info("Логин не изменился")
            else:
                st.warning("Логин не может быть пустым")

# БЛОК 2: Смена Пароля
with st.container(border=True):
    st.subheader("Изменить пароль")
    with st.form("change_pass"):
        p1 = st.text_input("Новый пароль", type="password")
        p2 = st.text_input("Повторите пароль", type="password")
        
        if st.form_submit_button("Обновить пароль"):
            if p1 and p2:
                if p1 == p2:
                    try:
                        utils.patch_user(current_uid, password=p1)
                        st.success("Пароль успешно изменен!")
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
                else:
                    st.error("Пароли не совпадают")
            else:
                st.warning("Введите пароль")