# twilio_server.py

from flask import Flask, request, jsonify
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from twilio.http.http_client import TwilioHttpClient

from datetime import datetime
import os
from dotenv import load_dotenv
from queue import Queue
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from operator import itemgetter
import logging

# Load environment variables for configuration
load_dotenv()

logging.basicConfig(level=logging.INFO)

# Initialize our communication queues that will be shared with Streamlit
log_queue = Queue()
error_queue = Queue()

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
VOICE = os.getenv("APP_VOICE")

twiml_http_client = TwilioHttpClient(timeout=120)

# Initialize Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, http_client=twiml_http_client)

# Initialize Flask application
app = Flask(__name__)

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
    print(f"Failed to initialize LLM: {e}")
    conversation_chain = None

# Store chat history in a way accessible to both Flask and Streamlit
chat_history = []

@app.route("/status_callback", methods=['POST'])
def status_callback():
    print("""Handle Twilio call status updates and recording completions.""")
    try:
        data = request.form.to_dict()
        data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data['type'] = 'status_update'
        
        # Send to queue for Streamlit to process
        log_queue.put(data)

        call_status = data.get('CallStatus')
        print(f"Current status of the call: {call_status}")
        
        return jsonify({"status": "success", "message": f"Status update processed"}), 200
        
    except Exception as e:
        print(f"Encountered an error : {e}")
        error_queue.put(f"Status callback error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/process-input", methods=['POST'])
def process_input():

    print("Processing the inputs.......")
    try:
        content_type = request.headers.get('Content-Type')

        print(str(content_type).lower())

        if 'application/json' in str(content_type).lower():
            # Handle JSON request
            data = request.get_json()  # Get JSON body
            speech_result = data.get('SpeechResult', "")
            digits = data.get('Digits', "")

        elif 'application/x-www-form-urlencoded' in str(content_type).lower():
            # Handle form-urlencoded request
            speech_result = request.form.get('SpeechResult', "")
            digits = request.form.get('Digits', "")

        else:
            # Unsupported content type
            print(f"Received unsupported Content-Type: {content_type}")
            return jsonify({"error": f"Unsupported Content-Type: {content_type}"}), 415

        print(speech_result)

        # greet = VoiceResponse()
        # greet.play("https://api.twilio.com/cowbell.mp3")
        # print(str(greet))

        response = VoiceResponse()
        if speech_result:
            print("Processing the speech response....")

            llm_response = conversation_chain.invoke({
                "input": speech_result,
                "chat_history": chat_history
            })

            print("waiting for 30 seconds....")
            response.pause(5)
            print(str(response))

            print("Speak what the LLM says.....")
            response.say(llm_response, voice=VOICE)
            print(str(response))
            
        elif digits:
            response.say(f"You pressed: {digits}", voice=VOICE)
        else:
            response.say("No input received.", voice=VOICE)

        # Add the gather verb to continue the conversation
        gather = response.gather(
            input='speech dtmf',  # Accept both speech and keypad input
            action='/process-input',  # Send the next input back to this same endpoint
            method='POST',
            timeout=5,  # Wait 5 seconds for input
            speechTimeout='auto'  # Automatically detect when speech is complete
        )

        return str(response), 200
    
    except Exception as e:
        print(f"Error in process_input: {e}")
        error_response = VoiceResponse()
        error_response.say("Sorry, something went wrong. Let's try again.", voice=VOICE)
        
        # Even on error, continue the conversation
        gather = error_response.gather(
            input='speech dtmf',
            action='/process-input',
            method='POST',
            timeout=5,
            speechTimeout='auto'
        )
        return str(error_response), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)