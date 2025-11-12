# Copyright (c) 2025 Simon Klenk
# This software is licensed under the MIT License.
# See the LICENSE file in the project directory for the full license text.

import ubinascii

def save_wifi_credentials():
    """
    Prompts the user to enter the Wi-Fi name (SSID) and password,
    encrypts the password using base64 encoding, and saves both
    credentials to a file.
    """
    # Prompt user for Wi-Fi name (SSID) and password
    ssid = input("Please enter the Wi-Fi name (SSID): ")
    password = input("Please enter the Wi-Fi password: ")

    # Encrypt the password using base64 encoding
    encoded_password = ubinascii.b2a_base64(password.encode('utf-8')).decode('utf-8')

    # Save Wi-Fi name and encrypted password to a file
    with open('wifi_credentials.txt', 'w') as f:
        f.write(f"SSID: {ssid}\n")
        f.write(f"Password: {encoded_password}")

    print("Wi-Fi credentials have been securely saved.")


# Execute the function to save Wi-Fi credentials
save_wifi_credentials()
