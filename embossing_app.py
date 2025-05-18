import streamlit as st
import pandas as pd
import os
import io
import json
import streamlit_authenticator as stauth
from datetime import datetime

# --- Constants and Env Vars ---
ROLES = {
    'ADMIN': 'admin',
    'DEPT': 'management',
    'UPLOADER': 'uploader',
    'VIEWER': 'viewer',
}
SECRET_KEY = os.getenv('STREAMLIT_AUTH_KEY', 'fallback_secret_key')

# --- Paths ---
DATA_DIR = 'data'
CRED_FILE = os.path.join(DATA_DIR, 'credentials.json')
MASTER_FILE = os.path.join(DATA_DIR, 'master_data.xlsx')

os.makedirs(DATA_DIR, exist_ok=True)

# --- Helper Functions ---
def load_credentials():
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, 'r') as f:
            return json.load(f)
    default = {
        'usernames': {
            'admin_user': {
                'name': 'Admin', 'password': None, 'email': 'admin@example.com',
                'phone': '', 'branch_code': '', 'branch_name': '', 'is_active': True,
                'role': ROLES['ADMIN'],
            },
            'branch101': {
                'name': 'Branch101', 'password': None, 'email': '', 'phone': '',
                'branch_code': '101', 'branch_name': 'Branch 101', 'is_active': True,
                'role': ROLES['VIEWER'],
            },
            'branch102': {
                'name': 'Branch102', 'password': None, 'email': '', 'phone': '',
                'branch_code': '102', 'branch_name': 'Branch 102', 'is_active': True,
                'role': ROLES['VIEWER'],
            },
        }
    }
    plain = {'admin_user': 'admin123', 'branch101': 'b101', 'branch102': 'b102'}
    for u, info in default['usernames'].items():
        info['password'] = stauth.Hasher([plain.get(u, 'password123')]).generate()[0]
    save_credentials(default)
    return default


def save_credentials(creds):
    with open(CRED_FILE, 'w') as f:
        json.dump(creds, f, indent=4)


def import_master_data(uploaded_file):
    ext = uploaded_file.name.lower().rsplit('.', 1)[-1]
    df_new = pd.read_csv(uploaded_file) if ext == 'csv' else pd.read_excel(uploaded_file)
    df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
    if os.path.exists(MASTER_FILE):
        df_existing = pd.read_excel(MASTER_FILE, dtype=str)
        df_all = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_all = df_new
    df_all.to_excel(MASTER_FILE, index=False)
    st.success('✅ البيانات محدثة بنجاح!')
    return df_new

# --- Authentication ---
credentials = load_credentials()
authenticator = stauth.Authenticate(
    credentials,
    cookie_name='embossing_cookie',
    key=SECRET_KEY,
    cookie_expiry_days=1,
)

name, auth_status, username = authenticator.login('🔐 تسجيل الدخول', 'main')
if auth_status is False:
    st.error('❌ اسم المستخدم أو كلمة المرور غير صحيحة')
elif auth_status is None:
    st.warning('👈 الرجاء تسجيل الدخول للاستمرار')
else:
    st.sidebar.success(f'مرحباً {name}')
    authenticator.logout('تسجيل الخروج', 'sidebar')

    user = credentials['usernames'][username]
    role = user.get('role', ROLES['VIEWER'])
    branch = user.get('branch_code', '')

    st.title('📋 نظام تسليم ومتابعة بطاقات Embossing')

    # Sidebar menu
    options = []
    if role in [ROLES['ADMIN'], ROLES['DEPT']]:
        options.append('👥 إدارة المستخدمين')
    options.append('📁 رفع بيانات البطاقات')
    options.append('📊 التقارير والبحث')
    choice = st.sidebar.radio('القائمة', options)

    # إدارة المستخدمين
    if choice == '👥 إدارة المستخدمين':
        st.header('👥 إدارة المستخدمين')
        tabs = st.tabs(['عرض', 'إضافة', 'تعديل'])
        # ... existing user management code ...

    # رفع البيانات
    elif choice == '📁 رفع بيانات البطاقات':
        st.header('📁 رفع بيانات البطاقات')
        if role in [ROLES['ADMIN'], ROLES['DEPT'], ROLES['UPLOADER']]:
            file = st.file_uploader('اختر ملف CSV أو XLSX', type=['csv', 'xlsx'])
            if file:
                try:
                    df_new = import_master_data(file)
                    st.subheader('معاينة البيانات المضافة')
                    st.dataframe(df_new)
                except Exception as e:
                    st.error(f'❌ خطأ: {e}')
        else:
            st.warning('🚫 لا تمتلك صلاحية لرفع الملفات.')

    # التقارير والبحث
    elif choice == '📊 التقارير والبحث':
        st.header('📊 التقارير والبحث')
        if os.path.exists(MASTER_FILE):
            df = pd.read_excel(MASTER_FILE, dtype=str)
            # Remove duplicates
            df = df.drop_duplicates(subset=['Unmasked Card Number', 'Account Number', 'Issuance Date', 'Delivery Branch Code'])
            df['Issuance Date'] = pd.to_datetime(df['Issuance Date'], dayfirst=True, errors='coerce')

            term = st.text_input('🔍 بحث')
            if term:
                mask = df['Unmasked Card Number'].str.contains(term, na=False) | df['Account Number'].str.contains(term, na=False)
                df = df[mask]

            # Date range filter
            if not df['Issuance Date'].isna().all():
                mn = df['Issuance Date'].min().date()
                mx = df['Issuance Date'].max().date()
                start = st.date_input('من', mn, mn, mx)
                end   = st.date_input('إلى', mx, mn, mx)
                df = df[(df['Issuance Date'].dt.date >= start) & (df['Issuance Date'].dt.date <= end)]

            # Branch-level filter for viewer
            if role == ROLES['VIEWER'] and branch:
                df = df[df['Delivery Branch Code'] == branch]

            if df.empty:
                st.warning('❗ لا توجد نتائج')
            else:
                st.dataframe(df)
                if role in [ROLES['ADMIN'], ROLES['DEPT'], ROLES['UPLOADER']]:
                    buffer = io.BytesIO()
                    df.to_excel(buffer, index=False)
                    buffer.seek(0)
                    st.download_button(
                        '⬇️ تحميل النتائج',
                        buffer,
                        'results.xlsx',
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
        else:
            st.info('ℹ️ لا توجد بيانات بعد')
