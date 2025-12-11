import streamlit as st
import requests
import os
from dotenv import load_dotenv
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import uuid

load_dotenv()

CREATE = os.getenv('CREATE', '')  # POST
READ  = os.getenv('READ', '')   # GET
UPDATE = os.getenv('UPDATE', '')   # PUT
DELETE = os.getenv('DELETE', '')   # DELETE
CONNECTION = os.getenv('AZURE_CONNECTION_STRING')
CONTAINER = "mediastorage" 
FIREBASE_API_KEY = os.getenv('FIREBASE_API_KEY')

# new feature code

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

def upload_media(create_url, file_object, user_file_name, user_name, user_id, is_private):
    file_extension = os.path.splitext(file_object.name)[1]

    file = {'File': (file_object.name, file_object, file_object.type)}
    data = {
        'fileName': user_file_name,
        'fileExtension': file_extension,
        'userName': user_name,
        'userID': user_id,
        'isPrivate': str(is_private).lower()
    }

    response = requests.post(create_url, files=file, data=data)
    
    return response.status_code

@st.cache_data(ttl=60)
def display_media(read_url, requesting_user_id):
    separator = "&" if "?" in read_url else "?"        
    secure_url = f"{read_url}{separator}userID={quote(requesting_user_id)}"
    response = requests.get(secure_url)
    data = response.json()

    return response.status_code, data

def format_url(url, item_id):
    safe_id = quote(str(item_id), safe='') 
    target_url = url.replace("%7Bid%7D", safe_id)

    return target_url

def update_media_metadata(update_url, document_id, media_file, user_file_name, is_private):
    data = media_file.copy()

    data['fileName'] = user_file_name
    data['isPrivate'] = is_private

    system_keys = [k for k in data.keys() if k.startswith('_')]
    for k in system_keys:
        data.pop(k)
    
    target_url = format_url(update_url, document_id)
    try:
        response = requests.put(target_url, json=data)
        return response.status_code
    except Exception as e: return str(e)

def update_media_likes(update_url, document_id, media_file, new_likes_count):
    data = media_file.copy()

    data['likes'] = new_likes_count

    system_keys = [k for k in data.keys() if k.startswith('_')]
    for k in system_keys:
        data.pop(k)
    
    target_url = format_url(update_url, document_id)
    try:
        response = requests.put(target_url, json=data)
        return response.status_code
    except Exception as e: return str(e)

def update_media_comments(update_url, document_id, media_file, new_comment):
    data = media_file.copy()

    current_comments = data.get('comments', [])
    data['comments'] = list(current_comments) 
    
    data['comments'].append(new_comment)

    system_keys = [k for k in data.keys() if k.startswith('_')]
    for k in system_keys:
        data.pop(k)
    
    target_url = format_url(update_url, document_id)
    try:
        response = requests.put(target_url, json=data)
        return response.status_code
    except Exception as e: return str(e)

def delete_media(delete_url, item_id):
    target_url = format_url(delete_url, item_id)
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

        languages = {
            "Original": "Original",
            "English": "en",
            "French": "fr",
            "Japanese": "ja"
        }
        
        selected_language_name = st.selectbox("Language:", options=list(languages.keys()))
        target_language_code = languages[selected_language_name]
            
        st.divider()

        st.header("Upload")
        with st.form("upload_form"):
            user_file_name = st.text_input("File Name", "")
            uploaded_file = st.file_uploader("Select File")

            is_private = st.toggle("Private", value=True)

            if st.form_submit_button("Upload"):
                if uploaded_file:
                    with st.spinner("Uploading..."):
                        user_name = current_user['email']
                        user_id = current_user['id']

                        status = upload_media(CREATE, uploaded_file, user_file_name, user_name, user_id, is_private)
                        if status == 202: st.success("Upload Started...")
                        else: st.error(f"Error: {status}")
        
        st.divider()

        return target_language_code

def handle_delete(delete_url, document_id):
    response = delete_media(delete_url, document_id)
    if response == 200:
        st.session_state.album_data = [
            item for item in st.session_state.album_data 
            if item.get('id') != document_id
        ]
        st.toast("Deleted.")
    else:
        st.toast(f"Failed: {response}")

