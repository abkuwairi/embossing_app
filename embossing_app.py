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
# Clear existing handlers
for handler in list(logger.handlers):
    logger.removeHandler(handler)
# File handler (append-only)
file_handler = logging.FileHandler(LOG_FILE, mode='a')
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(file_handler)

# ------------------ Credentials Handling ------------------
def load_credentials():
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, 'r') as f:
            return json.load(f)
    defaults = {
        'usernames': {
            'admin_user': {'name': 'Admin', 'password': None, 'role': 'admin'},
            'branch101': {'name': 'Branch101', 'password': None, 'role': 'viewer'},
            'branch102': {'name': 'Branch102', 'password': None, 'role': 'viewer'}
        }
    }
    plain = {'admin_user': 'admin123', 'branch101': 'b101', 'branch102': 'b102'}
    for u, info in defaults['usernames'].items():
        info['password'] = stauth.Hasher([plain[u]]).generate()[0]
    with open(CRED_FILE, 'w') as f:
        json.dump(defaults, f, indent=4)
    return defaults

credentials = load_credentials()
active_users = {u: {'name': v['name'], 'password': v['password']} for u, v in credentials['usernames'].items()}
auth = stauth.Authenticate(
    {'usernames': active_users},
    cookie_name='card_app_cookie',
    key='secure_and_unique_key',
    cookie_expiry_days=1
)

# ------------------ Data Loading ------------------
@st.cache_data(show_spinner=False)
def load_master_data() -> pd.DataFrame:
    if os.path.exists(MASTER_FILE):
        df = pd.read_excel(MASTER_FILE, dtype=str)
        df.columns = df.columns.str.strip()
        df['Delivery Branch Code'] = df['Delivery Branch Code'].astype(str).str.strip()
        df['Issuance Date'] = pd.to_datetime(df['Issuance Date'], errors='coerce')
        return df
    cols = REQUIRED_COLUMNS + ['Load Date']
    return pd.DataFrame(columns=cols)

# ------------------ UI ------------------
name, status, username = auth.login('🔐 Login', 'main')
if status is False:
    st.error('❌ Invalid credentials')
elif status is None:
    st.warning('👈 Please login to continue')
else:
    # Logout handling
    try:
        logout_clicked = auth.logout('Logout', 'sidebar', key='logout_btn')
    except KeyError as e:
        logger.error(f"Logout KeyError for {username}: {e}")
        logout_clicked = True
    if logout_clicked:
        st.stop()

    st.sidebar.success(f'Welcome {name}')
    user_info = credentials['usernames'].get(username, {})
    role = user_info.get('role', 'viewer')
    logger.info(f"{username} logged in")

    # Tabs
    tabs = []
    if role == 'admin':
        tabs.append('👥 User Management')
    tabs.extend(['📤 Upload Data', '📊 Reports & Analytics', '📝 Application Logs'])
    selected_tabs = st.tabs(tabs)
    tab_map = {label: tab for label, tab in zip(tabs, selected_tabs)}

    # User Management (Admin only)
    if role == 'admin':
        with tab_map['👥 User Management']:
            st.header('👥 User Management')
            df_users = pd.DataFrame.from_dict(credentials['usernames'], orient='index')
            df_display = df_users[['name', 'role']]
            df_display.index.name = 'username'
            st.dataframe(df_display, use_container_width=True)
            logger.info(f"{username} viewed user management")

    # Upload Data
    with tab_map['📤 Upload Data']:
        st.header('📤 Upload Card Data')
        uploaded_file = st.file_uploader(
            'Upload .xlsx, .xls or .csv',
            type=['xlsx', 'xls', 'csv'],
            help='Ensure columns: ' + ', '.join(REQUIRED_COLUMNS)
        )
        if uploaded_file:
            try:
                if uploaded_file.name.lower().endswith(('xlsx', 'xls')):
                    df_new = pd.read_excel(uploaded_file, dtype=str)
                else:
                    df_new = pd.read_csv(uploaded_file, dtype=str)
                df_new.columns = df_new.columns.str.strip()
                missing = [c for c in REQUIRED_COLUMNS if c not in df_new.columns]
                if missing:
                    st.error(f'Missing columns: {missing}')
                else:
                    st.subheader('Preview of Uploaded Data')
                    st.dataframe(df_new.head(5), use_container_width=True)
                    if st.button('Save to Master'):
                        df_new['Delivery Branch Code'] = df_new['Delivery Branch Code'].astype(str).str.strip()
                        df_new['Issuance Date'] = pd.to_datetime(
                            df_new['Issuance Date'], errors='coerce', dayfirst=True
                        )
                        df_new['Load Date'] = datetime.today().strftime('%Y-%m-%d')
                        master_df = load_master_data()
                        combined_df = pd.concat([master_df, df_new], ignore_index=True)
                        combined_df.drop_duplicates(
                            subset=['Unmasked Card Number', 'Account Number', 'Delivery Branch Code'],
                            inplace=True
                        )
                        combined_df.to_excel(MASTER_FILE, index=False)
                        st.success('✅ Data saved successfully')
                        logger.info(f"{username} saved {len(df_new)} rows")
                        # Clear cache so new data appears
                        load_master_data.clear()
            except Exception as e:
                st.error(f'❌ Error: {e}')
                logger.error(f"{username} upload error: {e}")

    # Reports & Analytics
    with tab_map['📊 Reports & Analytics']:
        st.header('📊 Reports & Branch Data')
        df_all = load_master_data()
        if df_all.empty:
            st.info('No data available. Please upload first.')
        else:
            counts = df_all.groupby('Delivery Branch Code').size().reset_index(name='Count')
            st.subheader('Cards per Branch')
            st.dataframe(counts, use_container_width=True)
            branches = sorted(df_all['Delivery Branch Code'].unique())
            selected_branches = st.multiselect('Select Branch(es)', branches, default=branches)
            filtered_view = df_all[df_all['Delivery Branch Code'].isin(selected_branches)]
            min_date, max_date = filtered_view['Issuance Date'].min(), filtered_view['Issuance Date'].max()
            # Separate From and To date pickers
            from_date = st.date_input('From date', min_value=min_date, max_value=max_date, value=min_date)
            to_date = st.date_input('To date', min_value=min_date, max_value=max_date, value=max_date)
            view = filtered_view[(filtered_view['Issuance Date'] >= pd.to_datetime(from_date)) & (filtered_view['Issuance Date'] <= pd.to_datetime(to_date))]
            st.subheader('Filtered Data')
            st.dataframe(view, use_container_width=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                view.to_excel(writer, index=False, sheet_name='Data')
            buf.seek(0)
            filename = f'cards_export_{timestamp}.xlsx'
            if st.download_button(label=f'⬇️ Download Export ({timestamp})', data=buf, file_name=filename,
                                  mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'):
                logger.info(f"{username} downloaded {filename}")

    # Application Logs (Admin only)
    if role == 'admin':
        with tab_map['📝 Application Logs']:
            st.header('📝 Application Logs')
            if os.path.exists(LOG_FILE):
                content = open(LOG_FILE, 'r').read()
                st.text_area('Log Output', content, height=400)
                if st.download_button('⬇️ Download Log File', data=content, file_name='app.log', mime='text/plain'):
                    logger.info(f"{username} downloaded log file")
                logger.info(f"{username} viewed logs")
            else:
                st.info('No log file found.')
