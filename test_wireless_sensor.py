"""
Unit tests for wireless sensor application
Tests cover all negative test cases and edge scenarios
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import serial
import csv
from wireless_sensor import (
    SensorErrorType, SensorData, RTDTemperatureTable, SerialPortManager,
    PacketProcessor, SensorDataParser
)


class TestSensorData(unittest.TestCase):
    """Test SensorData validation"""
    
    def test_valid_sensor_data(self):
        """Test valid sensor data"""
        data = SensorData(
            temperature=25.5,
            device_id="1 2 3 4",
            rtd_resistance=100.0,
            rtd_temperature=50,
            thermocouple=15.5,
            thermocouple_voltage_uv=500.0,
            battery_voltage=3.7,
            rssi=-50,
            raw_packet=list(range(16))
        )
        self.assertTrue(data.is_valid())
    
    def test_invalid_temperature_type(self):
        """Test invalid temperature type"""
        data = SensorData(
            temperature="25.5",  # String instead of float
            device_id="1 2 3 4",
            rtd_resistance=100.0,
            rtd_temperature=50,
            thermocouple=15.5,
            thermocouple_voltage_uv=500.0,
            battery_voltage=3.7,
            rssi=-50,
            raw_packet=list(range(16))
        )
        self.assertFalse(data.is_valid())
    
    def test_invalid_battery_voltage_too_high(self):
        """Test battery voltage exceeding maximum"""
        data = SensorData(
            temperature=25.5,
            device_id="1 2 3 4",
            rtd_resistance=100.0,
            rtd_temperature=50,
            thermocouple=15.5,
            thermocouple_voltage_uv=500.0,
            battery_voltage=15.0,  # Too high
            rssi=-50,
            raw_packet=list(range(16))
        )
        self.assertFalse(data.is_valid())
    
    def test_invalid_battery_voltage_negative(self):
        """Test negative battery voltage"""
        data = SensorData(
            temperature=25.5,
            device_id="1 2 3 4",
            rtd_resistance=100.0,
            rtd_temperature=50,
            thermocouple=15.5,
            thermocouple_voltage_uv=500.0,
            battery_voltage=-1.0,  # Negative
            rssi=-50,
            raw_packet=list(range(16))
        )
        self.assertFalse(data.is_valid())
    
    def test_invalid_packet_length(self):
        """Test invalid packet length"""
        data = SensorData(
            temperature=25.5,
            device_id="1 2 3 4",
            rtd_resistance=100.0,
            rtd_temperature=50,
            thermocouple=15.5,
            thermocouple_voltage_uv=500.0,
            battery_voltage=3.7,
            rssi=-50,
            raw_packet=list(range(10))  # Wrong length
        )
        self.assertFalse(data.is_valid())
    
    def test_invalid_device_id_type(self):
        """Test invalid device ID type"""
        data = SensorData(
            temperature=25.5,
            device_id=12345,  # Integer instead of string
            rtd_resistance=100.0,
            rtd_temperature=50,
            thermocouple=15.5,
            thermocouple_voltage_uv=500.0,
            battery_voltage=3.7,
            rssi=-50,
            raw_packet=list(range(16))
        )
        self.assertFalse(data.is_valid())


class TestRTDTemperatureTable(unittest.TestCase):
    """Test RTD temperature conversion"""
    
    def test_valid_rtd_conversion(self):
        """Test valid RTD resistance to temperature conversion"""
        temp = RTDTemperatureTable.get_temperature_from_resistance(100.0)
        self.assertIsInstance(temp, int)
    
    def test_invalid_rtd_type(self):
        """Test invalid RTD resistance type"""
        with self.assertRaises(ValueError):
            RTDTemperatureTable.get_temperature_from_resistance("100.0")
    
    def test_negative_rtd_resistance(self):
        """Test negative RTD resistance"""
        with self.assertRaises(ValueError):
            RTDTemperatureTable.get_temperature_from_resistance(-50.0)
    
    def test_zero_rtd_resistance(self):
        """Test zero RTD resistance"""
        temp = RTDTemperatureTable.get_temperature_from_resistance(0.0)
        self.assertIsInstance(temp, int)
    
    def test_extreme_rtd_value(self):
        """Test extremely high RTD value"""
        temp = RTDTemperatureTable.get_temperature_from_resistance(1000.0)
        self.assertIsInstance(temp, int)


class TestSerialPortManager(unittest.TestCase):
    """Test serial port management"""
    
    def setUp(self):
        self.manager = SerialPortManager()
    
    @patch('serial.tools.list_ports.comports')
    def test_get_available_ports_empty(self, mock_comports):
        """Test getting ports when none available"""
        mock_comports.return_value = []
        ports = self.manager.get_available_ports()
        self.assertEqual(ports, [])
    
    @patch('serial.tools.list_ports.comports')
    def test_get_available_ports_multiple(self, mock_comports):
        """Test getting multiple available ports"""
        mock_port1 = Mock()
        mock_port1.device = "COM1"
        mock_port1.description = "USB Serial Port"
        
        mock_port2 = Mock()
        mock_port2.device = "COM2"
        mock_port2.description = "Arduino"
        
        mock_comports.return_value = [mock_port1, mock_port2]
        ports = self.manager.get_available_ports()
        self.assertEqual(len(ports), 2)
    
    def test_open_port_empty_string(self):
        """Test opening empty port string"""
        success, msg = self.manager.open_port("")
        self.assertFalse(success)
        self.assertIn("empty", msg.lower())
    
    def test_open_port_invalid_format(self):
        """Test opening port with invalid format"""
        success, msg = self.manager.open_port("   ")
        self.assertFalse(success)
    
    @patch('serial.Serial')
    def test_open_port_serial_exception(self, mock_serial):
        """Test serial port exception handling"""
        mock_serial.side_effect = serial.SerialException("Device not found")
        success, msg = self.manager.open_port("COM1 - USB")
        self.assertFalse(success)
        self.assertIn("error", msg.lower())
    
    @patch('serial.Serial')
    def test_open_port_success(self, mock_serial):
        """Test successful port opening"""
        mock_serial.return_value = MagicMock()
        success, msg = self.manager.open_port("COM1 - USB")
        self.assertTrue(success)
    
    def test_close_port_not_open(self):
        """Test closing port when not open"""
        success, msg = self.manager.close_port()
        self.assertFalse(success)
    
    def test_read_byte_not_open(self):
        """Test reading byte when port not open"""
        data = self.manager.read_byte()
        self.assertIsNone(data)

    @patch('serial.Serial')
    def test_read_byte_serial_exception(self, mock_serial):
        """Test read error handling"""
        mock_ser = MagicMock()
        mock_ser.read.side_effect = serial.SerialException("Read error")
        mock_serial.return_value = mock_ser

        self.manager.open_port("COM1 - USB")
        data = self.manager.read_byte()
        self.assertIsNone(data)


class TestDatabaseAndHistory(unittest.TestCase):
    """Verify that the SQLite schema and export logic produce expected results."""

    def setUp(self):
        # create a minimal controller object with DB methods
        from wireless_sensor import SensorGUI
        self.app = SensorGUI()
        # use in-memory database for tests
        self.app.init_db(db_path=":memory:")

    def tearDown(self):
        try:
            self.app.conn.close()
        except Exception:
            pass

    def test_schema_columns(self):
        """Table should have the new six columns"""
        self.app.cursor.execute("PRAGMA table_info(measurements)")
        cols = [row[1] for row in self.app.cursor.fetchall()]
        expected = [
            'id', 'timestamp', 'device_id',
            'temp_raw', 'rtd_raw', 'thermo_raw', 'batt_raw'
        ]
        for col in expected:
            self.assertIn(col, cols)

    def test_log_and_retrieve(self):
        """log_to_db should insert raw ints that can be queried later"""
        # arbitrary sample values
        self.app.log_to_db('aa bb cc dd', 12345678, 0x1122, 0x3344, 0x5566)
        self.app.conn.commit()
        self.app.cursor.execute("SELECT device_id, temp_raw, rtd_raw, thermo_raw, batt_raw FROM measurements")
        row = self.app.cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 'aa bb cc dd')
        self.assertEqual(row[1], 12345678)
        self.assertEqual(row[2], 0x1122)
        self.assertEqual(row[3], 0x3344)
        self.assertEqual(row[4], 0x5566)

    @patch('tkinter.filedialog.asksaveasfilename')
    def test_export_csv_conversions(self, mock_dialog):
        """export_csv should write correctly converted rows"""
        import tempfile
        import tkinter as tk
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        tmp.close()
        mock_dialog.return_value = tmp.name

        # insert one record with known raw values
        # let temp_raw be 25.0000°C -> 250000 (25*10000)
        temp_raw = 25 * 10000
        # choose rtd_raw such that resistance and temperature are simple
        # use zero for simplicity (should convert to temperature value via table)
        rtd_raw = 0
        # choose thermo_raw that gives easy voltage; we will just pick 0 so melt temp 0
        thermo_raw = 0
        # battery raw corresponds to 3.7V -> 3700
        batt_raw = 3700
        self.app.log_to_db('de ad be ef', temp_raw, rtd_raw, thermo_raw, batt_raw)
        self.app.conn.commit()

        # export_csv lives on SettingsFrame, so instantiate one just for the call
        from wireless_sensor import SettingsFrame
        root = tk.Tk()
        frame = SettingsFrame(parent=root, controller=self.app)
        frame.export_csv()
        root.destroy()

        # read the generated file and verify contents
        with open(tmp.name, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        # header + one data row
        self.assertGreaterEqual(len(rows), 2)
        header = rows[0]
        self.assertEqual(header, [
            'Date', 'Transmitter ID', 'MeltTemp_C', 'RTDTemp_C',
            'DeviceTemp_C', 'BatteryVolts'
        ])
        data_row = rows[1]
        # device id should match
        self.assertEqual(data_row[1], 'de ad be ef')
        # device temp should be 25.0
        self.assertAlmostEqual(float(data_row[4]), 25.0)
        # battery voltage around 3.7
        self.assertAlmostEqual(float(data_row[5]), 3.7)

    def test_refresh_history_uses_db(self):
        """refresh_history should build list entries from DB"""
        # insert two rows
        self.app.log_to_db('11 22 33 44', 10000, 0, 0, 3000)
        self.app.log_to_db('55 66 77 88', 20000, 0, 0, 4000)
        self.app.conn.commit()
        # create a fake SettingsFrame and call refresh_history
        import tkinter as tk
        from wireless_sensor import SettingsFrame
        root = tk.Tk()
        frame = SettingsFrame(parent=root, controller=self.app)
        frame.refresh_history()
        # listbox should contain two items
        self.assertEqual(frame.history_list.size(), 2)


class TestPacketProcessor(unittest.TestCase):
    """Test packet processing"""
    
    def setUp(self):
        self.processor = PacketProcessor()
    
    def test_process_invalid_data(self):
        """Test processing invalid data"""
        result = self.processor.process_byte(b"")
        self.assertIsNone(result)
    
    def test_process_multi_byte_data(self):
        """Test processing multi-byte data"""
        result = self.processor.process_byte(b"ab")
        self.assertIsNone(result)
    
    def test_process_escape_byte(self):
        """Test escape byte handling"""
        result = self.processor.process_byte(b"\b")
        self.assertIsNone(result)
        self.assertTrue(self.processor.escape)
    
    def test_process_frame_start(self):
        """Test frame start handling"""
        result = self.processor.process_byte(b"\r")
        self.assertIsNone(result)
        self.assertEqual(len(self.processor.packet), 0)
    
    def test_process_incomplete_packet_frame_end(self):
        """Test incomplete packet at frame end"""
        # Add some data
        self.processor.packet = [1, 2, 3]  # Only 3 bytes instead of 18
        result = self.processor.process_byte(b"\n")
        self.assertIsNone(result)
    
    def test_reset_processor(self):
        """Test processor reset"""
        self.processor.packet = [1, 2, 3]
        self.processor.escape = True
        self.processor.reset()
        self.assertEqual(self.processor.packet, [])
        self.assertFalse(self.processor.escape)


class TestSensorDataParser(unittest.TestCase):
    """Test sensor data parsing"""
    
    def setUp(self):
        self.parser = SensorDataParser()
    
    def test_parse_empty_packet(self):
        """Test parsing empty packet"""
        with self.assertRaises(ValueError):
            self.parser.parse_packet([])
    
    def test_parse_none_packet(self):
        """Test parsing None packet"""
        with self.assertRaises(ValueError):
            self.parser.parse_packet(None)
    
    def test_parse_short_packet(self):
        """Test parsing short packet"""
        with self.assertRaises(ValueError):
            self.parser.parse_packet([1, 2, 3])
    
    def test_parse_long_packet(self):
        """Test parsing too long packet"""
        with self.assertRaises(ValueError):
            self.parser.parse_packet(list(range(30)))
    
    def test_parse_valid_packet(self):
        """Test parsing valid packet"""
        # Create a valid 16-byte packet with realistic values
        packet = [
            0xE8, 0x03, 0x00, 0x00,  # Bytes 0-3: Temperature = 1000 (0.1°C)
            0x00,  # Byte 4: RSSI
            0x00,  # Byte 5: Packet sequence
            0x01, 0x02, 0x03, 0x04,  # Bytes 6-9: Device ID
            0x64, 0x00,  # Bytes 10-11: RTD = 100
            0x00, 0x00,  # Bytes 12-13: Thermocouple
            0xFC, 0x0E,  # Bytes 14-15: Battery voltage (3.84V = 3844mV)
        ]
        result = self.parser.parse_packet(packet)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SensorData)
        # Verify it parsed correctly
        self.assertTrue(result.is_valid())
    
    def test_parse_negative_rtd_resistance(self):
        """Test parsing packet with negative RTD (should be handled gracefully)"""
        packet = list(range(16))
        packet[10] = 0xFF
        packet[11] = 0xFF  # Will result in large value, not negative
        result = self.parser.parse_packet(packet)
        self.assertIsNotNone(result)
    
    def test_parse_extreme_battery_voltage(self):
        """Test parsing packet with extreme battery voltage"""
        packet = [0] * 18
        packet[15] = 0xFF
        packet[16] = 0xFF  # Maximum voltage value (65.535V - out of range)
        # This should fail validation and raise an error
        with self.assertRaises(ValueError):
            result = self.parser.parse_packet(packet)
            # The parsed data should fail is_valid() check
            if result:
                self.assertFalse(result.is_valid())
    
    def test_parse_invalid_data_index(self):
        """Test parsing with malformed packet data"""
        packet = list(range(16))
        packet[1] = 0xFF
        packet[2] = 0xFF
        packet[3] = 0xFF
        packet[4] = 0xFF
        result = self.parser.parse_packet(packet)
        self.assertIsNotNone(result)


class TestSensorErrorTypes(unittest.TestCase):
    """Test sensor error enumeration"""
    
    def test_error_type_values(self):
        """Test error type values are defined"""
        self.assertEqual(SensorErrorType.INVALID_PACKET_LENGTH.value, "Invalid packet length")
        self.assertEqual(SensorErrorType.INVALID_PORT.value, "Invalid port")
        self.assertEqual(SensorErrorType.PORT_NOT_OPEN.value, "Port not open")
        self.assertEqual(SensorErrorType.INVALID_SENSOR_VALUE.value, "Invalid sensor value")
        self.assertEqual(SensorErrorType.NO_PORTS_AVAILABLE.value, "No ports available")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""
    
    def test_rtd_minimum_value(self):
        """Test RTD with minimum table value"""
        temp = RTDTemperatureTable.get_temperature_from_resistance(18.4932)
        self.assertEqual(temp, -200)
    
    def test_rtd_maximum_value(self):
        """Test RTD with maximum table value"""
        temp = RTDTemperatureTable.get_temperature_from_resistance(390.2623)
        self.assertIsInstance(temp, int)
    
    def test_rtd_between_values(self):
        """Test RTD with value between table entries"""
        temp = RTDTemperatureTable.get_temperature_from_resistance(100.5)
        self.assertIsInstance(temp, int)
    
    def test_battery_voltage_at_minimum(self):
        """Test minimum valid battery voltage"""
        data = SensorData(
            temperature=25.5,
            device_id="1 2 3 4",
            rtd_resistance=100.0,
            rtd_temperature=50,
            thermocouple=15.5,
            thermocouple_voltage_uv=500.0,
            battery_voltage=0.0,
            rssi=-50,
            raw_packet=list(range(16))
        )
        self.assertTrue(data.is_valid())
    
    def test_battery_voltage_at_maximum(self):
        """Test maximum valid battery voltage"""
        data = SensorData(
            temperature=25.5,
            device_id="1 2 3 4",
            rtd_resistance=100.0,
            rtd_temperature=50,
            thermocouple=15.5,
            thermocouple_voltage_uv=500.0,
            battery_voltage=10.0,
            rssi=-50,
            raw_packet=list(range(16))
        )
        self.assertTrue(data.is_valid())


if __name__ == '__main__':
    unittest.main()
