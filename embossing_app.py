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

# Ensure data directory exists
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
    for user, data in creds['usernames'].items():
        pwd = plain_defaults.get(user, 'password123')
        data['password'] = stauth.Hasher([pwd]).generate()[0]
    with open(cred_file, 'w') as f:
        json.dump(creds, f, indent=4)
    return creds

credentials = load_credentials()

# Prepare authenticator
active_users = {
    u: {'name': info['name'], 'password': info['password']}
    for u, info in credentials['usernames'].items()
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
    st.sidebar.success(f"مرحباً {credentials['usernames'][username]['name']}")
    authenticator.logout('تسجيل الخروج', 'sidebar')

    # Determine role and permissions
    role = credentials['usernames'][username].get('role', 'viewer')
    can_up = role in ['admin', 'management', 'uploader']
    can_dn = role in ['admin', 'management', 'uploader']

    # Display large logo and new title
    if os.path.exists('logo.png'):
        st.image('logo.png', use_container_width=True)
    st.title('🚀 منظومة إدارة البطاقات')

    # Main tabs: admin and management get user management
    if role in ['admin', 'management']:
        main_tabs = st.tabs(['👥 إدارة المستخدمين', '🗂️ تقارير البطاقات'])
        um_tab, report_tab = main_tabs
    else:
        report_tab = st.tabs(['🗂️ تقارير البطاقات'])[0]
        um_tab = None

    # User Management (admin and management)
    if um_tab:
        with um_tab:
            st.header('👥 إدارة المستخدمين')
            tabs = st.tabs(['عرض المستخدمين', 'إضافة مستخدم', 'تعديل/حظر'])
            # List users
            with tabs[0]:
                df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
                df_disp = df_users[['name', 'email', 'phone', 'branch_code', 'branch_name', 'role', 'is_active']]
                df_disp.index.name = 'username'
                st.dataframe(df_disp)

            # Add user
            with tabs[1]:
                st.subheader('إضافة مستخدم جديد')
                with st.form('add_user_form'):
                    new_id = st.text_input('Username')
                    full_name = st.text_input('الاسم الكامل')
                    email = st.text_input('البريد الإلكتروني')
                    phone = st.text_input('رقم الهاتف')
                    br_code = st.text_input('كود الفرع')
                    br_name = st.text_input('اسم الفرع')
                    pwd = st.text_input('كلمة المرور', type='password')
                    is_active = st.checkbox('مفعل', value=True)
                    if role == 'admin':
                        roles = ['admin', 'management', 'viewer', 'uploader']
                    else:
                        roles = ['management', 'viewer', 'uploader']
                    selected_role = st.selectbox('نوع المستخدم', roles)
                    if st.form_submit_button('إضافة'):
                        if new_id in credentials['usernames']:
                            st.error('المستخدم موجود بالفعل')
                        elif selected_role == 'admin' and role != 'admin':
                            st.error('غير مسموح بإنشاء مستخدم إدمن')
                        else:
                            credentials['usernames'][new_id] = {
                                'name': full_name,
                                'email': email,
                                'phone': phone,
                                'branch_code': br_code,
                                'branch_name': br_name,
                                'role': selected_role,
                                'is_active': is_active,
                                'password': stauth.Hasher([pwd]).generate()[0]
                            }
                            with open(cred_file, 'w') as f:
                                json.dump(credentials, f, indent=4)
                            st.success(f'تم إضافة المستخدم {new_id}')

            # Edit/Deactivate user
            with tabs[2]:
                st.subheader('تعديل/حظر مستخدم')
                user_list = list(credentials['usernames'].keys())
                sel_user = st.selectbox('اختر مستخدم', user_list)
                info = credentials['usernames'][sel_user]
                with st.form('edit_user_form'):
                    fn2 = st.text_input('الاسم الكامل', value=info['name'])
                    em2 = st.text_input('البريد الإلكتروني', value=info['email'])
                    ph2 = st.text_input('رقم الهاتف', value=info['phone'])
                    bc2 = st.text_input('كود الفرع', value=info['branch_code'])
                    bn2 = st.text_input('اسم الفرع', value=info['branch_name'])
                    active2 = st.checkbox('مفعل', value=info['is_active'])
                    if role == 'admin':
                        role_opts = ['admin', 'management', 'viewer', 'uploader']
                    else:
                        role_opts = ['management', 'viewer', 'uploader']
                    if info['role'] not in role_opts:
                        role_opts.insert(0, info['role'])
                    sel_role2 = st.selectbox('نوع المستخدم', role_opts, index=role_opts.index(info['role']))
                    cpwd = st.checkbox('تغيير كلمة مرور')
                    if cpwd:
                        new_pwd = st.text_input('كلمة المرور الجديدة', type='password')
                    if st.form_submit_button('حفظ'):
                        info.update({
                            'name': fn2,
                            'email': em2,
                            'phone': ph2,
                            'branch_code': bc2,
                            'branch_name': bn2,
                            'role': sel_role2,
                            'is_active': active2
                        })
                        if cpwd and new_pwd:
                            info['password'] = stauth.Hasher([new_pwd]).generate()[0]
                        credentials['usernames'][sel_user] = info
                        with open(cred_file, 'w') as f:
                            json.dump(credentials, f, indent=4)
                        st.success('تم حفظ التعديلات')

    # Card Reports Section
    with report_tab:
        st.header('🗂️ تقارير البطاقات')
        # Upload (accept xlsx and csv)
        if can_up:
            uploaded = st.file_uploader('📁 رفع تقرير البطاقات', type=['xlsx','csv'])
            if uploaded:
                try:
                    if uploaded.name.lower().endswith('.csv'):
                        df_new = pd.read_csv(uploaded, dtype=str)
                    else:
                        df_new = pd.read_excel(uploaded, dtype=str)
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
        # View/Download
        if os.path.exists(master_file):
            df_all = pd.read_excel(master_file, dtype=str)
            df_all.columns = df_all.columns.str.strip()
            if 'Delivery Branch Code' not in df_all.columns:
                st.error(f"عمود 'Delivery Branch Code' غير موجود. الأعمدة المتاحة: {list(df_all.columns)}")
            else:
                df_all['Delivery Branch Code'] = df_all['Delivery Branch Code'].str.strip()
                df_all = df_all.drop_duplicates(subset=['Unmasked Card Number', 'Account Number'])
                df_all['Issuance Date'] = pd.to_datetime(df_all['Issuance Date'], errors='coerce', dayfirst=True)
                term = st.text_input('🔍 بحث')
                if term:
                    df_all = df_all[df_all.apply(lambda r: r.astype(str).str.contains(term, case=False).any(), axis=1)]
                if not df_all['Issuance Date'].isna().all():
                    mn, mx = df_all['Issuance Date'].min(), df_all['Issuance Date'].max()
                    sd = st.date_input('📆 من تاريخ', min_value=mn, max_value=mx, value=mn)
                    ed = st.date_input('📆 إلى تاريخ', min_value=mn, max_value=mx, value=mx)
                    sd_ts, ed_ts = pd.to_datetime(sd), pd.to_datetime(ed)
                    df_all = df_all[(df_all['Issuance Date'] >= sd_ts) & (df_all['Issuance Date'] <= ed_ts)]
                for br in sorted(df_all['Delivery Branch Code'].unique()):
                    df_br = df_all[df_all['Delivery Branch Code'] == br]
                    with st.expander(f'📌 فرع {br}'):
                        st.dataframe(df_br, use_container_width=True)
                        if can_dn:
                            buf = io.BytesIO()
                            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                                df_br.to_excel(writer, index=False, sheet_name='Sheet1')
                            buf.seek(0)
                            st.download_button(f'⬇️ تحميل فرع {br}', buf, f'branch_{br}.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        else:
            st.info('ℹ️ لا توجد بيانات بعد.')
