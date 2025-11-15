# filename: display_manager.py
from machine import Pin, I2C
import uasyncio as asyncio
import sh1106
import framebuf
import _thread
import utime
import math

# --- KONFIGURATION ---
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
I2C_ADDR = 0x3c
SDA_PIN = 16
SCL_PIN = 17
SCROLL_SPEED = 3       # Pixel pro Schritt
SCROLL_DELAY_MS = 1    # Millisekunden zwischen Frames (Steuert die FPS)
# --- NEUE SKALIERUNGS KONFIGURATION ---
SCALE_FACTOR_WIDTH = 1.5      # Skalierungsfaktor für die Breite
SCALE_FACTOR_HEIGHT = 6        # Skalierungsfaktor für die Höhe (8 * 8 = 64)
# --------------------------------------

class DisplayInitializationError(Exception):
    """Custom exception for display initialization errors."""
    pass

class FramebufferScalingError(Exception):
    """Custom exception for framebuffer scaling errors."""
    pass

class DisplayManager:
    def __init__(self, display_event_queue):
        # Der Queue, aus dem Core 0 Events liest
        self._display_event_queue = display_event_queue 
        
        self._current_text = ""
        self.display = None
        
        # --- MULTI-CORE VARIABLEN ---
        self._core1_text = ""                
        self._core1_lock = _thread.allocate_lock() 
        self._core1_running = False          
        self._core1_power_on = False # NEU: Steuert den Stromstatus des Displays
        # ---------------------------

        try:
            # I2C Initialisierung (etc.) ...
            self.i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=400000)

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
            # Der Core 1 Thread wird später bei Bedarf gestartet.

        except Exception as e:
            raise DisplayInitializationError(f"Error initializing the display: {e}")

    # -------------------------
    # Framebuffer-Skalierungslogik (unverändert)
    # -------------------------
    # ... (scale_framebuf-Methode bleibt hier unverändert) ...

    def scale_framebuf(self, fb_source, width_source, height_source, width_dest, height_dest):
        """
        Skaliert den Framebuffer:
        - Vertikal: normal stretchen
        - Horizontal: Anti-Aliased-Skalierung für dünnere Schrift
        """
        # ... (Implementierung wie im Originalcode)
        try:
            fb_dest = framebuf.FrameBuffer(
                bytearray(math.ceil(width_dest * height_dest / 8)),
                width_dest,
                height_dest,
                framebuf.MONO_HLSB
            )

            x_ratio = width_source / width_dest
            y_ratio = height_source / height_dest

            for y in range(height_dest):
                py = int(y * y_ratio)

                for x in range(width_dest):
                    # horizontale Interpolation (macht die Schrift dünner!)
                    fx = x * x_ratio
                    x0 = int(fx)
                    x1 = min(x0 + 1, width_source - 1)

                    p0 = fb_source.pixel(x0, py)
                    p1 = fb_source.pixel(x1, py)

                    # Linear interpolieren → dünner, weicher
                    mix = (fx - x0)
                    val = 1 if (p0 * (1 - mix) + p1 * mix) > 0.5 else 0

                    fb_dest.pixel(x, y, val)

            return fb_dest

        except Exception as e:
            raise FramebufferScalingError(f"Error while scaling framebuffer: {e}")
    # -------------------------

    # -------------------------
    # NEU: Event-Behandlung (Läuft auf Core 0, ersetzt set_text)
    # -------------------------
    def _update_text_and_power(self, new_text, power_on):
        """
        Aktualisiert Text und Power-Zustand sicher für Core 1.
        Startet den Core 1 Thread, falls nötig.
        """
        with self._core1_lock:
            self._core1_text = new_text
            self._core1_power_on = power_on

        if not self._core1_running:
            print("[DisplayManager] Starte Scroll-Thread auf Core 1.")
            _thread.start_new_thread(self._core1_scroll_thread, ())

    async def handle_event(self, event):
        """Verarbeitet NEWTEXT und DELETETEXT Events."""
        event_type = event.get("type")
        
        if event_type == "NEWTEXT":
            text = event.get("value", "")
            if text != self._current_text:
                self._current_text = text
                # Setze Text und schalte Display ein
                self._update_text_and_power(text, True)
                print(f"[DisplayManager] Neuer Text: '{text}'")
                
        elif event_type == "DELETETEXT":
            # Schalte Display aus und setze Text auf leer
            self._update_text_and_power("", False) 
            self._current_text = ""
            print("[DisplayManager] Display ausgeschaltet.")
            
        else:
            print(f"[DisplayManager] Unbekannter Event-Typ: {event_type}")

    # -------------------------
    # Berechne skalierte Start/End-Koordinaten (unverändert)
    # -------------------------
    def _calculate_scaled_dims(self, text):
        # ... (Implementierung wie im Originalcode)
        """Berechnet die Abmessungen des skalierten Textes."""
        
        # 1. Padding für den Base-Framebuffer (muss durch 8 teilbar sein)
        text_length = len(text)
        padding_length = 8 - (text_length % 8) if text_length % 8 != 0 else 0
        padded_text = text + " " * padding_length
        text_length_padded = len(padded_text)
        base_char_height = 8 # Interner Font ist 8 Pixel hoch
        base_char_width = 8  # Interner Font ist 8 Pixel breit

        # 2. Basis- und Skalierte Dimensionen
        base_width = text_length_padded * base_char_width
        
        scaled_width = int(base_width * SCALE_FACTOR_WIDTH)
        scaled_height = int(base_char_height * SCALE_FACTOR_HEIGHT)
        
        # 3. Y-Startkoordinate (zentriert)
        y_start = (DISPLAY_HEIGHT - scaled_height) // 2

        # 4. Scroll-Grenzen
        if scaled_width <= DISPLAY_WIDTH:
            x_start = (DISPLAY_WIDTH - scaled_width) // 2
            x_end = x_start
        else:
            x_start = DISPLAY_WIDTH
            x_end = -scaled_width

        return scaled_width, scaled_height, y_start, x_start, x_end, padded_text


    # -------------------------
    # Haupt Scroll-Thread (Läuft auf Core 1)
    # -------------------------
    def _core1_scroll_thread(self):
        """
        Läuft blockierend auf Core 1, scrollt den Text.
        """
        self._core1_running = True
        
        _text = ""
        _padded_text = ""
        scaled_width = scaled_height = y_start = x_start = x_end = 0
        current_x = 0.0
        last_frame_time = utime.ticks_ms()
        fb_scaled = None # Der skalierte Framebuffer

        while self._core1_running:
            # 1. Datenabruf
            with self._core1_lock:
                new_text = self._core1_text
                is_power_on = self._core1_power_on # NEU: Power-Zustand abfragen

            # 2. Power-Logik (Minimale CPU-Last bei ausgeschaltetem Display)
            if not is_power_on:
                self.display.poweroff()
                # Wichtig: Sehr lange Pause, um CPU-Last zu minimieren
                utime.sleep_ms(500) 
                continue
            
            # Wenn eingeschaltet, sicherstellen, dass das Display an ist
            self.display.poweron() 

            # 3. Textwechsel: FrameBuffer neu erstellen (Rechenintensiver Teil)
            if new_text != _text:
                _text = new_text
                # Dimensionen berechnen und Framebuffer neu erstellen (wie im Original)
                # ... (Berechnung, Base FB erstellen, Skalierung)
                (scaled_width, scaled_height, y_start, x_start, x_end, _padded_text) = self._calculate_scaled_dims(_text)
                current_x = float(x_start)

                base_width = len(_padded_text) * 8
                fb_base = framebuf.FrameBuffer(bytearray(math.ceil(base_width * 8 / 8)), base_width, 8, framebuf.MONO_HLSB)
                fb_base.fill(0)
                fb_base.text(_padded_text, 0, 0, 1) 
                
                fb_scaled = self.scale_framebuf(
                    fb_base, 
                    base_width, 
                    8, 
                    scaled_width, 
                    scaled_height
                )
                
                # Statischer Text (einmaliges Rendern)
                if x_start == x_end:
                    self._render_scaled_framebuf(fb_scaled, y_start, int(current_x), scaled_height)
                    utime.sleep_ms(1000)
                    continue

            # 4. Scroll-Logik (Nur für scrollenden Text)
            if x_start != x_end and fb_scaled:
                now = utime.ticks_ms()
                if utime.ticks_diff(now, last_frame_time) >= SCROLL_DELAY_MS:
                    self._render_scaled_framebuf(fb_scaled, y_start, int(current_x), scaled_height)
                    current_x -= SCROLL_SPEED
                    
                    if current_x <= x_end:
                        current_x = x_start
                        utime.sleep_ms(500)
                    
                    last_frame_time = now
            else:
                # Wenn statisch oder kein Text, verhindere 100% Core-Auslastung
                utime.sleep_ms(100) 


    # -------------------------
    # Framebuffer rendern (unverändert)
    # -------------------------
    def _render_scaled_framebuf(self, fb_scaled, y_start, x_start, height):
        # ... (Implementierung wie im Originalcode)
        """Render-Funktion, die auf Core 1 läuft."""
        
        self.display.fill_rect(0, y_start, DISPLAY_WIDTH, height, 0)
        self.display.blit(fb_scaled, x_start, y_start)
        
        with self._core1_lock:
            self.display.show()

    # -------------------------
    # run-Funktion: Liest Events aus der Queue (Läuft auf Core 0)
    # -------------------------
    async def run(self):
        """Asynchroner Task, der Events verarbeitet und das Display steuert."""
        while True:
            print("[DisplayManager] Warte auf Event...")
            # Warten auf ein Event (blockiert Core 0 nicht)
            event = await self._display_event_queue.get()
            print("Display Event empfangen")
            await self.handle_event(event)

# Der alte 'set_text' ist nun obsolet und sollte in main.py entfernt werden.