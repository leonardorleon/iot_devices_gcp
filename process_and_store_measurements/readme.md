# Cloud function to store measurements in firestore

This cloud function takes the messages from the telemetry topic of the iot devices and stores them to firestore.

The measurements are stored by device with the following document path:

**devices** -> **{deviceId}** -> **measurements** -> **{timestamp}** 

Each document has a set of readings from sensors as well as a timestamp in date format which can be used to sort values in firestore in a simple manner.