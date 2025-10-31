import os
import re
from io import BytesIO
from flask import Flask, render_template, request, jsonify,send_file
import requests
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# Vapi configuration from .env
VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_BASE_URL = os.getenv("VAPI_BASE_URL")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")


@app.route("/", methods=["GET"])
def root():
    return jsonify({"ok": True, "service": "screenerbot", "version": "v1"})


 
@app.route('/make-outbound-call', methods=['POST'])
def make_outbound_call():
    data = request.json
    phone_number = data.get('phoneNumber')
    assistant_id = data.get('assistantId')   # ✅ accept from frontend
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
            "assistantId": assistant_id,                 # ✅ dynamic now
            "phoneNumberId": VAPI_PHONE_NUMBER_ID,
            "customer": {"number": phone_number}
        }

        # optionally include knowledgeBaseId if passed
        if knowledge_base_id:
            payload["knowledgeBaseId"] = knowledge_base_id

        response = requests.post(
            f"{VAPI_BASE_URL}/call/phone",
            headers=headers,
            json=payload
        )

        # ✅ success
        if response.status_code == 201:
            return jsonify({
                "success": True,
                "message": "Call initiated successfully",
                "callId": response.json().get("id")
            })

        # ✅ handle limit exceeded / recharge issue
        if response.status_code == 402 or \
           "limit" in response.text.lower() or \
           "exceed" in response.text.lower() or \
           "balance" in response.text.lower():
            return jsonify({
                "success": False,
                "message": "You have exceeded your call limit . Kindly connect to the admin."
            }), 402

        # ✅ other errors
        return jsonify({
            "success": False,
            "message": f"Vapi API error: {response.status_code} - {response.text}"
        }), response.status_code

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Server error: {str(e)}"
        }), 500


