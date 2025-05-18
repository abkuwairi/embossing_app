import streamlit as st
import pandas as pd
import os
import io
import json
import streamlit_authenticator as stauth
from datetime import datetime

# --- Constants ---
ROLES = {
    'ADMIN': 'admin',
    'DEPT': 'management',
    'UPLOADER': 'uploader',
    'VIEWER': 'viewer',
}
SECRET_KEY = os.getenv('STREAMLIT_AUTH_KEY', 'fallback_secret_key')

# --- File Paths ---
DATA_DIR = 'data'
CRED_FILE = os.path.join(DATA_DIR, 'credentials.json')
MASTER_FILE = os.path.join(DATA_DIR, 'master_data.xlsx')

os.makedirs(DATA_DIR, exist_ok=True)

# --- Helper Functions ---
def save_credentials(creds):
    """Save credentials dict to JSON file."""
    with open(CRED_FILE, 'w') as f:
        json.dump(creds, f, indent=4)


def load_credentials():
    """Load credentials from file or initialize defaults."""
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, 'r') as f:
            return json.load(f)
    # Default users
    default = {
        'usernames': {
            'admin_user': {
                'name': 'Admin', 'email': 'admin@example.com', 'phone': '',
                'branch_code': '', 'branch_name': '', 'is_active': True,
                'role': ROLES['ADMIN'], 'password': None,
            },
            'branch101': {
                'name': 'Branch101', 'email': '', 'phone': '',
                'branch_code': '101', 'branch_name': 'Branch 101', 'is_active': True,
                'role': ROLES['VIEWER'], 'password': None,
            },
            'branch102': {
                'name': 'Branch102', 'email': '', 'phone': '',
                'branch_code': '102', 'branch_name': 'Branch 102', 'is_active': True,
                'role': ROLES['VIEWER'], 'password': None,
            },
        }
    }
    # Default passwords
    plain = {'admin_user': 'admin123', 'branch101': 'b101', 'branch102': 'b102'}
    for user, info in default['usernames'].items():
        pwd = plain.get(user, 'password123')
        info['password'] = stauth.Hasher([pwd]).generate()[0]
    save_credentials(default)
    return default


def import_master_data(uploaded_file):
    """Read uploaded CSV/XLSX, append to master file, and return new records."""
    ext = uploaded_file.name.lower().rsplit('.', 1)[-1]
    if ext == 'csv':
        df_new = pd.read_csv(uploaded_file, dtype=str)
    else:
        df_new = pd.read_excel(uploaded_file, dtype=str)
    df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
    if os.path.exists(MASTER_FILE):
        df_existing = pd.read_excel(MASTER_FILE, dtype=str)
        df_all = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_all = df_new
    df_all.to_excel(MASTER_FILE, index=False)
    st.success('✅ البيانات محدثة بنجاح!')
    return df_new

# --- Main ---
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
    st.stop()

st.sidebar.success(f'مرحباً {name}')
authenticator.logout('تسجيل الخروج', 'sidebar')

user = credentials['usernames'][username]
role = user.get('role', ROLES['VIEWER'])

st.title('📋 نظام إدارة وتسليم البطاقات')

# --- Sidebar Navigation ---
sections = []
if role in [ROLES['ADMIN'], ROLES['DEPT']]:
    sections.append('👥 إدارة المستخدمين')
sections.append('📁 رفع بيانات البطاقات')
sections.append('📊 التقارير والبحث')
section = st.sidebar.radio('القائمة', sections)

