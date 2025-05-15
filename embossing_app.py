import streamlit as st
import pandas as pd
import os
import io
import json
import logging
import streamlit_authenticator as stauth
from datetime import datetime

# Must be first Streamlit command
st.set_page_config(page_title='Card Management', layout='wide')

# ------------------ Configuration ------------------
DATA_DIR = 'data'
CRED_FILE = os.path.join(DATA_DIR, 'credentials.json')
MASTER_FILE = os.path.join(DATA_DIR, 'master_data.xlsx')
LOG_FILE = os.path.join(DATA_DIR, 'app.log')
REQUIRED_COLUMNS = [
    'Unmasked Card Number',
    'Customer Name',
    'Account Number',
    'Issuance Date',
    'Delivery Branch Code'
]

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# ------------------ Logging Setup ------------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)
for handler in list(logger.handlers):
    logger.removeHandler(handler)
file_handler = logging.FileHandler(LOG_FILE, mode='a')
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(file_handler)

# ------------------ Credentials Handling ------------------
def load_credentials():
    if os.path.exists(CRED_FILE):
        return json.load(open(CRED_FILE))
    defaults = {'usernames': {'admin_user': {'name': 'Admin', 'role': 'admin', 'password': None},
                              'branch101': {'name': 'Branch101', 'role': 'viewer', 'password': None},
                              'branch102': {'name': 'Branch102', 'role': 'viewer', 'password': None}}}
    plain = {'admin_user': 'admin123', 'branch101': 'b101', 'branch102': 'b102'}
    for u,v in defaults['usernames'].items():
        v['password'] = stauth.Hasher([plain[u]]).generate()[0]
    json.dump(defaults, open(CRED_FILE,'w'), indent=4)
    return defaults

credentials = load_credentials()
active_users = {u: {'name': v['name'], 'password': v['password']} for u,v in credentials['usernames'].items()}
auth = stauth.Authenticate({'usernames': active_users}, cookie_name='cookie', key='key', cookie_expiry_days=1)

# ------------------ Data Loading ------------------
@st.cache_data
def load_master_data():
    if os.path.exists(MASTER_FILE):
        df = pd.read_excel(MASTER_FILE, dtype=str)
        df.columns = df.columns.str.strip()
        df['Delivery Branch Code'] = df['Delivery Branch Code'].astype(str).str.strip()
        df['Issuance Date'] = pd.to_datetime(df['Issuance Date'], errors='coerce')
        return df
    return pd.DataFrame(columns=REQUIRED_COLUMNS+['Load Date'])

# ------------------ UI ------------------
name, status, username = auth.login('🔐 Login','main')
if status is False:
    st.error('Invalid credentials')
elif status is None:
    st.warning('Please login')
else:
    # Logout
    try:
        if auth.logout('Logout','sidebar',key='logout'): st.stop()
    except Exception:
        st.stop()
    st.sidebar.success(f'Welcome {name}')
    user_role = credentials['usernames'][username]['role']
    logger.info(f"{username} logged in")

    # Navigation
    options = []
    if user_role=='admin': options.append('User Management')
    options += ['Upload Data','Reports & Branch Data','Application Logs']
    if 'page' not in st.session_state or st.session_state['page'] not in options:
        st.session_state['page'] = options[0]
    st.sidebar.title('Menu')
    page = st.sidebar.radio('', options, index=options.index(st.session_state['page']))
    st.session_state['page'] = page

    # Pages
    if page=='User Management':
        st.header('User Management')
        df_users = pd.DataFrame.from_dict(credentials['usernames'],orient='index')
        df_disp = df_users[['name','role']]
        df_disp.index.name='username'
        st.dataframe(df_disp,use_container_width=True)
    elif page=='Upload Data':
        st.header('Upload Card Data')
        f=st.file_uploader('Upload .xlsx/.xls/.csv',type=['xlsx','xls','csv'])
        if f:
            df_new = pd.read_excel(f,dtype=str) if f.name.lower().endswith(('xlsx','xls')) else pd.read_csv(f,dtype=str)
            df_new.columns=df_new.columns.str.strip()
            missing=[c for c in REQUIRED_COLUMNS if c not in df_new.columns]
            if missing: st.error(f'Missing cols: {missing}')
            else:
                st.dataframe(df_new.head(5),use_container_width=True)
                if st.button('Save to Master'):
                    df_new['Delivery Branch Code']=df_new['Delivery Branch Code'].str.strip()
                    df_new['Issuance Date']=pd.to_datetime(df_new['Issuance Date'],errors='coerce',dayfirst=True)
                    df_new['Load Date']=datetime.today().strftime('%Y-%m-%d')
                    m=load_master_data()
                    c=pd.concat([m,df_new],ignore_index=True)
                    c.drop_duplicates(subset=['Unmasked Card Number','Account Number','Delivery Branch Code'],inplace=True)
                    c.to_excel(MASTER_FILE,index=False)
                    st.success('Saved')
                    load_master_data.clear()
    elif page=='Reports & Branch Data':
        st.header('Reports & Branch Data')
        df=load_master_data()
        if df.empty: st.info('No data.')
        else:
            term=st.text_input('Search by name,card,account')
            dff=df.copy()
            if term:
                mask=(dff['Customer Name'].str.contains(term,case=False,na=False)|
                      dff['Unmasked Card Number'].str.contains(term,na=False)|
                      dff['Account Number'].str.contains(term,na=False))
                dff=dff[mask]
            mn, mx=dff['Issuance Date'].min(),dff['Issuance Date'].max()
            fr=st.date_input('From date',min_value=mn,max_value=mx,value=mn)
            to=st.date_input('To date',min_value=mn,max_value=mx,value=mx)
            res=dff[(dff['Issuance Date']>=fr)&(dff['Issuance Date']<=to)]
            st.dataframe(res.reset_index(drop=True),use_container_width=True)
    else:
        st.header('Application Logs')
        if os.path.exists(LOG_FILE):
            txt=open(LOG_FILE).read()
            st.text_area('Logs',txt,400)
        else: st.info('No logs.')
