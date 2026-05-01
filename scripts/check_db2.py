import os
from dotenv import load_dotenv
load_dotenv()
import httpx

url = f"{os.getenv('SUPABASE_URL')}/rest/v1/chat_messages"
headers = {
    'apikey': os.getenv('SUPABASE_SERVICE_ROLE_KEY'), 
    'Authorization': f"Bearer {os.getenv('SUPABASE_SERVICE_ROLE_KEY')}"
}
resp = httpx.get(url, headers=headers)
print(resp.json())
