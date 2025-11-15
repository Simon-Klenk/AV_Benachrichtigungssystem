# main.py
#
# Main application for the Raspberry Pi Pico.
# Initializes the ButtonMonitor and StateManager and starts the asyncio event loop.
#
# Author: Simon Klenk 2025
# License: MIT - See the LICENSE file in the project directory for the full license text.
#
import uasyncio as asyncio
from hardware import Hardware
from state_manager import StateManager
from async_queue import AsyncQueue
from display_manager import DisplayManager
import sys
import connect_wifi
import time_sync
from webserver import Webserver

async def main():
    event_queue = AsyncQueue()
    display_event_queue = AsyncQueue()
    
    hardware = Hardware(event_queue)
    state_manager = StateManager(event_queue, display_event_queue)
    webserver = Webserver(event_queue, state_manager)
    display_manager = DisplayManager(display_event_queue)

    # Start Coroutine
    task_syc_time = asyncio.create_task(time_sync.sync_time())
    task_controll_hardware = asyncio.create_task(hardware.run())
    task_manage_state = asyncio.create_task(state_manager.run())
    task_webserver = asyncio.create_task(webserver.run())

    
    # NEU: Der DisplayManager braucht einen Dummy-Task auf Core 0 (die run()-Funktion)
    # um die Task-Struktur zu vervollständigen, obwohl die Arbeit auf Core 1 läuft.
    task_display_manager = asyncio.create_task(display_manager.run())
    
    await event_queue.put({"type": "NEWTEXT", "value": "Test-Event"})
    # Program end
    # WICHTIGE KORREKTUR: Alle "ewig" laufenden Tasks müssen hier gesammelt werden,
    # um sicherzustellen, dass das Programm nicht vorzeitig endet.
    try:
        await asyncio.gather(
            task_controll_hardware, 
            task_manage_state,
            task_webserver, # Hinzugefügt: Webserver muss dauerhaft laufen!
            task_display_manager # Hinzugefügt: Display-Dummy-Task zur Sicherheit
        )
    except Exception as e:
        print(f"\nError during asyncio.gather: {e}")
        sys.print_exception(e)
    finally:
        print("Program end.")

if __name__ == "__main__":
    try:
        connect_wifi.connect_wifi()

        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram end by User (KeyboardInterrupt).")
    except Exception as e:
        print(f"\nError: {e}")
        sys.print_exception(e)
    finally:
        print("Program end.")