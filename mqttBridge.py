#!/usr/bin/python3

import os
import json
import time
import random
import datetime
from datetime import timezone
from dotenv import load_dotenv

# libraries for mqtt connection
import ssl
import jwt
import paho.mqtt.client as mqtt

# Load environment variables
load_dotenv()

# Define project-based variables. These should be the only ones needed to edit in order to use this script
# roots.pem certification needed for mqtt
ca_certs = os.getenv("CA_CERTS")
print(ca_certs)
# ca_certs = '/home/pi/root_pem/lts_certs/gtsltsr.crt' # for Long-term support (LTS) through 2030
# Device private key
private_key_file = os.getenv("PRIVATE_KEY_FILE")
print(private_key_file)
# SSL algorithm. Either RS256 or ES256
algorithm = os.getenv("SSL_ALGO")
print(algorithm)
# Project where device is registered
project_id = os.getenv("PROJECT_ID")
print(project_id)
# GCP location
cloud_region = os.getenv("REGISTRY_REGION")
print(cloud_region)
# IoT Core Registry
registry_id = os.getenv("REGISTRY_ID")
print(registry_id)
# Device ID from IoT Core
device_id = os.getenv("DEVICE_ID")
print(device_id)
# mqtt bridge hostname
mqtt_bridge_hostname = os.getenv("MQTT_BRIDGE_HOSTNAME")
print(mqtt_bridge_hostname)
# mqtt_bridge_hostname = 'mqtt.2030.ltsapis.goog' # for Long-term support (LTS) through 2030
# mqtt bridge port, default is 8883
mqtt_bridge_port = eval(os.getenv("MQTT_BRIDGE_PORT"))
print(mqtt_bridge_port)
# MQTT topic
MQTT_TELEMETRY_TOPIC = "/devices/{}/events".format(device_id)
print(MQTT_TELEMETRY_TOPIC)
# The initial backoff time after a disconnection occurs, in seconds.
minimum_backoff_time = eval(os.getenv("MINIMUM_BACKOFF_TIME"))

# The maximum backoff time before giving up, in seconds.
MAXIMUM_BACKOFF_TIME = eval(os.getenv("MAXIMUM_BACKOFF_TIME"))

# Whether to wait with exponential backoff before publishing.
should_backoff = False

# The time a JWT remains active
JWT_EXPIRES_MINUTES = eval(os.environ.get("JWT_EXPIRES_MINUTES"))

# For checking internet connection
isConnected = False

# remote server to check internet connection
REMOTE_SERVER = os.getenv("REMOTE_SERVER")

DATEFORMAT = "%Y%m%dT%H:%M:%S.%fZ"
# END OF USER VARIABLES

# Create the jwt token
def create_jwt(project_id, private_key_file, algorithm):
    """
    Function that creates a jwt token to connect with MQTT.
    Arguments:
        project_id: The project to which the device belongs to
        private_key_file: path to the private key for the device
        algorithm: The encryption algorithm for the SSL key. It can be either 'RS256' or 'ES256'
    Returns:
        a JWT generated form the arguments provided, it expires in 60 minutes. After 60 minutes the
        client is disconnected and a new JWT will be needed
    """
    token = {
        # The time that the token was issued at
        "iat": datetime.datetime.utcnow(),
        # The time the token expires.
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=JWT_EXPIRES_MINUTES),
        # The audience field should always be set to the GCP project id.
        "aud": project_id,
    }

    # Read the private key file
    with open(private_key_file, "r") as f:
        private_key = f.read()

    return jwt.encode(token, private_key, algorithm)


# Start the configuration of the mqtt client
def error_str(rc):
    """Convert a Paho error to a human readable string."""
    return "{}: {}".format(rc, mqtt.error_string(rc))


def on_connect(client, unused_userdata, unused_flags, rc):
    """Callback for when a device connects."""
    global should_backoff
    global minimum_backoff_time
    global isConnected
    global device_id

    print("on_connect", mqtt.connack_string(rc))
    print("connection time: ", datetime.datetime.utcnow())

    # This is the topic that the device will receive configuration updates on.
    mqtt_config_topic = "/devices/{}/config".format(device_id)

    # Subscribe to the config topic.
    client.subscribe(mqtt_config_topic, qos=1)

    # The topic that the device will receive commands on.
    mqtt_command_topic = "/devices/{}/commands/#".format(device_id)

    # Subscribe to the commands topic, QoS 1 enables message acknowledgement.
    print("Subscribing to {}".format(mqtt_command_topic))
    client.subscribe(mqtt_command_topic, qos=1)

    # After a successful connect, reset backoff time and stop backing off.
    should_backoff = False
    minimum_backoff_time = 1
    # Mark flag to continue after a successful conection
    isConnected = True


def on_disconnect(unused_client, unused_userdata, rc):
    """Paho callback for when a device disconnects."""
    print("on_disconnect", error_str(rc))
    print("disconnection time: ", datetime.datetime.utcnow())

    # Since a disconnect occurred, the next loop iteration will wait with
    # exponential backoff.
    global should_backoff
    global isConnected
    should_backoff = True
    isConnected = False


def on_publish(unused_client, unused_userdata, unused_mid):
    """Paho callback when a message is sent to the broker."""
    print("on_publish")


def commandSelection(payload):
    """
    Function that returns a bash command when given a valid command from the cloud.
    Otherwise it prints that the command was invalid.
    """
    commands = {
        "TEST COMMAND": "echo 'Test command was received and executed successfully'",
        "REBOOT": "sudo reboot now",
        "UPDATE": "sudo apt update && sudo apt upgrade -y",
    }
    return commands.get(payload, "echo 'Invalid Command'")


