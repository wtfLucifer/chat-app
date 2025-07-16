from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import urllib3
import datetime

# Suppress only the InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- API Configuration ---
# We now only need one key, for the working OpenRouter service.
OPENROUTER_API_KEY = os.environ.get('OPENACCOUNT_API_KEY') # Using the same Vercel variable name
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# --- DEBUGGING VERSION ---
APP_VERSION = "v6.1-nous-hermes-fix"

def call_openrouter(prompt, model_identifier):
    """A single, reliable function to call the OpenRouter API."""
    if not OPENROUTER_API_KEY:
        return {"error": "API key is not configured on the server."}

    payload = { 
        "model": model_identifier,
        "messages": [{"role": "user", "content": prompt}] 
    }
    headers = { 
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://final-chat-app.vercel.app", # Replace with your Vercel URL
        "X-Title": "Final Chat App" # Can be any name
    }
    try:
        response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        api_response_data = response.json()
        content = api_response_data['choices'][0]['message']['content']
        return {"response": content}
    except requests.exceptions.HTTPError as e:
        return {"error": f"API call to OpenRouter failed for model {model_identifier}: {e}. Response: {e.response.text}"}
    except (KeyError, IndexError) as e:
        return {"error": f"Failed to parse API response from OpenRouter. Response: {api_response_data}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}


def call_external_api(prompt, model):
    """Calls the appropriate external LLM API based on the model name."""
    if model == 'gemma-7b':
        # FIX: Switched to a different reliable free model on OpenRouter.
        return call_openrouter(prompt, "nousresearch/nous-hermes-2-mixtral-8x7b-dpo")
    elif model == 'mistral-7b':
        # Using the Mistral model via OpenRouter
        return call_openrouter(prompt, "mistralai/mistral-7b-instruct")
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
