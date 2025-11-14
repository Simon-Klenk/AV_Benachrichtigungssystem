# filename: display_manager.py
from machine import Pin, I2C
import uasyncio as asyncio
import sh1106
import writer
import spleen_32  # Font aus der funktionierenden Version
import _thread
import utime

# --- KONFIGURATION ---
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
I2C_ADDR = 0x3c
SDA_PIN = 16
SCL_PIN = 17
SCROLL_SPEED = 3       # Pixel pro Schritt
SCROLL_DELAY_MS = 1    # Millisekunden zwischen Frames
# ----------------------

class DisplayInitializationError(Exception):
    """Custom exception for display initialization errors."""
    pass

class DisplayManager:
    def __init__(self):
        self._current_text = ""
        self.display = None
        self.writer = None
        
        # --- MULTI-CORE VARIABLEN ---
        self._core1_text = ""                # Text, der von Core 1 verwendet wird
        self._core1_lock = _thread.allocate_lock() # Lock zum Schutz der Textübergabe
        self._core1_running = False          # Status-Flag für den Core 1 Thread
        # ---------------------------

        self.font = spleen_32  # Schriftart cachen

        try:
            # Hardware-I2C initialisieren
            self.i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=400000)

            # I2C-Scan prüfen
            devices = self.i2c.scan()
            if not devices or I2C_ADDR not in devices:
                raise DisplayInitializationError(
                    f"I2C-Adresse {hex(I2C_ADDR)} nicht gefunden. Gefunden: {[hex(d) for d in devices]}"
                )

            # Display initialisieren
            self.display = sh1106.SH1106_I2C(
                DISPLAY_WIDTH, DISPLAY_HEIGHT, self.i2c, addr=I2C_ADDR, rotate=180
            )
            self.display.fill(0)
            self.display.show()
            self.display.poweroff()

            # Writer initialisieren
            self.writer = writer.Writer(self.display, self.font)
            self.writer.wrap = False
            self.writer.col_clip = True

        except Exception as e:
            raise DisplayInitializationError(f"Error initializing the display: {e}")

    # -------------------------
    # Text setzen (Läuft auf Core 0, übergibt Daten an Core 1)
    # -------------------------
    def set_text(self, text):
        """Setzt neuen Text, startet den Core 1 Thread, falls nötig."""
        if text != self._current_text:
            self._current_text = text
            # Datenübergabe an Core 1, nur bei Textwechsel
            with self._core1_lock:
                self._core1_text = text

            # Thread auf Core 1 starten, falls er noch nicht läuft
            if not self._core1_running:
                print("[DisplayManager] Starte Scroll-Thread auf Core 1.")
                _thread.start_new_thread(self._core1_scroll_thread, ())

    # -------------------------
    # Berechne Start/End-Koordinaten (Synchron)
    # -------------------------
    def _calculate_dims(self, text):
        y_start = (DISPLAY_HEIGHT - self.font.height()) // 2
        text_width = self.writer.stringlen(text)

        if text_width <= DISPLAY_WIDTH:
            x_start = (DISPLAY_WIDTH - text_width) // 2
            x_end = x_start
        else:
            x_start = DISPLAY_WIDTH
            x_end = -text_width

        return text_width, y_start, x_start, x_end

    # -------------------------
    # Synchroner Scroll-Thread (Läuft auf Core 1)
    # -------------------------
    def _core1_scroll_thread(self):
        """
        Läuft blockierend auf Core 1, scrollt den Text.
        """
        self._core1_running = True
        self.display.poweron()

        _text = ""
        text_width = y_start = x_start = x_end = 0
        current_x = 0
        last_frame_time = utime.ticks_ms()

        while self._core1_running:
            # Text von Core 0 abrufen (nur bei Änderung locken)
            with self._core1_lock:
                new_text = self._core1_text

            if new_text != _text:
                _text = new_text
                text_width, y_start, x_start, x_end = self._calculate_dims(_text)
                current_x = x_start
                # Statischer Text
                if x_start == x_end:
                    self._render_text(_text, y_start, x_start)
                    utime.sleep_ms(1000)
                    continue

            # --- Scroll-Logik ---
            now = utime.ticks_ms()
            if utime.ticks_diff(now, last_frame_time) >= SCROLL_DELAY_MS:
                self._render_text(_text, y_start, int(current_x))
                current_x -= SCROLL_SPEED
                if current_x <= x_end:
                    current_x = x_start
                    utime.sleep_ms(500)  # Kurze Pause am Ende
                last_frame_time = now

    # -------------------------
    # Text rendern (Jetzt Synchron)
    # -------------------------
    def _render_text(self, text, y_start, x_start):
        """Render-Funktion, die auf Core 1 läuft."""
        devid = id(self.display)
        if devid in writer.Writer.state:
            state = writer.Writer.state[devid]
            state.text_row = y_start
            state.text_col = x_start

        # Nur den Bereich der Zeile löschen
        self.display.fill_rect(0, y_start, DISPLAY_WIDTH, self.font.height(), 0)

        # Text drucken
        self.writer.printstring(text)

        # I2C-Aufruf (Core 1 blockiert, Core 0 nicht)
        with self._core1_lock:
            self.display.show()

    # -------------------------
    # Dummy-run-Funktion (für Core 0 asyncio.gather)
    # -------------------------
    async def run(self):
        """Dummy-Task, der auf Core 0 läuft, um die Task-Liste zu vervollständigen."""
        while True:
            await asyncio.sleep(1)
