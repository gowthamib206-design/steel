import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages SQLite database operations for sensor data logging"""
    
    def __init__(self, db_path: str = "temperature_logs.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._commit_counter = 0
        self.init_db()

    def init_db(self):
        """Initialize SQLite database and create table if needed."""
        # Check if the old schema exists (no device_id column)
        try:
            self.cursor.execute("PRAGMA table_info(measurements)")
            cols = [row[1] for row in self.cursor.fetchall()]
            if cols and ('station_name' not in cols or 'rssi' not in cols):
                logger.info("Old measurements table schema detected. Migrating...")
                self.cursor.execute("ALTER TABLE measurements RENAME TO measurements_old")
                self.conn.commit()
        except sqlite3.OperationalError:
            pass

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                device_id TEXT,
                station_name TEXT,
                temp_raw INTEGER,
                rtd_raw INTEGER,
                thermo_raw INTEGER,
                batt_raw INTEGER,
                rssi INTEGER,
                tx_index INTEGER DEFAULT 1
            )
        """)
        
        # Add tx_index column to existing tables that don't have it yet
        try:
            self.cursor.execute("PRAGMA table_info(measurements)")
            existing_cols = [row[1] for row in self.cursor.fetchall()]
            if 'tx_index' not in existing_cols:
                self.cursor.execute("ALTER TABLE measurements ADD COLUMN tx_index INTEGER DEFAULT 1")
                self.conn.commit()
        except Exception:
            pass
        self.conn.commit()

    def log_measurement(self,
                        station_name: str,
                        device_id: str,
                        temp_raw: int,
                        rtd_raw: int,
                        thermo_raw: int,
                        batt_raw: int,
                        rssi: int,
                        tx_index: int = 1):
        """Insert raw measurement values into the database."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.cursor.execute(
                "INSERT INTO measurements (timestamp, device_id, station_name, temp_raw, rtd_raw, thermo_raw, batt_raw, rssi, tx_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, device_id, station_name, temp_raw, rtd_raw, thermo_raw, batt_raw, rssi, tx_index)
            )
            self._commit_counter += 1
            if self._commit_counter >= 10:
                self.conn.commit()
                self._commit_counter = 0
            logger.debug(f"Logged measurement TX{tx_index}: {station_name} | {device_id}")
        except Exception as exc:
            logger.error(f"Database error: {exc}")

    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None
