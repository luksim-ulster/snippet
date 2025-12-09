import streamlit as st
import requests
import os
from dotenv import load_dotenv
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

load_dotenv()

IUPS = os.getenv('IUPS', '')  # POST
RAI  = os.getenv('RAI', '')   # GET
UIA = os.getenv('UIA', '')   # UPDATE
DIA = os.getenv('DIA', '')   # DELETE
CONNECTION = os.getenv('AZURE_CONNECTION_STRING')
CONTAINER = "mediastorage" 
FIREBASE_API_KEY = os.getenv('FIREBASE_API_KEY')

def firebase_login(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    response = requests.post(url, json=payload)
    return response

def firebase_signup(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    response = requests.post(url, json=payload)
    return response

def render_login_ui():
    st.markdown("## Login")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign In")
            
            if submit:
                response = firebase_login(email, password)
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.user = {
                        "email": data['email'],
                        "id": data['localId'],
                        "token": data['idToken']
                    }
                    st.rerun()
                else: st.error(f"Login failed.")

    with tab2:
        with st.form("signup_form"):
            new_email = st.text_input("Email")
            new_pass = st.text_input("Password", type="password")
            new_submit = st.form_submit_button("Create Account")
            
            if new_submit:
                response = firebase_signup(new_email, new_pass)
                if response.status_code == 200:
                    st.success("Account created. Ready to log in.")
                else: st.error(f"Signup failed.")

def logout():
    if 'user' in st.session_state:
        del st.session_state.user
    st.rerun()

def get_connection_settings(connection):
    connection_settings_list = connection.split(';')
    connection_settings_dict = {}
    for setting_parameter in connection_settings_list:
        setting = setting_parameter.split('=', 1)
        setting_name = setting[0]
        setting_value = setting[1]
        connection_settings_dict[setting_name] = setting_value

    return connection_settings_dict['AccountName'], connection_settings_dict['AccountKey']

@st.cache_data(ttl=1800)
def create_secure_temporary_link(file_name):        
    account_name, account_key = get_connection_settings(CONNECTION)
    
    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=CONTAINER,
        blob_name=file_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
    )
    
    return f"https://{account_name}.blob.core.windows.net/{CONTAINER}/{file_name}?{sas_token}"

def upload_media(iups, file_object, user_file_name, user_name, user_id):
    file_extension = os.path.splitext(file_object.name)[1]

    file = {'File': (file_object.name, file_object, file_object.type)}
    data = {
        'fileName': user_file_name,
        'fileExtension': file_extension,
        'userName': user_name,
        'userID': user_id
    }

    response = requests.post(iups, files=file, data=data)
    
    return response.status_code

@st.cache_data(ttl=60)
def display_media(rai):
    response = requests.get(rai)
    data = response.json()

    return response.status_code, data

def format_url(url, item_id):
    safe_id = quote(str(item_id), safe='') 
    target_url = url.replace("%7Bid%7D", safe_id)

    return target_url

def update_media(uia, document_id, media_file, user_file_name):
    data = media_file.copy()

    data['fileName'] = user_file_name

    system_keys = [k for k in data.keys() if k.startswith('_')]
    for k in system_keys:
        data.pop(k)
    
    target_url = format_url(uia, document_id)
    try:
        response = requests.put(target_url, json=data)
        return response.status_code
    except Exception as e: return str(e)

def delete_media(dia, item_id):
    target_url = format_url(dia, item_id)
    try:
        response = requests.delete(target_url)
        return response.status_code
    except Exception as e: return str(e)

def render_upload_section(current_user):
    with st.sidebar:
        st.write(f"**{current_user['email']}**")
        if st.button("Logout"):
            logout()
            
        st.divider()

        st.header("Upload")
        with st.form("upload_form"):
            user_file_name = st.text_input("File Name", "")
            uploaded_file = st.file_uploader("Select File")

            if st.form_submit_button("Upload"):
                if uploaded_file:
                    with st.spinner("Uploading..."):
                        user_name = current_user['email']
                        user_id = current_user['id']

                        status = upload_media(IUPS, uploaded_file, user_file_name, user_name, user_id)
                        if status == 202: st.success("Upload Started...")
                        else: st.error(f"Error: {status}")

def handle_delete(dia, document_id):
    response = delete_media(dia, document_id)
    if response == 200:
        st.session_state.album_data = [
            item for item in st.session_state.album_data 
            if item.get('id') != document_id
        ]
        st.toast("Deleted.")
    else:
        st.toast(f"Failed: {response}")

def handle_update(uia, document_id, media_file, input_key):
    new_user_file_name = st.session_state.get(input_key)

    if new_user_file_name:
        response = update_media(uia, document_id, media_file, new_user_file_name)
        if response == 200:
            for item in st.session_state.album_data:
                if item['id'] == document_id:
                    item['fileName'] = new_user_file_name
                    break
            
            st.session_state.edit_id = None
            st.toast("Updated!")
        else:
            st.toast(f"Failed: {response}")

def render_album_tile(media_file, current_user):
    document_id = media_file.get('id')

    user_file_name = media_file.get('fileName', 'Unknown')
    stored_file_name = media_file.get('uniqueFileName', '')

    file_owner_name = media_file.get('userName', '')
    file_owner_id = media_file.get('userID', '')

    secure_url = create_secure_temporary_link(stored_file_name)
    
    st.markdown(f"**{user_file_name}**")
    st.caption(f"Uploaded by: {file_owner_name}")
    
    if secure_url:
        if stored_file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
            st.image(secure_url, width=100)

        elif stored_file_name.lower().endswith(('.mp4', '.mov', '.avi', '.webm')):
            st.video(secure_url)
    
    if file_owner_id == current_user['id']:
        is_editing = (st.session_state.edit_id == document_id)

        if is_editing:
            with st.container(border=True):
                st.caption("Editing")

                with st.form(f"edit_{document_id}"):
                    input_key = f"input_filename_{document_id}"
                    st.text_input("New Filename", value=user_file_name, key=input_key)
                    
                    st.form_submit_button(
                        "Save Changes", 
                        on_click=handle_update, 
                        args=(UIA, document_id, media_file, input_key)
                    )

                column_delete, column_cancel = st.columns(2)

                with column_delete:
                    st.button(
                        "Delete", 
                        key=f"delete_{document_id}", 
                        type="primary", 
                        on_click=handle_delete, 
                        args=(DIA, document_id)
                    )
                
                with column_cancel:
                    def close_edit():
                        st.session_state.edit_id = None
                    
                    st.button("Cancel", key=f"cancel_{document_id}", on_click=close_edit)
        else:
            def open_edit():
                st.session_state.edit_id = document_id
            
            st.button("Edit", key=f"edit_{document_id}", on_click=open_edit)

def render_album_section(columns, current_user):
    st.header("Album")

    if 'edit_id' not in st.session_state:
        st.session_state.edit_id = None

    if 'album_data' not in st.session_state:
        st.session_state.album_data = None

    if st.session_state.album_data is None:
        with st.spinner("Refreshing..."):
            status, data = display_media(RAI)
            if status == 200: 
                st.session_state.album_data = data
            else: 
                st.error(f"Error: {status}")
    
    def refresh_data():
        display_media.clear()
        st.session_state.album_data = None
        
    if st.button("Refresh"):
        refresh_data()
        st.rerun()

    album_container = st.container()

    if st.session_state.album_data is not None:
        data = st.session_state.album_data
        
        if not data:
            st.info("No media found.")
            return

        with album_container:
            album_columns = st.columns(columns)
            for index, media_file in enumerate(data):
                with album_columns[index % columns]:
                    render_album_tile(media_file, current_user)

if __name__ == "__main__":
    st.set_page_config(page_title="Snippet", layout="wide")

    if 'user' not in st.session_state:
        st.title("Snippet")
        render_login_ui()
    else:
        current_user = st.session_state.user
        st.title("Snippet")
        
        render_upload_section(current_user)
        render_album_section(4, current_user)

