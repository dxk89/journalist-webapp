# File: journalist_webapp/app.py

import os
import threading
import time
import json
from flask import Flask, render_template, request, jsonify
import requests

# --- Flask App Setup ---
app = Flask(__name__)

# --- Logging ---
def log_message(message):
    """Prints a message with a timestamp. This will show up in your server logs."""
    timestamp = time.strftime('%H:%M:%S')
    print(f"{timestamp} - {message}", flush=True)

# ==============================================================================
#  START: ENVIRONMENT DETECTION
# ==============================================================================
# Render.com automatically sets an environment variable called 'RENDER' to 'true'.
# We can check for this variable to know if we are in production or testing locally.
IS_ON_RENDER = os.environ.get('RENDER', False)

if IS_ON_RENDER:
    # If we are on Render, get the public URL of our reasoning engine from another
    # environment variable, which we will set in the Render dashboard.
    FRAMEWORK_API_URL = os.environ.get("FRAMEWORK_API_URL")
    log_message("🚀 Running in PRODUCTION mode on Render.com")
else:
    # If we are not on Render, we are running locally.
    # We will connect to our reasoning engine which is also running locally.
    FRAMEWORK_API_URL = "http://localhost:8000/invoke"
    log_message("🖥️  Running in LOCAL mode for testing")

if not FRAMEWORK_API_URL:
    log_message("🔥🔥🔥 FATAL ERROR: The URL for the reasoning engine is not set.")
# ==============================================================================
#  END: ENVIRONMENT DETECTION
# ==============================================================================


def run_bot_logic_worker(config_data):
    """
    This function acts as a proxy. It takes all the configuration from the browser,
    forwards it to your main reasoning engine API, and waits for the full process.
    """
    log_func = log_message
    log_func("🤖 Bot thread started. Forwarding request to reasoning engine...")

    # The payload for our reasoning engine API
    api_payload = {
        "input": config_data
    }

    try:
        # Make the POST request to our reasoning engine server (either local or on Render)
        # We set a very long timeout because the full process can take several minutes.
        response = requests.post(FRAMEWORK_API_URL, json=api_payload, timeout=1800) # 30 minute timeout
        response.raise_for_status() 
        log_func("✅ Successfully received response from reasoning engine.")
    except Exception as e:
        log_func(f"🔥🔥🔥 Error communicating with reasoning engine: {e}")

# --- Flask Routes ---
@app.route('/')
def index():
    """Serves the main HTML page to the user's browser."""
    return render_template('index.html')

@app.route('/run-bot', methods=['POST'])
def run_bot():
    """
    This is the endpoint that the browser calls. It receives the configuration
    and starts the main workflow in a background thread so the UI doesn't freeze.
    """
    config_data = request.json
    
    # Simple validation to ensure an API key is present
    ai_model = config_data.get('ai_model')
    if ai_model == 'openai' and not config_data.get('openai_api_key'):
        return jsonify({'status': 'error', 'message': 'Missing OpenAI API Key.'}), 400
    if ai_model == 'gemini' and not config_data.get('gemini_api_key'):
        return jsonify({'status': 'error', 'message': 'Missing Gemini API Key.'}), 400
    
    # Start the main logic in a background thread
    thread = threading.Thread(target=run_bot_logic_worker, args=(config_data,))
    thread.daemon = True
    thread.start()
    
    # Immediately tell the user's browser that the process has started
    return jsonify({'status': 'success', 'message': 'Bot process started. Check the server logs for progress.'})

# --- Main Execution ---
if __name__ == '__main__':
    # This allows Render to set the port, while defaulting to 5000 for local testing.
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)