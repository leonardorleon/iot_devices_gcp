import base64
import os
import json
from datetime import datetime
import firebase_admin
from firebase_admin import firestore

# Script variables
DATEFORMAT = "%Y%m%dT%H:%M:%S.%fZ"

# Initialize firebase client
firebase_admin.initialize_app()
# Initialize firestore database client
db = firestore.client()


def process_and_store_measurements(event, context):
    """Triggered from a message on a Cloud Pub/Sub topic.
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    pubsub_message = base64.b64decode(event["data"]).decode("utf-8")
    content = json.loads(pubsub_message)
    # Grab from contents
    timestamp_str = content["timestamp"]
    measurements = content["measurements"]
    # Add timestamp to the measurements payload for sorting purposes on firestore
    measurements["timestamp"] = datetime.strptime(timestamp_str, DATEFORMAT)

    # Obtain custom attributes
    attributes = event["attributes"]
    device = attributes["deviceId"]

    print(f"device: {device}")
    print(f"timestamp: {timestamp_str}")

    path = f"devices/{device}/measurements/{timestamp_str}"
    doc_ref = db.document(path)
    doc_ref.set(measurements)