def handle_update_metadata(update_url, document_id, media_file, name_key, privacy_key):
    new_user_file_name = st.session_state.get(name_key)
    new_privacy_status = st.session_state.get(privacy_key)

    if new_user_file_name:
        response = update_media_metadata(update_url, document_id, media_file, new_user_file_name, new_privacy_status)
        if response == 200:
            for item in st.session_state.album_data:
                if item['id'] == document_id:
                    item['fileName'] = new_user_file_name
                    item['isPrivate'] = new_privacy_status
                    break
            
            st.session_state.edit_id = None
            st.toast("Updated!")
        else:
            st.toast(f"Failed: {response}")

def handle_update_likes(update_url, document_id, media_file):
    current_likes = media_file.get('likes', 0)
    new_likes = current_likes + 1

    response = update_media_likes(update_url, document_id, media_file, new_likes)
    
    if response == 200:
        for item in st.session_state.album_data:
            if item['id'] == document_id:
                item['likes'] = new_likes
                break
        st.toast("Awarded!")
    else:
        st.toast(f"Failed: {response}")

def handle_update_comments(update_url, document_id, media_file, input_key, current_user_email):
    comment_text = st.session_state.get(input_key)

    if comment_text:
        comment_id = str(uuid.uuid4())

        new_comment = {
            "id": comment_id,
            "user": current_user_email,
            "text": comment_text,
            "timestamp": str(datetime.now()),
            "translations": {}
        }

        response = update_media_comments(update_url, document_id, media_file, new_comment)
        
        if response == 200:
            for item in st.session_state.album_data:
                if item['id'] == document_id:
                    if 'comments' not in item:
                        item['comments'] = []
                    item['comments'].append(new_comment)
                    break
            
            st.session_state[input_key] = "" 
            st.toast("Posted!")
        else:
            st.toast(f"Failed: {response}")

def send_translation_request(update_url, doc_id, comment_timestamp, target_lang, comment_id=None):
    payload = {
        "task": "translate_comment",
        "docID": doc_id,
        "commentTimestamp": comment_timestamp,
        "commentID": comment_id,
        "targetLang": target_lang
    }
    target_url = format_url(update_url, "translation_request")
    
    try:
        requests.put(target_url, json=payload)
        return True
    except Exception:
        return False

def handle_batch_translation(missing_items, update_url, target_lang):
    if 'requested_ids' not in st.session_state:
        st.session_state.requested_ids = set()
    
    new_requests = []
    for item in missing_items:
        unique_id = item.get('id')
        request_key = f"{item['doc_id']}_{unique_id}_{target_lang}"

        if request_key not in st.session_state.requested_ids:
            new_requests.append(item)
            st.session_state.requested_ids.add(request_key)

    if not new_requests:
        return False
        
    for new_request in new_requests:
        comment_id = new_request.get('id')
        send_translation_request(update_url, new_request['doc_id'], new_request['ts'], target_lang, comment_id=comment_id)
    
    return True

