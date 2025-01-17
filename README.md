# Chatr Bot
Runs a flask server and a streamlit UI. User can dial the number and have a conversation with an LLM using the Twilio SDK.
The LLM in use currently is the `llama3.2-vision` model of Ollama.

## Steps to run the service:
You'll need to create the `.env` file with the following params first:

```
TWILIO_ACCOUNT_SID = <TWILIO ACCOUNT SID>
TWILIO_AUTH_TOKEN = <TWILIO_AUTH_TOKEN>
TWILIO_PHONE_NUMBER = <YOUR_ASSIGNED_PHONE_NO>
NGROK_URL = <FLASK_SERVER_URL_ACCESSIBLE_TO_TWILIO>
APP_VOICE='woman'
```

#### Starting the backend service:
```
python twilio_server.py
```

#### Starting the frontend service:
```
streamlit run voice-bot.py
```