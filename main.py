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

async def main():

    event_queue = asyncio.Queue()
    hardware = Hardware(event_queue)
    state_manager = StateManager(event_queue)

    # Start Coroutine
    task_controll_hardware = asyncio.create_task(hardware.run())
    task_manage_state = asyncio.create_task(state_manager.run())

    # Program end
    await asyncio.gather(task_controll_hardware, task_manage_state)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\Program end by User (KeyboardInterrupt).")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        print("Program end.")