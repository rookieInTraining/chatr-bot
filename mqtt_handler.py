import paho.mqtt.client as mqtt
import json
from datetime import datetime
import logging
import streamlit as st
from queue import Queue
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MQTTHandler:
    def __init__(self, client_id="streamlit-mqtt"):
        self.broker = "broker.hivemq.com"
        self.port = 1883
        self.topic = "itest/messages"
        self.client_id = client_id
        self.message_queue = Queue()
        self.connected = False
        
        logger.info(f"Initializing MQTT Handler with client_id: {client_id}")
        
        # Initialize MQTT client with MQTT v5 protocol and callback API v2
        self.client = mqtt.Client(
            client_id=self.client_id,
            protocol=mqtt.MQTTv5,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        
        # Set up callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe
        
        # Enable logging
        self.client.enable_logger(logger)

    def on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            logger.info(f"MQTT Connected successfully. Client ID: {self.client_id}")
            # Subscribe to topic
            result = self.client.subscribe(self.topic, qos=1)
            logger.info(f"Subscription attempt result: {result}")
            self.connected = True
        else:
            logger.error(f"Connection failed with code: {rc}")
            self.connected = False

    def on_message(self, client, userdata, message, properties=None):
        """Callback for when a message is received."""
        try:
            data = json.loads(message.payload.decode())
            if 'timestamp' not in data:
                data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            logger.info(f"MQTT Message Received on {message.topic}: {data}")
            
            # Add to queue
            self.message_queue.put(data)
            logger.debug(f"Message added to queue. Queue size: {self.message_queue.qsize()}")
                
        except json.JSONDecodeError:
            logger.error(f"Failed to decode message payload: {message.payload}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def on_subscribe(self, client, userdata, mid, reason_codes, properties=None):
        """Callback for when the client subscribes to a topic."""
        logger.info(f"Subscribed to {self.topic} with mid: {mid}, reason_codes: {reason_codes}")

    def on_disconnect(self, client, userdata, rc, reasonCode, properties=None):
        """Callback for when the client disconnects from the broker."""
        if rc != 0 or reasonCode != 0:
            logger.warning(f"Unexpected disconnection: rc={rc}, reason_code={reasonCode}")
        else:
            logger.info("Disconnected successfully")
        self.connected = False

    def connect(self):
        """Connect to the MQTT broker."""
        try:
            logger.info(f"Attempting to connect to {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            logger.info("MQTT loop started")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT client disconnected")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    def publish(self, data):
        """Publish message to MQTT topic."""
        try:
            if 'timestamp' not in data:
                data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            message = json.dumps(data)
            logger.info(f"Publishing message to {self.topic}: {message}")
            
            result = self.client.publish(
                self.topic,
                message,
                qos=1
            )
            
            logger.info(f"Publish result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            raise

    def get_messages(self):
        """Get all available messages from the queue."""
        messages = []
        while not self.message_queue.empty():
            try:
                msg = self.message_queue.get_nowait()
                messages.append(msg)
                logger.debug(f"Retrieved message from queue: {msg}")
            except Exception as e:
                logger.error(f"Error getting message from queue: {e}")
                break
        
        if messages:
            logger.info(f"Retrieved {len(messages)} messages from queue")
        return messages

    def update_streamlit_state(self):
        """Update Streamlit session state with new messages."""
        try:
            new_messages = self.get_messages()
            if new_messages:
                st.session_state.messages.extend(new_messages)
                logger.info(f"Added {len(new_messages)} new messages to session state")
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating Streamlit state: {e}")
            return False