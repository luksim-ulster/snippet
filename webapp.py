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

def get_connection_settings(connection):
    connection_settings_list = connection.split(';')
    connection_settings_dict = {}
    for setting_parameter in connection_settings_list:
        setting = setting_parameter.split('=', 1)
        setting_name = setting[0]
        setting_value = setting[1]
        connection_settings_dict[setting_name] = setting_value

    return connection_settings_dict['AccountName'], connection_settings_dict['AccountKey']

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

def render_upload_section():
    with st.sidebar:
        st.header("Upload")
        with st.form("upload_form"):
            user_file_name = st.text_input("File Name", "")
            uploaded_file = st.file_uploader("Select File")

            user_name = st.text_input("User Name", "")
            user_id = st.text_input("User ID", "")
            
            if st.form_submit_button("Upload"):
                if uploaded_file:
                    with st.spinner("Uploading..."):
                        status = upload_media(IUPS, uploaded_file, user_file_name, user_name, user_id)
                        if status == 200: st.success("Uploaded!")
                        else: st.error(f"Error: {status}")

def render_update_section(document_id, media_file, user_file_name):
    with st.form(f"edit_{document_id}"):
        new_user_file_name = st.text_input("New Filename", value=user_file_name)
        
        if st.form_submit_button("Update"):
            response = update_media(UIA, document_id, media_file, new_user_file_name)
            if response == 200:
                st.success("Updated!")

                for item in st.session_state.album_data:
                    if item['id'] == media_file['id']:
                        item['fileName'] = new_user_file_name
                        break
                    
                st.rerun()
            else:
                st.error(f"Failed: {response}")

def render_delete_section(document_id):
    if st.button("Delete", key=f"delete_{document_id}"):
        response = delete_media(DIA, document_id)
        if response == 200:
            st.success("Deleted!")

            st.session_state.album_data = [
                    item for item in st.session_state.album_data 
                    if item.get('id') != document_id
                ]
            
            st.rerun()
        else:
            st.error(f"Failed: {response}")

def render_album_tile(media_file):
    document_id = media_file.get('id')

    user_file_name = media_file.get('fileName', 'Unknown')
    stored_file_name = media_file.get('uniqueFileName', '')

    user_name = media_file.get('userName', '')
    user_id = media_file.get('userID', '')

    secure_url = create_secure_temporary_link(stored_file_name)
    
    st.markdown(f"**{user_file_name}**")
    st.caption(f"Uploaded by: {user_name} ({user_id})")
    
    if secure_url:
        if stored_file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
            st.image(secure_url, width=100)

        elif stored_file_name.lower().endswith(('.mp4', '.mov', '.avi', '.webm')):
            st.video(secure_url)
        
    with st.expander("Edit"):
        render_update_section(document_id, media_file, user_file_name)
        render_delete_section(document_id)
        

def render_album_section(columns):
    st.header("Album")

    if 'album_data' not in st.session_state:
        st.session_state.album_data = None
    
    if st.button("Load"):
        with st.spinner("Loading..."):
            status, data = display_media(RAI)

            if status == 200: st.session_state.album_data = data
            else: st.error(f"Error: {status}")

    if st.session_state.album_data is not None:
        data = st.session_state.album_data
        
        if not data:
            st.info("No media found.")
            return

        album_columns = st.columns(columns)
        for index, media_file in enumerate(data):
            with album_columns[index % columns]:
                render_album_tile(media_file)

if __name__ == "__main__":
    st.set_page_config(page_title="Snippet", layout="wide")
    st.title("Snippet")

    render_upload_section()
    render_album_section(4)