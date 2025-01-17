from twilio.rest import Client
from twilio.http.http_client import TwilioHttpClient
from twilio.twiml.voice_response import VoiceResponse
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class TwilioHandler:
    def __init__(self):
        load_dotenv()
        
        # Twilio Configuration
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        self.voice = os.getenv("APP_VOICE")
        self.ngrok_url = os.getenv('NGROK_URL')
        
        # Initialize HTTP client with timeout
        self.http_client = TwilioHttpClient(timeout=120)
        
        # Initialize Twilio client
        self.client = Client(
            self.account_sid, 
            self.auth_token, 
            http_client=self.http_client
        )

    def validate_phone_number(self, phone):
        """Validate phone number format."""
        return phone and phone.startswith('+') and len(phone) >= 10

    def create_voice_response(self, message="Hello! How can I help you today?"):
        """Create a TwiML voice response."""
        response = VoiceResponse()
        response.say(message, voice=self.voice)
        response.gather(
            input='speech dtmf',
            action=f"{self.ngrok_url}/process-input",
            method='POST',
            timeout=5,
            speechTimeout='auto'
        )
        return response

    def make_call(self, to_number):
        """Initiate a call to the specified number."""
        if not self.validate_phone_number(to_number):
            raise ValueError("Invalid phone number format")

        response = self.create_voice_response()
        
        call = self.client.calls.create(
            to=to_number,
            from_=self.phone_number,
            twiml=str(response),
            status_callback=f"{self.ngrok_url}/status_callback",
            status_callback_event=["initiated", "ringing", "answered", "completed"]
        )
        
        return call
    
    def disconnect_call(self, call_sid):
        """Disconnect an established call."""
        return self.client.calls(call_sid).update(status="completed")

    def get_call_status(self, call_sid):
        """Get the current status of a call."""
        return self.client.calls(call_sid).fetch()