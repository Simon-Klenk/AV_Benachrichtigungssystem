# wifi_connector_sync.py
#
# This module provides synchronous functionality to connect a MicroPython device
# to a Wi-Fi network. It reads credentials from a file, decodes the password,
# and attempts to establish a connection, reporting the status and assigned IP address.
#
# Author: Simon Klenk 2025
# License: MIT - See the LICENSE file in the project directory for the full license text.

import time
import network
import ubinascii
from microdot import Microdot, send_file, redirect, Response

app = Microdot()
Response.default_content_type = 'application/json'


def connect_wifi():
    """
    Synchronously connects the MicroPython device to a Wi-Fi network.
    It reads the SSID and base64-encoded password from 'wifi_credentials.txt',
    decodes the password, and attempts to establish a Wi-Fi connection.
    It waits for a connection and returns the assigned IP address upon success,
    or None if the connection fails. This function will block until a connection
    is established or the timeout is reached.
    """
    ssid = None
    encoded_pw = None

    # Attempt to read Wi-Fi credentiaals from the 'wifi_credentials.txt' file.
    try:
        with open('wifi_credentials.txt', 'r') as f:
            lines = f.readlines()
            ssid = lines[0].strip().split(': ')[1]
            encoded_pw = lines[1].strip().split(': ')[1]
    except OSError as e:
        print(f'❌ Error reading wifi_credentials.txt: {e}. Make sure the file exists and is accessible.')
        return None
    except IndexError:
        print('❌ Error parsing wifi_credentials.txt. Ensure it contains "SSID: <your_ssid>" and "Password: <your_encoded_password>".')
        return None
    except Exception as e:
        print(f'❌ An unexpected error occurred while reading credentials: {e}')
        return None

    password = None
    # Attempt to decode the base64-encoded password.
    try:
        password = ubinascii.a2b_base64(encoded_pw).decode('utf-8')
    except Exception as e:
        print(f'❌ Failed to decode password: {e}. Ensure the password in the file is valid base64.')
        return None

    # Initialize WLAN interface in station mode.
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    print(f'🌐 Connecting to {ssid}...')

    # Wait for the connection to be established, with a timeout.
    while True:
        if wlan.isconnected():
            break
        time.sleep(0.5)

    # Check if the connection was successful.
    if not wlan.isconnected():
        wlan.active(False)
        print('❌ Connection failed.')
        return None

    # If connected, get the IP address.
    ip = wlan.ifconfig()[0]
    print(f'✅ Connected! IP: {ip}')
    return ip

