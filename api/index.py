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

# --- FINAL FIX FOR 404 ERROR ---
# The endpoint path was incorrect. Many providers use the base URL directly.
# We will also change the payload to a more standard format for instruct models.
RAPIDAPI_URL = "https://mistral-7b-instruct-v0.1.p.rapidapi.com/"
# NOTE: This is an assumed URL. Please double-check it against your provider's documentation.
OPENACCOUNT_API_URL = "https://api.openaccount.com/v1/mistral7b/chat" 

def call_external_api(prompt, model):
    """Calls the appropriate external LLM API based on the model name."""
    if model == 'mistral-rapidapi':
        if not RAPIDAPI_KEY:
            return {"error": "RapidAPI key is not configured on the server."}
        
        # --- FINAL FIX FOR 404 ERROR ---
        # Changed payload to a common format for this type of API.
        # It sends the prompt inside an 'inputs' field.
        payload = {"inputs": f"<|prompter|>{prompt}<|endoftext|><|assistant|>"}
        headers = {
            "content-type": "application/json",
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "mistral-7b-instruct-v0.1.p.rapidapi.com"
        }
        try:
            response = requests.post(RAPIDAPI_URL, json=payload, headers=headers, timeout=30, verify=False)
            response.raise_for_status()
            api_response_data = response.json()
            
            # --- FINAL FIX FOR 404 ERROR ---
            # The response is often a list with a dictionary inside.
            # We will parse it carefully and provide a helpful error if the format is unexpected.
            if isinstance(api_response_data, list) and len(api_response_data) > 0:
                content = api_response_data[0].get('generated_text', '')
                # The model might return the original prompt, so we remove it.
                if prompt in content:
                    content = content.split("<|assistant|>")[1].strip()
                return {"response": content}
            else:
                 return {"error": f"Unexpected API response format from RapidAPI. Response: {api_response_data}"}

        except requests.exceptions.RequestException as e:
            return {"error": f"API call to RapidAPI failed: {e}"}
        except (KeyError, IndexError) as e:
            return {"error": f"Failed to parse API response from RapidAPI. Response: {api_response_data}"}


    elif model == 'mistral-openaccount':
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

