from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import urllib3

# Suppress only the InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- API Configuration ---
HUGGINGFACE_API_KEY = os.environ.get('HUGGINGFACE_API_KEY') 
OPENACCOUNT_API_KEY = os.environ.get('OPENACCOUNT_API_KEY')

# --- API URLs ---
# This is the correct, standard URL for the Hugging Face Inference API.
HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
# You have correctly identified the OpenRouter URL.
OPENACCOUNT_API_URL = "https://openrouter.ai/api/v1/chat/completions"

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

            if isinstance(api_response_data, list) and len(api_response_data) > 0:
                content = api_response_data[0].get('generated_text', '')
                if content.startswith(prompt):
                    content = content[len(prompt):].strip()
                return {"response": content}
            else:
                # This handles cases where the model is loading and returns an error object
                if isinstance(api_response_data, dict) and 'error' in api_response_data:
                    return {"error": f"Hugging Face API Error: {api_response_data['error']}"}
                return {"error": f"Unexpected API response format from Hugging Face. Response: {api_response_data}"}

        except requests.exceptions.HTTPError as e:
            return {"error": f"API call to Hugging Face failed: {e}. Response: {e.response.text}"}
        except Exception as e:
            return {"error": f"An unexpected error occurred with the Hugging Face call: {e}"}

    elif model == 'mistral-openaccount':
        if not OPENACCOUNT_API_KEY:
            return {"error": "OpenAccount (OpenRouter) API key is not configured on the server."}
        
        # --- FIX FOR 400 BAD REQUEST ---
        # 1. The 'model' name must be the specific identifier used by OpenRouter.
        # 2. OpenRouter requires two custom headers: HTTP-Referer and X-Title.
        payload = { 
            "model": "mistralai/mistral-7b-instruct", # Correct model identifier for OpenRouter
            "messages": [{"role": "user", "content": prompt}] 
        }
        headers = { 
            "Authorization": f"Bearer {OPENACCOUNT_API_KEY}",
            "HTTP-Referer": "https://final-chat-app.vercel.app", # Replace with your Vercel URL
            "X-Title": "Final Chat App" # Can be any name for your app
        }
        try:
            response = requests.post(OPENACCOUNT_API_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            api_response_data = response.json()
            content = api_response_data['choices'][0]['message']['content']
            return {"response": content}
        except requests.exceptions.HTTPError as e:
            return {"error": f"API call to OpenRouter failed: {e}. Response: {e.response.text}"}
        except (KeyError, IndexError) as e:
            return {"error": f"Failed to parse API response from OpenRouter. Response: {api_response_data}"}
            
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
