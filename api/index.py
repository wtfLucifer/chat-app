from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import urllib3
import datetime

# Suppress only the InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- API Configuration ---
HUGGINGFACE_API_KEY = os.environ.get('HUGGINGFACE_API_KEY') 
OPENACCOUNT_API_KEY = os.environ.get('OPENACCOUNT_API_KEY')

# --- API URLs ---
# FINAL DIAGNOSTIC: Using a sentence-similarity model to guarantee a connection.
HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
# You have correctly identified the OpenRouter URL.
OPENACCOUNT_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# --- DEBUGGING VERSION ---
# We will use this to confirm the new code is deployed.
APP_VERSION = "v4.0-similarity-diagnostic"

def call_external_api(prompt, model):
    """Calls the appropriate external LLM API based on the model name."""
    if model == 'mistral-huggingface':
        if not HUGGINGFACE_API_KEY:
            return {"error": "Hugging Face API key is not configured on the server."}
        
        # Payload for the sentence similarity model.
        payload = {
            "inputs": {
                "source_sentence": prompt,
                "sentences": [
                    "That is a happy sentence.",
                    "That is an angry sentence."
                ]
            }
        }
        headers = { "Authorization": f"Bearer {HUGGINGFACE_API_KEY}" }
        
        try:
            response = requests.post(HUGGINGFACE_API_URL, json=payload, headers=headers, timeout=45)
            response.raise_for_status()
            api_response_data = response.json()

            # The response is a list of similarity scores.
            if isinstance(api_response_data, list) and len(api_response_data) == 2:
                content = f"Similarity to 'happy': {round(api_response_data[0], 2)}. Similarity to 'angry': {round(api_response_data[1], 2)}."
                return {"response": content}
            else:
                if isinstance(api_response_data, dict) and 'error' in api_response_data:
                    if "is currently loading" in api_response_data['error']:
                        return {"error": f"Model is loading, please try again in {int(api_response_data.get('estimated_time', 20))} seconds."}
                    return {"error": f"Hugging Face API Error: {api_response_data['error']}"}
                return {"error": f"Unexpected API response format from Hugging Face. Response: {api_response_data}"}

        except requests.exceptions.HTTPError as e:
            return {"error": f"API call to Hugging Face failed: {e}. Response: {e.response.text}"}
        except Exception as e:
            return {"error": f"An unexpected error occurred with the Hugging Face call: {e}"}

    elif model == 'mistral-openaccount':
        if not OPENACCOUNT_API_KEY:
            return {"error": "OpenAccount (OpenRouter) API key is not configured on the server."}
        
        payload = { 
            "model": "mistralai/mistral-7b-instruct",
            "messages": [{"role": "user", "content": prompt}] 
        }
        headers = { 
            "Authorization": f"Bearer {OPENACCOUNT_API_KEY}",
            "HTTP-Referer": "https://final-chat-app.vercel.app", 
            "X-Title": "Final Chat App"
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
    def do_GET(self):
        """Handles GET requests for debugging."""
        if self.path == '/api' or self.path == '/api/':
            self.send_response(200)
            self.send_header('Content-type','application/json')
            self.end_headers()
            response = {
                "status": "ok",
                "version": APP_VERSION,
                "timestamp": datetime.datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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
