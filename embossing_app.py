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

# Initialize authenticator
auth_users = { u: {'name':info['name'], 'password':info['password']} for u,info in credentials['usernames'].items() if info.get('is_active')} 
authenticator = stauth.Authenticate({'usernames': auth_users}, cookie_name='embossing_app_cookie', key='abcd1234abcd1234abcd1234abcd1234', cookie_expiry_days=1)

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

    # User management
    if role in ['admin','management']:
        st.header('👥 إدارة المستخدمين')
        tabs = st.tabs(['عرض المستخدمين','إضافة مستخدم','تعديل/حظر'])
        # List users
        with tabs[0]:
            df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
            df_disp = df_users[['name','email','phone','branch_code','branch_name','role','is_active']]
            df_disp.index.name='username'
            st.dataframe(df_disp)
        # Add user
        with tabs[1]:
            st.subheader('إضافة مستخدم جديد')
            with st.form('add_form'):
                uid = st.text_input('Username')
                nm = st.text_input('الاسم الكامل')
                em = st.text_input('البريد الإلكتروني')
                ph = st.text_input('رقم الهاتف')
                bc = st.text_input('كود الفرع')
                bn = st.text_input('اسم الفرع')
                pwd = st.text_input('كلمة المرور', type='password')
                act = st.checkbox('مفعل', value=True)
                options = ['viewer','uploader']
                if role=='admin': options = ['admin','management']+options
                sel = st.selectbox('نوع المستخدم', options)
                if st.form_submit_button('إضافة'):
                    if uid in credentials['usernames']:
                        st.error('المستخدم موجود بالفعل')
                    elif sel=='admin' and role!='admin':
                        st.error('غير مسموح بإنشاء مستخدم إدمن')
                    else:
                        credentials['usernames'][uid] = {'name':nm,'email':em,'phone':ph,'branch_code':bc,'branch_name':bn,'role':sel,'is_active':act,'password':stauth.Hasher([pwd]).generate()[0]}
                        with open(cred_file,'w') as f: json.dump(credentials,f,indent=4)
                        st.success(f'تم إضافة المستخدم {uid}')
        # Edit user
        with tabs[2]:
            st.subheader('تعديل/حظر مستخدم')
            users = list(credentials['usernames'].keys())
            sel_user = st.selectbox('اختر مستخدم', users)
            info = credentials['usernames'][sel_user]
            with st.form('edit_form'):
                nm2 = st.text_input('الاسم الكامل', value=info['name'])
                em2 = st.text_input('البريد الإلكتروني', value=info['email'])
                ph2 = st.text_input('رقم الهاتف', value=info['phone'])
                bc2 = st.text_input('كود الفرع', value=info['branch_code'])
                bn2 = st.text_input('اسم الفرع', value=info['branch_name'])
                act2 = st.checkbox('مفعل', value=info['is_active'])
                opts2 = ['viewer','uploader']
                if role=='admin': opts2 = ['admin','management']+opts2
                sel2 = st.selectbox('نوع المستخدم', opts2, index=opts2.index(info['role']))
                cp = st.checkbox('تغيير كلمة مرور')
                if cp: np = st.text_input('كلمة المرور الجديدة', type='password')
                if st.form_submit_button('حفظ'):
                    if sel2=='admin' and role!='admin': st.error('غير مسموح بتعيين دور إدمن')
                    else:
                        info.update({'name':nm2,'email':em2,'phone':ph2,'branch_code':bc2,'branch_name':bn2,'role':sel2,'is_active':act2})
                        if cp and np: info['password']=stauth.Hasher([np]).generate()[0]
                        credentials['usernames'][sel_user]=info
                        with open(cred_file,'w') as f: json.dump(credentials,f,indent=4)
                        st.success('تم حفظ التعديلات')
    # Permissions
    can_up=role in ['admin','management','uploader']
    can_dn=role in ['admin','management','uploader']
    # Upload
    if can_up:
        up=st.file_uploader('📁 رفع تقرير البطاقات', type=['xlsx'])
        if up:
            try:
                dn=pd.read_excel(up,dtype=str)
                dn['Load Date']=datetime.today().strftime('%Y-%m-%d')
                cf=pd.read_excel(master_file,dtype=str) if os.path.exists(master_file) else pd.DataFrame()
                cf=pd.concat([cf,dn],ignore_index=True) if not cf.empty else dn
                cf.to_excel(master_file,index=False)
                st.success('✅ تم التحديث')
            except Exception as e: st.error(f'❌ {e}')
    # View/Download
    if os.path.exists(master_file):
        df_all=pd.read_excel(master_file,dtype=str)
        df_all.columns=df_all.columns.str.strip()
        if 'Delivery Branch Code' not in df_all.columns:
            st.error(f"عمود 'Delivery Branch Code' غير موجود. الأعمدة المتاحة: {list(df_all.columns)}")
        else:
            df_all['Delivery Branch Code']=df_all['Delivery Branch Code'].str.strip()
            df_all=df_all.drop_duplicates(['Unmasked Card Number','Account Number'])
            df_all['Issuance Date']=pd.to_datetime(df_all['Issuance Date'],errors='coerce',dayfirst=True)
            term=st.text_input('🔍 بحث')
            if term: df_all=df_all[df_all.apply(lambda r:r.astype(str).str.contains(term,case=False).any(),axis=1)]
            if not df_all['Issuance Date'].isna().all():
                mn, mx=df_all['Issuance Date'].min(),df_all['Issuance Date'].max()
                sd=st.date_input('📆 من تاريخ',min_value=mn,max_value=mx,value=mn)
                ed=st.date_input('📆 إلى تاريخ',min_value=mn,max_value=mx,value=mx)
                sd_ts,ed_ts=pd.to_datetime(sd),pd.to_datetime(ed)
                df_all=df_all[(df_all['Issuance Date']>=sd_ts)&(df_all['Issuance Date']<=ed_ts)]
            for br in sorted(df_all['Delivery Branch Code'].unique()):
                db=df_all[df_all['Delivery Branch Code']==br]
                with st.expander(f'📌 فرع {br}'):
                    st.dataframe(db,use_container_width=True)
                    if can_dn:
                        buf=io.BytesIO()
                        with pd.ExcelWriter(buf,engine='xlsxwriter') as w: db.to_excel(w,index=False)
                        buf.seek(0)
                        st.download_button(f'⬇️ تحميل فرع {br}',buf,f'branch_{br}.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        st.info('ℹ️ لا توجد بيانات بعد.')
