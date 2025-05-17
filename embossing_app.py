import streamlit as st
import pandas as pd
import os
import io
import json
import streamlit_authenticator as stauth
from datetime import datetime

# Paths
data_dir = 'data'
cred_file = os.path.join(data_dir, 'credentials.json')
master_file = os.path.join(data_dir, 'master_data.xlsx')

os.makedirs(data_dir, exist_ok=True)

# Default credentials with roles
default_credentials = {
    'usernames': {
        'admin_user': {'name':'Admin','password':None,'email':'admin@example.com','phone':'','branch_code':'','branch_name':'','is_active':True,'role':'admin'},
        'branch101': {'name':'Branch101','password':None,'email':'','phone':'','branch_code':'101','branch_name':'Branch 101','is_active':True,'role':'viewer'},
        'branch102': {'name':'Branch102','password':None,'email':'','phone':'','branch_code':'102','branch_name':'Branch 102','is_active':True,'role':'viewer'}
    }
}
plain_defaults = {'admin_user':'admin123','branch101':'b101','branch102':'b102'}

# Load or initialize credentials
def load_credentials():
    if os.path.exists(cred_file):
        with open(cred_file,'r') as f:
            return json.load(f)
    creds = default_credentials
    # hash default passwords
    for user,data in creds['usernames'].items():
        pwd = plain_defaults.get(user,'password123')
        data['password'] = stauth.Hasher([pwd]).generate()[0]
    with open(cred_file,'w') as f:
        json.dump(creds,f,indent=4)
    return creds

credentials = load_credentials()

# Initialize authenticator with active users
active_users = {
    user: {'name': info['name'], 'password': info['password']}
    for user, info in credentials['usernames'].items()
    if info.get('is_active')
}
authenticator = stauth.Authenticate(
    {'usernames': active_users},
    cookie_name='embossing_app_cookie',
    key='abcd1234abcd1234abcd1234abcd1234',
    cookie_expiry_days=1
)

# Login UI
name, auth_status, username = authenticator.login('🔐 تسجيل الدخول', 'main')
if auth_status is False:
    st.error('❌ اسم المستخدم أو كلمة المرور غير صحيحة')
elif auth_status is None:
    st.warning('👈 الرجاء تسجيل الدخول للاستمرار')
else:
    st.sidebar.success(f'مرحباً {name}')
    authenticator.logout('تسجيل الخروج', 'sidebar')

    role = credentials['usernames'][username].get('role', 'viewer')
    st.title('📋 نظام تحميل ومتابعة بطاقات Embossing')

    # User management for admin/management\ n    if role in ['admin', 'management']:
        st.header('👥 إدارة المستخدمين')
        tabs = st.tabs(['عرض المستخدمين', 'إضافة مستخدم', 'تعديل/حظر'])
        # Tab: List Users
        with tabs[0]:
            df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
            df_disp = df_users[['name', 'email', 'phone', 'branch_code', 'branch_name', 'role', 'is_active']]
            df_disp.index.name = 'username'
            st.dataframe(df_disp)
        # Tab: Add User
        with tabs[1]:
            st.subheader('إضافة مستخدم جديد')
            with st.form('add_form'):
                user_id = st.text_input('Username')
                full_name = st.text_input('الاسم الكامل')
                email = st.text_input('البريد الإلكتروني')
                phone = st.text_input('رقم الهاتف')
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
                        with open(cred_file, 'w') as f:
                            json.dump(credentials, f, indent=4)
                        st.success(f'تم إضافة المستخدم {user_id}')
        # Tab: Edit User
        with tabs[2]:
            st.subheader('تعديل/حظر مستخدم')
            user_list = list(credentials['usernames'].keys())
            selected_user = st.selectbox('اختر مستخدم', user_list)
            user_info = credentials['usernames'][selected_user]
            with st.form('edit_form'):
                full_name2 = st.text_input('الاسم الكامل', value=user_info['name'])
                email2 = st.text_input('البريد الإلكتروني', value=user_info['email'])
                phone2 = st.text_input('رقم الهاتف', value=user_info['phone'])
                branch_code2 = st.text_input('كود الفرع', value=user_info['branch_code'])
                branch_name2 = st.text_input('اسم الفرع', value=user_info['branch_name'])
                is_active2 = st.checkbox('مفعل', value=user_info['is_active'])
                role_options2 = ['viewer', 'uploader']
                if role == 'admin':
                    role_options2 = ['admin', 'management'] + role_options2
                selected_role2 = st.selectbox('نوع المستخدم', role_options2, index=role_options2.index(user_info['role']))
                change_pwd = st.checkbox('تغيير كلمة المرور')
                if change_pwd:
                    new_password = st.text_input('كلمة المرور الجديدة', type='password')
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
                        credentials['usernames'][selected_user] = user_info
                        with open(cred_file, 'w') as f:
                            json.dump(credentials, f, indent=4)
                        st.success('تم حفظ التعديلات')

    # Permissions
auth_upload = role in ['admin', 'management', 'uploader']
auth_download = role in ['admin', 'management', 'uploader']

# Upload Section
if auth_upload:
    file = st.file_uploader('📁 رفع تقرير البطاقات', type=['xlsx'])
    if file:
        try:
            df_new = pd.read_excel(file, dtype=str)
            df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
            if os.path.exists(master_file):
                df_old = pd.read_excel(master_file, dtype=str)
                df_combined = pd.concat([df_old, df_new], ignore_index=True)
            else:
                df_combined = df_new
            df_combined.to_excel(master_file, index=False)
            st.success('✅ تم تحديث قاعدة البيانات بنجاح.')
        except Exception as e:
            st.error(f'❌ خطأ أثناء رفع الملف: {e}')

# View/Download Section
if os.path.exists(master_file):
    df_all = pd.read_excel(master_file, dtype=str)
    # Normalize column names by stripping whitespace
    df_all.columns = df_all.columns.str.strip()
    if 'Delivery Branch Code' not in df_all.columns:
        st.error(f"عمود 'Delivery Branch Code' غير موجود. الأعمدة المتاحة: {list(df_all.columns)}")
    else:
        df_all['Delivery Branch Code'] = df_all['Delivery Branch Code'].str.strip()
        df_all = df_all.drop_duplicates(subset=['Unmasked Card Number', 'Account Number'])
        df_all['Issuance Date'] = pd.to_datetime(df_all['Issuance Date'], errors='coerce', dayfirst=True)

        search_term = st.text_input('🔍 بحث')
        if search_term:
            df_all = df_all[df_all.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)]

        if not df_all['Issuance Date'].isna().all():
            min_date, max_date = df_all['Issuance Date'].min(), df_all['Issuance Date'].max()
            start_date = st.date_input('📆 من تاريخ', min_value=min_date, max_value=max_date, value=min_date)
            end_date = st.date_input('📆 إلى تاريخ', min_value=min_date, max_value=max_date, value=max_date)
            df_all = df_all[(df_all['Issuance Date'] >= start_date) & (df_all['Issuance Date'] <= end_date)]

        for branch in sorted(df_all['Delivery Branch Code'].unique()):
            df_branch = df_all[df_all['Delivery Branch Code'] == branch]
            with st.expander(f'📌 فرع {branch}'):
                st.dataframe(df_branch, use_container_width=True)
                if auth_download:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_branch.to_excel(writer, index=False, sheet_name='Sheet1')
                    buffer.seek(0)
                    st.download_button(f'⬇️ تحميل فرع {branch}', buffer, f'branch_{branch}.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
else:
    st.info('ℹ️ لا توجد بيانات بعد.')
