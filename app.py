import os
import re
from flask import Flask, render_template, request, jsonify
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


# @app.route('/make-outbound-call', methods=['POST'])
# def make_outbound_call():
#     data = request.json
#     phone_number = data.get('phoneNumber')
#     assistant_id = data.get('assistantId')   # ✅ accept from frontend
#     knowledge_base_id = data.get('knowledgeBaseId')
    
#     if not phone_number:
#         return jsonify({"success": False, "message": "Phone number required"}), 400

#     if not re.match(r'^\+\d{8,15}$', phone_number):
#         return jsonify({
#             "success": False,
#             "message": "Invalid phone format. Use E.164 format: +[country code][number] (8-15 digits)"
#         }), 400

#     if not assistant_id:
#         return jsonify({"success": False, "message": "Assistant ID required"}), 400

#     try:
#         headers = {
#             "Authorization": f"Bearer {VAPI_API_KEY}",
#             "Content-Type": "application/json"
#         }
        
#         payload = {
#             "assistantId": assistant_id,                 # ✅ dynamic now
#             "phoneNumberId": VAPI_PHONE_NUMBER_ID,
#             "customer": { "number": phone_number }
#         }

#         # optionally include knowledgeBaseId if passed
#         if knowledge_base_id:
#             payload["knowledgeBaseId"] = knowledge_base_id

#         response = requests.post(
#             f"{VAPI_BASE_URL}/call/phone",
#             headers=headers,
#             json=payload
#         )
        
#         if response.status_code == 201:
#             return jsonify({
#                 "success": True,
#                 "message": "Call initiated successfully",
#                 "callId": response.json().get("id")
#             })
#         else:
#             return jsonify({
#                 "success": False,
#                 "message": f"Vapi API error: {response.status_code} - {response.text}"
#             }), response.status_code
            
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "message": f"Server error: {str(e)}"
#         }), 500
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

# @app.route('/create-assistant', methods=['POST'])
# def create_assistant():
#     try:
#         data = request.json
 
#         # Require bot name from frontend
#         assistant_name = data.get('name')
#         if not assistant_name or assistant_name.strip() == "":
#             return jsonify({'error': 'Assistant name is required and cannot be empty'}), 400
 
#         # Require first message
#         if not data.get('firstMessage'):
#             return jsonify({'error': 'firstMessage is required from frontend'}), 400
 
#         # Require system prompt
#         system_prompt = data.get('content') or data.get('systemPrompt')
#         if not system_prompt or system_prompt.strip() == "":
#             return jsonify({'error': 'content or systemPrompt is required and cannot be empty from frontend'}), 400
 
#         # Build assistant config with hooks
#         assistant_config = {
#             'name': assistant_name,
#             'firstMessage': data['firstMessage'],
#             'firstMessageInterruptionsEnabled': data.get('firstMessageInterruptionsEnabled', True),
#             'endCallMessage': data.get('endCallMessage', 'Thank you for your time. Goodbye.'),
#             'model': {
#                 'provider': 'openai',
#                 'model': 'gpt-4.1-mini',
#                 'messages': [
#                     {
#                         'role': 'system',
#                         'content': system_prompt   
#                     }
#                 ]
#             },
#             'voice': {
#                 'provider': 'vapi',
#                 'voiceId': 'Neha'
#             },
#             'transcriber': {
#                 'provider': 'deepgram',
#                 'model': 'nova-2',
#                 'language': 'multi'
#             },
#             # Added hooks configuration
#             'hooks': [{
#                 'on': 'customer.speech.timeout',
#                 'options': {
#                     'timeoutSeconds': 10,
#                     'triggerMaxCount': 2,
#                     'triggerResetMode': 'onUserSpeech'
#                 },
#                 'do': [{
#                     'type': 'say',
#                     'prompt': 'Are you still there? Please let me know how I can help you.'
#                 }],
#                 'name': 'customer_timeout_check'
#             }]
#         }
 
#         print("Sending to VAPI:", assistant_config)
 
#         response = requests.post(
#             'https://api.vapi.ai/assistant',
#             headers={
#                 'Authorization': f'Bearer {VAPI_API_KEY}',
#                 'Content-Type': 'application/json'
#             },
#             json=assistant_config
#         )
 
#         if not response.ok:
#             print(f"VAPI error: {response.status_code} - {response.text}")
#             raise Exception(f'Failed to create assistant: {response.text}')
 
#         result = response.json()
#         print(f"Successfully created assistant with ID: {result.get('id')}")
#         return jsonify(result)
 
#     except Exception as e:
#         print(f"Error creating assistant: {str(e)}")
#         return jsonify({'error': str(e)}), 500


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
            'voice': {
                'provider': 'vapi',
                'voiceId': 'Neha'
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
            headers={
                "Authorization": f"Bearer {VAPI_API_KEY}"
            }
        )
        if response.ok:
            return jsonify(response.json())
        else:
            return jsonify({'error': f'Vapi API error: {response.status_code} - {response.text}'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            headers={
                "Authorization": f"Bearer {VAPI_API_KEY}"
            }
        )
        if response.ok:
            return jsonify(response.json())
        else:
            return jsonify({'error': f'Vapi API error: {response.status_code} - {response.text}'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
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
            return jsonify(response.json())
        else:
            return jsonify({'error': f'Vapi API error: {response.status_code} - {response.text}'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/call/<call_id>', methods=['GET'])
def get_call(call_id):
    try:
        response = requests.get(
            f"{VAPI_BASE_URL}/call/{call_id}",
            headers={"Authorization": f"Bearer {VAPI_API_KEY}"}
        )

        if response.ok:
            return jsonify(response.json())
        else:
            return jsonify({
                "error": f"Vapi API error: {response.status_code} - {response.text}"
            }), response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)