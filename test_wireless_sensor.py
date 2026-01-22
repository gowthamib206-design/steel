"""
Unit tests for wireless sensor application
Tests cover all negative test cases and edge scenarios
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import serial
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
            battery_voltage=3.7,
            raw_packet=list(range(18))
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
            battery_voltage=3.7,
            raw_packet=list(range(18))
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
            battery_voltage=15.0,  # Too high
            raw_packet=list(range(18))
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
            battery_voltage=-1.0,  # Negative
            raw_packet=list(range(18))
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
            battery_voltage=3.7,
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
            battery_voltage=3.7,
            raw_packet=list(range(18))
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
        # Create a valid 18-byte packet with realistic values
        packet = [
            0x00,  # Byte 0
            0xE8, 0x03, 0x00, 0x00,  # Bytes 1-4: Temperature = 1000 (0.1°C)
            0x00, 0x00,  # Bytes 5-6
            0x01, 0x02, 0x03, 0x04,  # Bytes 7-10: Device ID
            0x64, 0x00,  # Bytes 11-12: RTD = 100
            0x00, 0x00,  # Bytes 13-14: Thermocouple
            0xFC, 0x0E,  # Bytes 15-16: Battery voltage (3.84V = 3844mV)
            0x00  # Byte 17
        ]
        result = self.parser.parse_packet(packet)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SensorData)
        # Verify it parsed correctly
        self.assertTrue(result.is_valid())
    
    def test_parse_negative_rtd_resistance(self):
        """Test parsing packet with negative RTD (should be handled gracefully)"""
        packet = list(range(18))
        packet[11] = 0xFF
        packet[12] = 0xFF  # Will result in large value, not negative
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
        packet = list(range(18))
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
            battery_voltage=0.0,
            raw_packet=list(range(18))
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
            battery_voltage=10.0,
            raw_packet=list(range(18))
        )
        self.assertTrue(data.is_valid())


if __name__ == '__main__':
    unittest.main()
