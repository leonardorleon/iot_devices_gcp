# IoT Devices on GCP

This repository explores the usage of IoT devices on Google Cloud Platform. There will be instructions on what each of the elements do and how to get them to work. The objectives are to use raspberry pis to connect to GCP using IoT Core, which will allow to send commands to devices, monitor their connection status and more. For the purpose of this demo, random data will be generated to simulate querying an analyzer. 

---

## Quickstart

### On Raspberry pi

The comunication between the IoT device occurs by mqtt bridge, which will use JWT tokens as they are more secure than passwords. For this, the cryptography python library will be necessary, which in turn needs a few base libraries. The necessary base libraries for cryptography and pyjwt can be installed with the following commands:

    sudo apt-get install build-essential
    sudo apt-get install libssl-dev
    sudo apt-get install python-dev
    sudo apt-get install libffi-dev

Once the base libraries are installed, we can install the necessary python modules:

    sudo pip3 install paho-mqtt
    sudo pip3 install cryptography
    sudo pip3 install pyjwt

Additionally, a file roots.pem needs to be downloaded as it will be used to confirm it is communicatin with Google.

    wget https://pki.google.com/roots.pem

Finally, to connect with Google cloud and to register the device with IoT Core, an SSL certificate is needed. The following command can be used to create an RSA with x509:

    openssl req -x509 -nodes -newkey rsa:2048 -keyout rsa_private.pem \
        -out rsa_cert.pem -subj "/CN=unused"

### On GCP

These steps can be done both on the console using the UI or using the gcloud command. IoT Core will need a pub/sub topic as well as a pub/sub subscription. These will then be tied to the device registry on IoT Core.

* Create a pub/sub topic

        gcloud pubsub topics create [TOPIC_NAME] 

* Create a pub/sub subscription

        gcloud pubsub subscriptions create [SUBSCRIPTION_NAME] --topic=[TOPIC_NAME]

* Create an IoT Core registry (log-level of info to take advantage of connect/disconnect messages)

        gcloud iot registries create [REGISTRY_NAME] --region=[REGION] --event-notification-config=topic=[TOPIC_NAME] --log-level=[LOG_LEVEL]

* Create an IoT device (Using the SSL key previously created)

        gcloud iot devices create [DEVICE_NAME] --region=[REGION] --registry=[REGISTRY_NAME] --public-key=path=./rsa_cert.pem,type=rsa-x509-pem





