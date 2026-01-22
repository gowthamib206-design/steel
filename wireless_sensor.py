"""
Wireless Sensor Data Logger Application
Handles serial communication with wireless sensors and displays temperature/RTD data via GUI
Modern UI based on ACUCAST reference
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import serial
import serial.tools.list_ports
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import struct
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
    battery_voltage: float
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
            if len(self.raw_packet) != 18:
                return False
            return True
        except (TypeError, AttributeError):
            return False


class RTDTemperatureTable:
    """RTD resistance to temperature conversion table"""
    
    rtd_values = [18.4932, 18.9258, 19.3580, 19.7899, 20.2215, 20.6526, 21.0834, 21.5139, 21.9439, 22.3737, 22.8031,
                  23.2321, 23.6608, 24.0891, 24.5171, 24.9447, 25.3720, 25.7990, 26.2257, 26.6520, 27.0779, 27.5036,
                  27.9289, 28.3539, 28.7786, 29.2029, 29.6270, 30.0507, 30.4741, 30.8972, 31.3200, 31.7425, 32.1646,
                  32.5865, 33.0081, 33.4294, 33.8503, 34.2710, 34.6914, 35.1115, 35.5313, 35.9508, 36.3700, 36.7889,
                  37.2076, 37.6260, 38.0440, 38.4619, 38.8794, 39.2967, 39.7137, 40.1304, 40.5469, 40.9631, 41.3790,
                  41.7946, 42.2101, 42.6252, 43.0401, 43.4547, 43.8691, 44.2832, 44.6971, 45.1107, 45.5241, 45.9372,
                  46.3501, 46.7628, 47.1752, 47.5873, 47.9993, 48.4109, 48.8224, 49.2336, 49.6446, 50.0554, 50.4659,
                  50.8762, 51.2863, 51.6962, 52.1058, 52.5152, 52.9244, 53.3334, 53.7422, 54.1507, 54.5591, 54.9672,
                  55.3751, 55.7828, 56.1903, 56.5976, 57.0047, 57.4115, 57.8182, 58.2247, 58.6310, 59.0371, 59.4429,
                  59.8486, 60.2541, 60.6594, 61.0645, 61.4695, 61.8742, 62.2787, 62.6831, 63.0873, 63.4912, 63.8950,
                  64.2987, 64.7021, 65.1054, 65.5084, 65.9114, 66.3141, 66.7166, 67.1190, 67.5212, 67.9233, 68.3251,
                  68.7268, 69.1284, 69.5297, 69.9309, 70.3319, 70.7328, 71.1335, 71.5340, 71.9344, 72.3346, 72.7347,
                  73.1346, 73.5343, 73.9339, 74.3334, 74.7326, 75.1318, 75.5307, 75.9296, 76.3282, 76.7268, 77.1251,
                  77.5234, 77.9214, 78.3194, 78.7171, 79.1148, 79.5123, 79.9096, 80.3068, 80.7039, 81.1008, 81.4976,
                  81.8943, 82.2908, 82.6871, 83.0834, 83.4795, 83.8754, 84.2713, 84.6669, 85.0625, 85.4579, 85.8532,
                  86.2484, 86.6434, 87.0383, 87.4331, 87.8277, 88.2222, 88.6166, 89.0109, 89.4050, 89.7990, 90.1929,
                  90.5866, 90.9802, 91.3737, 91.7671, 92.1603, 92.5535, 92.9465, 93.3394, 93.7321, 94.1247, 94.5173,
                  94.9097, 95.3019, 95.6941, 96.0861, 96.4780, 96.8698, 97.2615, 97.6531, 98.0445, 98.4359, 98.8271,
                  99.2182, 99.6091, 100.0000, 100.3907, 100.7814, 101.1719, 101.5623, 101.9526, 102.3427, 102.7328,
                  103.1227, 103.5125, 103.9022, 104.2918, 104.6813, 105.0706, 105.4599, 105.8490, 106.2380, 106.6269,
                  107.0156, 107.4043, 107.7928, 108.1813, 108.5696, 108.9578, 109.3458, 109.7338, 110.1216, 110.5094,
                  110.8970, 111.2845, 111.6718, 112.0591, 112.4463, 112.8333, 113.2202, 113.6070, 113.9937, 114.3802,
                  114.7667, 115.1530, 115.5392, 115.9254, 116.3113, 116.6972, 117.0830, 117.4686, 117.8541, 118.2395,
                  118.6248, 119.0100, 119.3951, 119.7800, 120.1648, 120.5495, 120.9341, 121.3186, 121.7030, 122.0872,
                  122.4713, 122.8554, 123.2392, 123.6230, 124.0067, 124.3902, 124.7737, 125.1570, 125.5402, 125.9233,
                  126.3063, 126.6891, 127.0718, 127.4545, 127.8370, 128.2194, 128.6016, 128.9838, 129.3658, 129.7478,
                  130.1296, 130.5113, 130.8928, 131.2743, 131.6556, 132.0369, 132.4180, 132.7990, 133.1799, 133.5606,
                  133.9413, 134.3218, 134.7022, 135.0825, 135.4627, 135.8428, 136.2227, 136.6026, 136.9823, 137.3619,
                  137.7414, 138.1207, 138.5000, 138.8791, 139.2582, 139.6371, 140.0159, 140.3945, 140.7731, 141.1515,
                  141.5299, 141.9081, 142.2862, 142.6642, 143.0420, 143.4198, 143.7974, 144.1749, 144.5523, 144.9296,
                  145.3068, 145.6838, 146.0608, 146.4376, 146.8143, 147.1909, 147.5673, 147.9437, 148.3199, 148.6960,
                  149.0721, 149.4479, 149.8237, 150.1994, 150.5749, 150.9504, 151.3257, 151.7009, 152.0759, 152.4509,
                  152.8257, 153.2005, 153.5751, 153.9496, 154.3240, 154.6982, 155.0724, 155.4464, 155.8203, 156.1941,
                  156.5678, 156.9414, 157.3149, 157.6882, 158.0614, 158.4345, 158.8075, 159.1804, 159.5531, 159.9258,
                  160.2983, 160.6707, 161.0430, 161.4152, 161.7872, 162.1592, 162.5310, 162.9027, 163.2743, 163.6458,
                  164.0172, 164.3884, 164.7596, 165.1306, 165.5015, 165.8723, 166.2429, 166.6135, 166.9839, 167.3542,
                  167.7245, 168.0945, 168.4645, 168.8344, 169.2041, 169.5737, 169.9432, 170.3126, 170.6819, 171.0511,
                  171.4201, 171.7890, 172.1579, 172.5266, 172.8951, 173.2636, 173.6319, 174.0002, 174.3683, 174.7363,
                  175.1042, 175.4719, 175.8396, 176.2071, 176.5746, 176.9419, 177.3090, 177.6761, 178.0431, 178.4099,
                  178.7766, 179.1432, 179.5097, 179.8761, 180.2424, 180.6085, 180.9745, 181.3405, 181.7063, 182.0719,
                  182.4375, 182.8029, 183.1683, 183.5335, 183.8986, 184.2636, 184.6284, 184.9932, 185.3578, 185.7223,
                  186.0867, 186.4510, 186.8152, 187.1793, 187.5432, 187.9070, 188.2707, 188.6343, 188.9978, 189.3611,
                  189.7244, 190.0875, 190.4505, 190.8134, 191.1762, 191.5389, 191.9014, 192.2638, 192.6262, 192.9884,
                  193.3504, 193.7124, 197.3257, 196.9649, 196.6040, 196.2429, 195.8818, 195.5205, 195.1591, 194.7976,
                  194.4360, 194.0743, 197.3257, 196.9649, 196.6040, 196.2429, 195.8818, 195.5205, 195.1591, 194.7976,
                  194.4360, 194.0743, 194.0743, 194.4360, 194.7976, 195.1591, 195.5205, 195.8818, 196.2429, 196.6040,
                  196.9649, 197.3257, 197.6864, 198.0469, 198.4074, 198.7677, 199.1280, 199.4881, 199.8481, 200.2079,
                  200.5677, 200.9274, 201.2869, 201.6463, 202.0056, 202.3648, 202.7238, 203.0828, 203.4416, 203.8003,
                  204.1589, 204.5174, 204.8758, 205.2340, 205.5922, 205.9502, 206.3081, 206.6659, 207.0236, 207.3811,
                  207.7386, 208.0959, 208.4531, 208.8102, 209.1672, 209.5240, 209.8808, 210.2374, 210.5939, 210.9503,
                  211.3066, 211.6628, 212.0188, 212.3747, 212.7305, 213.0862, 213.4418, 213.7973, 214.1527, 214.5079,
                  214.8630, 215.2180, 215.5729, 215.9277, 216.2823, 216.6369, 216.9913, 217.3456, 217.6998, 218.0539,
                  218.4078, 218.7617, 219.1154, 219.4690, 219.8225, 220.1759, 220.5291, 220.8823, 221.2353, 221.5882,
                  221.9410, 222.2937, 222.6463, 222.9987, 223.3511, 223.7033, 224.0554, 224.4074, 224.7592, 225.1110,
                  225.4626, 225.8142, 226.1656, 226.5169, 226.8680, 227.2191, 227.5700, 227.9209, 228.2716, 228.6222,
                  228.9726, 229.3230, 229.6733, 229.6733, 230.3734, 230.7233, 231.0731, 231.4227, 231.7723, 232.1217,
                  232.4710, 232.8202, 233.1693, 233.5183, 233.8672, 234.2159, 234.5645, 234.9130, 235.2614, 235.6097,
                  235.9578, 236.3059, 236.6538, 237.0016, 237.3493, 237.6969, 238.0443, 238.3917, 238.7389, 239.0860,
                  239.4330, 239.7799, 240.1267, 240.4733, 240.8199, 241.1663, 241.5126, 241.8588, 242.2048, 242.5508,
                  242.8966, 243.2423, 243.5879, 243.9334, 244.2788, 244.6241, 244.9692, 245.3142, 245.6591, 246.0039,
                  246.3486, 246.6932, 247.0376, 247.3819, 247.7261, 248.0702, 248.4142, 248.7581, 249.1018, 249.4455,
                  249.7890, 250.1324, 250.4757, 250.8188, 251.1619, 251.5048, 251.8476, 252.1903, 252.5329, 252.8754,
                  253.2177, 253.5600, 253.9021, 254.2441, 254.5860, 254.9278, 255.2694, 255.6110, 255.9524, 256.2937,
                  256.6349, 256.9760, 257.3170, 257.6578, 257.9985, 258.3392, 258.6797, 259.0200, 259.3603, 259.7005,
                  260.0405, 260.3804, 260.7202, 261.0599, 261.3995, 261.7389, 262.0783, 262.4175, 262.7566, 263.0956,
                  263.4344, 263.7732, 264.1119, 264.4504, 264.7888, 265.1271, 265.4653, 265.8033, 266.1413, 266.4791,
                  266.8168, 267.1544, 267.4919, 267.8293, 268.1665, 268.5036, 268.8407, 269.1776, 269.5143, 269.8510,
                  270.1876, 270.5240, 270.8603, 271.1965, 271.5326, 271.8686, 272.2044, 272.5402, 272.8758, 273.2113,
                  273.5467, 273.8820, 274.2172, 274.5522, 274.8871, 275.2219, 275.5566, 275.8912, 276.2257, 276.5600,
                  276.8943, 277.2284, 277.5624, 277.8963, 278.2300, 278.5637, 278.8972, 279.2306, 279.5639, 279.8971,
                  280.2302, 280.5632, 280.8960, 281.2287, 281.5613, 281.8938, 282.2262, 282.5585, 282.8906, 283.2226,
                  283.5545, 283.8863, 284.2180, 284.5496, 284.8810, 285.2124, 285.5436, 285.8747, 286.2057, 286.5365,
                  286.8673, 287.1979, 287.5284, 287.8588, 288.1891, 288.5193, 288.8493, 289.1793, 289.5091, 289.8388,
                  290.1684, 290.4979, 293.7862, 293.4579, 293.1295, 292.8010, 292.4723, 292.1435, 291.8146, 291.4856,
                  291.1565, 290.8272, 290.8272, 291.1565, 291.4856, 291.8146, 292.1435, 292.4723, 292.8010, 293.1295,
                  293.4579, 293.7862]

    @classmethod
    def get_temperature_from_resistance(cls, rtd_resistance: float) -> int:
        """Convert RTD resistance value to temperature"""
        if not isinstance(rtd_resistance, (int, float)):
            logger.error(f"Invalid RTD resistance type: {type(rtd_resistance)}")
            raise ValueError("RTD resistance must be a number")
        
        if rtd_resistance < 0:
            logger.error(f"Negative RTD resistance: {rtd_resistance}")
            raise ValueError("RTD resistance cannot be negative")
        
        if not cls.rtd_values:
            logger.error("RTD values table is empty")
            raise ValueError("RTD values table not initialized")
        
        try:
            index = min(range(len(cls.rtd_values)), 
                       key=lambda i: abs(cls.rtd_values[i] - rtd_resistance))
            nearest_temp = index - 200
            logger.info(f"RTD resistance {rtd_resistance} -> temperature {nearest_temp}")
            return nearest_temp
        except Exception as e:
            logger.error(f"Error converting RTD resistance to temperature: {e}")
            raise ValueError(f"Failed to convert RTD resistance: {e}")


class SerialPortManager:
    """Manages serial port operations"""
    
    def __init__(self):
        self.ser: Optional[serial.Serial] = None
        self.is_open = False
    
    def get_available_ports(self) -> List[str]:
        """Get list of available serial ports"""
        try:
            ports = [f"{p.device} - {p.description}" for p in serial.tools.list_ports.comports()]
            if not ports:
                logger.warning("No serial ports available")
                return []
            logger.info(f"Found {len(ports)} available ports")
            return ports
        except Exception as e:
            logger.error(f"Error getting available ports: {e}")
            return []
    
    def open_port(self, port_str: str, baudrate: int = 115200) -> Tuple[bool, str]:
        """Open serial port"""
        if not port_str:
            error_msg = "Port string is empty"
            logger.error(error_msg)
            return False, error_msg
        
        try:
            parts = port_str.split(" - ")
            port = parts[0].strip() if parts else None
            
            if not port:
                error_msg = "Invalid port format"
                logger.error(error_msg)
                return False, error_msg
            
            self.ser = serial.Serial(port, baudrate, timeout=1)
            self.is_open = True
            success_msg = f"Successfully opened {port}"
            logger.info(success_msg)
            return True, success_msg
        
        except serial.SerialException as e:
            error_msg = f"Serial error: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error opening port: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def close_port(self) -> Tuple[bool, str]:
        """Close serial port"""
        try:
            if self.ser and self.is_open:
                self.ser.close()
                self.is_open = False
                success_msg = "Port closed successfully"
                logger.info(success_msg)
                return True, success_msg
            else:
                error_msg = "Port is not open"
                logger.warning(error_msg)
                return False, error_msg
        except Exception as e:
            error_msg = f"Error closing port: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def read_byte(self) -> Optional[bytes]:
        """Read single byte from serial port"""
        try:
            if self.ser and self.is_open:
                data = self.ser.read(1)
                return data if data else None
            return None
        except serial.SerialException as e:
            logger.error(f"Serial read error: {e}")
            self.is_open = False
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading data: {e}")
            return None


class PacketProcessor:
    """Processes serial packets from sensor"""
    
    PACKET_LENGTH = 18
    ESCAPE_BYTE = b"\b"
    FRAME_END = b"\n"
    FRAME_START = b"\r"
    
    def __init__(self):
        self.escape = False
        self.packet: List[int] = []
    
    def process_byte(self, data: bytes) -> Optional[List[int]]:
        """Process incoming byte and return complete packet if available"""
        if not data or len(data) != 1:
            logger.warning(f"Invalid data received: {data}")
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
                    logger.warning(f"Incomplete packet received: {len(self.packet)} bytes")
                    self.packet = []
                    return None
            
            self.packet.append(byte_val)
        else:
            self.packet.append(byte_val)
            self.escape = False
        
        return None
    
    def reset(self):
        """Reset packet parser"""
        self.packet = []
        self.escape = False


class SensorDataParser:
    """Parses packet data to extract sensor values"""
    
    @staticmethod
    def parse_packet(packet: List[int]) -> Optional[SensorData]:
        """Parse packet and extract sensor data"""
        if not packet or len(packet) != 18:
            logger.error(f"Invalid packet length: {len(packet) if packet else 0}")
            raise ValueError(SensorErrorType.INVALID_PACKET_LENGTH.value)
        
        try:
            temp = packet[4]
            temp = (temp << 8) | packet[3]
            temp = (temp << 8) | packet[2]
            temp = (temp << 8) | packet[1]
            temp = temp / 10000.0
            
            if temp < -100 or temp > 100:
                logger.warning(f"Temperature out of reasonable range: {temp}")
            
            device_id = f"{packet[7]} {packet[8]} {packet[9]} {packet[10]}"
            
            rtd = packet[12]
            rtd = (rtd << 8) | packet[11]
            rtd_resistance = (rtd * 400) / (2**15)
            
            if rtd_resistance < 0:
                logger.error(f"Negative RTD resistance: {rtd_resistance}")
                raise ValueError("RTD resistance cannot be negative")
            
            try:
                rtd_temperature = RTDTemperatureTable.get_temperature_from_resistance(rtd_resistance)
            except ValueError as e:
                logger.error(f"Failed to convert RTD: {e}")
                rtd_temperature = 0
            
            thermo = packet[14]
            thermo = (thermo << 8) | packet[13]
            
            battery_voltage = ((packet[16] << 8) | packet[15]) / 1000.0
            
            if battery_voltage < 0 or battery_voltage > 10:
                logger.warning(f"Battery voltage out of range: {battery_voltage}")
            
            sensor_data = SensorData(
                temperature=temp,
                device_id=device_id,
                rtd_resistance=rtd_resistance,
                rtd_temperature=rtd_temperature,
                thermocouple=thermo,
                battery_voltage=battery_voltage,
                raw_packet=packet
            )
            
            if not sensor_data.is_valid():
                logger.error("Parsed sensor data validation failed")
                raise ValueError("Invalid sensor data")
            
            logger.info(f"Successfully parsed packet: temp={temp}, rtd={rtd_resistance:.3f}, battery={battery_voltage}V")
            return sensor_data
        
        except (IndexError, struct.error, ValueError) as e:
            logger.error(f"Error parsing packet: {e}")
            raise ValueError(f"Packet parsing error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing packet: {e}")
            raise ValueError(f"Unexpected parsing error: {e}")


class SensorGUI(tk.Tk):
    """GUI for wireless sensor data logger with modern ACUCAST-style interface"""
    
    def __init__(self):
        super().__init__()
        self.title("Wireless Sensor Data Logger - ACUCAST")
        self.state('zoomed')
        self.minsize(1024, 600)
        self.configure(bg="#f0f0f0")
        
        self.port_manager = SerialPortManager()
        self.packet_processor = PacketProcessor()
        self.data_parser = SensorDataParser()
        
        self.current_temp = tk.StringVar(value="--")
        self.device_id_val = tk.StringVar(value="NOT PAIRED")
        self.rtd_temp = tk.StringVar(value="--")
        self.thermo_val = tk.StringVar(value="--")
        self.battery_val = tk.StringVar(value="--")
        self.status_msg = tk.StringVar(value="Ready")
        self.is_reading = False
        self.is_paired = tk.BooleanVar(value=False)
        
        self.container = tk.Frame(self, bg="#f0f0f0")
        self.container.pack(fill="both", expand=True)
        
        self.frames = {}
        for F in (DashboardFrame, SettingsFrame):
            frame = F(parent=self.container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        
        self.show_frame("DashboardFrame")
    
    def show_frame(self, name):
        """Show specified frame"""
        frame = self.frames[name]
        frame.tkraise()


class DashboardFrame(tk.Frame):
    """Main dashboard display"""
    
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#ffffff")
        self.controller = controller
        
        # Header
        header = tk.Frame(self, bg="#e6e6e6", height=100)
        header.pack(fill="x", pady=0)
        
        info_frame = tk.Frame(header, bg="#e6e6e6")
        info_frame.pack(side="left", fill="y", padx=20, pady=10)
        tk.Label(info_frame, text="WIRELESS SENSOR LOGGER", fg="#000000", bg="#e6e6e6", font=("Arial", 18, "bold"), anchor="w").pack(fill="x")
        conn_frame = tk.Frame(info_frame, bg="#e6e6e6")
        conn_frame.pack(fill="x", pady=(5, 0))
        tk.Label(conn_frame, text="DEVICE:", fg="#666666", bg="#e6e6e6", font=("Arial", 10)).pack(side="left")
        tk.Label(conn_frame, textvariable=controller.device_id_val, fg="#333333", bg="#e6e6e6", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        
        stat_frame = tk.Frame(header, bg="#e6e6e6")
        stat_frame.pack(side="right", padx=20, pady=10)
        tk.Label(stat_frame, textvariable=controller.battery_val, fg="#333333", bg="#e6e6e6", font=("Arial", 20, "bold")).pack(anchor="e")
        
        time_frame = tk.Frame(header, bg="#e6e6e6")
        time_frame.pack(side="right", padx=30, fill="y")
        self.lbl_time = tk.Label(time_frame, text="00:00:00", fg="#333333", bg="#e6e6e6", font=("Arial", 14, "bold"))
        self.lbl_time.pack(anchor="center")
        self.lbl_date = tk.Label(time_frame, text="DD-MMM-YYYY", fg="#666666", bg="#e6e6e6", font=("Arial", 10))
        self.lbl_date.pack(anchor="center")
        self.update_clock()
        
        self.main_container = tk.Frame(self, bg="#ffffff")
        self.main_container.pack(expand=True, fill="both")
        
        tk.Label(self.main_container, text="MELT TEMPERATURE", fg="#333333", bg="#ffffff", font=("Arial", 22)).pack(pady=(60, 10))
        tk.Label(self.main_container, textvariable=controller.current_temp, bg="#ffffff", fg="#d40000", font=("Arial", 120, "bold")).pack()
        tk.Label(self.main_container, text="°C", fg="#333333", bg="#ffffff", font=("Arial", 40)).pack(pady=(0, 30))
        
        sensor_frame = tk.Frame(self.main_container, bg="#ffffff")
        sensor_frame.pack(pady=20, fill="x")
        
        tk.Label(sensor_frame, text="RTD (Temp):", font=("Arial", 14), anchor="e", fg="#333").pack(side="left", padx=20)
        tk.Label(sensor_frame, textvariable=controller.rtd_temp, font=("Arial", 28, "bold"), fg="#5cb85c").pack(side="left", padx=10)
        
        tk.Label(sensor_frame, text="Thermocouple:", font=("Arial", 14), anchor="e", fg="#333").pack(side="left", padx=20)
        tk.Label(sensor_frame, textvariable=controller.thermo_val, font=("Arial", 28, "bold"), fg="#0275d8").pack(side="left", padx=10)
        
        footer = tk.Frame(self, bg="#e6e6e6", height=100)
        footer.pack(fill="x", side="bottom")
        
        port_frame = tk.Frame(footer, bg="#e6e6e6")
        port_frame.pack(side="left", padx=20, pady=15)
        tk.Label(port_frame, text="Port:", fg="#333333", bg="#e6e6e6", font=("Arial", 11)).pack(side="left", padx=5)
        self.combo = ttk.Combobox(port_frame, width=20, state="readonly", font=("Arial", 10))
        self.combo.pack(side="left", padx=5)
        
        btn_frame = tk.Frame(footer, bg="#e6e6e6")
        btn_frame.pack(side="left", padx=10, pady=15)
        
        tk.Button(btn_frame, text="Refresh", command=self.update_ports, font=("Arial", 10), width=12, bg="#cccccc").pack(side="left", padx=3)
        tk.Button(btn_frame, text="Connect", command=self._open_port, font=("Arial", 10), width=12, bg="#0066cc", fg="white").pack(side="left", padx=3)
        tk.Button(btn_frame, text="Disconnect", command=self._close_port, font=("Arial", 10), width=12, bg="#cc0000", fg="white").pack(side="left", padx=3)
        
        tk.Button(footer, text="⚙ CONFIGURATION", bg="#666666", fg="white", font=("Arial", 12, "bold"), width=20, command=self.check_password).pack(side="right", padx=20, pady=15)
        
        self.status_label = tk.Label(self.main_container, textvariable=controller.status_msg, fg="#006600", font=("Arial", 10))
        self.status_label.pack(pady=5)
        
        self.update_ports()
    
    def update_clock(self):
        """Update time and date"""
        now = datetime.now()
        self.lbl_time.config(text=now.strftime("%H:%M:%S"))
        self.lbl_date.config(text=now.strftime("%d-%b-%Y"))
        self.after(1000, self.update_clock)
    
    def update_ports(self):
        """Update available ports"""
        ports = self.controller.port_manager.get_available_ports()
        self.combo['values'] = ports if ports else []
        if ports:
            self.combo.current(0)
    
    def _open_port(self):
        """Open port"""
        sel = self.combo.get()
        if not sel:
            messagebox.showerror("Error", "Select a port")
            return
        
        success, msg = self.controller.port_manager.open_port(sel)
        if success:
            self.controller.status_msg.set(f"Connected: {sel}")
            self.controller.is_paired.set(True)
            self.controller.is_reading = True
            self._read_data()
        else:
            messagebox.showerror("Error", msg)
    
    def _close_port(self):
        """Close port"""
        self.controller.port_manager.close_port()
        self.controller.is_reading = False
        self.controller.is_paired.set(False)
        self.controller.status_msg.set("Disconnected")
        self.controller.packet_processor.reset()
    
    def _read_data(self):
        """Read from serial port"""
        if not self.controller.is_reading or not self.controller.port_manager.is_open:
            return
        
        try:
            data = self.controller.port_manager.read_byte()
            if data:
                packet = self.controller.packet_processor.process_byte(data)
                if packet:
                    self._process_data(packet)
        except Exception as e:
            logger.error(f"Read error: {e}")
        
        if self.controller.is_reading:
            self.after(1, self._read_data)
    
    def _process_data(self, packet):
        """Process sensor data"""
        try:
            data = self.controller.data_parser.parse_packet(packet)
            self.controller.current_temp.set(f"{data.temperature:.1f}")
            self.controller.device_id_val.set(data.device_id)
            self.controller.rtd_temp.set(str(data.rtd_temperature))
            self.controller.thermo_val.set(str(data.thermocouple))
            self.controller.battery_val.set(f"{data.battery_voltage:.2f}V")
        except ValueError as e:
            logger.error(f"Parse error: {e}")
    
    def check_password(self):
        """Check password"""
        password = simpledialog.askstring("Security", "Enter Password:", show='*')
        if password == "1111":
            self.controller.show_frame("SettingsFrame")
        elif password is not None:
            messagebox.showerror("Access Denied", "Wrong Password")


class SettingsFrame(tk.Frame):
    """Settings frame"""
    
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f0f0f0")
        self.controller = controller
        
        tk.Label(self, text="CONFIGURATION", fg="#333333", bg="#f0f0f0", font=("Arial", 28, "bold")).pack(pady=10)
        
        style = ttk.Style()
        style.configure("TNotebook.Tab", font=("Arial", 11), padding=[15, 8])
        
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=30, pady=10)
        
        tab1 = tk.Frame(nb, bg="#f0f0f0")
        nb.add(tab1, text="Device Info")
        
        tk.Label(tab1, text="Paired Device:", font=("Arial", 12), bg="#f0f0f0").pack(anchor="w", padx=20, pady=10)
        tk.Label(tab1, textvariable=controller.device_id_val, font=("Arial", 14, "bold"), fg="#0055aa", bg="#f0f0f0").pack(anchor="w", padx=40, pady=5)
        
        tab2 = tk.Frame(nb, bg="#f0f0f0")
        nb.add(tab2, text="Sensor Data")
        
        tk.Label(tab2, text="Temperature:", font=("Arial", 12), bg="#f0f0f0").pack(anchor="w", padx=20, pady=10)
        tk.Label(tab2, textvariable=controller.current_temp, font=("Arial", 14, "bold"), fg="#d40000", bg="#f0f0f0").pack(anchor="w", padx=40, pady=5)
        
        tk.Label(tab2, text="Battery:", font=("Arial", 12), bg="#f0f0f0").pack(anchor="w", padx=20, pady=10)
        tk.Label(tab2, textvariable=controller.battery_val, font=("Arial", 14, "bold"), fg="#333333", bg="#f0f0f0").pack(anchor="w", padx=40, pady=5)
        
        btn_frame = tk.Frame(self, bg="#f0f0f0")
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="✔ EXIT", bg="#4caf50", fg="white", font=("Arial", 12, "bold"), padx=30, pady=10, command=self.exit_settings).pack()
    
    def exit_settings(self):
        """Exit settings"""
        self.controller.show_frame("DashboardFrame")


def main():
    """Main entry point"""
    app = SensorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
