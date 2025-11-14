# state_manager.py
import uasyncio as asyncio
from machine import RTC
import ujson
import os
import time

_max_messages = 5
_message_file = 'messages.txt'
_messages = []  # [{"type": "...", "value": "...", "state": "...", "timestamp": ...}]


class StateManager:

    def __init__(self, event_queue):
        self.event_queue = event_queue
        self._current_state = "INITIAL"
        
        # --- Optimierung: Asynchrones Schreiben ---
        # Dieses Event signalisiert dem _file_writer_task, dass es Arbeit gibt.
        self._messages_dirty = asyncio.Event()

        # --- Optimierung: RTC-Objekt Cachen ---
        # Erstelle das Objekt nur einmal, anstatt in _current_timestamp()
        self.rtc = RTC()

        # Datei prüfen und laden/erstellen
        self._ensure_message_file()
        self._load_messages_from_file()

    def _current_timestamp(self):
        # Verwendet das gecachte self.rtc Objekt
        t = self.rtc.datetime()  # (year, month, day, weekday, hour, min, sec, ms)
        return f"{t[2]:02d}.{t[1]:02d}.{t[0]} {t[4]:02d}:{t[5]:02d}"

    # ---------------------------------------------------
    # Datei-Management
    # ---------------------------------------------------

    def _ensure_message_file(self):
        """Prüft, ob die Datei existiert. Wenn nicht → erstellen."""
        if _message_file not in os.listdir():
            with open(_message_file, "w") as f:
                f.write("[]")  # leere JSON-Liste
            print("[StateManager] messages.txt angelegt.")


    def _load_messages_from_file(self):
        """Lädt Nachrichten aus der Datei in die Liste."""
        global _messages
        try:
            with open(_message_file, "r") as f:
                data = f.read().strip()
                if data:
                    _messages = ujson.loads(data)
                else:
                    _messages = []
        except Exception as e:
            print("[StateManager] Fehler beim Lesen von messages.txt:", e)
            _messages = []
        print(f"[StateManager] {_message_file} geladen. Aktuelle Einträge: {len(_messages)}")

    def _write_messages_to_file(self):
        """
        Stellt sicher, dass die Liste nicht überläuft und speichert sie.
        HINWEIS: Dies ist eine BLOCKIERENDE Operation!
        Sie sollte nur vom _file_writer_task aufgerufen werden.
        """
        global _messages
        
        # Sicherstellen, dass die globale Liste referenziert wird
        temp_messages = list(_messages)
        
        # Wenn über Limit → so lange vorne löschen, bis die Größe stimmt
        while len(temp_messages) > _max_messages:
            removed = temp_messages.pop(0)
            
        # Aktualisiere die globale Liste, falls sie gekürzt wurde
        if len(temp_messages) < len(_messages):
             _messages = temp_messages

        try:
            with open(_message_file, "w") as f:
                f.write(ujson.dumps(temp_messages))
            print(f"[StateManager] {len(temp_messages)} Nachrichten gespeichert.")
        except Exception as e:
            print("[StateManager] Fehler beim Schreiben in messages.txt:", e)

    def get_all_messages(self):
        return list(_messages)


    # ---------------------------------------------------
    # Asynchroner Schreib-Task (Optimierung)
    # ---------------------------------------------------

    async def _file_writer_task(self):
        """
        Ein dedizierter Task, der im Hintergrund läuft und auf das Signal
        zum Speichern der Nachrichten wartet.
        """
        while True:
            # 1. Warte, bis jemand signalisiert, dass gespeichert werden muss
            await self._messages_dirty.wait()
            
            # 2. Event zurücksetzen
            self._messages_dirty.clear()
            
            # 3. Debouncing: Warte kurz, falls mehr Änderungen kommen
            #    Dies bündelt mehrere Schreibvorgänge (z.B. 3 Events in 100ms)
            #    in einen einzigen Speicher-Vorgang.
            await asyncio.sleep_ms(500) 
            
            # 4. Jetzt die blockierende Operation ausführen
            print("[StateManager] Änderungen erkannt, starte Schreibvorgang...")
            self._write_messages_to_file()


    # ---------------------------------------------------
    # Event loop
    # ---------------------------------------------------

    async def run(self):
        # Starte den asynchronen Hintergrund-Schreib-Task
        asyncio.create_task(self._file_writer_task())
        
        # Haupt-Event-Schleife (reagiert schnell)
        while True:
            event = await self.event_queue.get()
            print(f"[StateManager] Empfing Ereignis: '{event}'")

            event_type = event.get("type", "UNKNOWN_TYPE")
            event_value = event.get("value", "UNKNOWN_VALUE")

            if event_type == "BUTTON_PRESSED":
                if event_value == "ACCEPT":
                    self._handle_accept()
                elif event_value == "REJECT":
                    self._handle_reject()

            elif event_type == "PICKUP":
                self._handle_pickup(event_value)

            elif event_type == "EMERGENCY_CB":
                self._handle_emergency_cb()

            elif event_type == "EMERGENCY_EVENT":
                self._handle_emergency_event()


    # ---------------------------------------------------
    # Event handling
    # ---------------------------------------------------

    def update_state(self, index, new_state):
        if 0 <= index < len(_messages):
            _messages[index]["state"] = new_state
            # NICHT-BLOCKIEREND: Signalisiere dem Writer-Task, dass Arbeit ansteht
            self._messages_dirty.set()


    def _handle_accept(self):
        print("[StateManager] Verarbeite 'ACCEPT'")
        # weitere Logik hier
        # Falls dieser Handler _messages ändert, muss hier auch
        # self._messages_dirty.set() aufgerufen werden!


    def _handle_reject(self):
        print("[StateManager] Verarbeite 'REJECT'")
        # weitere Logik hier
        # Falls dieser Handler _messages ändert, muss hier auch
        # self._messages_dirty.set() aufgerufen werden!


    def _handle_pickup(self, pickup_value):
        print(f"[StateManager] Verarbeite 'PICKUP' mit Wert {pickup_value}")

        entry = {
            "type": "PICKUP",
            "value": pickup_value,
            "state": "wait",
            "timestamp": self._current_timestamp()
        }
        _messages.append(entry)
        
        # NICHT-BLOCKIEREND: Signalisiere dem Writer-Task, dass Arbeit ansteht
        self._messages_dirty.set()

    def _handle_emergency_cb(self):
        print(f"[StateManager] Verarbeite 'EMERGENCY_CB'")

        entry = {
            "type": "EMERGENCY_CB",
            "value": "Staffler bitte zum Kids-Check-In kommen",
            "state": "wait",
            "timestamp": self._current_timestamp()
        }
        _messages.append(entry)

        # NICHT-BLOCKIEREND: Signalisiere dem Writer-Task, dass Arbeit ansteht
        self._messages_dirty.set()

    def _handle_emergency_event(self):
        print(f"[StateManager] Verarbeite 'EMERGENCY_EVENT'")
        
        entry = {
            "type": "EMERGENCY_EVENT",
            "value": "Sanitäterteam bitte zum Kids-Check-In kommen",
            "state": "wait",
            "timestamp": self._current_timestamp()
        }
        _messages.append(entry)
        
        # NICHT-BLOCKIEREND: Signalisiere dem Writer-Task, dass Arbeit ansteht
        self._messages_dirty.set()