from enum import Enum
from dataclasses import dataclass
from typing import List

class SensorErrorType(Enum):
    """Enumeration for sensor error types"""
    INVALID_PACKET_LENGTH = "Invalid packet length"
    INVALID_PORT = "Invalid port"
    PORT_NOT_OPEN = "Port not open"
    INVALID_SENSOR_VALUE = "Invalid sensor value"
    NO_PORTS_AVAILABLE = "No ports available"
    INVALID_DATA = "Invalid data received"
    DEVICE_NOT_CONNECTED = "Device not connected"


@dataclass
class SensorData:
    """Data class for sensor readings"""
    temperature: float
    device_id: str
    rtd_resistance: float
    rtd_temperature: int
    thermocouple: float
    thermocouple_voltage_uv: float  # Raw thermocouple voltage in microvolts
    battery_voltage: float
    rssi: int
    raw_packet: List[int]

    def is_valid(self) -> bool:
        """Validate sensor data"""
        try:
            if not isinstance(self.temperature, (int, float)):
                return False
            if not isinstance(self.battery_voltage, (int, float)):
                return False
            if self.battery_voltage < 0 or self.battery_voltage > 10:
                return False
            if not isinstance(self.device_id, str):
                return False
            if len(self.raw_packet) != 16:
                return False
            return True
        except (TypeError, AttributeError):
            return False
