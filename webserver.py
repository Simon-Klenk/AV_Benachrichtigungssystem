import uasyncio as asyncio
import network
from microdot import Microdot, send_file, redirect, Response

app = Microdot()
Response.default_content_type = 'application/json'


class Webserver:
    def __init__(self, event_queue, state_manager, base_dir="/"):
        self._base_dir = base_dir
        self._event_queue = event_queue
        self.page_files = self.create_page_files()
        self.state_manager = state_manager

    def create_page_files(self):
        return {
            'pickup': f'{self._base_dir}/pickup.html',
            'status': f'{self._base_dir}/status.html',
            'emergency': f'{self._base_dir}/emergency.html'
        }

    async def index(self, request):
        page = request.args.get('page', 'pickup')
        file = self.page_files.get(page, self.page_files['pickup'])
        try:
            return send_file(file, max_age=0)
        except Exception as e:
            return f"404 - Datei nicht gefunden ({e})", 404

    async def handle_post(self, request):
        form = request.form
        msg_content = form.get('content')
        msg_emergency = form.get('emergency_type')

        if msg_content:
            # Event in die Queue
            await self._event_queue.put({
                "type": "PICKUP",
                "value": msg_content,
            })

        elif msg_emergency:
            if msg_emergency.lower() == "staff":
                await self._event_queue.put({
                    "type": "EMERGENCY_CB",
            })
            elif msg_emergency.lower() == "medical":
                await self._event_queue.put({
                    "type": "EMERGENCY_EVENT",
            })
        return redirect('/?page=status')

    async def show_messages(self, request):
        msgs = self.state_manager.get_all_messages()
        print("Sende Nachrichten:", msgs)
        return {'messages': msgs[-5:]}

    async def run(self):
        app.route('/')(self.index)
        app.route('/submit', methods=['POST'])(self.handle_post)
        app.route('/messages')(self.show_messages)

        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            ip = wlan.ifconfig()[0]
            print(f"📡 Webserver läuft unter http://{ip}")
            await app.start_server(port=80, debug=False)
        else:
            print("⚠️ WLAN nicht verbunden – Webserver nicht gestartet.")