@app.route('/create-assistant', methods=['POST'])
def create_assistant():
    try:
        data = request.json
 
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
                'tools': [
                    {
                        'type': 'endCall'
                    }
                ]
            },
            # 'voice': {
            #     'provider': 'vapi',
            #     'voiceId': 'Neha'
            # },
            # 'transcriber': {
            #     'provider': 'deepgram',
            #     'model': 'nova-2',
            #     'language': 'multi'
            # },
             'voice': {
                'provider': '11labs',
                'voiceId': 'nlRBcodAo9LA6ChkhS0i'
            },
            'transcriber': {
                'provider': 'deepgram',
                'model': 'nova-2',
                'language': 'multi'
            },
            'hooks': [{
                'on': 'customer.speech.timeout',
                'options': {
                    'timeoutSeconds': 10,
                    'triggerMaxCount': 2,
                    'triggerResetMode': 'onUserSpeech'
                },
                'do': [{
                    'type': 'say',
                    'prompt': 'Are you still there? Please let me know how I can help you.'
                }],
                'name': 'customer_timeout_check'
            }]
        }
 
        print("Sending to VAPI:", assistant_config)
 
        response = requests.post(
            'https://api.vapi.ai/assistant',
            headers={
                'Authorization': f'Bearer {VAPI_API_KEY}',
                'Content-Type': 'application/json'
            },
            json=assistant_config
        )
 
        if not response.ok:
            print(f"VAPI error: {response.status_code} - {response.text}")
            raise Exception(f'Failed to create assistant: {response.text}')
 
        result = response.json()
        print(f"Successfully created assistant with ID: {result.get('id')}")
        return jsonify(result)
 
    except Exception as e:
        print(f"Error creating assistant: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/list-assistants', methods=['GET'])
def list_assistants():
    try:
        response = requests.get(
            "https://api.vapi.ai/assistant",
            headers={"Authorization": f"Bearer {VAPI_API_KEY}"}
        )

        if response.ok:
            data = response.json()
            # Return minimal info for all assistants
            if isinstance(data, list) and len(data) > 0:
                assistants = [
                    {"id": item.get("id"), "name": item.get("name", "")}
                    for item in data
                ]
                return jsonify(assistants)
            return jsonify([{
                "id": os.getenv("DEFAULT_ASSISTANT_ID"),
                "name": "Default Assistant"
            }])

        # Mask error — no Vapi details shown
        return jsonify({
            'error': 'Unable to load assistants right now. Please try again later.'
        }), 502

    except requests.exceptions.RequestException:
        return jsonify({
            'error': 'Connection issue. Please try again later.'
        }), 502

    except Exception:
        return jsonify({
            'error': 'Something went wrong. Please contact support if it continues.'
        }), 500


@app.route('/create-campaign', methods=['POST'])
def create_campaign():
    data = request.json
    campaign_name = data.get('name')
    phone_number_id = data.get('phoneNumberId')
    assistant_id = data.get('assistantId')
    customers = data.get('customers')
 
    if not campaign_name or not phone_number_id or not assistant_id or not customers:
        return jsonify({"success": False, "message": "All campaign fields are required"}), 400
 
    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": campaign_name,
        "phoneNumberId": phone_number_id,
        "assistantId": assistant_id,
        "customers": customers
    }
 
    try:
        response = requests.post(
            f"{VAPI_BASE_URL}/campaign",
            headers=headers,
            json=payload
        )
        if response.status_code == 201:
            return jsonify({"success": True, "campaign": response.json()})
        else:
            return jsonify({
                "success": False,
                "message": f"Vapi API error: {response.status_code} - {response.text}"
            }), response.status_code
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/upload-files', methods=['POST'])
def upload_files():
    try:
        # Only handle knowledge base files
        kb_files = request.files.getlist('knowledgeBase')
        file_ids = []
        for file in kb_files:
            response = requests.post(
                'https://api.vapi.ai/file',
                headers={'Authorization': f'Bearer {VAPI_API_KEY}'},
                files={'file': file}
            )
            file_ids.append(response.json()['id'])
        # Create knowledge base
        kb_response = requests.post(
            'https://api.vapi.ai/tool',
            headers={
                'Authorization': f'Bearer {VAPI_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'type': 'query',
                'function': {'name': 'your-query-tool'},
                'knowledgeBases': [{
                    'provider': 'google',
                    'name': 'your-kb',
                    'fileIds': file_ids
                }]
            }
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/delete-assistant/<assistant_id>', methods=['DELETE'])
def delete_assistant(assistant_id):
    try:
        response = requests.delete(
            f"https://api.vapi.ai/assistant/{assistant_id}",
            headers={"Authorization": f"Bearer {VAPI_API_KEY}"}
        )

        if response.ok:
            return jsonify({"message": "Assistant deleted successfully"}), 200
        elif response.status_code == 404:
            # Mask real API details
            return jsonify({"error": "Assistant not found"}), 404
        elif response.status_code == 401:
            return jsonify({"error": "Unauthorized request"}), 401
        else:
            return jsonify({
                "error": "Failed to delete assistant. Please try again later."
            }), 500
    except requests.exceptions.RequestException:
        return jsonify({
            "error": "Network error while connecting to assistant service."
        }), 502
    except Exception:
        return jsonify({
            "error": "Unexpected server error."
        }), 500

 
@app.route('/get-call-logs', methods=['GET'])
def get_call_logs():
    try:
        response = requests.get(
            "https://api.vapi.ai/call",
            headers={
                "Authorization": f"Bearer {VAPI_API_KEY}"
            }
        )
        if response.ok:
            data = response.json()
            # Filter only required fields
            filtered_logs = []
            for call in data:
                filtered_logs.append({
                    "id": call.get("id"),          # call ID
                    "type": call.get("type"),      # call type (inbound/outbound)
                     "createdAt": call.get("createdAt") or call.get("startedAt"),  # fallback
                    "startedAt": call.get("startedAt"), # call start time
                    "endedAt": call.get("endedAt") # call ended time
                })
            return jsonify(filtered_logs)
        else:
            return jsonify({'error': f'Vapi API error: {response.status_code} - {response.text}'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# @app.route('/call/<call_id>', methods=['GET'])
# def get_call(call_id):
#     """
#     Fetch minimal call details for frontend
#     """
#     try:
#         response = requests.get(
#             f"{VAPI_BASE_URL}/call/{call_id}",
#             headers={"Authorization": f"Bearer {VAPI_API_KEY}"}
#         )
#         if not response.ok:
#             return jsonify({"error": f"VAPI API error: {response.status_code}"}), response.status_code

#         data = response.json()
#         result = {
#             "id": data.get("id"),
#             "type": data.get("type"),
#             "transcript": data.get("transcript") or data.get("messagesOpenAIFormatted"),
#             "createdAt": data.get("createdAt") or data.get("startedAt"),
#             "recordingUrl": None
#         }

#         # Proxy recording URL
#         recording_url = data.get("recordingUrl") or (data.get("artifacts") or [{}])[0].get("recordingUrl")
#         if recording_url:
#             recording_id = recording_url.split("/")[-1]
#             extension = recording_id.split('.')[-1] if '.' in recording_id else "wav"
#             result["recordingUrl"] = f"/recording/{recording_id}?ext={extension}"

#         return jsonify(result)

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
@app.route('/call/<call_id>', methods=['GET'])
def get_call(call_id):
    """
    Fetch minimal call details for frontend, including structured outputs
    """
    try:
        response = requests.get(
            f"{VAPI_BASE_URL}/call/{call_id}",
            headers={"Authorization": f"Bearer {VAPI_API_KEY}"}
        )
        if not response.ok:
            return jsonify({"error": f"VAPI API error: {response.status_code}"}), response.status_code
        
        data = response.json()
        
        # Extract structured outputs from the artifact section
        structured_outputs = {}
        artifact = data.get("artifact", {})
        if "structuredOutputs" in artifact:
            for key, value in artifact["structuredOutputs"].items():
                name = value.get("name")
                result_val = value.get("result")
                if name:
                    structured_outputs[name] = result_val
        
        result = {
            "id": data.get("id"),
            "type": data.get("type"),
            "transcript": data.get("transcript") or data.get("messagesOpenAIFormatted"),
            "createdAt": data.get("createdAt") or data.get("startedAt"),
            "recordingUrl": None,
            "structuredOutputs": structured_outputs  # Use the extracted structured outputs
        }
        
        # Proxy recording URL - check both locations
        recording_url = (
            data.get("recordingUrl") or 
            artifact.get("recordingUrl")
        )
        
        if recording_url:
            recording_id = recording_url.split("/")[-1]
            extension = recording_id.split('.')[-1] if '.' in recording_id else "wav"
            result["recordingUrl"] = f"/recording/{recording_id}?ext={extension}"
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/recording/<recording_id>', methods=['GET'])
def get_recording(recording_id):
    """
    Proxy recording audio from VAPI
    """
    try:
        ext = request.args.get("ext", "wav").lower()
        original_url = f"https://storage.vapi.ai/{recording_id}"
        response = requests.get(original_url, stream=True)

        if not response.ok:
            return jsonify({"error": "Failed to fetch recording from VAPI"}), response.status_code

        mimetype = "audio/wav" if ext == "wav" else "audio/mpeg"

        return send_file(
            BytesIO(response.content),
            mimetype=mimetype,
            as_attachment=False,
            download_name=recording_id
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

