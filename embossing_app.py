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
            'admin_user': {'name': 'Admin', 'password': None, 'email': 'admin@example.com', 'phone': '', 'branch_code': '', 'branch_name': '', 'is_active': True, 'role': ROLES['ADMIN']},
            'branch101': {'name': 'Branch101', 'password': None, 'email': '', 'phone': '', 'branch_code': '101', 'branch_name': 'Branch 101', 'is_active': True, 'role': ROLES['VIEWER']},
            'branch102': {'name': 'Branch102', 'password': None, 'email': '', 'phone': '', 'branch_code': '102', 'branch_name': 'Branch 102', 'is_active': True, 'role': ROLES['VIEWER']},
        }
    }
    plain = {'admin_user': 'admin123', 'branch101': 'b101', 'branch102': 'b102'}
    for user, info in default['usernames'].items():
        pwd = plain.get(user, 'password123')
        info['password'] = stauth.Hasher([pwd]).generate()[0]
    with open(CRED_FILE, 'w') as f:
        json.dump(default, f, indent=4)
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
        df_concat = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_concat = df_new
    df_concat.to_excel(MASTER_FILE, index=False)
    st.success('✅ البيانات محدثة بنجاح!')

# --- Load credentials and Auth ---
credentials = load_credentials()
authenticator = stauth.Authenticate(
    credentials,
    cookie_name='embossing_app_cookie',
    key=SECRET_KEY,
    cookie_expiry_days=1
)

# --- Login Flow ---
name, auth_status, username = authenticator.login('🔐 تسجيل الدخول', 'main')
if auth_status is False:
    st.error('❌ اسم المستخدم أو كلمة المرور غير صحيحة')
elif auth_status is None:
    st.warning('👈 الرجاء تسجيل الدخول للاستمرار')
else:
    st.sidebar.success(f'مرحباً {name}')
    authenticator.logout('تسجيل الخروج', 'sidebar')

    # Determine user role and branch
    user_info = credentials['usernames'][username]
    role = user_info.get('role', ROLES['VIEWER'])
    user_branch = user_info.get('branch_code', '')

    st.title('📋 نظام تسليم ومتابعة بطاقات Embossing')

    # --- Sidebar Navigation ---
    menu = []
    if role in [ROLES['ADMIN'], ROLES['DEPT']]:
        menu.append('👥 إدارة المستخدمين')
    menu.append('📁 رفع بيانات البطاقات')
    menu.append('📊 التقارير والبحث')
    selection = st.sidebar.radio('القائمة', menu)

    # --- User Management Section ---
    if selection == '👥 إدارة المستخدمين':
        st.header('👥 إدارة المستخدمين')
        tab1, tab2, tab3 = st.tabs(['عرض المستخدمين', 'إضافة مستخدم', 'تعديل/حظر'])
        # List users
        with tab1:
            df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
            display = df_users[['name', 'email', 'phone', 'branch_code', 'branch_name', 'role', 'is_active']]
            display.index.name = 'username'
            st.dataframe(display)
        # Add user
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
                options = [ROLES['VIEWER'], ROLES['UPLOADER']]
                if role == ROLES['DEPT']:
                    options.append(ROLES['DEPT'])
                if role == ROLES['ADMIN']:
                    options = [ROLES['ADMIN'], ROLES['DEPT'], ROLES['UPLOADER'], ROLES['VIEWER']]
                sel_role = st.selectbox('نوع المستخدم', options)
                submitted = st.form_submit_button('إضافة')
                if submitted:
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
        # Edit or Block user
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
                sub2 = st.form_submit_button('حفظ')
                if sub2:
                    if rl2 == ROLES['ADMIN'] and role != ROLES['ADMIN']:
                        st.error('غير مسموح بتعيين دور إدمن')
                    else:
                        info.update({'name': nm2, 'email': em2, 'phone': ph2, 'branch_code': bc2, 'branch_name': bn2, 'role': rl2, 'is_active': is2})
                        if ch:
                            info['password'] = stauth.Hasher([npw]).generate()[0]
                        credentials['usernames'][sel] = info
                        save_credentials(credentials)
                        st.success('تم تحديث بيانات المستخدم')

    # --- Card Upload Section ---
    elif selection == '📁 رفع بيانات البطاقات':
        st.header('📁 رفع بيانات البطاقات')
        if role in [ROLES['ADMIN'], ROLES['DEPT'], ROLES['UPLOADER']]:
            uploaded = st.file_uploader('اختر ملف CSV أو XLSX', type=['csv', 'xlsx'])
            if uploaded:
                try:
                    import_master_data(uploaded)
                except Exception as e:
                    st.error(f'❌ خطأ أثناء الاستيراد: {e}')
        else:
            st.warning('🚫 لا تمتلك صلاحية لرفع الملفات.')

    # --- Reports & Search Section ---
    elif selection == '📊 التقارير والبحث':
        st.header('📊 التقارير والبحث')
        if os.path.exists(MASTER_FILE):
            df_all = pd.read_excel(MASTER_FILE, dtype=str)
            df_all['Delivery Branch Code'] = df_all['Delivery Branch Code'].str.strip()
            df_all = df_all.drop_duplicates(['Unmasked Card Number', 'Account Number'])
            df_all['Issuance Date'] = pd.to_datetime(df_all['Issuance Date'], errors='coerce', dayfirst=True)

            term = st.text_input('🔍 بحث (رقم البطاقة أو الحساب)')
            if term:
                mask = (
                    df_all['Unmasked Card Number'].str.contains(term, case=False, na=False) |
                    df_all['Account Number'].str.contains(term, case=False, na=False)
                )
                df_all = df_all[mask]

            if not df_all['Issuance Date'].isna().all():
                mn, mx = df_all['Issuance Date'].min(), df_all['Issuance Date'].max()
                sd = st.date_input('من', min_value=mn, max_value=mx, value=mn)
                ed = st.date_input('إلى', min_value=mn, max_value=mx, value=mx)
                df_all = df_all[(df_all['Issuance Date'] >= pd.to_datetime(sd)) & (df_all['Issuance Date'] <= pd.to_datetime(ed))]

            if role == ROLES['VIEWER'] and user_branch:
                df_all = df_all[df_all['Delivery Branch Code'] == user_branch]

            if df_all.empty:
                st.warning('❗ لا توجد نتائج مطابقة')
            else:
                for br in sorted(df_all['Delivery Branch Code'].unique()):
                    df_b = df_all[df_all['Delivery Branch Code'] == br]
                    with st.expander(f'فرع {br}'):
                        st.dataframe(df_b, use_container_width=True)
                        if role in [ROLES['ADMIN'], ROLES['DEPT'], ROLES['UPLOADER']]:
                            buf = io.BytesIO()
                            with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
                                df_b.to_excel(w, index=False)
                            buf.seek(0)\ n                            st.download_button(f'⬇️ تحميل {br}', buf, f'{br}.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        else:
            st.info('ℹ️ لا توجد بيانات بعد')