def respondToMessage(payload):
    """
    Function that reacts to the payload on a message coming from the MQTT bridge
    """
    print('RPI Responding to message "{}"'.format(payload))
    # Execute a command depending on the payload (TODO implement differentiation between command and config)
    os.system(commandSelection(payload))


def on_message(unused_client, unused_userdata, message):
    """Callback when the device receives a message on a subscription."""
    payload = str(message.payload.decode("utf-8"))
    print("Received message '{}' on topic '{}' with Qos {}".format(payload, message.topic, str(message.qos)))
    respondToMessage(payload)


def on_log(unused_client, unused_userdata, level, buf):
    print(f"log of level {level}: {buf}")


def get_client(
    project_id,
    cloud_region,
    registry_id,
    device_id,
    private_key_file,
    algorithm,
    ca_certs,
    mqtt_bridge_hostname,
    mqtt_bridge_port,
):
    """Create our MQTT client. The client_id is a unique string that identifies
    this device. For Google Cloud IoT Core, it must be in the format below."""
    client_id = "projects/{}/locations/{}/registries/{}/devices/{}".format(
        project_id, cloud_region, registry_id, device_id
    )

    print("Device client_id is '{}'".format(client_id))

    client = mqtt.Client(client_id=client_id)

    print("got client")
    # With Google Cloud IoT Core, the username field is ignored, and the
    # password field is used to transmit a JWT to authorize the device.
    client.username_pw_set(username="unused", password=create_jwt(project_id, private_key_file, algorithm))

    print("logged in to client with JWT")
    # Enable SSL/TLS support.
    client.tls_set(ca_certs=ca_certs, tls_version=ssl.PROTOCOL_TLSv1_2)
    # client.tls_set(ca_certs=ca_certs)
    print("tls set")
    # Register message callbacks. https://eclipse.org/paho/clients/python/docs/
    # describes additional callbacks that Paho supports.
    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect
    # When a message is received, the rpi can respond accordingly with respondToMessage function
    client.on_message = on_message
    client.on_log = on_log

    print("returning client")

    return client


def get_payload():
    """
    Simulated payload, should be replaced with queries from an analyzer
    """
    payload_keys = ["temperature", "pressure", "humidity"]
    payload = {}
    for key in payload_keys:
        payload[key] = random.random()

    payload["timestamp"] = datetime.datetime.strftime(datetime.datetime.now(timezone.utc), DATEFORMAT)

    return json.dumps(payload)


def main():

    # global JWT_EXPIRES_MINUTES
    global minimum_backoff_time
    global isConnected

    jwt_iat = datetime.datetime.utcnow()
    jwt_exp_mins = JWT_EXPIRES_MINUTES

    while not isConnected:
        try:
            # Use gateway to connect to server
            client = get_client(
                project_id,
                cloud_region,
                registry_id,
                device_id,
                private_key_file,
                algorithm,
                ca_certs,
                mqtt_bridge_hostname,
                mqtt_bridge_port,
            )
            # Connect to the Google MQTT bridge.
            print(f"Trying to connect, isconnected: {isConnected}")
            client.connect(mqtt_bridge_hostname, mqtt_bridge_port)
            time.sleep(5)
            isConnected = True
            print(f"Connected? {isConnected}")
        except Exception as e:
            print(f"failed connection: {e}")
            isConnected = False
            time.sleep(5)

    print("Continuing to application")
    # Once able to connect, continue to application loop
    while True:
        try:
            client.loop()
        except Exception as e:
            print(f"Error on client.loop(): {e}. Backing off")
            global should_backoff
            should_backoff = True

        if should_backoff:
            # If backoff time is too large, give up.
            if minimum_backoff_time > MAXIMUM_BACKOFF_TIME:
                # print('Exceeded maximum backoff time. Giving up.')
                # break
                print("Exceeded maximum backoff time. Resetting exponential backoff time")
                minimum_backoff_time = 1

            delay = minimum_backoff_time + random.randint(0, 1000) / 1000.0
            time.sleep(delay)
            minimum_backoff_time *= 2
            try:
                client.connect(mqtt_bridge_hostname, mqtt_bridge_port)
            except Exception as e:
                print(f"Error connecting after backoff with delay {delay}.\nError: {e}.\nBacking off again")
                should_backoff = True

        seconds_since_issue = (datetime.datetime.utcnow() - jwt_iat).seconds
        # print(f"seconds since issue: {seconds_since_issue}")
        if seconds_since_issue > 60 * jwt_exp_mins:
            print("Refreshing token after {}s".format(seconds_since_issue))
            jwt_iat = datetime.datetime.utcnow()
            client.loop()
            client.disconnect()
            # Wait a short time, so the cloud function has some buffer to react to the disconnection,
            # before reacting to the connection.
            time.sleep(5)
            try:
                client = get_client(
                    project_id,
                    cloud_region,
                    registry_id,
                    device_id,
                    private_key_file,
                    algorithm,
                    ca_certs,
                    mqtt_bridge_hostname,
                    mqtt_bridge_port,
                )
                # Connect to the Google MQTT bridge.
                client.connect(mqtt_bridge_hostname, mqtt_bridge_port)
            except Exception as e:
                print(f"Error connecting during refresh: {e}.\n Backing off.")
                should_backoff = True

        # Publish data
        payload = get_payload()
        print(payload)
        client.publish(MQTT_TELEMETRY_TOPIC, payload, qos=1)

        time.sleep(15)


if __name__ == "__main__":
    main()
