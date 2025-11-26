import streamlit as st
import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import utils

# --- AUTH CHECK ---
if not st.session_state.get("token"):
    st.stop()

# Проверка роли (Только админ может видеть это)
user_role = str(st.session_state.get("role", "")).lower()
if user_role != "admin":
    st.error("⛔ Доступ запрещен. Эта страница только для Администраторов.")
    st.stop()

# --- STATE ---
if "adm_active_id" not in st.session_state:
    st.session_state.adm_active_id = None

def reset_adm():
    st.session_state.adm_active_id = None
    st.rerun()

st.title("🛡️ Управление пользователями")

# ==========================================
# LIST MODE
# ==========================================
if st.session_state.adm_active_id is None:
    
    try:
        users = utils.get_users()
    except Exception as e:
        st.error(f"Ошибка: {e}")
        users = []

    if users:
        # Подготовка для таблицы
        rows = []
        for u in users:
            rows.append({
                "ID": u["user_id"],
                "Login": u["username"],
                "Role": u["role"],
                "Active": "✅" if u["is_active"] else "❌",
                "Created": u["created_at"]
            })
        
        df = pd.DataFrame(rows)
        
        st.info("Выберите пользователя в таблице для редактирования прав.")
        
        event = st.dataframe(
            df, 
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun"
        )
        
        if event.selection.rows:
            idx = event.selection.rows[0]
            st.session_state.adm_active_id = df.iloc[idx]["ID"]
            st.rerun()
            
    else:
        st.warning("Пользователей нет.")

    # --- CREATE NEW USER ---
    st.divider()
    with st.expander("➕ Зарегистрировать нового пользователя"):
        with st.form("admin_reg"):
            c1, c2 = st.columns(2)
            u_name = c1.text_input("Логин *")
            u_pass = c2.text_input("Пароль *", type="password")
            u_role = st.selectbox("Роль", ["user", "admin"])
            
            if st.form_submit_button("Зарегистрировать"):
                if u_name and u_pass:
                    try:
                        utils.register_user(u_name, u_pass, role=u_role)
                        st.success(f"Пользователь {u_name} создан!")
                        utils.clear_caches()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
                else:
                    st.warning("Заполните логин и пароль")

# ==========================================
# EDIT MODE
# ==========================================
else:
    uid = st.session_state.adm_active_id
    
    if st.button("⬅️ Назад"):
        reset_adm()
        
    # Ищем пользователя в списке
    users = utils.get_users()
    target_user = next((u for u in users if u['user_id'] == uid), None)
    
    if not target_user:
        st.error("Пользователь не найден.")
        if st.button("Сброс"): reset_adm()
        st.stop()

    st.subheader(f"Редактирование: {target_user['username']}")
    
    # --- ЗАЩИТА ОТ ИЗМЕНЕНИЯ СЕБЯ ---
    current_username = st.session_state.get("username")
    is_self = (target_user['username'] == current_username)

    with st.form("edit_user"):
        c1, c2 = st.columns(2)
        
        # Редактирование роли
        role_opts = ["user", "admin"]
        curr_role_idx = role_opts.index(target_user['role']) if target_user['role'] in role_opts else 0
        
        # Блокируем выбор, если это мы сами
        new_role = c1.selectbox("Роль", role_opts, index=curr_role_idx, disabled=is_self)
        if is_self:
            c1.caption("⚠️ Нельзя менять свою роль")
        
        # Редактирование статуса (Блокировка)
        is_active = c2.checkbox("Активен (Может входить в систему)", value=target_user['is_active'], disabled=is_self)
        if is_self:
            c2.caption("⚠️ Нельзя заблокировать себя")
        
        if st.form_submit_button("Сохранить изменения"):
            try:
                # Если редактируем себя, шлем None, чтобы бэкенд не менял эти поля
                role_payload = new_role if not is_self else None
                active_payload = is_active if not is_self else None
                
                utils.patch_user(uid, role=role_payload, is_active=active_payload)
                st.success("Права обновлены!")
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка: {e}")
                
    st.divider()
    
    # Кнопка удаления
    if is_self:
        st.warning("⚠️ Вы не можете удалить собственный аккаунт.")
        st.button("🗑️ Удалить пользователя", disabled=True)
    else:
        if st.button("🗑️ Удалить пользователя", type="primary"):
            try:
                utils.delete_user(uid)
                st.success("Пользователь удален.")
                reset_adm()
            except Exception as e:
                st.error(f"Ошибка удаления: {e}")