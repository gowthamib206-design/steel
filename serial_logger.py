"""
Serial Port Raw Byte Logger
- Uses the same framing protocol as wireless_sensor.py PacketProcessor
- Frame: 0x0D (\r) = start, 0x0A (\n) = end, 0x08 (\b) = escape next byte
- Extracts 16 payload bytes per packet, prints to console and saves to SQLite
"""

import serial
import serial.tools.list_ports
import sqlite3
from datetime import datetime

PORT        = "COM8"
BAUDRATE    = 115200
DB_FILE     = "serial_packets.db"
PACKET_SIZE = 16

# Same framing constants as wireless_sensor.py PacketProcessor
FRAME_START = 0x0D   # \r
FRAME_END   = 0x0A   # \n
ESCAPE_BYTE = 0x08   # \b


def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS packets (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            b0  INTEGER, b1  INTEGER, b2  INTEGER, b3  INTEGER,
            b4  INTEGER, b5  INTEGER, b6  INTEGER, b7  INTEGER,
            b8  INTEGER, b9  INTEGER, b10 INTEGER, b11 INTEGER,
            b12 INTEGER, b13 INTEGER, b14 INTEGER, b15 INTEGER
        )
    """)
    conn.commit()
    return conn


def save(conn, packet):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    conn.execute(
        "INSERT INTO packets VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ts, *packet)
    )
    conn.commit()


def run():
    ports = serial.tools.list_ports.comports()
    if ports:
        print("Available ports: " + ", ".join(f"{p.device} - {p.description}" for p in ports))
    else:
        print("No ports found. Plug in your device and try again.")
        return

    conn = init_db()

    print(f"\nOpening {PORT} @ {BAUDRATE} baud ...")
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
    except serial.SerialException as e:
        print(f"Error: {e}")
        conn.close()
        return

    print(f"Reading from {PORT} — press Ctrl+C to stop.\n")

    packet = []
    escape = False
    count  = 0

    try:
        while True:
            raw = ser.read(1)
            if not raw:
                continue

            byte_val = raw[0]

            if not escape:
                if byte_val == ESCAPE_BYTE:
                    escape = True
                    continue
                if byte_val == FRAME_START:
                    packet = []
                    continue
                if byte_val == FRAME_END:
                    if len(packet) == PACKET_SIZE:
                        count += 1
                        print(f"[{count:04d}] " + " ".join(f"{b:02X}" for b in packet))
                        save(conn, packet)
                    packet = []
                    continue
                packet.append(byte_val)
            else:
                packet.append(byte_val)
                escape = False

    except KeyboardInterrupt:
        print(f"\nStopped by user. {count} packets saved.")
    except serial.SerialException as e:
        print(f"Serial error: {e}")
    finally:
        if ser.is_open:
            ser.close()
        conn.close()


if __name__ == "__main__":
    run()
