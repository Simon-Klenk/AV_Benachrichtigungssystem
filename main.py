import uasyncio as asyncio
import os
import hardware
from webserver import server_task, connect_wifi
import state_manager
from display_manager import DisplayManager, DisplayInitializationError
import time_sync  # import der ausgelagerten Zeit-Synchronisation

display_manager = None
_main_display_task_running = False

def start_main_display_task():
    global _main_display_task_running
    if not _main_display_task_running:
        print("💡 Haupt-Display-Logik wird gestartet (durch neue Nachricht/Neustart).")
        asyncio.create_task(display_message_from_state_task())

async def display_message_from_state_task():
    global display_manager, _main_display_task_running
    if display_manager is None:
        return

    _main_display_task_running = True
    last_message = ""

    while True:
        current_message = await state_manager.get_message()

        display_text = ""
        if current_message:
            display_text = f"Pickup: {current_message}"

        if display_text != last_message:
            print(f"🖥️ Setze Display-Text: '{display_text}' (Dunkel, wenn leer)")
            display_manager.set_text(display_text)
            last_message = display_text

            if not current_message:
                print("💤 Keine Nachricht mehr vorhanden. Beende Haupt-Display-Task.")
                _main_display_task_running = False
                await asyncio.sleep(0.1)
                return

        await asyncio.sleep(1)

async def initial_display_task(message, duration=3):
    global display_manager
    if display_manager is None:
        return

    print(f"📢 Initialer '{message}'-Screen aktiv ({duration}s)")
    display_manager.set_text(message)
    await asyncio.sleep(duration)

    old_message = await state_manager.get_message()

    if old_message:
        print(f"💾 Alte unakzeptierte Nachricht gefunden ('{old_message}'). Starte Haupt-Display-Logik.")
        start_main_display_task()
    else:
        print("✅ Keine unakzeptierte Nachricht. Display bleibt dunkel.")
        display_manager.set_text("")

async def main():
    global display_manager
    # Hardware initialisieren
    hardware.init_hardware()

    # State Manager initialisieren
    state_manager.init_state()
    state_manager.set_display_callback(start_main_display_task)

    ip = None
    try:
        print("🌐 Starte WLAN-Verbindungsversuch...")
        ip = await connect_wifi()

        if ip:
            # Zeit synchronisieren, sobald WLAN verbunden ist
            await time_sync.sync_time()

        print("🖥️ Initializing DisplayManager...")
        try:
            display_manager = DisplayManager()
            asyncio.create_task(display_manager.display_task())
        except DisplayInitializationError as e:
            print(f"⚠️ Display-Initialisierung fehlgeschlagen. Läuft ohne Display weiter: {e}")
            display_manager = None

        if ip:
            if display_manager:
                asyncio.create_task(initial_display_task("Bereit", 3))
            asyncio.create_task(server_task(os.getcwd()))
            asyncio.create_task(state_manager.periodic_task())
        else:
            print("❌ WLAN-Verbindung fehlgeschlagen. Starte ohne Webserver.")
            if display_manager:
                asyncio.create_task(initial_display_task("WLAN Fehler", 5))

        # Button-Task starten (ändert Status in messages.txt)
        asyncio.create_task(hardware.button_task())

    except Exception as e:
        print(f"💥 Schwerwiegender Fehler im Hauptprozess: {e}")

    while True:
        await asyncio.sleep(1)

try:
    asyncio.run(main())
finally:
    print("Programm beendet.")
    asyncio.new_event_loop()