# --- Sections ---
# User Management
if section == '👥 إدارة المستخدمين':
    st.header('👥 إدارة المستخدمين')
    tab1, tab2, tab3 = st.tabs(['عرض المستخدمين', 'إضافة مستخدم', 'تعديل/حظر'])

    # View Users
    with tab1:
        df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
        df_users.index.name = 'username'
        st.dataframe(df_users[['name', 'email', 'phone', 'branch_code', 'branch_name', 'role', 'is_active']])

    # Add User
    with tab2:
        st.subheader('إضافة مستخدم جديد')
        with st.form('add_form'):
            u = st.text_input('Username')
            nm = st.text_input('الاسم الكامل')
            em = st.text_input('البريد الإلكتروني')
            ph = st.text_input('رقم الهاتف')
            bc = st.text_input('كود الفرع')
            bn = st.text_input('اسم الفرع')
            pwd = st.text_input('كلمة المرور', type='password')
            is_act = st.checkbox('مفعل', True)
            opts = [ROLES['VIEWER'], ROLES['UPLOADER']]
            if role == ROLES['DEPT']:
                opts.append(ROLES['DEPT'])
            elif role == ROLES['ADMIN']:
                opts = [ROLES['ADMIN'], ROLES['DEPT'], ROLES['UPLOADER'], ROLES['VIEWER']]
            sel_role = st.selectbox('نوع المستخدم', opts)

            if st.form_submit_button('إضافة'):
                if not u.strip() or u in credentials['usernames']:
                    st.error('اسم المستخدم غير صالح أو موجود مسبقاً')
                else:
                    credentials['usernames'][u] = {
                        'name': nm, 'email': em, 'phone': ph,
                        'branch_code': bc, 'branch_name': bn,
                        'role': sel_role, 'is_active': is_act,
                        'password': stauth.Hasher([pwd]).generate()[0]
                    }
                    save_credentials(credentials)
                    st.success('تم إضافة المستخدم بنجاح')

    # Edit / Block User
    with tab3:
        st.subheader('تعديل/حظر مستخدم')
        sel = st.selectbox('اختر مستخدم', list(credentials['usernames'].keys()))
        info = credentials['usernames'][sel]
        with st.form('edit_form'):
            nm2 = st.text_input('الاسم الكامل', info['name'])
            em2 = st.text_input('البريد الإلكتروني', info['email'])
            ph2 = st.text_input('رقم الهاتف', info['phone'])
            bc2 = st.text_input('كود الفرع', info['branch_code'])
            bn2 = st.text_input('اسم الفرع', info['branch_name'])
            is2 = st.checkbox('مفعل', info['is_active'])
            # Role options for editing
            roles_opt = [ROLES['VIEWER'], ROLES['UPLOADER']]
            if role == ROLES['ADMIN']:
                roles_opt.extend([ROLES['DEPT'], ROLES['ADMIN']])
            elif role == ROLES['DEPT']:
                roles_opt.append(ROLES['DEPT'])
            # Determine default index without error
            default_idx = roles_opt.index(info['role']) if info['role'] in roles_opt else 0
            rl2 = st.selectbox('نوع المستخدم', roles_opt, index=default_idx)
            ch2 = st.checkbox('تغيير كلمة المرور')
            npw = None
            if ch2:
                npw = st.text_input('كلمة المرور الجديدة', type='password')

            if st.form_submit_button('حفظ'):
                # Prevent management from modifying admin
                if role != ROLES['ADMIN'] and info['role'] == ROLES['ADMIN']:
                    st.error('🚫 غير مسموح بتعديل مستخدم إدمن')
                else:
                    info.update({
                        'name': nm2,
                        'email': em2,
                        'phone': ph2,
                        'branch_code': bc2,
                        'branch_name': bn2,
                        'role': rl2,
                        'is_active': is2,
                    })
                    if ch2 and npw:
                        info['password'] = stauth.Hasher([npw]).generate()[0]
                    save_credentials(credentials)
                    st.success('تم تحديث بيانات المستخدم بنجاح')

# Upload Cards Data
elif section == '📁 رفع بيانات البطاقات':
    st.header('📁 رفع بيانات البطاقات')
    if role in [ROLES['ADMIN'], ROLES['DEPT'], ROLES['UPLOADER']]:
        uploaded_file = st.file_uploader('اختر ملف CSV أو XLSX', type=['csv', 'xlsx'])
        if uploaded_file:
            df_new = import_master_data(uploaded_file)
            st.subheader('معاينة البيانات المضافة')
            st.dataframe(df_new)
    else:
        st.warning('🚫 لا تمتلك صلاحية رفع الملفات')

# Reports & Search
elif section == '📊 التقارير والبحث':
    st.header('📊 التقارير والبحث')
    if os.path.exists(MASTER_FILE):
        df = pd.read_excel(MASTER_FILE, dtype=str)
        df['Issuance Date'] = pd.to_datetime(df['Issuance Date'], dayfirst=True, errors='coerce')
        df = df.drop_duplicates(subset=['Unmasked Card Number', 'Account Number', 'Delivery Branch Code', 'Issuance Date'])
        term = st.text_input('🔍 بحث')
        if term:
            df = df[df['Unmasked Card Number'].str.contains(term, na=False) | df['Account Number'].str.contains(term, na=False)]
        if not df['Issuance Date'].isna().all():
            mn = df['Issuance Date'].min().date()
            mx = df['Issuance Date'].max().date()
            start = st.date_input('من', mn, mn, mx)
            end = st.date_input('إلى', mx, mn, mx)
            df = df[(df['Issuance Date'].dt.date >= start) & (df['Issuance Date'].dt.date <= end)]
        if df.empty:
            st.warning('❗ لا توجد نتائج')
        else:
            st.dataframe(df)
            buf = io.BytesIO()
            df.to_excel(buf, index=False)
            buf.seek(0)
            st.download_button('⬇️ تحميل النتائج', buf, 'results.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        st.info('ℹ️ لا توجد بيانات بعد')
