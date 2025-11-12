import uasyncio as asyncio
import network
import ubinascii
from microdot import Microdot, send_file, redirect, Response
from state_manager import set_message, get_all_messages, update_state

app = Microdot()
Response.default_content_type = 'application/json'  # JSON-Standard

# --------------------------
# WLAN-Verbindung
# --------------------------
async def connect_wifi():
    try:
        with open('wifi_credentials.txt', 'r') as f:
            lines = f.readlines()
            ssid = lines[0].strip().split(': ')[1]
            encoded_pw = lines[1].strip().split(': ')[1]
    except Exception as e:
        print('❌ Fehler beim Lesen von wifi_credentials.txt:', e)
        return None

    try:
        password = ubinascii.a2b_base64(encoded_pw).decode('utf-8')
    except Exception as e:
        print('❌ Passwort konnte nicht dekodiert werden:', e)
        return None

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    print(f'🌐 Verbinde mit {ssid}...')

    for _ in range(40):
        if wlan.isconnected():
            break
        await asyncio.sleep(0.5)

    if not wlan.isconnected():
        wlan.active(False)
        print('❌ Verbindung fehlgeschlagen.')
        return None

    ip = wlan.ifconfig()[0]
    print('✅ Verbunden! IP:', ip)
    return ip

# --------------------------
# HTML-Dateien
# --------------------------
def create_page_files(base_dir):
    return {
        'pickup': f'{base_dir}/pickup.html',
        'status': f'{base_dir}/status.html',
        'emergency': f'{base_dir}/emergency.html'
    }

# --------------------------
# Routen
# --------------------------
@app.route('/')
async def index(request):
    page = request.args.get('page', 'pickup')
    files = app.page_files
    file = files.get(page, files['pickup'])
    try:
        return send_file(file, max_age=0)
    except Exception as e:
        return f'404 - Datei nicht gefunden ({e})', 404

@app.route('/submit', methods=['POST'])
async def handle_post(request):
    form = request.form
    msg_content = form.get('content')
    msg_emergency = form.get('emergency_type')

    msg_type, msg_text = None, None

    if msg_content:
        msg_type = "pickup"
        msg_text = msg_content
        redirect_page = '/?page=status'
    elif msg_emergency:
        if msg_emergency.lower() == "staff":
            msg_type = "emergency_cb"
            msg_text = "NOTFALL: Stafflerteam anfordern (CB)"
        else:
            msg_type = "emergency_event"
            msg_text = "NOTFALL: Sanitäterteam anfordern (Veranstaltung)"
        redirect_page = '/?page=status'
    else:
        redirect_page = '/'

    if msg_type and msg_text:
        data = {"type": msg_type, "text": msg_text, "state": "wait"}
        await set_message(data)
        print(f"✅ Nachricht gespeichert: {data}")

    return redirect(redirect_page)

@app.route('/update_state', methods=['POST'])
async def change_state(request):
    idx = int(request.form.get('index', -1))
    new_state = request.form.get('state', 'wait')
    await update_state(idx, new_state)
    return redirect('/?page=status')

@app.route('/messages')
async def show_messages(request):
    msgs = await get_all_messages()
    # Nur die letzten 5 Nachrichten senden
    return {'messages': msgs[-5:]}

# --------------------------
# Server starten
# --------------------------
async def server_task(base_dir):
    app.page_files = create_page_files(base_dir)
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print(f"📡 Webserver läuft unter http://{ip}")
        await app.start_server(port=80, debug=False)
    else:
        print("⚠️ WLAN nicht verbunden – Webserver nicht gestartet.")
