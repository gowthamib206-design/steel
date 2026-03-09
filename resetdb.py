import os
import sqlite3

db_path = "temperature_logs.db"

# Delete old file, if present
if os.path.exists(db_path):
    os.remove(db_path)

# Create new database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        location_name TEXT,
        station_name TEXT,    -- New column!
        device_id TEXT,
        temp_raw INTEGER,
        rtd_raw INTEGER,
        thermo_raw INTEGER,
        batt_raw INTEGER,
        rssi_raw INTEGER      -- New column!
    )
""")
conn.commit()
conn.close()
print("Database reset with new columns.")