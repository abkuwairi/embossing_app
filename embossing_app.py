import streamlit as st
import pandas as pd
import os
import io
import json
import logging
import streamlit_authenticator as stauth
from datetime import datetime

# ------------------ Configuration ------------------
DATA_DIR = 'data'
CRED_FILE = os.path.join(DATA_DIR, 'credentials.json')
MASTER_FILE = os.path.join(DATA_DIR, 'master_data.xlsx')
REQUIRED_COLUMNS = ['Unmasked Card Number', 'Customer Name', 'Account Number', 'Issuance Date', 'Delivery Branch Code']

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Set up logging to file
logging.basicConfig(
    filename=os.path.join(DATA_DIR, 'app.log'),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# ------------------ Credentials Handling ------------------
def load_credentials():
    if os.path.exists(CRED_FILE):
        return json.load(open(CRED_FILE))
    # Initialize defaults
    default_credentials = {
        'usernames': {
            'admin_user': {'name':'Admin','password':None,'email':'admin@example.com','phone':'','branch_code':'','branch_name':'','is_active':True,'role':'admin'},
            'branch101': {'name':'Branch101','password':None,'email':'','phone':'','branch_code':'101','branch_name':'Branch 101','is_active':True,'role':'viewer'},
            'branch102': {'name':'Branch102','password':None,'email':'','phone':'','branch_code':'102','branch_name':'Branch 102','is_active':True,'role':'viewer'}
        }
    }
    plain_defaults = {'admin_user':'admin123','branch101':'b101','branch102':'b102'}
    for user, info in default_credentials['usernames'].items():
        pwd = plain_defaults.get(user, 'password123')
        info['password'] = stauth.Hasher([pwd]).generate()[0]
    with open(CRED_FILE, 'w') as f:
        json.dump(default_credentials, f, indent=4)
    return default_credentials

credentials = load_credentials()

# ------------------ Streamlit-Authenticator ------------------
active_users = {u:{'name':i['name'],'password':i['password']} for u,i in credentials['usernames'].items() if i.get('is_active')}
authenticator = stauth.Authenticate(
    {'usernames': active_users},
    cookie_name='card_mgmt_cookie',
    key='xyz123xyz123xyz123xyz123xyz123',
    cookie_expiry_days=1
)

# ------------------ Caching Data Loads ------------------
@st.cache_data
def load_master_data():
    if os.path.exists(MASTER_FILE):
        df = pd.read_excel(MASTER_FILE, dtype=str)
        df.columns = df.columns.str.strip()
        return df
    return pd.DataFrame(columns=REQUIRED_COLUMNS + ['Load Date'])

# ------------------ UI ------------------
name, auth_status, username = authenticator.login('🔐 تسجيل الدخول', 'main')
if auth_status is False:
    st.error('❌ اسم المستخدم أو كلمة المرور غير صحيحة')
elif auth_status is None:
    st.warning('👈 الرجاء تسجيل الدخول للاستمرار')
else:
    # Greet
    if username in credentials['usernames']:
        st.sidebar.success(f"مرحباً {credentials['usernames'][username]['name']}")
    else:
        st.sidebar.error('خطأ: اسم المستخدم غير موجود.')
    authenticator.logout('تسجيل الخروج', 'sidebar', key='logout_btn')

    # Determine permissions
    role = credentials['usernames'][username]['role']
    can_upload = role in ['admin','management','uploader']
    can_manage = role == 'admin'

    # Header with logo
    if os.path.exists('logo.png'):
        st.image('logo.png', use_container_width=True)
    st.markdown('# 🚀 منظومة إدارة البطاقات')

    # Tabs
    tabs = ['🗂️ تقارير البطاقات']
    if can_manage:
        tabs.insert(0, '👥 إدارة المستخدمين')
    selected_tab = st.selectbox('القائمة الرئيسية', tabs)

    # ------------------ User Management ------------------
    if selected_tab == '👥 إدارة المستخدمين':
        st.header('👥 إدارة المستخدمين')
        # List users
        st.subheader('جميع المستخدمين')
        df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
        df_disp = df_users[['name','email','phone','branch_code','branch_name','role','is_active']]
        df_disp.index.name = 'username'
        st.dataframe(df_disp, use_container_width=True)

        # Forms to add/edit
        st.subheader('إضافة مستخدم جديد')
        with st.form('add_form'):
            u = st.text_input('Username')
            nm = st.text_input('الاسم الكامل')
            em = st.text_input('البريد الإلكتروني')
            ph = st.text_input('رقم الهاتف')
            bc = st.text_input('كود الفرع')
            bn = st.text_input('اسم الفرع')
            pw = st.text_input('كلمة المرور', type='password')
            is_act = st.checkbox('مفعل', value=True)
            role_opt = st.selectbox('الدور', ['admin','management','viewer','uploader'])
            if st.form_submit_button('إضافة'):
                if not set(REQUIRED_COLUMNS).issubset(load_master_data().columns):
                    st.error('لا يمكن إضافة مستخدم قبل رفع البيانات الأساسية.')
                elif u in credentials['usernames']:
                    st.error('المستخدم موجود بالفعل.')
                else:
                    credentials['usernames'][u] = {'name':nm,'email':em,'phone':ph,'branch_code':bc,'branch_name':bn,'role':role_opt,'is_active':is_act,'password':stauth.Hasher([pw]).generate()[0]}
                    json.dump(credentials, open(CRED_FILE,'w'), indent=4)
                    st.success('تم إضافة المستخدم.')

    # ------------------ Card Reports ------------------
    if selected_tab == '🗂️ تقارير البطاقات':
        st.header('🗂️ تقارير البطاقات')
        st.info('ارفع ملف XLSX أو CSV يحتوي على الأعمدة التالية: ' + ', '.join(REQUIRED_COLUMNS))
        if can_upload:
            file = st.file_uploader('اختر ملفاً', type=['xlsx','csv'], help='تأكد من تسمية الأعمدة بالضبط')
            if file:
                try:
                    df_new = pd.read_csv(file, dtype=str) if file.name.endswith('.csv') else pd.read_excel(file, dtype=str)
                    missing = [c for c in REQUIRED_COLUMNS if c not in df_new.columns]
                    if missing:
                        st.error(f'الأعمدة المفقودة: {missing}')
                    else:
                        df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
                        df_master = load_master_data()
                        df_comb = pd.concat([df_master, df_new], ignore_index=True)
                        df_comb.to_excel(MASTER_FILE, index=False)
                        st.success('✅ تم تحديث البيانات.')
                        logging.info(f"User {username} uploaded file {file.name}")
                except Exception as e:
                    st.error(f'خطأ: {e}')

        # Display and filter
        df_all = load_master_data()
        if df_all.empty:
            st.info('ℹ️ لا توجد بيانات.')
        else:
            # Date parsing and warnings
            df_all['Issuance Date'] = pd.to_datetime(df_all['Issuance Date'], errors='coerce', dayfirst=True)
            bad_dates = df_all['Issuance Date'].isna().sum()
            if bad_dates > 0:
                st.warning(f'فشل تحويل {bad_dates} تواريخ.')

            # Filters
            search = st.text_input('🔍 بحث عام')
            if search:
                df_all = df_all[df_all.apply(lambda r: r.astype(str).str.contains(search, case=False).any(), axis=1)]
            if not df_all['Issuance Date'].isna().all():
                start, end = st.date_input('من تاريخ'), st.date_input('إلى تاريخ')
                df_all = df_all[(df_all['Issuance Date']>=start)&(df_all['Issuance Date']<=end)]

            # Show per branch
            branches = sorted(df_all['Delivery Branch Code'].unique())
            for br in branches:
                with st.expander(f'فرع {br} ({len(df_all[df_all["Delivery Branch Code"]==br])} صف)'):
                    st.dataframe(df_all[df_all['Delivery Branch Code']==br], use_container_width=True)
                    if can_upload:
                        buf = io.BytesIO()
                        pd.ExcelWriter(buf, engine='xlsxwriter').book;
                        df_all[df_all['Delivery Branch Code']==br].to_excel(buf, index=False)
                        buf.seek(0)
                        st.download_button('⬇️ تحميل', buf, f'{br}.xlsx')

    # End of app
