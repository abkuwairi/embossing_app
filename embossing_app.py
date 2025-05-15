import streamlit as st
import pandas as pd
import os
import io
import streamlit_authenticator as stauth
from datetime import datetime

# Must be first command
st.set_page_config(page_title='Card Management', layout='wide')

# -------------------- Paths and Config --------------------
DATA_DIR = 'data'
CRED_PATH = os.path.join(DATA_DIR, 'credentials.json')
MASTER_FILE = os.path.join(DATA_DIR, 'master_data.xlsx')
os.makedirs(DATA_DIR, exist_ok=True)

# -------------------- Load or Initialize Credentials --------------------
def load_credentials():
    if os.path.exists(CRED_PATH):
        return json.load(open(CRED_PATH))
    # initialize default
    creds = {
        'usernames': {
            'admin_user': {'name': 'Admin', 'password': None, 'role': 'admin'},
            'branch101': {'name': 'Branch 101', 'password': None, 'role': 'viewer'},
            'branch102': {'name': 'Branch 102', 'password': None, 'role': 'viewer'}
        }
    }
    # Set default passwords
    defaults = {'admin_user': 'admin123', 'branch101': 'b101', 'branch102': 'b102'}
    hashed = stauth.Hasher(list(defaults.values())).generate()
    for (u,p), h in zip(defaults.items(), hashed):
        creds['usernames'][u]['password'] = h
    json.dump(creds, open(CRED_PATH, 'w'), indent=4)
    return creds

credentials = load_credentials()

# Build authenticator
active_users = {u: {'name': info['name'], 'password': info['password']} for u, info in credentials['usernames'].items()}
authenticator = stauth.Authenticate(
    {'usernames': active_users},
    cookie_name='card_app_cookie',
    key='secure_key_123',
    cookie_expiry_days=1
)

# -------------------- Authentication --------------------
name, auth_status, username = authenticator.login('🔐 Login', 'main')
if auth_status is False:
    st.error('❌ Invalid username or password')
elif auth_status is None:
    st.warning('👈 Please log in to continue')
else:
    # Logout
    authenticator.logout('Logout', 'sidebar')
    st.sidebar.success(f'Welcome {name}')
    user_info = credentials['usernames'][username]
    role = user_info.get('role', 'viewer')
    is_admin = (role == 'admin')

    # -------------------- Admin User Management --------------------
    if is_admin:
        st.sidebar.markdown('---')
        st.sidebar.header('Admin: User Management')
        df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
        df_disp = df_users[['name','role']].rename(columns={'name':'Full Name'})
        df_disp.index.name = 'Username'
        st.sidebar.dataframe(df_disp)
        st.sidebar.subheader('Add New User')
        with st.sidebar.form('add_user'):
            new_user = st.text_input('Username')
            full_name = st.text_input('Full Name')
            pwd = st.text_input('Password', type='password')
            role_choice = st.selectbox('Role', ['admin','uploader','viewer'])
            submit_user = st.form_submit_button('Create User')
            if submit_user:
                if new_user in credentials['usernames']:
                    st.sidebar.error('User already exists')
                elif not new_user or not full_name or not pwd:
                    st.sidebar.error('All fields are required')
                else:
                    # Hash and save
                    h = stauth.Hasher([pwd]).generate()[0]
                    credentials['usernames'][new_user] = {'name': full_name, 'password': h, 'role': role_choice}
                    json.dump(credentials, open(CRED_PATH, 'w'), indent=4)
                    st.sidebar.success(f'User {new_user} created')
                    st.experimental_rerun()

    # -------------------- Upload Section --------------------
    st.title('📤 Upload Daily Card Report')
    if is_admin or role.startswith('branch'):
        uploaded = st.file_uploader('Choose Excel (.xlsx) file', type=['xlsx'])
        if uploaded:
            df_new = pd.read_excel(uploaded, dtype=str)
            df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
            if os.path.exists(MASTER_FILE):
                df_old = pd.read_excel(MASTER_FILE, dtype=str)
                df_comb = pd.concat([df_old, df_new], ignore_index=True)
            else:
                df_comb = df_new
            df_comb.to_excel(MASTER_FILE, index=False)
            st.success('✅ Master data updated')

    # -------------------- Reports & Branch Data --------------------
    st.title('📊 Reports & Branch Data')
    if os.path.exists(MASTER_FILE):
        df_all = pd.read_excel(MASTER_FILE, dtype=str)
        df_all['Delivery Branch Code'] = df_all['Delivery Branch Code'].astype(str).str.strip()
        df_all = df_all.drop_duplicates(subset=['Unmasked Card Number','Account Number'])
        df_all['Issuance Date'] = pd.to_datetime(df_all['Issuance Date'], errors='coerce', dayfirst=True)

        search = st.text_input('🔍 Search by customer, card, or account')
        df_f = df_all.copy()
        if search:
            mask = (
                df_f['Customer Name'].str.contains(search, case=False, na=False) |
                df_f['Account Number'].str.contains(search, na=False) |
                df_f['Unmasked Card Number'].str.contains(search, na=False)
            )
            df_f = df_f[mask]

        # Separate From and To date filters
        min_date = df_f['Issuance Date'].min()
        max_date = df_f['Issuance Date'].max()
        from_date = st.date_input('From date', min_value=min_date, max_value=max_date, value=min_date)
        to_date = st.date_input('To date', min_value=min_date, max_value=max_date, value=max_date)
        # Convert to timestamps for comparison
        start_ts = pd.to_datetime(from_date)
        end_ts = pd.to_datetime(to_date)
        # Filter DataFrame
        df_f = df_f[(df_f['Issuance Date'] >= start_ts) & (df_f['Issuance Date'] <= end_ts)]

        # Display by branch
        branches = sorted(df_f['Delivery Branch Code'].unique())
        for b in branches:
            df_b = df_f[df_f['Delivery Branch Code'] == b]
            st.subheader(f'Branch {b} ({len(df_b)} records)')
            st.dataframe(df_b, use_container_width=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
                df_b.to_excel(w, index=False, sheet_name='Sheet1')
            buf.seek(0)
            st.download_button(f'⬇️ Download Branch {b}', buf, f'branch_{b}.xlsx',
                               'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        st.info('ℹ️ No data available. Please upload a report.')
