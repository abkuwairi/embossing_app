import streamlit as st
import pandas as pd
import os
import json
import streamlit_authenticator as stauth

# ─── Paths ────────────────────────────────────────────────────────────────────────
data_dir = 'data'
cred_file = os.path.join(data_dir, 'credentials.json')
master_file = os.path.join(data_dir, 'master_data.xlsx')
os.makedirs(data_dir, exist_ok=True)

# ─── Load or Initialize Credentials ───────────────────────────────────────────────
if not os.path.exists(cred_file):
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
                "password": stauth.Hasher(["admin123"]).generate()[0]
            }
        }
    }
    with open(cred_file, 'w') as f:
        json.dump(default, f, indent=4)

credentials = json.load(open(cred_file))

# ─── Prepare Authenticator ────────────────────────────────────────────────────────
authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="embossing_app",
    key="some_random_key_123",
    cookie_expiry_days=1
)

# ─── Login Flow ───────────────────────────────────────────────────────────────────
name, auth_status, username = authenticator.login("Login", "main")

if auth_status == False:  # Fixed comparison
    st.error("اسم المستخدم أو كلمة المرور خاطئة")
    st.stop()
elif auth_status is None:
    st.warning("الرجاء إدخال اسم المستخدم وكلمة المرور")
    st.stop()
else:
    role = credentials["usernames"][username]["role"]
    display_name = name
    authenticator.logout("Logout", "sidebar")
    st.sidebar.success(f"مرحباً {display_name} ({role})")

    if role in ['admin', 'management']:
        st.header('👥 إدارة المستخدمين')
        tabs = st.tabs(['عرض المستخدمين', 'إضافة مستخدم', 'تعديل/حظر'])

        # Tab 1: List Users (unchanged)
        with tabs[0]:
            df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
            df_disp = df_users[['name', 'email', 'phone', 'branch_code', 'branch_name', 'role', 'is_active']]
            st.dataframe(df_disp, use_container_width=True)

        # Tab 2: Add User (unchanged)
        with tabs[1]:
            st.subheader('إضافة مستخدم جديد')
            with st.form('add_user_form'):
                user_id = st.text_input('اسم المستخدم')
                # ... (rest of add user form remains the same)

        # Tab 3: Edit/Deactivate User (FIXED FORM CONTEXT)
        with tabs[2]:
            st.subheader('تعديل/حظر مستخدم')
            with st.form('edit_user_form'):  # Added form context
                user_list = list(credentials['usernames'].keys())
                selected_user = st.selectbox('اختر مستخدم', user_list)
                user_info = credentials['usernames'][selected_user]

                full_name2 = st.text_input('الاسم الكامل', value=user_info['name'])
                email2 = st.text_input('البريد الإلكتروني', value=user_info['email'])
                phone2 = st.text_input('رقم الجوال', value=user_info['phone'])
                branch_code2 = st.text_input('كود الفرع', value=user_info['branch_code'])
                branch_name2 = st.text_input('اسم الفرع', value=user_info['branch_name'])

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
                new_password = st.text_input('كلمة المرور الجديدة', type='password') if change_pwd else None

                if st.form_submit_button('حفظ'):
                    if selected_role2 == 'admin' and role != 'admin':
                        st.error('غير مسموح بتعيين دور إدمن')
                    else:
                        user_info.update({
                            'name': full_name2,
                            'email': email2,
                            'phone': phone2,
                            'branch_code': branch_code2,
                            'branch_name': branch_name2,
                            'role': selected_role2,
                            'is_active': is_active2
                        })
                        if change_pwd and new_password:
                            user_info['password'] = stauth.Hasher([new_password]).generate()[0]
                        with open(cred_file, 'w') as f:
                            json.dump(credentials, f, indent=4)
                        st.success('تم حفظ التعديلات')

    # Rest of the app logic...
