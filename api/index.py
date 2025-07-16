from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import urllib3

# Suppress only the InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- API Configuration ---
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY')
OPENACCOUNT_API_KEY = os.environ.get('OPENACCOUNT_API_KEY')

# --- FINAL FIX: PLEASE CONFIGURE THESE VALUES ---

# 1. For RapidAPI:
# Go to your RapidAPI dashboard, find the API you subscribed to, and get the correct Host and URL.
# The error "API doesn't exists" means the host below is WRONG for your key.
RAPIDAPI_HOST = "mistral-7b-instruct-v0.1.p.rapidapi.com" # <-- REPLACE THIS with the correct host from RapidAPI
RAPIDAPI_URL = f"https://{RAPIDAPI_HOST}/" # The URL is built from the host.

# 2. For OpenAccount:
# The error "NameResolutionError" means the URL below is WRONG.
# PLEASE REPLACE THE URL BELOW WITH THE CORRECT ONE FROM YOUR API PROVIDER'S DOCUMENTATION.
OPENACCOUNT_API_URL = "https://api.your-openaccount-provider.com/v1/chat" # <-- REPLACE THIS with the correct URL.

def call_external_api(prompt, model):
    """Calls the appropriate external LLM API based on the model name."""
    if model == 'mistral-rapidapi':
        if not RAPIDAPI_KEY:
            return {"error": "RapidAPI key is not configured on the server."}
        
        payload = {"message": prompt}
        headers = {
            "content-type": "application/json",
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST # Using the variable from above
        }
        try:
            response = requests.post(RAPIDAPI_URL, json=payload, headers=headers, timeout=30, verify=False)
            response.raise_for_status()
            api_response_data = response.json()
            content = api_response_data.get('output', f"Error: Could not find 'output' in API response. Full response: {api_response_data}")
            return {"response": content}
        except requests.exceptions.HTTPError as e:
            return {"error": f"API call to RapidAPI failed: {e}. Response: {e.response.text}"}
        except Exception as e:
            return {"error": f"An unexpected error occurred with the RapidAPI call: {e}"}

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
