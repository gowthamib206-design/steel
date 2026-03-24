import serial
import serial.tools.list_ports
import logging
import struct
from typing import List, Optional, Tuple
from models import SensorData, SensorErrorType
from conversions import (
    RTDTemperatureTable, 
    raw_to_voltage_uV, 
    voltage_uV_to_temperature_C, 
    apply_rtd_compensation
)

logger = logging.getLogger(__name__)

class SerialPortManager:
    """Manages serial port operations"""
    
    def __init__(self):
         self.serial = None         
         self.is_open = False
         self.current_port = None 
         self.input_serial = None
         self.input_is_open = False
         self.input_port = None
         self.output_serial = None
         self.output_is_open = False
         self.output_port = None
    
    def get_available_ports(self, exclude_connected=False) -> List[str]:
        """Get list of available serial ports"""
        try:
            all_ports = [f"{p.device} - {p.description}" for p in serial.tools.list_ports.comports()]
            if not all_ports:
                return []
            if exclude_connected and self.current_port:
                current_device = self.current_port.split(" - ")[0].strip() if " - " in self.current_port else self.current_port
                filtered_ports = [p for p in all_ports if not p.startswith(current_device)]
                return filtered_ports
            return all_ports
        except Exception as exc:
            logger.error(f"Error getting available ports: {exc}")
            return []
       
    def open_port(self, port_str: str, baudrate: int = 115200) -> Tuple[bool, str]:
        """Open INPUT serial port"""
        if not port_str:
            return False, "Port string is empty"
        try:
            port = port_str.split(" - ")[0].strip()
            if self.serial and self.serial.is_open:
                self.serial.close()
            self.serial = serial.Serial(port, baudrate, timeout=1)
            self.input_serial = self.serial
            self.is_open = True
            self.input_is_open = True
            self.current_port = port_str
            self.input_port = port_str
            return True, f"Successfully opened {port}"
        except Exception as exc:
            return False, f"Error opening port: {exc}"
    
    def close_port(self) -> Tuple[bool, str]:
        """Close INPUT serial port"""
        try:
            if self.serial and self.serial.is_open:
                self.serial.close()
                self.serial = None
                self.is_open = False
                return True, "Port closed"
            return False, "Port not open"
        except Exception as exc:
            return False, f"Error: {exc}"

    def read_byte(self) -> Optional[bytes]:
        """Read single byte from INPUT port"""
        try:
            if self.serial and self.is_open:
                data = self.serial.read(1)
                return data if data else None
            return None
        except Exception as exc:
            logger.error(f"Read error: {exc}")
            return None

    def open_output_port(self, port_str: str, baudrate: int = 115200) -> Tuple[bool, str]:
        """Open output serial port"""
        if not port_str:
            return False, "Output port empty"
        try:
            port = port_str.split(" - ")[0].strip()
            if self.input_port and port == self.input_port.split(" - ")[0].strip():
                return False, "Same port for IN and OUT"
            if self.output_serial and self.output_serial.is_open:
                self.output_serial.close()
            self.output_serial = serial.Serial(port, baudrate, timeout=1)
            self.output_is_open = True
            self.output_port = port_str
            return True, f"Opened output {port}"
        except Exception as exc:
            return False, str(exc)

    def close_output_port(self) -> Tuple[bool, str]:
        if self.output_serial and self.output_serial.is_open:
            self.output_serial.close()
            self.output_is_open = False
            return True, "Closed"
        return False, "Not open"

    def write_byte(self, data: bytes) -> Tuple[bool, str]:
        try:
            if self.output_serial and self.output_is_open:
                self.output_serial.write(data)
                self.output_serial.flush()
                return True, "Success"
            return False, "Not open"
        except Exception as exc:
            return False, str(exc)


class PacketProcessor:
    """Processes serial packets from sensor"""
    
    PACKET_LENGTH = 16
    ESCAPE_BYTE = b"\b"
    FRAME_END = b"\n"
    FRAME_START = b"\r"
    
    def __init__(self):
        self.escape = False
        self.packet: List[int] = []
    
    def process_byte(self, data: bytes) -> Optional[List[int]]:
        if not data or len(data) != 1:
            return None
        byte_val = data[0]
        if not self.escape:
            if data == self.ESCAPE_BYTE:
                self.escape = True
                return None
            if data == self.FRAME_START:
                self.packet = []
                return None
            if data == self.FRAME_END:
                if len(self.packet) == self.PACKET_LENGTH:
                    complete_packet = self.packet.copy()
                    self.packet = []
                    return complete_packet
                else:
                    self.packet = []
                    return None
            self.packet.append(byte_val)
        else:
            self.packet.append(byte_val)
            self.escape = False
        return None
    
    def reset(self):
        self.packet = []
        self.escape = False


class SensorDataParser:
    """Parses packet data to extract sensor values"""
    
    @staticmethod
    def parse_packet(packet: List[int], enable_rtd_compensation: bool = False) -> Optional[SensorData]:
        if not packet or len(packet) != 16:
            raise ValueError(SensorErrorType.INVALID_PACKET_LENGTH.value)
        
        try:
            # Parse temperature (4 bytes, little-endian)
            temp = packet[3]
            temp = (temp << 8) | packet[2]
            temp = (temp << 8) | packet[1]
            temp = (temp << 8) | packet[0]
            temp = temp / 10000.0
            
            rssi = packet[4] - 128
            device_id = f"{packet[6]:02x} {packet[7]:02x} {packet[8]:02x} {packet[9]:02x}"
            
            rtd = (packet[11] << 8) | packet[10]
            rtd_resistance = (rtd * 400) / (2**15)
            
            rtd_temperature = None
            try:
                rtd_temperature = RTDTemperatureTable.get_temperature_from_resistance(rtd_resistance)
            except ValueError:
                rtd_temperature = None
            
            thermo_raw = (packet[13] << 8) | packet[12] 
            thermo_uV = raw_to_voltage_uV(thermo_raw)
            
            if enable_rtd_compensation and rtd_temperature is not None:
                thermo_temperature_C = apply_rtd_compensation(rtd_temperature, thermo_uV)
            else:
                thermo_temperature_C = voltage_uV_to_temperature_C(thermo_uV)
            
            battery_voltage = ((packet[15] << 8) | packet[14]) / 1000.0
            
            sensor_data = SensorData(
                temperature=temp,
                device_id=device_id,
                rtd_resistance=rtd_resistance,
                rtd_temperature=rtd_temperature,
                thermocouple=thermo_temperature_C,
                thermocouple_voltage_uv=thermo_uV,
                battery_voltage=battery_voltage,
                rssi=rssi,
                raw_packet=packet
            )
            return sensor_data
        except Exception as exc:
            logger.error(f"Error parsing packet: {exc}")
            raise ValueError(f"Parsing error: {exc}")
