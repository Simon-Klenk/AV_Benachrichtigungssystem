from machine import RTC
import ntptime
import time

def is_sommerzeit(year, month, day, hour):
    """
    Prüft, ob ein Datum in Deutschland in der Sommerzeit liegt.
    Rückgabe: True = MESZ, False = MEZ
    """
    # Letzter Sonntag im März
    last_sunday_march = max(
        d for d in range(25, 32)
        if time.localtime(time.mktime((year, 3, d, 0, 0, 0, 0, 0)))[6] == 6
    )
    # Letzter Sonntag im Oktober
    last_sunday_october = max(
        d for d in range(25, 32)
        if time.localtime(time.mktime((year, 10, d, 0, 0, 0, 0, 0)))[6] == 6
    )

    if (month > 3 and month < 10):
        return True
    elif month == 3 and (day > last_sunday_march or (day == last_sunday_march and hour >= 2)):
        return True
    elif month == 10 and (day < last_sunday_october or (day == last_sunday_october and hour < 3)):
        return True
    else:
        return False

async def sync_time():
    """
    Synchronisiert die RTC-Zeit über NTP und setzt die deutsche Zeit inkl. Sommer-/Winterzeit.
    """
    rtc = RTC()
    try:
        print("⏱️ Synchronisiere Zeit über NTP...")
        ntptime.settime()  # UTC-Zeit setzen
        t = rtc.datetime()  # (year, month, day, weekday, hour, min, sec, ms)

        # Prüfen, ob Sommerzeit
        if is_sommerzeit(t[0], t[1], t[2], t[4]):
            tz_offset = 2  # MESZ
        else:
            tz_offset = 1  # MEZ

        # Stunde korrekt anpassen (über Mitternacht hinaus)
        hour = (t[4] + tz_offset) % 24
        t_local = (t[0], t[1], t[2], t[3], hour, t[5], t[6], t[7])
        rtc.datetime(t_local)
        print(f"✅ Lokale deutsche Zeit gesetzt (UTC+{tz_offset}): {rtc.datetime()}")
    except Exception as e:
        print(f"⚠️ NTP-Zeit konnte nicht gesetzt werden: {e}")
