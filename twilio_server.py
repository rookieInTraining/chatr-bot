from flask import Flask, request, jsonify
import logging
from datetime import datetime
import json
from mqtt_handler import MQTTHandler
from twilio_handler import TwilioHandler
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from operator import itemgetter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)

# Initialize handlers
mqtt_handler = MQTTHandler(client_id="flask-mqtt-client")
twilio_handler = TwilioHandler()

# Initialize LLM and conversation chain
try:
    llm = OllamaLLM(model="llama3.2-vision")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful AI assistant handling phone calls. Keep responses clear, concise, and natural."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])
    
    def create_chain():
        return (
            {
                "input": itemgetter("input"),
                "chat_history": itemgetter("chat_history")
            }
            | prompt
            | llm
            | StrOutputParser()
        )
    
    conversation_chain = create_chain()
except Exception as e:
    logger.error(f"Failed to initialize LLM: {e}")
    conversation_chain = None

# Store chat history
chat_history = []

def get_response(speech_result, digits):
    """Get appropriate response based on input."""
    if speech_result and conversation_chain:
        return conversation_chain.invoke({
            "input": speech_result,
            "chat_history": chat_history
        })
    elif digits:
        return f"You pressed: {digits}"
    else:
        return "No input received."

@app.route("/status_callback", methods=['POST'])
def status_callback():
    """Handle Twilio call status updates and recording completions."""
    try:
        data = request.form.to_dict()
        data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data['type'] = 'status_update'
        
        try:
            mqtt_handler.publish(data)
            logger.info(f"Published status update: {data['CallStatus']}")
        except Exception as e:
            logger.error(f"Failed to publish status to MQTT: {e}")
        
        return jsonify({"status": "success", "message": "Status update processed"}), 200
        
    except Exception as e:
        logger.error(f"Status callback error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/process-input", methods=['POST'])
def process_input():
    """Process voice and DTMF input from Twilio."""
    ollm_resp = {}
    ollm_resp['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        content_type = request.headers.get('Content-Type')

        if 'application/json' in str(content_type).lower():
            data = request.get_json()
        elif 'application/x-www-form-urlencoded' in str(content_type).lower():
            data = request.form.to_dict()
        else:
            logger.warning(f"Received unsupported Content-Type: {content_type}")
            return jsonify({"error": f"Unsupported Content-Type: {content_type}"}), 415

        # Add message type and timestamp
        data['type'] = 'user_input'
        data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Publish to MQTT
        try:
            mqtt_handler.publish(data)
            logger.info("Published user input to MQTT")
        except Exception as e:
            logger.error(f"Failed to publish input to MQTT: {e}")

        # Process the response
        speech_result = data.get('SpeechResult', '')
        digits = data.get('Digits', '')

        llm_response = get_response(speech_result, digits)
        ollm_resp['type'] = 'agent_response'
        ollm_resp['agent'] = llm_response
        mqtt_handler.publish(ollm_resp)
        
        response = twilio_handler.create_voice_response(
            message=llm_response
        )

        return str(response), 200
    
    except Exception as e:
        logger.error(f"Error in process_input: {e}")
        error_response = twilio_handler.create_voice_response(
            message="Sorry, something went wrong. Let's try again."
        )
        return str(error_response), 500

# Connect to MQTT broker when starting the application
try:
    mqtt_handler.connect()
except Exception as e:
    logger.error(f"Failed to initialize MQTT connection: {e}")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)