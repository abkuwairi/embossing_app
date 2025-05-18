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
    # Default credentials setup
    default = {
        'usernames': {
            'admin_user': {
                'name': 'Admin',
                'password': None,
                'email': 'admin@example.com',
                'phone': '',
                'branch_code': '',
                'branch_name': '',
                'is_active': True,
                'role': ROLES['ADMIN'],
            },
            'branch101': {
                'name': 'Branch101',
                'password': None,
                'email': '',
                'phone': '',
                'branch_code': '101',
                'branch_name': 'Branch 101',
                'is_active': True,
                'role': ROLES['VIEWER'],
            },
            'branch102': {
                'name': 'Branch102',
                'password': None,
                'email': '',
                'phone': '',
                'branch_code': '102',
                'branch_name': 'Branch 102',
                'is_active': True,
                'role': ROLES['VIEWER'],
            },
        }
    }
    # Hash default passwords
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
    if ext == 'csv':
        df_new = pd.read_csv(uploaded_file, dtype=str)
    else:
        df_new = pd.read_excel(uploaded_file, dtype=str)
    df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
    # Append to master file
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
    st.stop()

# User is authenticated
st.sidebar.success(f'مرحباً {name}')
authenticator.logout('تسجيل الخروج', 'sidebar')

user = credentials['usernames'][username]
role = user.get('role', ROLES['VIEWER'])
branch = user.get('branch_code', '')

st.title('📋 نظام تسليم ومتابعة بطاقات Embossing')

# Sidebar menu options
options = []
if role in [ROLES['ADMIN'], ROLES['DEPT']]:
    options.append('👥 إدارة المستخدمين')
options.append('📁 رفع بيانات البطاقات')
options.append('📊 التقارير والبحث')
choice = st.sidebar.radio('القائمة', options)

# Section: User Management
if 'إدارة المستخدمين' in choice:
    st.header('👥 إدارة المستخدمين')
    tab1, tab2, tab3 = st.tabs(['عرض المستخدمين', 'إضافة مستخدم', 'تعديل/حظر'])

    with tab1:
        df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
        display = df_users[['name', 'email', 'phone', 'branch_code', 'branch_name', 'role', 'is_active']]
        display.index.name = 'username'
        st.dataframe(display)

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
            is_act = st.checkbox('مفعل', value=True)
            options_role = [ROLES['VIEWER'], ROLES['UPLOADER']]
            if role == ROLES['DEPT']:
                options_role.append(ROLES['DEPT'])
            if role == ROLES['ADMIN']:
                options_role = [ROLES['ADMIN'], ROLES['DEPT'], ROLES['UPLOADER'], ROLES['VIEWER']]
            sel_role = st.selectbox('نوع المستخدم', options_role)
            if st.form_submit_button('إضافة'):
                if u in credentials['usernames']:
                    st.error('المستخدم موجود بالفعل')
                elif sel_role == ROLES['ADMIN'] and role != ROLES['ADMIN']:
                    st.error('غير مسموح بإنشاء مستخدم إدمن')
                else:
                    credentials['usernames'][u] = {
                        'name': nm,
                        'email': em,
                        'phone': ph,
                        'branch_code': bc,
                        'branch_name': bn,
                        'role': sel_role,
                        'is_active': is_act,
                        'password': stauth.Hasher([pwd]).generate()[0]
                    }
                    save_credentials(credentials)
                    st.success(f'تم إضافة المستخدم {u}')

    with tab3:
        st.subheader('تعديل/حظر مستخدم')
        sel = st.selectbox('اختر مستخدم', list(credentials['usernames'].keys()))
        info = credentials['usernames'][sel]
        with st.form('edit_form'):
            nm2 = st.text_input('الاسم الكامل', value=info['name'])
            em2 = st.text_input('البريد الإلكتروني', value=info['email'])
            ph2 = st.text_input('رقم الهاتف', value=info['phone'])
            bc2 = st.text_input('كود الفرع', value=info['branch_code'])
            bn2 = st.text_input('اسم الفرع', value=info['branch_name'])
            is2 = st.checkbox('مفعل', value=info['is_active'])
            roles_opt = [ROLES['VIEWER'], ROLES['UPLOADER']]
            if role in [ROLES['ADMIN'], ROLES['DEPT']]:
                roles_opt.extend([ROLES['DEPT'], ROLES['ADMIN']])
            rl2 = st.selectbox('نوع المستخدم', roles_opt, index=roles_opt.index(info['role']))
            ch = st.checkbox('تغيير كلمة المرور')
            if ch:
                npw = st.text_input('كلمة المرور الجديدة', type='password')
            if st.form_submit_button('حفظ'):
                if rl2 == ROLES['ADMIN'] and role != ROLES['ADMIN']:
                    st.error('غير مسموح بتعيين دور إدمن')
                else:
                    info.update({'name': nm2, 'email': em2, 'phone': ph2, 'branch_code': bc2, 'branch_name': bn2, 'role': rl2, 'is_active': is2})
                    if ch:
                        info['password'] = stauth.Hasher([npw]).generate()[0]
                    credentials['usernames'][sel] = info
                    save_credentials(credentials)
                    st.success('تم تحديث بيانات المستخدم')

# Section: Upload Cards Data
elif 'رفع بيانات البطاقات' in choice:
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

# Section: Reports & Search
elif 'التقارير والبحث' in choice:
    st.header('📊 التقارير والبحث')
    if os.path.exists(MASTER_FILE):
        df = pd.read_excel(MASTER_FILE, dtype=str)
        # Parse dates
        df['Issuance Date'] = pd.to_datetime(df['Issuance Date'], dayfirst=True, errors='coerce')
        # Drop duplicates except different dates
        df = df.drop_duplicates(subset=['Unmasked Card Number', 'Account Number', 'Delivery Branch Code', 'Issuance Date'])
        # Search filter
        term = st.text_input('🔍 بحث')
        if term:
            mask = df['Unmasked Card Number'].str.contains(term, na=False) | df['Account Number'].str.contains(term, na=False)
            df = df[mask]
        # Date range
        if not df['Issuance Date'].isna().all():
            mn = df['Issuance Date'].min().date()
            mx = df['Issuance Date'].max().date()
            start = st.date_input('من', mn, mn, mx)
            end   = st.date_input('إلى', mx, mn, mx)
            df = df[(df['Issuance Date'].dt.date >= start) & (df['Issuance Date'].dt.date <= end)]
        # Branch view: allow all branches for viewers too
        # No filtering by branch
        if df.empty:
            st.warning('❗ لا توجد نتائج')
        else:
            st.dataframe(df)
            if role in [ROLES['ADMIN'], ROLES['DEPT'], ROLES['UPLOADER'], ROLES['VIEWER']]:
                buffer = io.BytesIO()
                df.to_excel(buffer, index=False)
                buffer.seek(0)
                st.download_button('⬇️ تحميل النتائج', buffer, 'results.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        st.info('ℹ️ لا توجد بيانات بعد')}]}
