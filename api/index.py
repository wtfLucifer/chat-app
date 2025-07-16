from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import urllib3

# Suppress only the InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- API Configuration ---
# NEW: Key for the Hugging Face API
HUGGINGFACE_API_KEY = os.environ.get('HUGGINGFACE_API_KEY') 
OPENACCOUNT_API_KEY = os.environ.get('OPENACCOUNT_API_KEY')


# --- PLEASE CONFIGURE THIS VALUE ---
# The error "NameResolutionError" means the URL below is WRONG.
# PLEASE REPLACE THE URL BELOW WITH THE CORRECT ONE FROM YOUR API PROVIDER'S DOCUMENTATION.
OPENACCOUNT_API_URL = "https://openrouter.ai/api/v1/chat/completions" # <-- PASTE YOUR CORRECT URL HERE


# --- No need to edit below this line ---
HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"

def call_external_api(prompt, model):
    """Calls the appropriate external LLM API based on the model name."""
    if model == 'mistral-huggingface':
        if not HUGGINGFACE_API_KEY:
            return {"error": "Hugging Face API key is not configured on the server."}
        
        payload = {"inputs": prompt}
        headers = { "Authorization": f"Bearer {HUGGINGFACE_API_KEY}" }
        
        try:
            response = requests.post(HUGGINGFACE_API_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            api_response_data = response.json()

            # The response is a list with a dictionary inside.
            if isinstance(api_response_data, list) and len(api_response_data) > 0:
                content = api_response_data[0].get('generated_text', '')
                # The model often returns the original prompt, so we remove it.
                if content.startswith(prompt):
                    content = content[len(prompt):].strip()
                return {"response": content}
            else:
                return {"error": f"Unexpected API response format from Hugging Face. Response: {api_response_data}"}

        except requests.exceptions.RequestException as e:
            return {"error": f"API call to Hugging Face failed: {e}"}
        except Exception as e:
            return {"error": f"An unexpected error occurred with the Hugging Face call: {e}"}

    elif model == 'mistral-openaccount':
        if "your-openaccount-provider.com" in OPENACCOUNT_API_URL:
            return {"error": "The OpenAccount API URL has not been configured in api/index.py."}
        if not OPENACCOUNT_API_KEY:
            return {"error": "OpenAccount API key is not configured on the server."}
        
        payload = { "model": "mistral-7b", "messages": [{"role": "user", "content": prompt}] }
        headers = { "Content-Type": "application/json", "Authorization": f"Bearer {OPENACCOUNT_API_KEY}" }
        try:
            response = requests.post(OPENACCOUNT_API_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            api_response_data = response.json()
            content = api_response_data['choices'][0]['message']['content']
            return {"response": content}
        except requests.exceptions.RequestException as e:
            return {"error": f"API call to OpenAccount failed: {e}"}
        except (KeyError, IndexError) as e:
            return {"error": f"Failed to parse API response from OpenAccount. Response: {api_response_data}"}
            
    else:
        return {"error": "Invalid model specified."}

class handler(BaseHTTPRequestHandler):
    """Vercel's required handler class for Python serverless functions."""
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(content_length))
            prompt, model = body.get('prompt'), body.get('model')

            if not prompt or not model:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Prompt and model are required."}).encode('utf-8'))
                return

            response_data = call_external_api(prompt, model)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"An internal server error occurred: {e}"}).encode('utf-8'))
