import os
import time
import json
import base64
from dotenv import load_dotenv
from azure.storage.queue import QueueClient
from azure.cosmos import CosmosClient
import requests
import uuid

load_dotenv()

STORAGE_CONNECTION = os.getenv('AZURE_CONNECTION_STRING')
QUEUE_NAME = "media-processing"
COSMOS_URL = os.getenv('COSMOS_ENDPOINT') 
COSMOS_KEY = os.getenv('COSMOS_KEY')
DATABASE_NAME = "mediacollection"
CONTAINER_NAME = "snippetmediacollection"
TRANSLATOR_KEY = os.getenv('AZURE_TRANSLATOR_KEY')
TRANSLATOR_REGION = os.getenv('AZURE_TRANSLATOR_REGION')
TRANSLATOR_ENDPOINT = "https://api.cognitive.microsofttranslator.com"

# new feature code

def process_upload(job_data):
    try:
        client = CosmosClient(COSMOS_URL, credential=COSMOS_KEY)
        database = client.get_database_client(DATABASE_NAME)
        container = database.get_container_client(CONTAINER_NAME)

        is_private = job_data.get('isPrivate', 'false')
        is_private_bool = str(is_private).lower() == 'true'

        new_document = {
            "id": job_data['id'],
            "fileName": job_data['fileName'],
            "uniqueFileName": job_data['blobName'],
            "userName": job_data['userName'],
            "userID": job_data['userID'],
            "filePath": f"/mediastorage/{job_data['blobName']}",
            "isPrivate": is_private_bool,
            "likes": 0,
            "comments": []
        }

        container.upsert_item(new_document)
        return True

    except Exception as e: return False

def call_azure_translator(text, target_language):
    path = '/translate'
    url = TRANSLATOR_ENDPOINT + path
    params = {'api-version': '3.0', 'to': target_language}
    headers = {
        'Ocp-Apim-Subscription-Key': TRANSLATOR_KEY,
        'Ocp-Apim-Subscription-Region': TRANSLATOR_REGION,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    body = [{'text': text}]
    
    try:
        resp = requests.post(url, params=params, headers=headers, json=body)
        return resp.json()[0]['translations'][0]['text']
    except Exception as e: return None

def process_comment_translation(job_data):
    try:
        client = CosmosClient(COSMOS_URL, credential=COSMOS_KEY)
        container = client.get_database_client(DATABASE_NAME).get_container_client(CONTAINER_NAME)
        
        doc_id = job_data['docID']
        target_language = job_data['targetLang']
        comment_timestamp = job_data['commentTimestamp']
        comment_id = job_data.get('commentID')

        query = "SELECT * FROM c WHERE c.id = @id"
        items = list(container.query_items(query=query, parameters=[{"name":"@id", "value": doc_id}], enable_cross_partition_query=True))
        
        if not items: return False
        doc = items[0]
        
        updated = False
        if 'comments' in doc:
            for comment in doc['comments']:
                match = False
                
                if comment_id and comment.get('id') == comment_id:
                    match = True

                if match:
                    text_to_translate = comment.get('text')
                    
                    translated_text = call_azure_translator(text_to_translate, target_language)
                    
                    if translated_text:
                        if 'translations' not in comment:
                            comment['translations'] = {}
                        
                        comment['translations'][target_language] = translated_text
                        updated = True
                    break
        
        if updated:
            container.upsert_item(doc)
            return True
            
        return False

    except Exception as e: return False

def worker():
    queue = QueueClient.from_connection_string(STORAGE_CONNECTION, QUEUE_NAME)

    while True:
        messages = queue.receive_messages(visibility_timeout=30)

        for msg in messages:
            try:
                message_body = msg.content
                try:
                    decoded_bytes = base64.b64decode(message_body)
                    json_str = decoded_bytes.decode('utf-8')
                except:
                    json_str = message_body
                
                job_data = json.loads(json_str)
                success = False

                if job_data.get('task') == 'translate_comment':
                    success = process_comment_translation(job_data)

                elif 'blobName' in job_data:
                    success = process_upload(job_data)
                
                else:
                    success = True

                if success:
                    queue.delete_message(msg)
                
            except Exception as e: print(f"{e}")
        
        time.sleep(2)

if __name__ == "__main__":
    worker()
