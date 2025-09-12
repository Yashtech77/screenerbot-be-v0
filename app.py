import os
import re
import jwt
import requests
from io import BytesIO
from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# Google token verification
from google.oauth2 import id_token
from google.auth.transport import requests as grequests

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# --------- VAPI configuration (from .env) ----------
VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_BASE_URL = os.getenv("VAPI_BASE_URL", "https://api.vapi.ai")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")

# --------- Auth configuration (from .env) ----------
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")        # required for verifying Google tokens
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret")   # change this in production
JWT_EXP_HOURS = int(os.getenv("JWT_EXP_HOURS", "1"))
ADMIN_EMAILS = [e.strip() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]

# ---------------------------
# JWT helpers
# ---------------------------
def create_jwt(payload: dict) -> str:
    body = {**payload, "exp": datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS)}
    token = jwt.encode(body, JWT_SECRET, algorithm="HS256")
    # PyJWT may return bytes in some versions; ensure string
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def decode_jwt(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])

# ---------------------------
# Decorators
# ---------------------------
def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401
        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = decode_jwt(token)
            # attach user info to request object
            request.user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except Exception as e:
            return jsonify({"error": f"Invalid token: {str(e)}"}), 401
        return f(*args, **kwargs)
    return wrapper

def role_required(role):
    def decorator(f):
        @wraps(f)
        @auth_required
        def wrapper(*args, **kwargs):
            user = getattr(request, "user", {})
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            if user.get("role") != role:
                return jsonify({"error": "Forbidden - insufficient role"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ---------------------------
# Auth route - Google sign-in verification -> issue JWT
# ---------------------------
@app.route("/auth/google", methods=["POST"])
def google_login():
    """
    Frontend must POST: { "token": "<google-id-token>" }
    Backend verifies token with Google, determines role, returns JWT.
    """
    data = request.get_json() or {}
    token = data.get("token")
    if not token:
        return jsonify({"error": "Google ID token is required"}), 400
    if not GOOGLE_CLIENT_ID:
        return jsonify({"error": "GOOGLE_CLIENT_ID not configured on server"}), 500

    try:
        idinfo = id_token.verify_oauth2_token(token, grequests.Request(), GOOGLE_CLIENT_ID)
        email = idinfo.get("email")
        if not email:
            return jsonify({"error": "Google token did not contain email"}), 400

        role = "admin" if email in ADMIN_EMAILS else "user"
        jwt_token = create_jwt({"email": email, "role": role})

        return jsonify({"success": True, "token": jwt_token, "role": role, "email": email})
    except ValueError as e:
        # token invalid
        return jsonify({"error": f"Invalid Google token: {str(e)}"}), 401
    except Exception as e:
        return jsonify({"error": f"Google verification failed: {str(e)}"}), 500

# ---------------------------
# Root
# ---------------------------
@app.route("/", methods=["GET"])
def root():
    return jsonify({"ok": True, "service": "screenerbot", "version": "v1"})

# ---------------------------
# Outbound Call (Admin only)
# ---------------------------
@app.route('/make-outbound-call', methods=['POST'])
@role_required("admin")
def make_outbound_call():
    data = request.get_json() or {}
    phone_number = data.get('phoneNumber')
    assistant_id = data.get('assistantId')   # accepted from frontend
    knowledge_base_id = data.get('knowledgeBaseId')

    if not phone_number:
        return jsonify({"success": False, "message": "Phone number required"}), 400

    if not re.match(r'^\+\d{8,15}$', phone_number):
        return jsonify({
            "success": False,
            "message": "Invalid phone format. Use E.164 format: +[country code][number] (8-15 digits)"
        }), 400

    if not assistant_id:
        return jsonify({"success": False, "message": "Assistant ID required"}), 400

    try:
        headers = {
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "assistantId": assistant_id,
            "phoneNumberId": VAPI_PHONE_NUMBER_ID,
            "customer": {"number": phone_number}
        }

        if knowledge_base_id:
            payload["knowledgeBaseId"] = knowledge_base_id

        response = requests.post(f"{VAPI_BASE_URL}/call/phone", headers=headers, json=payload)

        if response.status_code == 201:
            return jsonify({
                "success": True,
                "message": "Call initiated successfully",
                "callId": response.json().get("id")
            })

        if response.status_code == 402 or \
           "limit" in (response.text or "").lower() or \
           "exceed" in (response.text or "").lower() or \
           "balance" in (response.text or "").lower():
            return jsonify({
                "success": False,
                "message": "You have exceeded your call limit. Kindly connect to the admin."
            }), 402

        return jsonify({
            "success": False,
            "message": f"Vapi API error: {response.status_code} - {response.text}"
        }), response.status_code

    except Exception as e:
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

# ---------------------------
# Create Assistant (Admin only)
# ---------------------------
@app.route('/create-assistant', methods=['POST'])
@role_required("admin")
def create_assistant():
    try:
        data = request.get_json() or {}

        assistant_name = data.get('name')
        if not assistant_name or assistant_name.strip() == "":
            return jsonify({'error': 'Assistant name is required and cannot be empty'}), 400

        if not data.get('firstMessage'):
            return jsonify({'error': 'firstMessage is required from frontend'}), 400

        system_prompt = data.get('content') or data.get('systemPrompt')
        if not system_prompt or system_prompt.strip() == "":
            return jsonify({'error': 'content or systemPrompt is required and cannot be empty from frontend'}), 400

        assistant_config = {
            'name': assistant_name,
            'firstMessage': data['firstMessage'],
            'firstMessageInterruptionsEnabled': data.get('firstMessageInterruptionsEnabled', True),
            'endCallMessage': data.get('endCallMessage', 'Thank you for your time. Goodbye.'),
            'model': {
                'provider': 'openai',
                'model': 'gpt-4.1-mini',
                'messages': [
                    {
                        'role': 'system',
                        'content': system_prompt + " When the user says goodbye or indicates they want to end the call, use the endCall function."
                    }
                ],
                'tools': [{'type': 'endCall'}]
            },
            'voice': {'provider': 'vapi', 'voiceId': data.get('voiceId', 'Neha')},
            'transcriber': {'provider': 'deepgram', 'model': 'nova-2', 'language': 'multi'},
            'hooks': data.get('hooks', [{
                'on': 'customer.speech.timeout',
                'options': {
                    'timeoutSeconds': 10,
                    'triggerMaxCount': 2,
                    'triggerResetMode': 'onUserSpeech'
                },
                'do': [{'type': 'say', 'prompt': 'Are you still there? Please let me know how I can help you.'}],
                'name': 'customer_timeout_check'
            }])
        }

        response = requests.post(
            f"{VAPI_BASE_URL}/assistant",
            headers={'Authorization': f'Bearer {VAPI_API_KEY}', 'Content-Type': 'application/json'},
            json=assistant_config
        )

        if not response.ok:
            return jsonify({'error': f'VAPI error: {response.status_code} - {response.text}'}), response.status_code

        return jsonify(response.json())

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------------------
# List Assistants (unchanged - open)
# ---------------------------
@app.route('/list-assistants', methods=['GET'])
def list_assistants():
    try:
        response = requests.get(f"{VAPI_BASE_URL}/assistant", headers={"Authorization": f"Bearer {VAPI_API_KEY}"})
        if response.ok:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return jsonify({"id": data[0].get("id"), "name": data[0].get("name", "")})
            return jsonify({"id": os.getenv("DEFAULT_ASSISTANT_ID")})
        else:
            return jsonify({'error': f'Vapi API error: {response.status_code}'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------------------
# Create Campaign (Admin only)
# ---------------------------
@app.route('/create-campaign', methods=['POST'])
@role_required("admin")
def create_campaign():
    data = request.get_json() or {}
    campaign_name = data.get('name')
    phone_number_id = data.get('phoneNumberId')
    assistant_id = data.get('assistantId')
    customers = data.get('customers')

    if not campaign_name or not phone_number_id or not assistant_id or not customers:
        return jsonify({"success": False, "message": "All campaign fields are required"}), 400

    headers = {"Authorization": f"Bearer {VAPI_API_KEY}", "Content-Type": "application/json"}
    payload = {"name": campaign_name, "phoneNumberId": phone_number_id, "assistantId": assistant_id, "customers": customers}

    try:
        response = requests.post(f"{VAPI_BASE_URL}/campaign", headers=headers, json=payload)
        if response.status_code == 201:
            return jsonify({"success": True, "campaign": response.json()})
        else:
            return jsonify({"success": False, "message": f"Vapi API error: {response.status_code} - {response.text}"}), response.status_code
    except Exception as e:
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

# ---------------------------
# Upload files (unchanged - open)
# ---------------------------
@app.route('/upload-files', methods=['POST'])
def upload_files():
    try:
        kb_files = request.files.getlist('knowledgeBase')
        file_ids = []
        for file in kb_files:
            resp = requests.post(f"{VAPI_BASE_URL}/file", headers={'Authorization': f'Bearer {VAPI_API_KEY}'}, files={'file': file})
            resp.raise_for_status()
            file_ids.append(resp.json()['id'])

        kb_response = requests.post(
            f"{VAPI_BASE_URL}/tool",
            headers={'Authorization': f'Bearer {VAPI_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'type': 'query',
                'function': {'name': 'your-query-tool'},
                'knowledgeBases': [{'provider': 'google', 'name': 'your-kb', 'fileIds': file_ids}]
            }
        )
        kb_response.raise_for_status()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------------------
# Delete assistant (Admin only)
# ---------------------------
@app.route('/delete-assistant/<assistant_id>', methods=['DELETE'])
@role_required("admin")
def delete_assistant(assistant_id):
    try:
        response = requests.delete(f"{VAPI_BASE_URL}/assistant/{assistant_id}", headers={"Authorization": f"Bearer {VAPI_API_KEY}"})
        if response.ok:
            return jsonify(response.json())
        else:
            return jsonify({'error': f'Vapi API error: {response.status_code} - {response.text}'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------------------
# Get call logs (Admin only)
# ---------------------------
@app.route('/get-call-logs', methods=['GET'])
@role_required("admin")
def get_call_logs():
    try:
        response = requests.get(f"{VAPI_BASE_URL}/call", headers={"Authorization": f"Bearer {VAPI_API_KEY}"})
        if response.ok:
            data = response.json()
            filtered_logs = []
            for call in data:
                filtered_logs.append({
                    "id": call.get("id"),
                    "type": call.get("type"),
                    "createdAt": call.get("createdAt") or call.get("startedAt"),
                    "startedAt": call.get("startedAt"),
                    "endedAt": call.get("endedAt")
                })
            return jsonify(filtered_logs)
        else:
            return jsonify({'error': f'Vapi API error: {response.status_code} - {response.text}'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------------------
# Get single call (open)
# ---------------------------
@app.route('/call/<call_id>', methods=['GET'])
def get_call(call_id):
    try:
        response = requests.get(f"{VAPI_BASE_URL}/call/{call_id}", headers={"Authorization": f"Bearer {VAPI_API_KEY}"})
        if not response.ok:
            return jsonify({"error": f"VAPI API error: {response.status_code}"}), response.status_code

        data = response.json()
        result = {
            "id": data.get("id"),
            "type": data.get("type"),
            "transcript": data.get("transcript") or data.get("messagesOpenAIFormatted"),
            "createdAt": data.get("createdAt") or data.get("startedAt"),
            "recordingUrl": None
        }

        recording_url = data.get("recordingUrl") or (data.get("artifacts") or [{}])[0].get("recordingUrl")
        if recording_url:
            recording_id = recording_url.split("/")[-1]
            extension = recording_id.split('.')[-1] if '.' in recording_id else "wav"
            result["recordingUrl"] = f"/recording/{recording_id}?ext={extension}"

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------
# Proxy recording (open)
# ---------------------------
@app.route('/recording/<recording_id>', methods=['GET'])
def get_recording(recording_id):
    try:
        ext = request.args.get("ext", "wav").lower()
        original_url = f"https://storage.vapi.ai/{recording_id}"
        response = requests.get(original_url, stream=True)
        if not response.ok:
            return jsonify({"error": "Failed to fetch recording from VAPI"}), response.status_code

        mimetype = "audio/wav" if ext == "wav" else "audio/mpeg"
        return send_file(BytesIO(response.content), mimetype=mimetype, as_attachment=False, download_name=recording_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
