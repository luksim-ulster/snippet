import streamlit as st
import requests
import os
from dotenv import load_dotenv
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta, timezone

load_dotenv()

IUPS = os.getenv('IUPS', '')  # POST
RAI  = os.getenv('RAI', '')   # GET
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

def render_album_tile(media_file):
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
        
    st.divider()

def render_album_section(columns):
    st.header("Album")
    if st.button("Load"):
        with st.spinner("Loading..."):
            status, data = display_media(RAI)

            if not data:
                st.info("No media available.")
            elif status == 200:
                album_columns = st.columns(columns)
                for index, media_file in enumerate(data):
                    with album_columns[index % columns]:
                        render_album_tile(media_file)
            else: st.error(f"Error: {status}")

if __name__ == "__main__":
    st.set_page_config(page_title="Snippet", layout="wide")
    st.title("Snippet")

    render_upload_section()
    render_album_section(4)