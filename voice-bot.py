import streamlit as st
import time
import logging
from mqtt_handler import MQTTHandler
from twilio_handler import TwilioHandler
from datetime import datetime
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_session_state():
    """Initialize all session state variables."""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
        logger.info("Initialized empty messages list in session state")
        
    if 'mqtt_handler' not in st.session_state:
        logger.info("Initializing new MQTT handler")
        st.session_state.mqtt_handler = MQTTHandler(client_id="streamlit-mqtt-client")
        try:
            st.session_state.mqtt_handler.connect()
            logger.info("MQTT handler connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect MQTT handler: {e}")
            st.session_state.error_message = f"Failed to connect to MQTT broker: {e}"
            
    if 'twilio_handler' not in st.session_state:
        logger.info("Initializing Twilio handler")
        st.session_state.twilio_handler = TwilioHandler()
        
    # Initialize status messages
    if 'status_message' not in st.session_state:
        st.session_state.status_message = None
    if 'error_message' not in st.session_state:
        st.session_state.error_message = None
    if 'info_message' not in st.session_state:
        st.session_state.info_message = None
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if 'call_active' not in st.session_state:
        st.session_state.call_active = False
    if 'call_sid' not in st.session_state:
        st.session_state.call_sid = None

def display_debug_info():
    """Display debug information in the sidebar."""
    with st.sidebar:
        st.subheader("Debug Information")
        st.write("MQTT Status:", "Connected" if st.session_state.mqtt_handler.connected else "Disconnected")
        st.write("Queue Size:", st.session_state.mqtt_handler.message_queue.qsize())
        st.write("Total Messages:", len(st.session_state.messages))

        st.write(st.session_state)
        
        if st.button("Test MQTT"):
            try:
                test_msg = {
                    "type": "test",
                    "message": "Test message",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.mqtt_handler.publish(test_msg)
                st.session_state.status_message = "Test message published successfully"
                st.rerun()
            except Exception as e:
                st.session_state.error_message = f"Failed to publish test message: {e}"
                st.rerun()

def format_message(msg):
    """Format message for display based on its type."""
    msg_type = msg.get('type', 'unknown')
    
    if msg_type == 'status_update':
        return {
            "Status": msg.get('CallStatus', 'Unknown'),
            "Time": msg.get('timestamp', 'Unknown'),
            "Duration": msg.get('CallDuration', 'N/A'),
            "data": msg
        }
    elif msg_type == 'user_input':
        speech = msg.get('SpeechResult', 'No speech detected')
        input_type = 'Speech' if speech != 'No speech detected' else 'DTMF'
        return {
            "Type": input_type,
            "Speech": speech,
            "Digits": msg.get('Digits', 'No digits pressed'),
            "Time": msg.get('timestamp', 'Unknown'),
            "data": msg
        }
    else:
        return {
            "Type": msg.get('type', 'unknown'),
            "data": msg,
            "Time": msg.get('timestamp', 'Unknown'),
        }

def handle_call_initiation(phone_number, twilio_handler):
    """Handle the call initiation process."""
    twilio = twilio_handler
    
    if not twilio.validate_phone_number(phone_number):
        st.session_state.error_message = "Please enter a valid phone number in E.164 format"
        return

    try:
        call = twilio.make_call(phone_number)
        st.session_state.call_sid = call.sid
        st.info(f"Call placed successfully! Call SID: {st.session_state.call_sid}")

        prev_state = ""
        # with st.spinner("Call in progress..."):
        while True:
            current_call = twilio.get_call_status(st.session_state.call_sid)
            
            if current_call.status != prev_state:
                st.session_state.info_message = f"Current status: {current_call.status}"
                prev_state = current_call.status
                
            if current_call.status in ["completed", "failed", "busy", "no-answer", "canceled"]:
                if current_call.status == "completed":
                    st.session_state.status_message = "Call completed successfully."
                else:
                    st.session_state.error_message = f"Call ended with status: {current_call.status}"
                break
                
            time.sleep(5)
                    
    except Exception as e:
        st.session_state.error_message = f"Error placing call: {str(e)}"
        st.session_state.call_active = False

def main():
    st.title("Chatr Bot")
    
    # Initialize session state
    initialize_session_state()
    
    # Display any persisted messages
    if st.session_state.error_message:
        st.error(st.session_state.error_message)
    if st.session_state.status_message:
        st.success(st.session_state.status_message)
    if st.session_state.info_message:
        st.info(st.session_state.info_message)
    
    # Display debug information
    display_debug_info()
    
    # Update MQTT messages
    mqtt_handler = st.session_state.mqtt_handler
    if mqtt_handler.update_streamlit_state():
        logger.info("New messages added to session state")
    
    # Phone number input and call initiation
    phone_number = st.text_input("Enter phone number to call (E.164 format)", "+91")

    # Make Call button is disabled when a call is in progress
    if st.button("📞 Make Call", help="Click to initiate a new call"):
        st.session_state.call_active = True
        handle_call_initiation(phone_number, st.session_state.twilio_handler)
        st.rerun()
    
    # Display messages with pagination
    if st.session_state.messages:
        st.subheader("Message History")
        
        # Pagination setup
        messages_per_page = 5
        total_messages = len(st.session_state.messages)
        # Calculate total pages needed to display all messages
        total_pages = total_messages // messages_per_page + (1 if total_messages % messages_per_page > 0 else 0)
        
        # Page selection interface
        if total_pages > 1:
            col1, col2 = st.columns([3, 1])
            with col2:
                # Start from page 1 by default (showing oldest messages)
                page = st.selectbox(
                    "Page", 
                    range(1, total_pages + 1), 
                    index=0,  # Changed from total_pages-1 to 0 to start from first page
                    key="page_selector"
                )
        else:
            page = 1
        
        # Calculate indices for current page
        start_idx = (page - 1) * messages_per_page
        end_idx = min(start_idx + messages_per_page, total_messages)
        
        # Display page information for better user context
        st.caption(f"Showing messages {start_idx + 1} to {end_idx} of {total_messages}")
        
        # Display messages for current page in chronological order
        # Removed reversed() to show messages from oldest to newest
        for msg in st.session_state.messages[start_idx:end_idx]:
            formatted_msg = format_message(msg)
            
            # Create an expander for each message
            with st.expander(
                f"{formatted_msg.get('Time', 'Unknown Time')} - "
                f"{formatted_msg.get('Status', formatted_msg.get('Type', 'Message'))}"
            ):
                st.json(formatted_msg)

    # Add a refresh button and last refresh time
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Refresh Messages"):
            st.session_state.last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # # Clear status messages on refresh
            # st.session_state.status_message = None
            # st.session_state.error_message = None
            # st.session_state.info_message = None
            # st.rerun()
    with col2:
        st.write("Last refreshed:", st.session_state.last_refresh)

if __name__ == "__main__":
    main()