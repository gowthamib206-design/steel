"""
Unit tests for modular wireless sensor application
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import os
import sqlite3
import csv
import tempfile

# Internal imports
from models import SensorErrorType, SensorData
from conversions import RTDTemperatureTable, voltage_uV_to_temperature_C, raw_to_voltage_uV, apply_rtd_compensation
from hardware import SerialPortManager, PacketProcessor, SensorDataParser
from database import DatabaseManager

class TestSensorData(unittest.TestCase):
    def test_valid_sensor_data(self):
        data = SensorData(
            temperature=25.5, device_id="11 22 33 44",
            rtd_resistance=100.0, rtd_temperature=50,
            thermocouple=15.5, thermocouple_voltage_uv=500.0,
            battery_voltage=3.7, rssi=-50, raw_packet=list(range(16))
        )
        self.assertTrue(data.is_valid())

class TestRTDTemperatureTable(unittest.TestCase):
    def test_valid_rtd_conversion(self):
        # Resistance 100.0 corresponds to ~0C for PT100
        temp = RTDTemperatureTable.get_temperature_from_resistance(100.0)
        self.assertIsInstance(temp, int)

class TestHardware(unittest.TestCase):
    def setUp(self):
        self.manager = SerialPortManager()
        self.processor = PacketProcessor()
        self.parser = SensorDataParser()

    def test_packet_processor_logic(self):
        # Test basic frame handling
        self.processor.process_byte(b"\r")
        self.assertEqual(len(self.processor.packet), 0)
        for i in range(16):
            self.processor.process_byte(bytes([i]))
        res = self.processor.process_byte(b"\n")
        self.assertEqual(len(res), 16)

    def test_parser_logic(self):
        # Valid 16-byte dummy packet
        pkt = [0]*16
        pkt[14] = 0xFC; pkt[15] = 0x0E # ~3.84V
        res = self.parser.parse_packet(pkt)
        self.assertAlmostEqual(res.battery_voltage, 3.84, places=2)

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(":memory:")

    def test_log_and_query(self):
        self.db.log_measurement("LADLE 01", "AA BB CC DD", 100, 200, 300, 400, -60, 1)
        self.db.conn.commit()
        self.db.cursor.execute("SELECT station_name, device_id, rssi FROM measurements")
        row = self.db.cursor.fetchone()
        self.assertEqual(row[0], "LADLE 01")
        self.assertEqual(row[1], "AA BB CC DD")
        self.assertEqual(row[2], -60)

if __name__ == '__main__':
    unittest.main()
