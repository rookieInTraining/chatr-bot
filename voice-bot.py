# voice_bot_ui.py

import streamlit as st
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
import os
from dotenv import load_dotenv
import time
from datetime import datetime
from collections import deque
from twilio_server import log_queue, error_queue, client, TWILIO_PHONE_NUMBER

# Load environment variables
load_dotenv()

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
VOICE = os.getenv("APP_VOICE")

twiml_http_client = TwilioHttpClient(timeout=120)

# Initialize Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, http_client=twiml_http_client)

def validate_phone_number(phone):
    print("""Validate phone number format (basic E.164 check).""")
    return phone and phone.startswith('+') and len(phone) >= 10

def main():
    st.title("Twilio Voice Bot with LLM Decision Making")
    
    # Phone number input and call initiation
    phone_number = st.text_input("Enter phone number to call (E.164 format)", "+91")
    
    if st.button("Make Call"):
        if not validate_phone_number(phone_number):
            st.error("Please enter a valid phone number in E.164 format")
        elif not client:
            st.error("Twilio client is not properly initialized")
        else:
            try:
                response = VoiceResponse()
                response.say("Hello! How can I help you today?", voice=VOICE)
                response.gather(
                    input='speech dtmf',
                    action=os.getenv('NGROK_URL') + "/process-input",
                    timeout=5
                )

                print("Triggerin the call...")

                call = client.calls.create(
                    to=phone_number,
                    from_=TWILIO_PHONE_NUMBER,
                    twiml=str(response),
                    status_callback=os.getenv('NGROK_URL') + "/status_callback",
                    status_callback_event=["initiated", "ringing", "answered", "completed"]
                )

                st.success(f"Call placed successfully! Call SID: {call.sid}")

                while True:
                    current_call = client.calls(call.sid).fetch()
                    print(str(current_call))
                    st.info(f"Current status: {current_call.status}")
                    if current_call.status == "completed":
                        st.success("Call completed.")
                        break
                    time.sleep(10)
            except Exception as e:
                st.error(f"Error placing call: {str(e)}")

if __name__ == "__main__":
    main()