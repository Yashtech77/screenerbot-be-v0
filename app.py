import re
from flask import Flask, render_template, request, jsonify
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app) 
# Vapi configuration
VAPI_API_KEY = "0f0a5b82-c9d4-4db5-8c9f-075c0f155897"#private key
VAPI_BASE_URL = "https://api.vapi.ai"
ASSISTANT_ID = "fe02f58c-3e25-45a9-85b1-80457f6dcefb"
VAPI_PHONE_NUMBER_ID = "a9801017-89b1-4fa0-9496-84b19131502b"  # Your Vapi phone number ID


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/make-outbound-call', methods=['POST'])
def make_outbound_call():
    data = request.json
    phone_number = data.get('phoneNumber')
    
    if not phone_number:
        return jsonify({"success": False, "message": "Phone number required"}), 400

    # Validate E.164 format
    if not re.match(r'^\+\d{8,15}$', phone_number):
        return jsonify({
            "success": False,
            "message": "Invalid phone format. Use E.164 format: +[country code][number] (8-15 digits)"
        }), 400

    try:
        headers = {
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Working payload structure
        payload = {
            "assistantId": ASSISTANT_ID,
            "phoneNumberId": VAPI_PHONE_NUMBER_ID,
            "customer": {
                "number": phone_number
            }
 }
        
        response = requests.post(
            f"{VAPI_BASE_URL}/call/phone",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 201:
            return jsonify({
                "success": True,
                "message": "Call initiated successfully",
                "callId": response.json().get("id")
            })
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

@app.route('/create-assistant', methods=['POST'])
def create_assistant():
    try:
        data = request.json

        # Require bot name from frontend
        assistant_name = data.get('name')
        if not assistant_name or assistant_name.strip() == "":
            return jsonify({'error': 'Assistant name is required and cannot be empty'}), 400

        # Require first message
        if not data.get('firstMessage'):
            return jsonify({'error': 'firstMessage is required from frontend'}), 400

        # Require system prompt
        system_prompt = data.get('content') or data.get('systemPrompt')
        if not system_prompt or system_prompt.strip() == "":
            return jsonify({'error': 'content or systemPrompt is required and cannot be empty from frontend'}), 400

        # Build assistant config (no voicemailMessage)
        # assistant_config = {
        #     'name': assistant_name,
        #     'firstMessage': data['firstMessage'],
        #     'firstMessageInterruptionsEnabled': data.get('firstMessageInterruptionsEnabled', True),
        #     'endCallMessage': data.get('endCallMessage', 'Thank you for your time. Goodbye.'),
        #     'model': {
        #         'provider': 'openai',
        #         'model': 'gpt-4',
        #         'messages': [
        #             {
        #                 'role': 'system',
        #                 'content': system_prompt
        #             }
        #         ]
        #     },
        #     'voice': {
        #         'provider': 'vapi',
        #         'voiceId': 'Neha'
        #     },
        #     'transcriber': {
        #         'provider': 'deepgram',
        #         'model': 'nova-2',
        #         'language': 'en'
        #     }
        # }
        assistant_config = {
            'name': assistant_name,
            'firstMessage': data['firstMessage'],
            'firstMessageInterruptionsEnabled': data.get('firstMessageInterruptionsEnabled', True),
            'endCallMessage': data.get('endCallMessage', 'Thank you for your time. Goodbye.'),
            'model': {
                'provider': 'openai',
                'model': 'gpt-4',
                'messages': [
                    {
                        'role': 'system',
                        'content': system_prompt
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
                'language': 'en'
            }
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


@app.route('/make-batch-calls', methods=['POST'])
def make_batch_calls():
    try:
        data = request.json
        phone_numbers = data['customers']

        # Call Vapi's API for batch outbound calls
        response = requests.post(
            'https://api.vapi.ai/call',
            headers={
                'Authorization': f'Bearer {VAPI_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                "assistantId": ASSISTANT_ID,
                "phoneNumberId": VAPI_PHONE_NUMBER_ID,
                "customers": phone_numbers
                # Optionally add schedulePlan if needed
                # "schedulePlan": {
                #     "earliestAt": "2025-05-30T00:00:00Z"
                # }
            }
        )

        if not response.ok:
            raise Exception('Failed to initiate batch calls')

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500



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

if __name__ == '__main__':
    app.run(debug=True)