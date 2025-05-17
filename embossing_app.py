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

# Load credentials with UTF-8 encoding
with open(cred_file, 'r', encoding='utf-8') as f:
    credentials = json.load(f)

# ─── Prepare Authenticator ────────────────────────────────────────────────────────
authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="embossing_app",
    key="some_random_key_123",
    cookie_expiry_days=1
)

# ─── Login Flow ───────────────────────────────────────────────────────────────────
name, auth_status, username = authenticator.login("Login", "main")

if auth_status == False:
    st.error("اسم المستخدم أو كلمة المرور خاطئة")
    st.stop()
elif auth_status is None:
    st.warning("الرجاء إدخال اسم المستخدم وكلمة المرور")
    st.stop()
else:
    role = credentials["usernames"][username].get("role", "viewer")
    display_name = name
    authenticator.logout("Logout", "sidebar")
    st.sidebar.success(f"مرحباً {display_name} ({role})")

    if role in ['admin', 'management']:
        st.header('👥 إدارة المستخدمين')
        tabs = st.tabs(['عرض المستخدمين', 'إضافة مستخدم', 'تعديل/حظر'])

        # ─── Tab 1: List Users ────────────────────────────────────────────────────
        with tabs[0]:
            # Create DataFrame with guaranteed columns
            required_columns = ['name', 'email', 'phone', 'branch_code', 'branch_name', 'role', 'is_active']
            
            df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
            
            # Add missing columns with empty values
            for col in required_columns:
                if col not in df_users.columns:
                    df_users[col] = ""
            
            df_disp = df_users[required_columns]
            df_disp.index.name = 'username'
            st.dataframe(df_disp, use_container_width=True)

        # ─── Tab 2: Add User ─────────────────────────────────────────────────────
        with tabs[1]:
            st.subheader('إضافة مستخدم جديد')
            with st.form('add_user_form'):
                user_id = st.text_input('اسم المستخدم')
                full_name = st.text_input('الاسم الكامل')
                email = st.text_input('البريد الإلكتروني')
                phone = st.text_input('رقم الجوال')
                branch_code = st.text_input('كود الفرع')
                branch_name = st.text_input('اسم الفرع')
                password = st.text_input('كلمة المرور', type='password')
                is_active = st.checkbox('مفعل', value=True)

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
                            'name': full_name,
                            'email': email,
                            'phone': phone,
                            'branch_code': branch_code,
                            'branch_name': branch_name,
                            'role': selected_role,
                            'is_active': is_active,
                            'password': stauth.Hasher([password]).generate()[0]
                        }
                        with open(cred_file, 'w', encoding='utf-8') as f:
                            json.dump(credentials, f, indent=4, ensure_ascii=False)
                        st.success(f'تم إضافة المستخدم {user_id}')

        # ─── Tab 3: Edit/Deactivate User ──────────────────────────────────────────
        with tabs[2]:
            st.subheader('تعديل/حظر مستخدم')
            with st.form('edit_user_form'):
                user_list = list(credentials['usernames'].keys())
                selected_user = st.selectbox('اختر مستخدم', user_list)
                user_info = credentials['usernames'][selected_user]

                # Safe field access with defaults
                full_name2 = st.text_input('الاسم الكامل', value=user_info.get('name', ''))
                email2 = st.text_input('البريد الإلكتروني', value=user_info.get('email', ''))
                phone2 = st.text_input('رقم الجوال', value=user_info.get('phone', ''))
                branch_code2 = st.text_input('كود الفرع', value=user_info.get('branch_code', ''))
                branch_name2 = st.text_input('اسم الفرع', value=user_info.get('branch_name', ''))

                role_options2 = ['viewer', 'uploader']
                if role == 'admin':
                    role_options2 = ['admin', 'management'] + role_options2
                
                current_role = user_info.get('role', 'viewer')
                selected_role2 = st.selectbox(
                    'نوع المستخدم',
                    role_options2,
                    index=role_options2.index(current_role) if current_role in role_options2 else 0
                )

                is_active2 = st.checkbox('مفعل', value=user_info.get('is_active', True))
                change_pwd = st.checkbox('تغيير كلمة المرور')
                new_password = st.text_input('كلمة المرور الجديدة', type='password') if change_pwd else None

                if st.form_submit_button('حفظ'):
                    if selected_role2 == 'admin' and role != 'admin':
                        st.error('غير مسموح بتعيين دور إدمن')
                    else:
                        # Update user info with fallbacks
                        update_data = {
                            'name': full_name2,
                            'email': email2,
                            'phone': phone2,
                            'branch_code': branch_code2,
                            'branch_name': branch_name2,
                            'role': selected_role2,
                            'is_active': is_active2
                        }
                        
                        # Preserve existing fields not in form
                        user_info.update({k: v for k, v in update_data.items() if v})
                        
                        if change_pwd and new_password:
                            user_info['password'] = stauth.Hasher([new_password]).generate()[0]
                        
                        with open(cred_file, 'w', encoding='utf-8') as f:
                            json.dump(credentials, f, indent=4, ensure_ascii=False)
                        st.success('تم حفظ التعديلات')

    # ─── Rest of Application Logic ────────────────────────────────────────────────
    st.header("التطبيق الرئيسي")
    # Add your main application content here
