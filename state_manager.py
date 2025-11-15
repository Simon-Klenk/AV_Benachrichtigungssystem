# state_manager.py
import uasyncio as asyncio
from machine import RTC
import ujson
import os

_max_messages = 5
_message_file = 'messages.txt'
_messages = []  # [{"type": "...", "value": "...", "state": "...", "timestamp": ...}]


class StateManager:

    def __init__(self, event_queue, display_event_queue):
        self._event_queue = event_queue
        self._display_event_queue = display_event_queue
        self._current_state = "INITIAL"
        
        # Index der aktuell auf dem Display angezeigten Nachricht (-1 = keine)
        self._current_display_message_index = -1
        
        # Event zum asynchronen Schreiben
        self._messages_dirty = asyncio.Event()

        # RTC-Objekt cachen
        self.rtc = RTC()

        # Datei prüfen und laden/erstellen
        self._ensure_message_file()
        self._load_messages_from_file()

    def _current_timestamp(self):
        t = self.rtc.datetime()  # (year, month, day, weekday, hour, min, sec, ms)
        return f"{t[2]:02d}.{t[1]:02d}.{t[0]} {t[4]:02d}:{t[5]:02d}"

    # ---------------- File Management ----------------

    def _ensure_message_file(self):
        if _message_file not in os.listdir():
            with open(_message_file, "w") as f:
                f.write("[]")
            print("[StateManager] messages.txt angelegt.")

    def _load_messages_from_file(self):
        global _messages
        try:
            with open(_message_file, "r") as f:
                data = f.read().strip()
                _messages = ujson.loads(data) if data else []
        except Exception as e:
            print("[StateManager] Fehler beim Lesen von messages.txt:", e)
            _messages = []
        print(f"[StateManager] {_message_file} geladen. Aktuelle Einträge: {len(_messages)}")

    def _write_messages_to_file(self):
        global _messages
        temp_messages = list(_messages)
        while len(temp_messages) > _max_messages:
            temp_messages.pop(0)
        _messages = temp_messages
        try:
            with open(_message_file, "w") as f:
                f.write(ujson.dumps(temp_messages))
            print(f"[StateManager] {len(temp_messages)} Nachrichten gespeichert.")
        except Exception as e:
            print("[StateManager] Fehler beim Schreiben in messages.txt:", e)

    def get_all_messages(self):
        return list(_messages)

    # ---------------- Async File Writer ----------------

    async def _file_writer_task(self):
        while True:
            await self._messages_dirty.wait()
            self._messages_dirty.clear()
            await asyncio.sleep_ms(500)
            print("[StateManager] Änderungen erkannt, starte Schreibvorgang...")
            self._write_messages_to_file()

    # ---------------- Event Loop ----------------

    async def run(self):
        asyncio.create_task(self._file_writer_task())
        while True:
            event = await self._event_queue.get()
            print(f"[StateManager] Empfing Ereignis: '{event}'")

            event_type = event.get("type", "UNKNOWN_TYPE")
            event_value = event.get("value", "UNKNOWN_VALUE")

            if event_type == "BUTTON_PRESSED":
                if event_value == "ACCEPT":
                    await self._handle_accept()
                elif event_value == "REJECT":
                    await self._handle_reject()

            elif event_type == "PICKUP":
                await self._handle_pickup(event_value)

            elif event_type == "EMERGENCY_CB":
                await self._handle_emergency_cb()

            elif event_type == "EMERGENCY_EVENT":
                await self._handle_emergency_event()

    # ---------------- State Update ----------------

    def update_state(self, index, new_state):
        print(f"[StateManager] update_state aufgerufen für index {index}, neuer state: {new_state}")
        _messages[index]["state"] = new_state
        self._messages_dirty.set()
        print(f"[StateManager] update_state aufgerufen für index {index}, neuer state: {new_state}")

    # ---------------- Event Handlers ----------------

    async def _handle_accept(self):
        print("[StateManager] Verarbeite 'ACCEPT'")
        if self._current_display_message_index != -1:
            display_index = self._current_display_message_index
            self.update_state(display_index, "accepted")
            await self._display_event_queue.put({"type": "DELETETEXT", "value": ""})
            self._current_display_message_index = -1
        else:
            print("[StateManager] ACCEPT ignoriert: Kein aktiver Nachrichtentext.")

    async def _handle_reject(self):
        print("[StateManager] Verarbeite 'REJECT'")
        if self._current_display_message_index != -1:
            display_index = self._current_display_message_index
            self.update_state(display_index, "rejected")
            await self._display_event_queue.put({"type": "DELETETEXT", "value": ""})
            self._current_display_message_index = -1
        else:
            print("[StateManager] REJECT ignoriert: Kein aktiver Nachrichtentext.")

    async def _handle_pickup(self, pickup_value):
        print(f"[StateManager] Verarbeite 'PICKUP' mit Wert {pickup_value}")
        entry = {
            "type": "PICKUP",
            "value": pickup_value,
            "state": "wait",
            "timestamp": self._current_timestamp()
        }
        _messages.append(entry)
        self._current_display_message_index = len(_messages) - 1
        self._messages_dirty.set()
        await self._display_event_queue.put({
            "type": "NEWTEXT",
            "value": f"Kind abholen: {pickup_value}"
        })

    async def _handle_emergency_cb(self):
        print(f"[StateManager] Verarbeite 'EMERGENCY_CB'")
        entry = {
            "type": "EMERGENCY_CB",
            "value": "Staffler bitte zum Kids-Check-In kommen",
            "state": "wait",
            "timestamp": self._current_timestamp()
        }
        _messages.append(entry)
        self._current_display_message_index = len(_messages) - 1
        self._messages_dirty.set()
        await self._display_event_queue.put({
            "type": "NEWTEXT",
            "value": "Staffler bitte zum Kids-Check-In kommen"
        })
        print(f"[StateManager] event eingetragen mit index {self._current_display_message_index}")

    async def _handle_emergency_event(self):
        print(f"[StateManager] Verarbeite 'EMERGENCY_EVENT'")
        entry = {
            "type": "EMERGENCY_EVENT",
            "value": "Sanitäterteam bitte zum Kids-Check-In kommen",
            "state": "wait",
            "timestamp": self._current_timestamp()
        }
        _messages.append(entry)
        self._current_display_message_index = len(_messages) - 1
        self._messages_dirty.set()
        await self._display_event_queue.put({
            "type": "NEWTEXT",
            "value": "Sanitäterteam bitte zum Kids-Check-In kommen"
        })