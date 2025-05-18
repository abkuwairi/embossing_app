import streamlit as st
import pandas as pd
import os
import io
import json
import streamlit_authenticator as stauth
from datetime import datetime

# Paths
DATA_DIR = 'data'
CRED_FILE = os.path.join(DATA_DIR, 'credentials.json')
MASTER_FILE = os.path.join(DATA_DIR, 'master_data.xlsx')

os.makedirs(DATA_DIR, exist_ok=True)

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
if os.path.exists(CRED_FILE):
    with open(CRED_FILE,'r') as f:
        credentials = json.load(f)
else:
    creds = default_credentials
    # hash defaults
    for user,data in creds['usernames'].items():
        pwd = plain_defaults.get(user,'password123')
        data['password'] = stauth.Hasher([pwd]).generate()[0]
    credentials = creds
    with open(CRED_FILE,'w') as f:
        json.dump(credentials,f,indent=4)

# Prepare authenticator with active users
active = {u:{'name':info['name'],'password':info['password']} for u,info in credentials['usernames'].items() if info.get('is_active')}
authenticator = stauth.Authenticate({'usernames':active},cookie_name='embossing_app_cookie',key='abcd1234abcd1234abcd1234abcd1234',cookie_expiry_days=1)

# Login
name, auth_status, username = authenticator.login('🔐 تسجيل الدخول','main')
if auth_status is False:
    st.error('❌ اسم المستخدم أو كلمة المرور غير صحيحة')
elif auth_status is None:
    st.warning('👈 الرجاء تسجيل الدخول للاستمرار')
else:
    st.sidebar.success(f'مرحباً {name}')
    authenticator.logout('تسجيل الخروج','sidebar')
    # fetch role
    role = credentials['usernames'][username].get('role','viewer')
    st.title('📋 نظام تحميل ومتابعة بطاقات Embossing')

    # User management for admin and management roles
    if role in ['admin','management']:
        st.header('👥 إدارة المستخدمين')
        tab1, tab2, tab3 = st.tabs(['عرض المستخدمين','إضافة مستخدم','تعديل/حظر'])
        # List
        with tab1:
            df = pd.DataFrame.from_dict(credentials['usernames'],orient='index')
            display = df[['name','email','phone','branch_code','branch_name','role','is_active']]
            display.index.name='username'
            st.dataframe(display)
        # Add
        with tab2:
            st.subheader('إضافة مستخدم جديد')
            with st.form('add_form'):
                u = st.text_input('username')
                nm = st.text_input('الاسم الكامل')
                em = st.text_input('البريد الإلكتروني')
                ph = st.text_input('رقم الهاتف')
                bc = st.text_input('كود الفرع')
                bn = st.text_input('اسم الفرع')
                pwd = st.text_input('كلمة المرور',type='password')
                is_act = st.checkbox('مفعل',value=True)
                # role select
                options = ['viewer','uploader']
                if role=='admin': options.insert(0,'management'); options.insert(0,'admin')
                sel_role = st.selectbox('نوع المستخدم',options)
                submitted = st.form_submit_button('إضافة')
                if submitted:
                    if u in credentials['usernames']:
                        st.error('المستخدم موجود بالفعل')
                    elif sel_role=='admin' and role!='admin':
                        st.error('غير مسموح بإنشاء مستخدم إدمن')
                    else:
                        credentials['usernames'][u] = {'name':nm,'email':em,'phone':ph,'branch_code':bc,'branch_name':bn,'role':sel_role,'is_active':is_act,'password':stauth.Hasher([pwd]).generate()[0]}
                        with open(CRED_FILE,'w') as f: json.dump(credentials,f,indent=4)
                        st.success(f'تم إضافة {u}')
        # Edit
        with tab3:
            st.subheader('تعديل/حظر مستخدم')
            sel = st.selectbox('اختر مستخدم',list(credentials['usernames'].keys()))
            info = credentials['usernames'][sel]
            with st.form('edit_form'):
                nm2 = st.text_input('الاسم الكامل',value=info['name'])
                em2 = st.text_input('البريد الإلكتروني',value=info['email'])
                ph2 = st.text_input('رقم الهاتف',value=info['phone'])
                bc2 = st.text_input('كود الفرع',value=info['branch_code'])
                bn2 = st.text_input('اسم الفرع',value=info['branch_name'])
                is2 = st.checkbox('مفعل',value=info['is_active'])
                # role change
                roles = ['viewer','uploader']
                if role=='admin': roles.extend(['management','admin'])
                rl2 = st.selectbox('نوع المستخدم',roles,index=roles.index(info['role']))
                ch = st.checkbox('تغيير كلمة المرور')
                if ch: np = st.text_input('كلمة المرور الجديدة',type='password')
                sub2 = st.form_submit_button('حفظ')
                if sub2:
                    if rl2=='admin' and role!='admin':
                        st.error('غير مسموح بتعيين دور إدمن')
                    else:
                        info.update({'name':nm2,'email':em2,'phone':ph2,'branch_code':bc2,'branch_name':bn2,'is_active':is2,'role':rl2})
                        if ch: info['password']=stauth.Hasher([np]).generate()[0]
                        credentials['usernames'][sel]=info
                        with open(CRED_FILE,'w') as f: json.dump(credentials,f,indent=4)
                        st.success('تم التحديث')

    # Card logic
    can_upload = role in ['admin','management','uploader']
    can_download = role in ['admin','management','uploader']
    if can_upload:
        uploaded = st.file_uploader('📁 رفع تقرير البطائق',type=['xlsx'])
        if uploaded:
            try:
                dfn = pd.read_excel(uploaded,dtype=str)
                dfn['Load Date']=datetime.today().strftime('%Y-%m-%d')
                dfc = pd.concat([pd.read_excel(MASTER_FILE,dtype=str),dfn],ignore_index=True) if os.path.exists(MASTER_FILE) else dfn
                dfc.to_excel(MASTER_FILE,index=False)
                st.success('✅ تم التحديث')
            except Exception as e: st.error(f'❌ {e}')
    if os.path.exists(MASTER_FILE):
        df_all=pd.read_excel(MASTER_FILE,dtype=str)
        df_all['Delivery Branch Code']=df_all['Delivery Branch Code'].str.strip()
        df_all=df_all.drop_duplicates(['Unmasked Card Number','Account Number'])
        df_all['Issuance Date']=pd.to_datetime(df_all['Issuance Date'],errors='coerce',dayfirst=True)
        term=st.text_input('🔍 بحث')
        if term: df_all=df_all[df_all.apply(lambda x: x.astype(str).str.contains(term,case=False).any(),axis=1)]
        if not df_all['Issuance Date'].isna().all():
            mn, mx=df_all['Issuance Date'].min(),df_all['Issuance Date'].max()
            sd=st.date_input('من',min_value=mn,max_value=mx,value=mn)
            ed=st.date_input('إلى',min_value=mn,max_value=mx,value=mx)
            df_all=df_all[(df_all['Issuance Date']>=pd.to_datetime(sd))&(df_all['Issuance Date']<=pd.to_datetime(ed))]
        for br in sorted(df_all['Delivery Branch Code'].unique()):
            df_b=df_all[df_all['Delivery Branch Code']==br]
            with st.expander(f'فرع {br}'):
                st.dataframe(df_b,use_container_width=True)
                if can_download:
                    buf=io.BytesIO()
                    with pd.ExcelWriter(buf,engine='xlsxwriter') as w:
                        df_b.to_excel(w,index=False)
                    buf.seek(0)
                    st.download_button(f'⬇️ تحميل {br}',buf,f'{br}.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        st.info('ℹ️ لا توجد بيانات')
