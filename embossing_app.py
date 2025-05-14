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
    # hash defaults
    for user,data in creds['usernames'].items():
        pwd = plain_defaults.get(user,'password123')
        data['password'] = stauth.Hasher([pwd]).generate()[0]
    with open(cred_file,'w') as f:
        json.dump(creds,f,indent=4)
    return creds

credentials = load_credentials()

# Prepare authenticator with active users
active_users = {
    u: {'name':info['name'], 'password':info['password']}
    for u,info in credentials['usernames'].items()
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

    # User management for admin/management
    if role in ['admin', 'management']:
        st.header('👥 إدارة المستخدمين')
        tabs = st.tabs(['عرض المستخدمين', 'إضافة مستخدم', 'تعديل/حظر'])
        # List
        with tabs[0]:
            df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
            df_disp = df_users[['name','email','phone','branch_code','branch_name','role','is_active']]
            df_disp.index.name = 'username'
            st.dataframe(df_disp)
        # Add
        with tabs[1]:
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
                roles = ['viewer','uploader']
                if role=='admin':
                    roles = ['admin','management'] + roles
                sel_role = st.selectbox('نوع المستخدم', roles)
                if st.form_submit_button('إضافة'):
                    if u in credentials['usernames']:
                        st.error('المستخدم موجود بالفعل')
                    elif sel_role=='admin' and role!='admin':
                        st.error('غير مسموح بإنشاء مستخدم إدمن')
                    else:
                        credentials['usernames'][u] = {
                            'name':nm,'email':em,'phone':ph,'branch_code':bc,
                            'branch_name':bn,'role':sel_role,'is_active':is_act,
                            'password':stauth.Hasher([pwd]).generate()[0]
                        }
                        with open(cred_file,'w') as f:
                            json.dump(credentials,f,indent=4)
                        st.success(f'تم إضافة المستخدم {u}')
        # Edit
        with tabs[2]:
            st.subheader('تعديل/حظر مستخدم')
            users = list(credentials['usernames'].keys())
            sel = st.selectbox('اختر مستخدم', users)
            info = credentials['usernames'][sel]
            with st.form('edit_form'):
                nm2 = st.text_input('الاسم الكامل', value=info['name'])
                em2 = st.text_input('البريد الإلكتروني', value=info['email'])
                ph2 = st.text_input('رقم الهاتف', value=info['phone'])
                bc2 = st.text_input('كود الفرع', value=info['branch_code'])
                bn2 = st.text_input('اسم الفرع', value=info['branch_name'])
                is2 = st.checkbox('مفعل', value=info['is_active'])
                roles2 = ['viewer','uploader']
                if role=='admin': roles2 = ['admin','management'] + roles2
                rl2 = st.selectbox('نوع المستخدم', roles2, index=roles2.index(info['role']))
                ch = st.checkbox('تغيير كلمة المرور')
                if ch: npwd = st.text_input('كلمة المرور الجديدة', type='password')
                if st.form_submit_button('حفظ'):
                    if rl2=='admin' and role!='admin':
                        st.error('غير مسموح بتعيين دور إدمن')
                    else:
                        info.update({'name':nm2,'email':em2,'phone':ph2,'branch_code':bc2,'branch_name':bn2,'is_active':is2,'role':rl2})
                        if ch:
                            info['password'] = stauth.Hasher([npwd]).generate()[0]
                        credentials['usernames'][sel] = info
                        with open(cred_file,'w') as f:
                            json.dump(credentials,f,indent=4)
                        st.success('تم حفظ التعديلات')

    # Card upload/download permissions
    can_upload = role in ['admin','management','uploader']
    can_download = role in ['admin','management','uploader']

    # Upload
    if can_upload:
        up = st.file_uploader('📁 رفع تقرير البطاقات', type=['xlsx'])
        if up:
            try:
                df_new = pd.read_excel(up, dtype=str)
                df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
                df_combined = pd.concat([pd.read_excel(master_file, dtype=str), df_new], ignore_index=True) if os.path.exists(master_file) else df_new
                df_combined.to_excel(master_file, index=False)
                st.success('✅ تم تحديث قاعدة البيانات بنجاح.')
            except Exception as e:
                st.error(f'❌ خطأ أثناء رفع الملف: {e}')

    # View/download
    if os.path.exists(master_file):
        df_all = pd.read_excel(master_file, dtype=str)
        if 'Delivery Branch Code' not in df_all.columns:
            st.error(f"عمود 'Delivery Branch Code' غير موجود. الأعمدة المتاحة: {list(df_all.columns)}")
        else:
            df_all['Delivery Branch Code'] = df_all['Delivery Branch Code'].str.strip()
            df_all = df_all.drop_duplicates(subset=['Unmasked Card Number', 'Account Number'])
            df_all['Issuance Date'] = pd.to_datetime(df_all['Issuance Date'], errors='coerce', dayfirst=True)

            term = st.text_input('🔍 بحث')
            if term:
                df_all = df_all[df_all.apply(lambda row: row.astype(str).str.contains(term, case=False).any(), axis=1)]

            if not df_all['Issuance Date'].isna().all():
                min_d, max_d = df_all['Issuance Date'].min(), df_all['Issuance Date'].max()
                start_d = st.date_input('📆 من تاريخ', min_value=min_d, max_value=max_d, value=min_d)
                end_d = st.date_input('📆 إلى تاريخ', min_value=min_d, max_value=max_d, value=max_d)
                df_all = df_all[(df_all['Issuance Date'] >= start_d) & (df_all['Issuance Date'] <= end_d)]

            for br in sorted(df_all['Delivery Branch Code'].unique()):
                df_br = df_all[df_all['Delivery Branch Code'] == br]
                with st.expander(f'📌 فرع {br}'):
                    st.dataframe(df_br, use_container_width=True)
                    if can_download:
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                            df_br.to_excel(writer, index=False, sheet_name='Sheet1')
                        buf.seek(0)
                        st.download_button(f'⬇️ تحميل فرع {br}', buf, f'branch_{br}.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        st.info('ℹ️ لا توجد بيانات بعد.')