def render_album_tile(media_file, current_user, selected_lang_code):
    document_id = media_file.get('id')

    user_file_name = media_file.get('fileName', 'Unknown')
    stored_file_name = media_file.get('uniqueFileName', '')

    file_owner_name = media_file.get('userName', '')
    file_owner_id = media_file.get('userID', '')

    is_private = media_file.get('isPrivate', False)
    likes = media_file.get('likes', 0)
    comments = media_file.get('comments', [])

    secure_url = create_secure_temporary_link(stored_file_name)
    
    with st.container(border=True):
        with st.container(height=300, border=None, horizontal_alignment="center", vertical_alignment="center"):
            if secure_url:
                if stored_file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    st.image(secure_url, width='content')

                elif stored_file_name.lower().endswith(('.mp4', '.mov', '.avi', '.webm')):
                    st.video(secure_url)

        if file_owner_id == current_user['id']:
            is_editing = (st.session_state.edit_id == document_id)

            if is_editing:
                with st.container(border=True):
                    st.caption("Editing")

                    with st.form(f"edit_{document_id}"):
                        input_key_filename = f"input_filename_{document_id}"
                        input_key_privacy = f"input_privacy_{document_id}"

                        st.text_input("New Filename", value=user_file_name, key=input_key_filename)

                        st.toggle("Private", value=is_private, key=input_key_privacy)
                        
                        st.form_submit_button(
                            "Save Changes",
                            use_container_width=True,
                            on_click=handle_update_metadata, 
                            args=(UPDATE, document_id, media_file, input_key_filename, input_key_privacy)
                        )

                    column_delete, column_cancel = st.columns(2)

                    with column_delete:
                        st.button(
                            "Delete", 
                            key=f"delete_{document_id}", 
                            type="primary", 
                            use_container_width=True,
                            on_click=handle_delete, 
                            args=(DELETE, document_id)
                        )
                    
                    with column_cancel:
                        def close_edit():
                            st.session_state.edit_id = None
                        
                        st.button("Cancel", key=f"cancel_{document_id}", use_container_width=True, on_click=close_edit)
            else:
                def open_edit():
                    st.session_state.edit_id = document_id
                
                st.button("Edit", key=f"edit_{document_id}", use_container_width=True, on_click=open_edit)

        column_info, column_like = st.columns([2, 1])
        
        with column_info:
            privacy_icon = "🔴 " if is_private else ""
            st.markdown(f"**{privacy_icon}{user_file_name}**")
            st.caption(f"Uploaded by {file_owner_name}")

        with column_like:
            st.button(
                f"⭐️ {likes}", 
                key=f"like_{document_id}", 
                on_click=handle_update_likes,
                use_container_width=True,
                args=(UPDATE, document_id, media_file)
            )

        with st.form(key=f"comment_form_{document_id}", clear_on_submit=True):
            input_key = f"new_comment_{document_id}"
            
            st.text_input("Write a comment...", key=input_key, label_visibility="visible")
            
            st.form_submit_button(
                "Post",
                use_container_width=True,
                on_click=handle_update_comments,
                args=(UPDATE, document_id, media_file, input_key, current_user['email'])
            )

        with st.container(height=200, border=False):
            if comments:
                for comment in comments:
                    original_text = comment.get('text', '')
                    user_name = comment.get('user', 'anonymous')
                    saved_translations = comment.get('translations', {})

                    if selected_lang_code == "Original":
                        display_text = original_text
                    elif selected_lang_code in saved_translations:
                        display_text = saved_translations[selected_lang_code]
                    else:
                        display_text = original_text 

                    with st.chat_message("user"):
                        st.write(f"**{user_name}**: {display_text}")
                        
                        if selected_lang_code != "Original" and display_text != original_text:
                            st.caption(f"(Original) {original_text}")
            else:
                st.caption("No comments.")


def render_album_section(columns, current_user, target_language_code):
    st.header("Explore")

    if 'edit_id' not in st.session_state:
        st.session_state.edit_id = None

    if 'album_data' not in st.session_state:
        st.session_state.album_data = None

    if st.session_state.album_data is None:
        with st.spinner("Refreshing..."):
            status, data = display_media(READ, current_user['id'])
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

        if target_language_code != "Original":
            missing_translations = []
            
            for file in data:
                is_private = file.get('isPrivate', False)
                owner_id = file.get('userID')
                if not is_private or (is_private and owner_id == current_user['id']):
                    
                    for comment in file.get('comments', []):
                        if target_language_code not in comment.get('translations', {}):
                            missing_translations.append({
                                'doc_id': file['id'],
                                'ts': comment['timestamp'],
                                'id': comment.get('id')
                            })
            
            if missing_translations:
                sent_new_work = handle_batch_translation(missing_translations, UPDATE, target_language_code)                
                if sent_new_work:
                    st.toast(f"Translating...")

        visible_files = []
        for file in data:
            owner_id = file.get('userID')
            is_private = file.get('isPrivate', False)
            
            if not is_private or (is_private and owner_id == current_user['id']):
                visible_files.append(file)
        
        if not visible_files:
            st.info("No media found.")
            return

        with album_container:
            album_columns = st.columns(columns)
            for index, media_file in enumerate(visible_files):
                with album_columns[index % columns]:
                    render_album_tile(media_file, current_user, target_language_code)

if __name__ == "__main__":
    st.set_page_config(page_title="Snippet", layout="wide")

    if 'user' not in st.session_state:
        st.title("Snippet")
        render_login_ui()
    else:
        current_user = st.session_state.user
        st.title("Snippet")
        
        selected_language = render_upload_section(current_user)
        render_album_section(3, current_user, selected_language)

