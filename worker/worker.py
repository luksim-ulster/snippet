import os
import time
import json
import base64
from dotenv import load_dotenv
from azure.storage.queue import QueueClient
from azure.cosmos import CosmosClient

load_dotenv()

STORAGE_CONNECTION = os.getenv('AZURE_CONNECTION_STRING')
QUEUE_NAME = "media-processing"
COSMOS_URL = os.getenv('COSMOS_ENDPOINT') 
COSMOS_KEY = os.getenv('COSMOS_KEY')
DATABASE_NAME = "mediacollection"
CONTAINER_NAME = "snippetmediacollection"

def process_upload(job_data):
    try:
        client = CosmosClient(COSMOS_URL, credential=COSMOS_KEY)
        database = client.get_database_client(DATABASE_NAME)
        container = database.get_container_client(CONTAINER_NAME)

        new_document = {
            "id": job_data['id'],
            "fileName": job_data['fileName'],
            "uniqueFileName": job_data['blobName'],
            "userName": job_data['userName'],
            "userID": job_data['userID'],
            "filePath": f"/mediastorage/{job_data['blobName']}"
        }

        container.upsert_item(new_document)
        return True

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

                if process_upload(job_data):
                    queue.delete_message(msg)
                
            except Exception as e: print(f"{e}")
        
        time.sleep(2)

if __name__ == "__main__":
    worker()
