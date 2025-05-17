import streamlit as st
import pandas as pd
import os
import json
import streamlit_authenticator as stauth
from datetime import datetime

# ─── Paths ────────────────────────────────────────────────────────────────────────

data_dir    = 'data'
cred_file   = os.path.join(data_dir, 'credentials.json')
master_file = os.path.join(data_dir, 'master_data.xlsx')

os.makedirs(data_dir, exist_ok=True)

# ─── Load or Initialize Credentials ───────────────────────────────────────────────
if not os.path.exists(cred_file):
    # first run: write a minimal default
    default = {
        "usernames": {
            "admin": {
                "name": "Administrator",
                "email": "admin@bank.com",
                "phone": "",
                "branch_code": "",
                "branch_name": "",
                "role": "admin",
                "is_active": True,
                # generate a one-off password hash for 'admin123'
                "password": stauth.Hasher(["admin123"]).generate()[0]
            }
        }
        # no top-level hashed_passwords key
    }
    with open(cred_file, 'w') as f:
        json.dump(default, f, indent=4)

credentials = json.load(open(cred_file))

# ─── Prepare Authenticator ─────────────────────────────────────────────────────────
# Build lists aligned: usernames, display names, and hashed passwords
user_list = list(credentials.get("usernames", {}).keys())
names = [credentials["usernames"][user].get("name", user) for user in user_list]
hashed_passwords = [credentials["usernames"][user].get("password", "") for user in user_list]

authenticator = stauth.Authenticate(
    names,
    user_list,
    hashed_passwords,
    cookie_name="embossing_app",
    key="some_random_key_123",
    cookie_expiry_days=1
)

# ─── Login Flow ─────────────────────────────────────────────────────────────────────
name, auth_status, role = authenticator.login("Login", "main")

if auth_status is False:
    st.error("اسم المستخدم أو كلمة المرور خاطئة")
    st.stop()
elif auth_status is None:
    st.warning("الرجاء إدخال اسم المستخدم وكلمة المرور")
    st.stop()
else:
    authenticator.logout("Logout", "sidebar")
    st.sidebar.success(f"مرحباً {name} ({role})")

    # ─── User management for admin/management ────────────────────────────────────
    if role in ['admin', 'management']:
        st.header('👥 إدارة المستخدمين')
        tabs = st.tabs(['عرض المستخدمين', 'إضافة مستخدم', 'تعديل/حظر'])

        # Tab: List Users
        with tabs[0]:
            df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
            df_disp  = df_users[['name', 'email', 'phone', 'branch_code', 'branch_name', 'role', 'is_active']]
            df_disp.index.name = 'username'
            st.dataframe(df_disp, use_container_width=True)

        # Tab: Add User
        with tabs[1]:
            st.subheader('إضافة مستخدم جديد')
            with st.form('add_user_form'):
                user_id     = st.text_input('اسم المستخدم')
                full_name   = st.text_input('الاسم الكامل')
                email       = st.text_input('البريد الإلكتروني')
                phone       = st.text_input('رقم الجوال')
                branch_code = st.text_input('كود الفرع')
                branch_name = st.text_input('اسم الفرع')
                password    = st.text_input('كلمة المرور', type='password')
                is_active   = st.checkbox('مفعل', value=True)

                role_options = ['viewer', 'uploader']
                if role == 'admin':
                    role_options = ['admin', 'management'] + role_options
                selected_role = st.selectbox('نوع المستخدم', role_options)

                if st.form_submit_button('إضافة'):
                    if user_id in credentials['usernames']:
                        st.error('المستخدم موجود بالفعل')
                    elif selected_role == 'admin' and role != 'admin':
                        st.error('غير مسموح بإنشاء مستخدم إدمن')
                    else:
                        credentials['usernames'][user_id] = {
                            'name':        full_name,
                            'email':       email,
                            'phone':       phone,
                            'branch_code': branch_code,
                            'branch_name': branch_name,
                            'role':        selected_role,
                            'is_active':   is_active,
                            'password':    stauth.Hasher([password]).generate()[0]
                        }
                        with open(cred_file, 'w') as f:
                            json.dump(credentials, f, indent=4)
                        st.success(f'تم إضافة المستخدم {user_id}')

        # Tab: Edit/Deactivate User
        with tabs[2]:
            st.subheader('تعديل/حظر مستخدم')
            user_list     = list(credentials['usernames'].keys())
            selected_user = st.selectbox('اختر مستخدم', user_list)
            user_info     = credentials['usernames'][selected_user]

            full_name2   = st.text_input('الاسم الكامل',   value=user_info['name'])
            email2       = st.text_input('البريد الإلكتروني', value=user_info['email'])
            phone2       = st.text_input('رقم الجوال',     value=user_info['phone'])
            branch_code2 = st.text_input('كود الفرع',      value=user_info['branch_code'])
            branch_name2 = st.text_input('اسم الفرع',      value=user_info['branch_name'])

            role_options2 = ['viewer', 'uploader']
            if role == 'admin':
                role_options2 = ['admin', 'management'] + role_options2
            selected_role2 = st.selectbox(
                'نوع المستخدم',
                role_options2,
                index=role_options2.index(user_info['role'])
            )

            is_active2 = st.checkbox('مفعل', value=user_info.get('is_active', True))
            change_pwd = st.checkbox('تغيير كلمة المرور')
            if change_pwd:
                new_password = st.text_input('كلمة المرور الجديدة', type='password')

            if st.form_submit_button('حفظ'):
                if selected_role2 == 'admin' and role != 'admin':
                    st.error('غير مسموح بتعيين دور إدمن')
                else:
                    user_info.update({
                        'name':        full_name2,
                        'email':       email2,
                        'phone':       phone2,
                        'branch_code': branch_code2,
                        'branch_name': branch_name2,
                        'role':        selected_role2,
                        'is_active':   is_active2
                    })
                    if change_pwd and new_password:
                        user_info['password'] = stauth.Hasher([new_password]).generate()[0]
                    credentials['usernames'][selected_user] = user_info
                    with open(cred_file, 'w') as f:
                        json.dump(credentials, f, indent=4)
                    st.success('تم حفظ التعديلات')

    # ─── Permissions & the rest of your app’s logic ──────────────────────────────
    auth_upload   = role in ['admin', 'management', 'uploader']
    auth_download = True  # or role in [...]  
    # ←── INSERT your existing data-loading, reporting, download, search, etc. here ─→
