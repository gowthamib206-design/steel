"""
Wireless Sensor Data Logger Application
Handles serial communication with wireless sensors and displays temperature/RTD data via GUI
Modern UI based on ACUCAST reference
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.filedialog import Open
from PIL import Image, ImageTk
import serial
import serial.tools.list_ports
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import struct
from datetime import datetime
import time
import re
import sys
import os
import csv
import sqlite3
from collections import deque
import threading
import calendar

# plotting support (similar to acucast demo)
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from PIL import Image, ImageTk

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


class ThermocoupleTable:
    
       
    @classmethod
    def get_temperature_from_voltage(cls, voltage: float) -> float:
        """Convert thermocouple voltage to temperature"""
        if not isinstance(voltage, (int, float)):
            logger.error(f"Invalid thermocouple voltage type: {type(voltage)}")
            raise ValueError("Thermocouple voltage must be a number")
        
        if not cls.thermocouple_values:
            logger.error("Thermocouple values table is empty")
            raise ValueError("Thermocouple values table not initialized")
        
        try:
            index = min(range(len(cls.thermocouple_values)), 
                       key=lambda i: abs(cls.thermocouple_values[i] - voltage))
            temperature = index - 50
            logger.info(f"Thermocouple voltage {voltage} -> temperature {temperature}")
            return temperature
        except Exception as e:
            logger.error(f"Error converting thermocouple voltage to temperature: {e}")
            raise ValueError(f"Failed to convert thermocouple voltage: {e}")

    @classmethod
    def get_voltage_from_temperature(cls, temperature: int) -> float:
        """Convert RTD temperature to thermocouple voltage (mV) using polynomial.
        
        This is used for RTD compensation: we calculate the thermocouple voltage
        corresponding to the RTD temperature using the polynomial equation.
        Returns voltage in millivolts (mV).
        """
        if not isinstance(temperature, (int, float)):
            logger.error(f"Invalid temperature type: {type(temperature)}")
            raise ValueError("Temperature must be a number")
        
        try:
            # Use polynomial to get voltage in µV
            voltage_uV = temperature_C_to_voltage_uV(temperature)
            
            # Convert from µV to mV
            voltage_mV = voltage_uV / 1000.0
            
            logger.info(f"RTD temperature {temperature}°C -> thermocouple voltage {voltage_mV} mV ({voltage_uV} µV)")
            return voltage_mV
        except Exception as e:
            logger.error(f"Error converting temperature to thermocouple voltage: {e}")
            raise ValueError(f"Failed to convert temperature: {e}")

# =========================
# Thermocouple calculation
# =========================



# LOW range coefficients (291 µV – 2431 µV)
COEFFS_LOW = [ 9.8423321e1,6.9971500e-1,-8.4765304e-4,1.0052644e-6,-8.3345952e-10,
              4.5508542e-13,-1.5523037e-16,2.9886750e-20,-2.4742860e-24,
]

# HIGH range coefficients (2431 µV – 13820 µV)
COEFFS_HIGH = [2.1315071e2,2.8510504e-1,-5.2742887e-5,9.9160804e-9,-1.2965303e-12,
               1.1195870e-16,-6.0625199e-21, 1.8661696e-25,-2.4878585e-30,
]

RANGE_LOW_UV = (291.0, 2431.0)
RANGE_HIGH_UV = (2431.0, 13820.0)

def raw_to_voltage_uV(raw_value):
    """
    Convert raw thermocouple ADC value to voltage in µV.
    Formula: v = (raw * 1250000) / (32 * 2**16)
    """
    return (raw_value * 1250000.0) / (32.0 * (2**16))

def voltage_uV_to_temperature_C(uV):
    """
    Convert voltage (µV) to temperature (°C) using polynomial directly.
    """
    # choose coefficients based on range
    if RANGE_LOW_UV[0] <= uV <= RANGE_LOW_UV[1]:
        coeffs = COEFFS_LOW
    elif RANGE_HIGH_UV[0] < uV <= RANGE_HIGH_UV[1]:
        coeffs = COEFFS_HIGH
    else:
        coeffs = COEFFS_LOW if uV < RANGE_LOW_UV[0] else COEFFS_HIGH

    # polynomial expects millivolts
    v = uV 

   
    terms = []
    for i in range(len(coeffs)):
     c = coeffs[i]
     t = c * (v ** i)
     terms.append(t)
     

# sum all terms
    temp_C = sum(terms)
    logger.debug(f"Thermocouple voltage {uV}µV converted to temperature {temp_C}°C")


    return temp_C


# Type B Thermocouple: Temperature to Voltage conversion coefficients
# Reference: ITS-90 polynomial coefficients
# Equation: E = Σ c_i(t_90)^i, where E is in microvolts and t_90 is in °C

# Temperature range: 0 to 630.615°C
COEFFS_TEMP_TO_UV_LOW = [
    0.0,                    # c0
    -2.465081834600e-1,      # c1: -2.465 081 834 6 × 10^1
    5.904042111700e-3,       # c2: 5.904 042 111 7 × 10^3
    -1.325793163600e-6,     # c3: -1.325 793 163 6 × 10^-6
    1.566829190100e-9,      # c4: 1.566 829 190 1 × 10^-9
    -1.694452924000e-12,    # c5: -1.694 452 924 0 × 10^-12
    6.229034709400e-16,     # c6: 6.229 034 709 4 × 10^-16
]

# Temperature range: 630.615°C to 1,820°C
COEFFS_TEMP_TO_UV_HIGH = [
    -3.8938168621e3,           # c0
    2.8571747470e1,            # c1
    -8.4885104785e-3,          # c2
    1.5785280164e-6,           # c3
    -1.6835344864e-10,         # c4
    1.1109794013e-14,          # c5
    -4.4515431033e-18,         # c6
    9.8975640821e-23,          # c7
    -9.3791330289e-28,         # c8
    
]

RANGE_TEMP_LOW_C = (0.0, 630.615)
RANGE_TEMP_HIGH_C = (630.615, 1820.0)


def temperature_C_to_voltage_uV(temperature_C: float) -> float:
   
    # Choose coefficients based on temperature range
    if RANGE_TEMP_LOW_C[0] <= temperature_C <= RANGE_TEMP_LOW_C[1]:
        coeffs = COEFFS_TEMP_TO_UV_LOW
    elif RANGE_TEMP_HIGH_C[0] < temperature_C <= RANGE_TEMP_HIGH_C[1]:
        coeffs = COEFFS_TEMP_TO_UV_HIGH
    else:
        # Extrapolate using nearest range
        coeffs = COEFFS_TEMP_TO_UV_LOW if temperature_C < RANGE_TEMP_LOW_C[0] else COEFFS_TEMP_TO_UV_HIGH
        logger.warning(f"Temperature {temperature_C}°C outside calibrated range, using extrapolation")
    
    # Calculate polynomial: E = Σ c_i(t_90)^i
    terms = []
    for i in range(len(coeffs)):
        c = coeffs[i]
        t = c * (temperature_C ** i)
        terms.append(t)
    
    # Sum all terms to get voltage in µV
    voltage_uV = sum(terms)
    logger.debug(f"Temperature {temperature_C}°C converted to thermocouple voltage {voltage_uV}µV")
    
    return voltage_uV


    """Manages serial port operations"""
def apply_rtd_compensation(rtd_temperature: int, thermo_uV: float) -> float:
    """Apply RTD compensation to thermocouple voltage.
    
    Algorithm:
    1. Calculate RTD temperature equivalent voltage using polynomial
    2. Add this voltage to the raw thermocouple voltage (in µV)
    3. Convert the combined voltage back to temperature using voltage_uV_to_temperature_C
    
    Args:
        rtd_temperature: RTD temperature in °C
        thermo_uV: Raw thermocouple voltage in µV
    
    Returns:
        Compensated thermocouple temperature in °C
    """
    try:
        # Step 1: Calculate thermocouple voltage corresponding to RTD temperature using polynomial
        rtd_voltage_uV = temperature_C_to_voltage_uV(rtd_temperature)
        
        # Step 2: Add RTD voltage to raw thermocouple voltage
        combined_voltage_uV = thermo_uV + rtd_voltage_uV
        
        # Step 3: Convert combined voltage to temperature
        compensated_temp = voltage_uV_to_temperature_C(combined_voltage_uV)
        
        logger.info(f"RTD Compensation: RTD_temp={rtd_temperature}°C, RTD_voltage={rtd_voltage_uV}µV, "
                   f"TC_raw={thermo_uV}µV, Combined={combined_voltage_uV}µV, Result={compensated_temp}°C")
        
        return compensated_temp
    except Exception as e:
        logger.error(f"Error applying RTD compensation: {e}")
        # Return original thermocouple temperature if compensation fails
        return voltage_uV_to_temperature_C(thermo_uV)

class SerialPortManager:
    """Manages serial port operations"""
    
    def __init__(self):
         self.serial = None          # ✅ ADD THIS LINE
         self.is_open = False
         self.current_port = None 
    
    def get_available_ports(self, exclude_connected=False) -> List[str]:
       """Get list of available serial ports
    
       Args:
          exclude_connected: If True, exclude the currently connected port
    """
       try:
           all_ports = [f"{p.device} - {p.description}" for p in serial.tools.list_ports.comports()]
           if not all_ports:
             logger.warning("No serial ports available")
             return []
           if exclude_connected and self.current_port:
            # Extract just the device name from current_port (e.g., "COM3" from "COM3 - USB...")
              current_device = self.current_port.split(" - ")[0].strip() if " - " in self.current_port else self.current_port
            
            # Filter out the connected port by matching the device name
              filtered_ports = [p for p in all_ports if not p.startswith(current_device)]
              logger.info(f"Found {len(all_ports)} total ports, showing {len(filtered_ports)} available (excluded: {current_device})")
              return filtered_ports
        
           logger.info(f"Found {len(all_ports)} available ports")
           return all_ports
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
        
          self.serial = serial.Serial(port, baudrate, timeout=1)
          self.is_open = True
        # Store FULL port string with description for proper exclusion later
          self.current_port = port_str  # Changed: store the full string like "COM3 - USB Serial Port"
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
            if self.serial and self.serial.is_open:
                self.serial.close()
                self.serial = None
                self.is_open = False
                self.current_port = None  # Clear the tracked port
                return True, "Port closed successfully"
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
            if self.serial and self.is_open:
                data = self.serial.read(1)
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
    
    PACKET_LENGTH = 16
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
    def parse_packet(packet: List[int], enable_rtd_compensation: bool = False) -> Optional[SensorData]:
        
        if not packet or len(packet) != 16:
            logger.error(f"Invalid packet length: {len(packet) if packet else 0}")
            raise ValueError(SensorErrorType.INVALID_PACKET_LENGTH.value)
        
        try:
            # Parse temperature from bytes 1-4 (4 bytes, big-endian)
            temp = packet[3]
            temp = (temp << 8) | packet[2]
            temp = (temp << 8) | packet[1]
            temp = (temp << 8) | packet[0]
            temp = temp / 10000.0
            
            if temp < -100 or temp > 100:
                logger.warning(f"Temperature out of reasonable range: {temp}")

            # Parse RSSI from byte 4
            rssi = packet[4]
            rssi = rssi - 128

            # Parse device ID from bytes 7-9 (3 bytes)
            device_id = f"{packet[6]:02x} {packet[7]:02x} {packet[8]:02x} {packet[9]:02x}"
            
            # Parse RTD from bytes 10-11 (2 bytes, big-endian)
            rtd = packet[11]
            rtd = (rtd << 8) | packet[10]
            rtd_resistance = (rtd * 400) / (2**15)
            
            if rtd_resistance < 0:
                logger.error(f"Negative RTD resistance: {rtd_resistance}")
                raise ValueError("RTD resistance cannot be negative")
            
            rtd_temperature = None
            try:
                rtd_temperature = RTDTemperatureTable.get_temperature_from_resistance(rtd_resistance)
            except ValueError as e:
                logger.error(f"Failed to convert RTD: {e}")
                rtd_temperature = None
            
            # Parse thermocouple from bytes 12-13 (2 bytes, big-endian)
            thermo_raw = packet[13]
            thermo_raw = (thermo_raw << 8) | packet[12] 
            thermo_uV = raw_to_voltage_uV(thermo_raw)
            
            # Apply RTD compensation if enabled and RTD data is valid
            if enable_rtd_compensation and rtd_temperature is not None:
                try:
                    thermo_temperature_C = apply_rtd_compensation(rtd_temperature, thermo_uV)
                    logger.debug(f"RTD compensation applied: RTD={rtd_temperature}°C, Result={thermo_temperature_C}°C")
                except Exception as e:
                    logger.warning(f"RTD compensation failed: {e}, using raw thermocouple conversion")
                    thermo_temperature_C = voltage_uV_to_temperature_C(thermo_uV)
            else:
                thermo_temperature_C = voltage_uV_to_temperature_C(thermo_uV)
            
            #thermo_uV = (thermo_raw * 1250000.0) / (32.0 * (2 ** 16))
             # Convert µV -> temperature using provided coefficients
          


            # Parse battery voltage from bytes 14-15 (2 bytes, big-endian)
            battery_voltage = ((packet[15] << 8) | packet[14]) / 1000.0
            
            
            if battery_voltage < 0 or battery_voltage > 10:
                logger.warning(f"Battery voltage out of range: {battery_voltage}")

            print(f"raw thermo: {thermo_raw}, uV: {thermo_uV}, temp: {thermo_temperature_C},rtd temp: {rtd_temperature}, rtd resistance: {rtd_resistance}")
            
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
            
            if not sensor_data.is_valid():
                logger.error("Parsed sensor data validation failed")
                raise ValueError("Invalid sensor data")
            
            logger.debug(f"Successfully parsed packet: temp={temp}°C, rtd_temp={rtd_temperature}°C, "
                          f"tc_temp={thermo_temperature_C:.1f}°C, rtd={rtd_resistance:.3f}Ω, battery={battery_voltage}V")
            return sensor_data
        
        except (IndexError, struct.error, ValueError) as e:
            logger.error(f"Error parsing packet: {e}")
            raise ValueError(f"Packet parsing error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing packet: {e}")
            raise ValueError(f"Unexpected parsing error: {e}")


class CalendarPopup(tk.Toplevel):
    """A minimal calendar popup to choose a date (YYYY-MM-DD).

    Usage: CalendarPopup(parent, callback)
    callback will be called with the selected date string.
    """
    def __init__(self, parent, select_callback, year=None, month=None):
        super().__init__(parent)
        self.withdraw()
        self.transient(parent)
        self.title('Select Date')
        self.select_callback = select_callback
        self.resizable(False, False)

        now = datetime.now()
        self.year = year or now.year
        self.month = month or now.month

        self.body = tk.Frame(self)
        self.body.pack(padx=8, pady=8)

        nav = tk.Frame(self.body)
        nav.pack(fill='x')
        tk.Button(nav, text='<', width=3, command=self._prev_month).pack(side='left')
        self.title_lbl = tk.Label(nav, text='', width=20)
        self.title_lbl.pack(side='left', padx=6)
        tk.Button(nav, text='>', width=3, command=self._next_month).pack(side='right')

        self.cal_frame = tk.Frame(self.body)
        self.cal_frame.pack()

        self._build_calendar()
        self.update_idletasks()
        self.deiconify()

    def _build_calendar(self):
        for w in self.cal_frame.winfo_children():
            w.destroy()

        self.title_lbl.config(text=f"{calendar.month_name[self.month]} {self.year}")
        wkday_names = ['Mo','Tu','We','Th','Fr','Sa','Su']
        header = tk.Frame(self.cal_frame)
        header.grid(row=0, column=0)
        for c, name in enumerate(wkday_names):
            tk.Label(self.cal_frame, text=name, width=3).grid(row=0, column=c)

        month_mat = calendar.monthcalendar(self.year, self.month)
        for r, week in enumerate(month_mat, start=1):
            for c, day in enumerate(week):
                if day == 0:
                    tk.Label(self.cal_frame, text='', width=3).grid(row=r, column=c)
                else:
                    b = tk.Button(self.cal_frame, text=str(day), width=3,
                                  command=lambda d=day: self._select_day(d))
                    b.grid(row=r, column=c, padx=1, pady=1)

    def _select_day(self, day: int):
        dt = datetime(self.year, self.month, day)
        self.select_callback(dt.strftime('%Y-%m-%d'))
        self.destroy()

    def _prev_month(self):
        if self.month == 1:
            self.month = 12
            self.year -= 1
        else:
            self.month -= 1
        self._build_calendar()

    def _next_month(self):
        if self.month == 12:
            self.month = 1
            self.year += 1
        else:
            self.month += 1
        self._build_calendar()


class DateTimePopup(tk.Toplevel):
    """A calendar and time picker popup to choose a datetime (YYYY-MM-DD HH:MM:SS).

    Usage: DateTimePopup(parent, callback)
    callback will be called with the selected datetime string.
    """
    def __init__(self, parent, select_callback, year=None, month=None):
        super().__init__(parent)
        self.withdraw()
        self.transient(parent)
        self.title('Select Date and Time')
        self.select_callback = select_callback
        self.resizable(False, False)

        now = datetime.now()
        self.year = year or now.year
        self.month = month or now.month
        self.day = None
        self.hour = now.hour
        self.minute = now.minute
        self.second = now.second

        # Create StringVar variables for time inputs
        self.hour_var = tk.StringVar(value=str(self.hour).zfill(2))
        self.minute_var = tk.StringVar(value=str(self.minute).zfill(2))
        self.second_var = tk.StringVar(value=str(self.second).zfill(2))

        self.body = tk.Frame(self)
        self.body.pack(padx=8, pady=8)

        # Calendar section
        nav = tk.Frame(self.body)
        nav.pack(fill='x', pady=(0, 10))
        tk.Button(nav, text='<', width=3, command=self._prev_month).pack(side='left')
        self.title_lbl = tk.Label(nav, text='', width=20)
        self.title_lbl.pack(side='left', padx=6)
        tk.Button(nav, text='>', width=3, command=self._next_month).pack(side='right')

        self.cal_frame = tk.Frame(self.body)
        self.cal_frame.pack(pady=(0, 10))

        # Time section
        time_frame = tk.Frame(self.body)
        time_frame.pack(fill='x', pady=10)
        
        tk.Label(time_frame, text='Time:', font=('Arial', 10, 'bold')).pack(anchor='w')
        
        time_input_frame = tk.Frame(time_frame)
        time_input_frame.pack(fill='x', pady=(5, 0))
        
        tk.Label(time_input_frame, text='HH:').pack(side='left', padx=(5, 0))
        self.hour_spinbox = tk.Spinbox(time_input_frame, from_=0, to=23, width=3, textvariable=self.hour_var)
        self.hour_spinbox.pack(side='left', padx=(2, 10))
        
        tk.Label(time_input_frame, text='MM:').pack(side='left')
        self.minute_spinbox = tk.Spinbox(time_input_frame, from_=0, to=59, width=3, textvariable=self.minute_var)
        self.minute_spinbox.pack(side='left', padx=(2, 10))
        
        tk.Label(time_input_frame, text='SS').pack(side='left')
        self.second_spinbox = tk.Spinbox(time_input_frame, from_=0, to=59, width=3, textvariable=self.second_var)
        self.second_spinbox.pack(side='left', padx=(2, 0))
        
        # Buttons
        button_frame = tk.Frame(self.body)
        button_frame.pack(fill='x', pady=(10, 0))
        tk.Button(button_frame, text='OK', width=10, command=self._confirm).pack(side='left', padx=5)
        tk.Button(button_frame, text='Cancel', width=10, command=self.destroy).pack(side='left')

        self._build_calendar()
        self.update_idletasks()
        self.deiconify()

    def _build_calendar(self):
        for w in self.cal_frame.winfo_children():
            w.destroy()

        self.title_lbl.config(text=f"{calendar.month_name[self.month]} {self.year}")
        wkday_names = ['Mo','Tu','We','Th','Fr','Sa','Su']
        
        # Place day names directly in cal_frame
        for c, name in enumerate(wkday_names):
            tk.Label(self.cal_frame, text=name, width=3).grid(row=0, column=c, padx=1, pady=1)

        month_mat = calendar.monthcalendar(self.year, self.month)
        for r, week in enumerate(month_mat, start=1):
            for c, day in enumerate(week):
                if day == 0:
                    tk.Label(self.cal_frame, text='', width=3).grid(row=r, column=c, padx=1, pady=1)
                else:
                    style = {}
                    if day == self.day:
                        style['bg'] = '#4caf50'
                        style['fg'] = 'white'
                    b = tk.Button(self.cal_frame, text=str(day), width=3,
                                  command=lambda d=day: self._select_day(d), **style)
                    b.grid(row=r, column=c, padx=1, pady=1)

    def _select_day(self, day: int):
        self.day = day
        self._build_calendar()

    def _prev_month(self):
        if self.month == 1:
            self.month = 12
            self.year -= 1
        else:
            self.month -= 1
        self._build_calendar()

    def _next_month(self):
        if self.month == 12:
            self.month = 1
            self.year += 1
        else:
            self.month += 1
        self._build_calendar()

    def _confirm(self):
        if self.day is None:
            messagebox.showwarning('Select Date', 'Please select a date')
            return
        
        try:
            hour = int(self.hour_var.get())
            minute = int(self.minute_var.get())
            second = int(self.second_var.get())
            
            dt = datetime(self.year, self.month, self.day, hour, minute, second)
            self.select_callback(dt.strftime('%Y-%m-%d %H:%M:%S'))
            self.destroy()
        except ValueError:
            messagebox.showerror('Invalid Time', 'Please enter valid time values')



class SensorGUI(tk.Tk):
    """GUI for wireless sensor data logger with professional ACUCAST-style interface"""
    
    def __init__(self):
        super().__init__()
        self.title("WIRELESS SENSOR - MOLTEN METAL CONTINUOUS TEMPERATURE SYSTEM")
        # Make the window fullscreen by default and also start maximized
        try:
            self.attributes('-fullscreen', True)
        except Exception:
            pass
        self.state('zoomed')
        self.minsize(1024, 600)
        self.configure(bg="#f0f0f0")

        # Load logo image (optional)
        logo_path = None
        try:
            if getattr(sys, 'frozen', False):
                # Running in a bundle
                logo_path = os.path.join(sys._MEIPASS, 'arrdy-logo.png')
            else:
                logo_path = 'arrdy-logo.png'
            pil_image = Image.open(logo_path)
            self.logo_img = ImageTk.PhotoImage(pil_image)  # For icon
            try:
                self.iconphoto(False, self.logo_img)
            except Exception:
                # e.g. running in headless test environment
                pass

            # Resize for display (50x50)
            pil_image_resized = pil_image.resize((50, 50), Image.Resampling.LANCZOS)
            self.logo_img_small = ImageTk.PhotoImage(pil_image_resized)
        except Exception:
            # icon or file may not exist in unit test environment
            self.logo_img = None
            self.logo_img_small = None

        # Allow exiting fullscreen with Escape (handy for testing)
        self.bind('<Escape>', lambda e: self.attributes('-fullscreen', False))

        self.sel = tk.StringVar(value="")
        self.apply_rtd_compensation = tk.BooleanVar(value=True)  # Checkbox selected by default
        self.station_name = tk.StringVar(value="LADLE STATION 01")
        self.view_mode = tk.StringVar(value="Digital View")
        # when view mode changes update dashboard layout
        self.view_mode.trace_add('write', lambda *args: self.frames.get("DashboardFrame").refresh_layout() if "DashboardFrame" in self.frames else None)
        self.operator_name = tk.StringVar(value="")
        self.ip_address = tk.StringVar(value="")
        self.port_number = tk.StringVar(value="")
        self.location_name = tk.StringVar(value="")
        self.company_name = tk.StringVar(value="")
        self.units = tk.StringVar(value="°C")
        self.com_port = tk.StringVar()
        self.baud_rate = tk.StringVar(value="")
        self.mb_slave_id = tk.StringVar(value="")
        self.eth_ip = tk.StringVar(value="")
        self.eth_port = tk.StringVar()
        self.analog_low = tk.StringVar(value="0")
        self.analog_high = tk.StringVar(value="")
        self.prof_station = tk.StringVar(value="")
        self.raw_hex = tk.StringVar()
        self.bat_voltage = tk.StringVar()
        self.signal_strength = tk.StringVar()
        self.firmware_version = tk.StringVar()
        self.apply_rtd_compensation = tk.BooleanVar(value=False)
        
        # --- Database & logging setup ---
        self.init_db()
        
        # Graph/History data variables
        self.buffer_size = 20
        self.temp_data = deque([0] * self.buffer_size, maxlen=self.buffer_size)
        self.time_data = deque([0] * self.buffer_size, maxlen=self.buffer_size)
        self.history_display = deque(maxlen=30)
        self.x_counter = 0

        # Graph settings (used from settings tab)
        self.time_scale_str = tk.StringVar(value="1 Minute")
        # adjust buffer length when scale changes
        self.time_scale_str.trace_add('write', lambda *args: self.update_buffer_size())
        self.y_axis_mode = tk.StringVar(value="Autoscale")
        self.y_min = tk.DoubleVar(value=1500.0)
        self.y_max = tk.DoubleVar(value=1600.0)

         # Observable variables
        self.current_temp = tk.StringVar(value="--")
        self.device_id_val = tk.StringVar(value="NOT PAIRED")
        self.thermo_val = tk.StringVar(value="--")
        self.rtd_temp = tk.StringVar(value="--")
        self.battery_val = tk.StringVar(value="--")
        self.rssi_val = tk.StringVar(value="--")
        self.status_msg = tk.StringVar(value="Ready")
        self.is_reading = False
        self.is_paired = tk.BooleanVar(value=False)  
        self.transmitter_id_val = tk.StringVar(value="WAITING")
        self.com_port_val = tk.StringVar(value="NOT CONNECTED")

        
        self.port_manager = SerialPortManager()
        self.packet_processor = PacketProcessor()
        self.data_parser = SensorDataParser()


        self.container = tk.Frame(self, bg="#f0f0f0")
        self.container.pack(fill="both", expand=True)
        # Ensure grid-managed children inside the container expand to fill the window
        try:
            self.container.grid_rowconfigure(0, weight=1)
            self.container.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        
        self.frames = {}
        for F in (DashboardFrame, SettingsFrame):
            frame = F(parent=self.container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        
        self.show_frame("DashboardFrame")
    
    # --- database & history helpers copied from ACUCAST demo ---
    def init_db(self, db_path: str = "temperature_logs.db"):
        """Initialize SQLite database and create table if needed.

        Args:
            db_path: Path to the database file. Defaults to "temperature_logs.db".
                     Allows tests to pass ":memory:" or other locations.
        """
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Check if the old schema exists (no device_id column)
        try:
            self.cursor.execute("PRAGMA table_info(measurements)")
            cols = [row[1] for row in self.cursor.fetchall()]
            if cols and ('station_name' not in cols or 'rssi' not in cols):
                # Old schema detected, migrate by renaming old table and creating new one
                logger.info("Old measurements table schema detected. Migrating to new schema...")
                self.cursor.execute("ALTER TABLE measurements RENAME TO measurements_old")
                self.conn.commit()
        except sqlite3.OperationalError:
            # Table doesn't exist yet, that's fine
            pass

        # Create new schema table (will work whether table existed or not after migration)
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
                rssi INTEGER
            )
        """)
        self.conn.commit()
        logger.info("Database initialized with updated schema (station_name + rssi)")

    def log_to_db(self,
                  station_name: str,
                  device_id: str,
                  temp_raw: int,
                  rtd_raw: int,
                  thermo_raw: int,
                  batt_raw: int,
                  rssi: int):
        """Insert raw measurement values into the database.

        Args:
            device_id: human-readable 4-byte ID string
            station_name: Station name (e.g., "LADLE STATION 01")
            temp_raw: 32-bit integer representing temperature*10000
            rtd_raw: 16-bit raw ADC reading for RTD
            thermo_raw: 16-bit raw ADC reading for thermocouple
            batt_raw: 16-bit raw ADC reading for battery voltage
            rssi: Signal strength indicator
        """
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.cursor.execute(
                "INSERT INTO measurements (timestamp, device_id, station_name, temp_raw, rtd_raw, thermo_raw, batt_raw, rssi) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, device_id, station_name, temp_raw, rtd_raw, thermo_raw, batt_raw, rssi)
            )
            # commit every 10 records instead of every single one
            if not hasattr(self, '_commit_counter'):
                self._commit_counter = 0
            self._commit_counter += 1
            if self._commit_counter >= 10:
                self.conn.commit()
                self._commit_counter = 0
            logger.debug(f"Logged measurement: {station_name} | {device_id} | RSSI: {rssi}")
        except Exception as e:
            logger.error(f"Database error: {e}")

    def update_buffer_size(self):
        """Recalculate in-memory buffers when time scale changes"""
        scale_map = {"1 Minute": 60, "5 Minutes": 300, "15 Minutes": 900, "30 Minutes": 1800, "1 Hour": 3600}
        seconds = scale_map.get(self.time_scale_str.get(), 60)
        new_len = int(seconds / 3)
        if new_len != self.buffer_size:
            self.buffer_size = new_len
            self.temp_data = deque(self.temp_data, maxlen=self.buffer_size)
            self.time_data = deque(self.time_data, maxlen=self.buffer_size)

    def show_frame(self, name):
        """Show specified frame"""
        frame = self.frames[name]
        frame.tkraise()
        # after raising, give the new page a chance to update its layout or data
        if name == "DashboardFrame" and hasattr(frame, "refresh_layout"):
            frame.refresh_layout()
        if name == "SettingsFrame" and hasattr(frame, "refresh_history"):
            frame.refresh_history()

class DashboardFrame(tk.Frame):
    """Main dashboard display - Full Screen"""
    
    def __init__(self,parent, controller):
        super().__init__(parent, bg="#1a1a1a")
        self.controller = controller

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.last_battery_alert = 0  # timestamp of last battery warning
        self.battery_alerted = False  # to prevent repeated popups
        self.last_thermocouple = None
        self.last_rtd = None   # ✅ ADD

        self.rtd_ready = False  # Flag to indicate RTD & TC data is received
        self.rtd_ready = False
        self.tc_fifo = []   # FIFO buffer for thermocouple averaging
        self.is_connected = False  # Track connection state for ConnectionSettings persistence

        # Header
        header = tk.Frame(self, bg="#e6e6e6", height=100)
        header.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        header.grid_propagate(False)
        
        # Logo (only show if image loaded successfully)
        if controller.logo_img_small:
            try:
                logo_label = tk.Label(header, image=controller.logo_img_small, bg="#e6e6e6")
            except Exception:
                # invalid image object (common in headless/unit tests)
                logo_label = tk.Label(header, text="LOGO", bg="#e6e6e6")
        else:
            logo_label = tk.Label(header, text="LOGO", bg="#e6e6e6")
        logo_label.pack(side="left", padx=10, pady=10)
        
        # Title and device info (left side)
        left_info = tk.Frame(header, bg="#e6e6e6")
        left_info.pack(side="left", fill="y", padx=10, pady=15)
        
        tk.Label(left_info, textvariable=controller.station_name, fg="#333333", bg="#e6e6e6", 
                font=("Arial", 18, "bold")).pack(anchor="w")
        
        device_frame = tk.Frame(left_info, bg="#e6e6e6")
        device_frame.pack(fill="x", pady=(5, 0))
        tk.Label(device_frame, text="DEVICE ID:", fg="#666666", bg="#e6e6e6", font=("Arial", 10)).pack(side="left")
        tk.Label(device_frame, textvariable=controller.transmitter_id_val, fg="#333333", bg="#e6e6e6", 
                font=("Arial", 12, "bold")).pack(side="left", padx=5)
         
        # Time and status (center)
        center_info = tk.Frame(header, bg="#e6e6e6")
        center_info.pack(side="left", fill="both", expand=True, padx=20)
        
        self.lbl_time = tk.Label(center_info, text="00:00:00", fg="#333333", bg="#e6e6e6", 
                                font=("Arial", 16, "bold"))
        self.lbl_time.pack()
        self.lbl_date = tk.Label(center_info, text="DD-MMM-YYYY", fg="#666666", bg="#e6e6e6", 
                                font=("Arial", 11))
        self.lbl_date.pack()
        self.update_clock()
        
        # Battery and RSSI (right side)
        right_info = tk.Frame(header, bg="#e6e6e6")
        right_info.pack(side="right", padx=30, pady=15)
        
        self.lbl_bat = tk.Label(right_info, text="BAT --%", fg="#333333", bg="#e6e6e6", 
                font=("Arial", 20, "bold"))
        self.lbl_bat.pack(anchor="e")
        controller.battery_val.trace_add('write', lambda *args: self.lbl_bat.config(text=f"BAT {controller.battery_val.get()}%"))
        self.lbl_rssi = tk.Label(right_info, text="SIGNAL STRENGTH(RSSI)", fg="#0055aa", bg="#e6e6e6", 
                font=("Arial", 20, "bold"))
        self.lbl_rssi.pack(anchor="e")
        controller.rssi_val.trace_add('write', lambda *args: self.lbl_rssi.config(text=f"SIGNAL STRENGTH(RSSI) {controller.rssi_val.get()}"))
       
        # Main content area
        self.main_container = tk.Frame(self, bg="#ffffff")
        self.main_container.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        
        # Prepare graph frame (hidden until needed)
        self.graph_frame = tk.Frame(self, bg="white")
        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.fig.patch.set_facecolor('#ffffff')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Process Trend (Live)", fontsize=14, color='#666666')
        self.ax.set_facecolor('#f9f9f9')
        self.ax.grid(True, linestyle='--', alpha=0.5)
        self.line, = self.ax.plot([], [], 'r-', linewidth=3)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.lbl_graph_overlay = tk.Label(self.graph_frame, textvariable=controller.thermo_val,
                          bg="white", fg="#d40000", font=("Arial", 40, "bold"), highlightthickness=1)

        # Temperature display area (large)
        temp_display_area = tk.Frame(self.main_container, bg="#ffffff")
        temp_display_area.grid(row=0, column=0, sticky="nsew")
        temp_display_area.grid_rowconfigure(0, weight=1)
        temp_display_area.grid_rowconfigure(1, weight=0)
        temp_display_area.grid_rowconfigure(2, weight=0)  # Sensor data
        temp_display_area.grid_columnconfigure(0, weight=1)
        
        # Centered temperature section
        center_frame = tk.Frame(temp_display_area, bg="#ffffff")
        center_frame.grid(row=0, column=0, sticky="nsew")
        center_frame.grid_rowconfigure(0, weight=0)
    
        center_frame.grid_rowconfigure(1, weight=0)
        center_frame.grid_rowconfigure(2, weight=0)
        #center_frame.grid_rowconfigure(3, weight=0)
        center_frame.grid_columnconfigure(0, weight=1)

        tk.Label(center_frame, text="MELT TEMPERATURE", fg="#333333", bg="#ffffff",
             font=("Arial", 18, "bold")).grid(row=0, column=0, pady=(20, 10))

        temp_box = tk.Frame(center_frame, bg="#d40000", relief="ridge", borderwidth=3,width=700, height=180)
        temp_box.grid(row=1, column=0, pady=10, padx=20)
        temp_box.pack_propagate(False)

        tk.Label(temp_box, textvariable=controller.thermo_val, bg="#d40000", fg="#ffffff",
             font=("Arial", 90, "bold"), padx=20, pady=15).pack()

        # Temperature unit
        tk.Label(center_frame, text="°C", fg="#333333", bg="#ffffff", font=("Arial", 24, "bold")).grid(row=2, column=0, pady=(0, 10))
        
        alert_boxes_frame = tk.Frame(temp_display_area, bg="#ffffff")
        alert_boxes_frame.grid(row=1, column=0, sticky="ew", pady=15, padx=20)
        alert_boxes_frame.grid_columnconfigure(0, weight=1)
        alert_boxes_frame.grid_columnconfigure(1, weight=1)
        alert_boxes_frame.grid_columnconfigure(2, weight=1)
        
        # Initialize alert tracking
        self.active_alerts = {
            "BATTERY": [],
            "THERMOCOUPLE": [],
            "RTD": []
        }
        
        # ==================== BATTERY ALERT BOX ====================
        self.battery_alert_box = tk.Frame(alert_boxes_frame, bg="#ffffff", relief="solid", borderwidth=2)
        self.battery_alert_box.grid(row=0, column=0, sticky="ew", padx=5)
        
        
        tk.Label(self.battery_alert_box, text="🔴 BATTERY", fg="#000000", bg="#ffffff",
                font=("Arial", 16, "bold")).pack(pady=(8, 5))
        
        self.battery_alert_label = tk.Label(self.battery_alert_box, text="Battery Normal", fg="#006600", bg="#ffffff",
                font=("Arial", 24, "bold"))
        self.battery_alert_label.pack(pady=(8, 10))
        
        # ==================== THERMOCOUPLE ALERT BOX ====================
        self.tc_alert_box = tk.Frame(alert_boxes_frame, bg="#ffffff", relief="solid", borderwidth=2)
        self.tc_alert_box.grid(row=0, column=1, sticky="ew", padx=5)
        
        
        tk.Label(self.tc_alert_box, text="🔴 THERMOCOUPLE", fg="#000000", bg="#ffffff",
                font=("Arial", 16, "bold")).pack(pady=(8, 5))
        
        self.tc_alert_label = tk.Label(self.tc_alert_box, text="Thermocouple Normal", fg="#006600", bg="#ffffff",
                font=("Arial", 24, "bold"))
        self.tc_alert_label.pack(pady=(8, 10))
        
        # ==================== RTD ALERT BOX ====================
        self.rtd_alert_box = tk.Frame(alert_boxes_frame, bg="#ffffff", relief="solid", borderwidth=2)
        self.rtd_alert_box.grid(row=0, column=2, sticky="ew", padx=8)
        
        
        tk.Label(self.rtd_alert_box, text="🔴 RTD", fg="#000000", bg="#ffffff",
                font=("Arial", 16, "bold")).pack(pady=(8, 5))
        
        self.rtd_alert_label = tk.Label(self.rtd_alert_box, text="RTD Normal", fg="#006600", bg="#ffffff",
                font=("Arial", 24, "bold"))
        self.rtd_alert_label.pack(pady=(8, 10))

        # Sensor data grid (RTD, Thermocouple, RSSI)
        sensor_frame = tk.Frame(temp_display_area, bg="#ffffff")
        sensor_frame.grid(row=2, column=0, sticky="ew", pady=20, padx=20)
        sensor_frame.grid_columnconfigure(0, weight=1)
        sensor_frame.grid_columnconfigure(1, weight=1)
        sensor_frame.grid_columnconfigure(2, weight=1)

        # RTD sensor
        rtd_frame = tk.Frame(sensor_frame, bg="#ffffff")
        rtd_frame.grid(row=0, column=0, sticky="ew", padx=10)
        tk.Label(rtd_frame, text="RTD TEMPERATURE", fg="#333333", bg="#ffffff", font=("Arial", 11, "bold")).pack()
        tk.Label(rtd_frame, textvariable=controller.rtd_temp, fg="#0066cc", bg="#ffffff",
            font=("Arial", 26, "bold")).pack(pady=8)
        tk.Label(rtd_frame, text="°C", fg="#333333", bg="#ffffff", font=("Arial", 13)).pack()

        # DEVICE temperature sensor
        temp_frame = tk.Frame(sensor_frame, bg="#ffffff")
        temp_frame.grid(row=0, column=1, sticky="nsew", padx=10)
        tk.Label(temp_frame, text="DEVICE TEMPERATURE", fg="#333333", bg="#ffffff", font=("Arial", 12, "bold")).pack(anchor='e')
        tk.Label(temp_frame, textvariable=controller.current_temp, fg="#d40000", bg="#ffffff",
             font=("Arial", 32, "bold")).pack(pady=10, anchor='e')
        tk.Label(temp_frame, text="°C", fg="#333333", bg="#ffffff", font=("Arial", 16)).pack(anchor='e')
        
        # Footer with controls
        footer = tk.Frame(self, bg="#e6e6e6", height=70)
        footer.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
        footer.grid_propagate(False)
        
         # Settings button (right)
        tk.Button(footer, text="⚙ PAIRED DEVICE", bg="#cccccc", fg="black", font=("Arial", 11, "bold"),
                 width=20, command=self.check_password).pack(side="right", padx=20, pady=12)
         
        # ⚙ CONFIGURATION Button - WITH PASSWORD (NEW)
        tk.Button(footer, text="⚙ CONFIGURATION", bg="#cccccc", fg="black", font=("Arial", 11, "bold"),
                 width=20, command=self.check_configuration_password).pack(side="right", padx=20, pady=12)
        
    def check_paired_device_password(self):
        """Check password for Paired Device button"""
        password = simpledialog.askstring("Security", "Enter Password for Paired Device:", show='*')
        if password == "1111":
            self.open_paired_device_settings()
        elif password is not None:
            messagebox.showerror("Access Denied", "Incorrect Password")

    def check_configuration_password(self):
        """Check password for Configuration button"""
        password = simpledialog.askstring("Security", "Enter Configuration Password:", show='*')
        if password == "1111":
            self.controller.show_frame("SettingsFrame")
        elif password is not None:
            messagebox.showerror("Access Denied", "Incorrect Password")

    def open_paired_device_settings(self):
        """Open paired device connection window"""
        try:
            self.connection_window = ConnectionSettings(
                controller=self.controller,
                dashboard=self
            )
        except Exception as e:
            logger.exception("Failed to open ConnectionSettings")
            messagebox.showerror("Error", f"Unable to open connection settings:\n{e}")
        
# -------------------------------
# RTD Compensation Callback
# -------------------------------
    def on_rtd_compensation_changed(self):
        """Handle RTD compensation checkbox toggle"""
        enabled = self.controller.apply_rtd_compensation.get()
        logger.info(f"RTD Compensation checkbox toggled: {enabled}")

         # Send hardware command in background thread to avoid UI lag
        def send_command():
            try:
                if (hasattr(self.controller, 'port_manager') and 
                    self.controller.port_manager.serial and 
                    self.controller.port_manager.serial.is_open):
                    cmd = b'RTD_ON\n' if enabled else b'RTD_OFF\n'
                    self.controller.port_manager.serial.write(cmd)
                    logger.info(f"RTD command sent to hardware: {cmd.decode().strip()}")
            except Exception as e:
                logger.error(f"Error sending RTD command: {e}")

        # Run in background thread (no lag on UI)
        thread = threading.Thread(target=send_command, daemon=True)
        thread.start()
        
        # Clear thermocouple FIFO buffer to avoid stale data
        self.tc_fifo.clear()
        
        # Send command to hardware
        self.send_rtd_compensation_command(enabled)

# -------------------------------
# Hardware Command Function
# -------------------------------
    def send_rtd_compensation_command(self, enabled):
        """Send RTD compensation command to hardware"""
        try:
            if enabled:
                cmd = b'RTD_ON\n'
                logger.info("RTD Compensation ENABLED - Command sent to hardware")
            else:
                cmd = b'RTD_OFF\n'
                logger.info("RTD Compensation DISABLED - Command sent to hardware")
            
            # Send via serial port
            if (hasattr(self.controller, 'port_manager') and 
                hasattr(self.controller.port_manager, 'serial') and 
                self.controller.port_manager.serial and 
                self.controller.port_manager.serial.is_open):
                self.controller.port_manager.serial.write(cmd)
                logger.info(f"Sent RTD command to hardware: {cmd.decode().strip()}")
            else:
                logger.info("Serial port not available. Hardware command not sent, but software compensation will be applied based on checkbox state.")
        except Exception as e:
            logger.error(f"Error sending RTD command to hardware: {e}", exc_info=True)

    def check_battery(self, battery_text):
        # expects strings like "3.50V" or "3.5"
        if not battery_text or battery_text == "--":
          self.lbl_bat.config(text="BAT --", fg="#333333")
          self.bat_progress['value'] = 0
          self.bat_pct_label.config(text="--%", fg="#333333")
          return

        m = re.search(r"(\d+(?:\.\d+)?)", str(battery_text))
        if not m:
          self.lbl_bat.config(text=f"BAT {battery_text}", fg="#333333")
          return

        voltage = float(m.group(1))
        # linear map 3.0V->0%  4.2V->100%
        pct = int(round(100.0 * (voltage - 3.0) / (4.2 - 3.0)))
        pct = max(0, min(100, pct))

        # update UI
        self.lbl_bat.config(text=f"BAT {voltage:.2f}V ({pct}%)")
        try:
            self.bat_progress['value'] = pct
        except Exception:
            pass
        self.bat_pct_label.config(text=f"{pct}%")
        # color indicator
        if voltage >= 3.6:
         color = "#006600"   # good
        elif voltage >= 3.0:
         color = "orange"    # low
        else:
         color = "red"       # critical

        self.lbl_bat.config(fg=color)
        self.bat_pct_label.config(fg=color)
 
        # optional: rate-limited popups for low/critical
        now = time.time()
        if voltage < 3.0 and now - getattr(self, "last_battery_alert", 0) > 10:
            try:
               messagebox.showerror("Critical Battery", f"Battery critically low ({voltage:.2f}V) - {pct}%")
            except Exception:
               pass
            self.last_battery_alert = now
        elif 3.0 <= voltage < 3.6 and not getattr(self, "battery_alerted", False):
            try:
               messagebox.showwarning("Low Battery", f"Battery low: {voltage:.2f}V ({pct}%)")
            except Exception:
             pass
             self.battery_alerted = True
    
    def update_clock(self):
        """Update time and date"""
        now = datetime.now()
        self.lbl_time.config(text=now.strftime("%H:%M:%S"))
        self.lbl_date.config(text=now.strftime("%d-%b-%Y"))
        self.after(1000, self.update_clock)

    def refresh_layout(self):
        """Toggle between digital and graph view depending on controller setting"""
        # hide both
        try:
            self.main_container.grid_forget()
        except Exception:
            pass
        try:
            self.graph_frame.grid_forget()
        except Exception:
            pass
        self.lbl_graph_overlay.place_forget()
        if self.controller.view_mode.get() == "Digital View":
            self.main_container.grid(row=1, column=0, sticky="nsew")
        else:
            self.graph_frame.grid(row=1, column=0, sticky="nsew")
            self.lbl_graph_overlay.place(relx=0.95, rely=0.05, anchor="ne")
            self.update_graph()

    def update_graph(self):
        """Redraw live graph"""
        x = list(self.controller.time_data)
        y = list(self.controller.temp_data)
        if not x:
            return
        try:
            self.line.set_data(x, y)
            self.ax.relim()
            if self.controller.y_axis_mode.get() == "Manual":
                try:
                    self.ax.set_ylim(self.controller.y_min.get(), self.controller.y_max.get())
                except Exception:
                    pass
            else:
                self.ax.autoscale(enable=True, axis='y')
            self.canvas.draw()
        except Exception:
            pass

    def _open_port(self):
        """Open selected port in background thread (non-blocking)."""
        sel = getattr(self, "combo", None)
        port_name = None
        if sel:
            port_name = sel.get()
        if not port_name:
            messagebox.showerror("Error", "Select a port")
            return
        
        # Update status in ConnectionSettings window if available
        conn_window = getattr(self, "connection_window", None)
        if conn_window and hasattr(conn_window, "status_label"):
            conn_window.status_label.config(text=f"Connecting to {port_name}...", fg="orange")
        
        logger.info(f"Attempting to connect to {port_name}...")
        
        # Run port opening in background thread to avoid freezing UI
        thread = threading.Thread(target=self._open_port_bg, args=(port_name,), daemon=True)
        thread.start()

    def _open_port_bg(self, port_name):
        """Background thread: open port and initialize connection"""
        try:
            # This is blocking, so it runs in background
            success, msg = self.controller.port_manager.open_port(port_name)
            
            if success:
                # Update UI via main thread
                self.controller.com_port_val.set(port_name)
                self.controller.is_paired.set(True)
                self.controller.is_reading = True
                self.controller.serial = self.controller.port_manager.serial
                self.controller.status_msg.set("Connected")
                self.is_connected = True
                
                # Send RTD setting
                self.send_rtd_compensation_command(self.controller.apply_rtd_compensation.get())
                
                # Update status label in ConnectionSettings if available
                def update_status():
                    conn_window = getattr(self, "connection_window", None)
                    if conn_window and hasattr(conn_window, "status_label"):
                        conn_window.status_label.config(text=f"✓ Connected to {port_name}", fg="green")
                    logger.info(f"Connected to {port_name}")
                self.after(0, update_status)
                
                # Start read loop from main thread
                self.after(0, self._read_data)
                
            else:
                logger.error(f"Failed to connect: {msg}")
                self.controller.status_msg.set("Connection failed")
                def update_error():
                    conn_window = getattr(self, "connection_window", None)
                    if conn_window and hasattr(conn_window, "status_label"):
                        conn_window.status_label.config(text=f"✗ Failed: {msg}", fg="red")
                self.after(0, update_error)
        except Exception as e:
            logger.error(f"Error opening port: {e}", exc_info=True)
            self.controller.status_msg.set("Connection error")
            def update_exception():
                conn_window = getattr(self, "connection_window", None)
                if conn_window and hasattr(conn_window, "status_label"):
                    conn_window.status_label.config(text=f"✗ Error: {str(e)}", fg="red")
            self.after(0, update_exception)

    def _close_port(self):
        self.controller.port_manager.close_port()
        self.controller.is_reading = False
        self.controller.is_paired.set(False)
        self.controller.transmitter_id_val.set("NOT PAIRED")
        self.controller.packet_processor.reset()
        self.controller.serial = None
        self.controller.status_msg.set("Disconnected")
        messagebox.showinfo("Disconnected", "Port closed")
        self.is_connected = False

    def update_ports(self):
        """Update available ports"""
        ports = self.controller.port_manager.get_available_ports()
        self.combo['values'] = ports if ports else []
        if ports:
            self.combo.current(0)
    

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
            self.after(20, self._read_data)

    def _process_data(self, packet):
        """Process sensor data and update UI"""

    # -------- PARSE DATA --------
        try:
           data = self.controller.data_parser.parse_packet(
               packet,
               enable_rtd_compensation=self.controller.apply_rtd_compensation.get()
           )
           # Update all main UI labels with parsed values (including raw)
           # Device temperature
           device_temp = getattr(data, "temperature", None)
           if device_temp is not None:
               self.controller.current_temp.set(f"{device_temp:.1f}")
           else:
               self.controller.current_temp.set("--")

           # RTD temperature
           rtd_temp = getattr(data, "rtd_temperature", None)
           if rtd_temp is not None:
               self.controller.rtd_temp.set(f"{rtd_temp:.1f}")
           else:
               self.controller.rtd_temp.set("--")

           # RTD resistance
           rtd_res = getattr(data, "rtd_resistance", None)
           if rtd_res is not None:
               self.controller.rtd_resistance = f"{rtd_res:.2f} Ω"
           else:
               self.controller.rtd_resistance = "--"

           # Thermocouple temperature
           tc = getattr(data, "thermocouple", None)
           if tc is not None:
               self.controller.thermo_val.set(f"{tc:.1f}")
           else:
               self.controller.thermo_val.set("--")

           # Thermocouple voltage (uV)
           tc_uv = getattr(data, "thermocouple_voltage_uv", None)
           if tc_uv is not None:
               self.controller.tc_uv = f"{tc_uv:.0f} µV"
           else:
               self.controller.tc_uv = "--"

           # Battery voltage
           batt = getattr(data, "battery_voltage", None)
           if batt is not None:
               self.controller.battery_val.set(f"{batt:.2f}V")
               self.controller.bat_voltage.set(f"{batt:.2f}V")
           else:
               self.controller.battery_val.set("--")
               self.controller.bat_voltage.set("--")

           # RSSI
           rssi = getattr(data, "rssi", None)
           if rssi is not None:
               try:
                   self.controller.rssi_val.set(f"{float(rssi):.0f} dBm")
               except Exception:
                   self.controller.rssi_val.set(str(rssi))
           else:
               if self.controller.rssi_val.get() == "":
                   self.controller.rssi_val.set("--")

           # Device ID
           dev_id = getattr(data, "device_id", None)
           if dev_id is not None:
               self.controller.transmitter_id_val.set(str(dev_id))

           # Raw packet
           raw_packet = getattr(data, "raw_packet", None)
           if raw_packet:
               self.controller.raw_hex.set(" ".join(f"{b:02x}" for b in raw_packet))
           else:
               self.controller.raw_hex.set("--")
        except Exception as e:
           logger.error(f"Error parsing packet (RTD compensation: {self.controller.apply_rtd_compensation.get()}): {e}", exc_info=True)
           return   # Exit only if parsing completely fails
        
        # ===============================
# TRANSMITTER DISCOVERY & FILTERING
# ===============================
        tx_id = getattr(data, "device_id", None)
        
        try:
           conn = getattr(self, "connection_window", None)

           if conn and tx_id:
            tx_id = str(tx_id)

            # Check if connection window is still valid (not destroyed)
            try:
                conn.winfo_exists()
            except tk.TclError:
                conn = None

            if conn and conn.winfo_exists():
              # Add to list if new
              if tx_id not in conn.tx_ids:
                conn.tx_ids.append(tx_id)
                try:
                    conn.tx_combo["values"] = conn.tx_ids
                except tk.TclError:
                    logger.warning("tx_combo widget no longer exists")
                logger.info(f"Discovered new transmitter: {tx_id}")

              # Auto-select first TX
              if len(conn.tx_ids) == 1:
                try:
                    conn.tx_combo.current(0)
                    conn.selected_tx = tx_id
                    self.controller.transmitter_id_val.set(tx_id)
                    logger.info(f"Auto-selected first transmitter: {tx_id}")
                except tk.TclError:
                    logger.warning("Cannot update tx_combo - window may have closed")
                    conn.selected_tx = tx_id
                    self.controller.transmitter_id_val.set(tx_id)
            else:
              # Connection window closed, just store TX ID
              if tx_id not in getattr(conn, "tx_ids", []):
                if not hasattr(self, "_discovered_tx_ids"):
                    self._discovered_tx_ids = []
                if tx_id not in self._discovered_tx_ids:
                    self._discovered_tx_ids.append(tx_id)
                    logger.info(f"Discovered transmitter (offline): {tx_id}")
                    # If dashboard has no transmitter selected yet, show this one
                    cur = self.controller.transmitter_id_val.get()
                    if not cur or cur in ("WAITING", "NOT PAIRED"):
                        try:
                            self.controller.transmitter_id_val.set(tx_id)
                        except Exception:
                            pass
        except Exception as e:
           logger.error(f"Error in transmitter discovery: {e}", exc_info=True)
        
        # ===============================
# TRANSMITTER SELECTION FILTERING
    #        ===============================
        conn = getattr(self, "connection_window", None)
        selected_tx = None
        
        # Check if connection window exists and is valid
        if conn:
            try:
                if conn.winfo_exists():
                    selected_tx = getattr(conn, "selected_tx", None)
                else:
                    conn = None
            except tk.TclError:
                conn = None
        
        # If a transmitter is selected, only process its data
        if selected_tx and str(tx_id) != str(selected_tx):
            logger.debug(f"Packet from {tx_id} ignored - only processing {selected_tx}")
            return
        
        # If no transmitter is selected yet, show the data anyway (useful during discovery)
        logger.info(f"Processing packet from TX: {tx_id} (selected: {selected_tx})")
        
        # -------- DEVICE TEMPERATURE --------
        device_temp = getattr(data, "temperature", None)
        if device_temp is not None:
           self.controller.current_temp.set(f"{device_temp:.1f}")
        else:
          self.controller.current_temp.set("--")
    # -------- RTD TEMPERATURE --------
        rtd_temp = getattr(data, "rtd_temperature", None)
        if rtd_temp is not None:
          self.controller.rtd_temp.set(f"{rtd_temp:.1f}")
        else:
          self.controller.rtd_temp.set("--")

        # --- log to database and update history/graph ---
        # Use melt temperature (thermocouple) for graph instead of device temperature
        melt_temp = getattr(data, "thermocouple", None)
        if melt_temp is not None:
            try:
                new_val = float(melt_temp)
            except Exception:
                new_val = None
        else:
            new_val = None

        if new_val is not None:
            self.controller.x_counter += 1
            self.controller.temp_data.append(new_val)
            self.controller.time_data.append(self.controller.x_counter)

            # compute battery pct if voltage available
            bat_pct = None
            batt = getattr(data, "battery_voltage", None)
            if batt is not None:
                try:
                    voltage = float(batt)
                    bat_pct = int(round(100.0 * (voltage - 3.0) / (4.2 - 3.0)))
                    bat_pct = max(0, min(100, bat_pct))
                except Exception:
                    bat_pct = None

            # pull raw values directly from the packet so we can log them
            pkt = data.raw_packet or packet
            # device id string is already available in data.device_id
            dev_id = getattr(data, "device_id", "")

            # reconstruct raw integers exactly as parser does
            temp_int = pkt[3]
            temp_int = (temp_int << 8) | pkt[2]
            temp_int = (temp_int << 8) | pkt[1]
            temp_int = (temp_int << 8) | pkt[0]

            rtd_int = pkt[11]
            rtd_int = (rtd_int << 8) | pkt[10]

            thermo_int = pkt[13]
            thermo_int = (thermo_int << 8) | pkt[12]

            batt_int = (pkt[15] << 8) | pkt[14]

# WITH THIS:
            station_name = self.controller.station_name.get() or "UNKNOWN"
            rssi_val = getattr(data, "rssi", 0) or 0
            try:
               rssi_int = int(float(str(rssi_val).replace(" dBm", "").strip()))
            except Exception:
               rssi_int = 0

            self.controller.log_to_db(station_name,dev_id,temp_int,
            rtd_int,thermo_int,batt_int,rssi_int
          )

            ts = datetime.now().strftime("%H:%M:%S")
            # history display still uses simplified string
            self.controller.history_display.appendleft(
                f"{ts} | Melt:{new_val}{self.controller.units.get()} | RTD:{rtd_temp} | Bat:{bat_pct}% | {rssi}dBm"
            )
            if "DashboardFrame" in self.controller.frames:
                try:
                    self.controller.frames["DashboardFrame"].update_graph()
                except Exception:
                    pass
        # -------------------------------
# 
# Valid thermocouple temperature
        elif tc is not None:
            self.tc_fifo.append(tc)

            if len(self.tc_fifo) > 10:
                self.tc_fifo.pop(0)

            avg_tc = sum(self.tc_fifo) / len(self.tc_fifo)
            self.controller.thermo_val.set(f"{avg_tc:.1f}")

        # Battery: accept battery_voltage (float) or battery_text
        batt = getattr(data, "battery_voltage", None)
        if batt is None:
            batt_text = getattr(data, "battery_text", None)
            if batt_text:
                m = re.search(r"(\d+(?:\.\d+)?)", str(batt_text))
                if m:
                    try:
                        batt = float(m.group(1))
                    except Exception:
                        batt = None

        if batt is not None:
            self.controller.battery_val.set(f"{batt:.2f}V")
            # Also update diagnostic display
            self.controller.bat_voltage.set(f"{batt:.2f}V")
        else:
            self.controller.battery_val.set("--")
            self.controller.bat_voltage.set("--")

        # Update raw hex for diagnostics
        raw_packet = getattr(data, "raw_packet", None)
        if raw_packet:
            self.controller.raw_hex.set(" ".join(f"{b:02x}" for b in raw_packet))

        # RSSI
        rssi = getattr(data, "rssi", None)
        if rssi is not None:
            try:
                self.controller.rssi_val.set(f"{float(rssi):.0f} dBm")
            except Exception:
                self.controller.rssi_val.set(str(rssi))
        else:
            if self.controller.rssi_val.get() == "":
                self.controller.rssi_val.set("--")
    
    def _check_alerts(self, data):
        """Check sensor data for alert conditions"""

        if not hasattr(self, 'battery_alert_label'):
            return
        
        # Clear previous alerts
        self.active_alerts = {
            "BATTERY": [],
            "THERMOCOUPLE": [],
            "RTD": []
        }
        
        # RTD resistance alerts
        rtd_resistance = getattr(data, "rtd_resistance", None)
        rtd_status = " Normal"
        rtd_color = "#006600"
        
        if rtd_resistance is not None:
            if rtd_resistance < 100:
                self.active_alerts["RTD"].append(("RTD under lower limit. May be short circuit", "red"))
                rtd_status = " Short Circuit"
                rtd_color = "#d40000"
            elif rtd_resistance > 390:
                self.active_alerts["RTD"].append(("RTD over upper limit. May be RTD is melt and open", "red"))
                rtd_status = "Open Circuit"
                rtd_color = "#d40000"
        
        # Update RTD alert box
        try:
            self.rtd_alert_label.config(text=rtd_status, fg=rtd_color)
            if rtd_color == "#d40000":  # red alert
                self.rtd_alert_box.config(bg=rtd_color)
                self.rtd_alert_label.config(bg=rtd_color, fg="#ffffff")  # white text
            else:
                self.rtd_alert_box.config(bg="#ffffff")
                self.rtd_alert_label.config(bg="#ffffff", fg=rtd_color)
        except:
            pass
        
        # Thermocouple voltage alerts
        tc_voltage_uv = getattr(data, "thermocouple_voltage_uv", None)
        tc_status = " Normal"
        tc_color = "#006600"
        
        if tc_voltage_uv is not None:
            if tc_voltage_uv < 100:
                self.active_alerts["THERMOCOUPLE"].append(("Thermo couple temperature is under lower limit. May be short", "red"))
                tc_status = " Short Circuit"
                tc_color = "#d40000"
            elif tc_voltage_uv > 14000:
                self.active_alerts["THERMOCOUPLE"].append(("Thermocouple is not connected or short", "red"))
                tc_status = " Not Connected"
                tc_color = "#d40000"
            elif 100 <= tc_voltage_uv <= 1800:
                tc_status = " Connected"
                tc_color = "#ff9900"
        
        # Update Thermocouple alert box
        try:
            self.tc_alert_label.config(text=tc_status, fg=tc_color)
            if tc_color == "#d40000":  # red alert
               self.tc_alert_box.config(bg=tc_color)
               self.tc_alert_label.config(bg=tc_color, fg="#ffffff")
            else:
               self.tc_alert_box.config(bg="#ffffff")
               self.tc_alert_label.config(bg="#ffffff", fg=tc_color)
        except:
            pass
        
        # Battery voltage alerts
        battery_voltage = getattr(data, "battery_voltage", None)
        battery_status = " Normal"
        battery_color = "#006600"
        
        if battery_voltage is not None:
            if battery_voltage < 3.35:
                self.active_alerts["BATTERY"].append(("Battery critically low - Charge immediately!", "red"))
                battery_status = " Critical"
                battery_color = "#d40000"
            elif battery_voltage < 3.6:
                self.active_alerts["BATTERY"].append(("Battery low - Recharge soon", "yellow"))
                battery_status = " Low"
                battery_color =  "#d40000"
        
        # Update Battery alert box
        try:
            self.battery_alert_label.config(text=battery_status, fg=battery_color)
            if battery_color == "#d40000":  # red alert
              self.battery_alert_box.config(bg=battery_color)
              self.battery_alert_label.config(bg=battery_color, fg="#ffffff")
            else:
               self.battery_alert_box.config(bg="#ffffff")
               self.battery_alert_label.config(bg="#ffffff", fg=battery_color)
        except:
            pass
        
        # Set overall status message
        all_alerts = self.active_alerts["BATTERY"] + self.active_alerts["THERMOCOUPLE"] + self.active_alerts["RTD"]
        if all_alerts:
            red_alerts = [alert for alert in all_alerts if alert[1] == "red"]
            if red_alerts:
                try:
                    self.controller.status_msg.set(red_alerts[0][0])
                    self.lbl_status.config(fg="red")
                except:
                    pass
            else:
                yellow_alerts = [alert for alert in all_alerts if alert[1] == "yellow"]
                if yellow_alerts:
                    try:
                        self.controller.status_msg.set(yellow_alerts[0][0])
                        self.lbl_status.config(fg="orange")
                    except:
                        pass
        else:
            try:
                self.controller.status_msg.set("✓ Normal - All Systems OK")
                self.lbl_status.config(fg="green")
            except:
                pass
       

    def check_password(self):
        """Open Connection Settings popup safely, reusing window if possible."""
        try:
            # If window exists and is not destroyed, bring to front
            if hasattr(self, 'connection_window') and self.connection_window is not None:
                try:
                    if self.connection_window.winfo_exists():
                        self.connection_window.lift()
                        self.connection_window.focus_force()
                        return
                except Exception:
                    pass
            # Otherwise, create new window and store reference
            self.connection_window = ConnectionSettings(
                controller=self.controller,
                dashboard=self,
                is_connected=self.is_connected
            )
        except Exception as e:
            logger.exception("Failed to open ConnectionSettings")
            messagebox.showerror(
                "Error",
                f"Unable to open connection settings:\n{e}"
            )

class ConnectionSettings(tk.Toplevel):
    """COM Port Configuration Popup — opens immediately, requests password, enables controls on success."""

    def __init__(self, controller, dashboard, is_connected=False):
        super().__init__(dashboard)

        self.controller = controller
        self.dashboard = dashboard

        # Track connection state
        self._is_connected = is_connected

        self.title("Connection Settings")
        self.geometry("420x250")
        self.resizable(False, False)
        self.configure(bg="#f0f0f0")

        self.transient(dashboard)
        self.grab_set()

        # ---------- TITLE ----------
        tk.Label(self,text="USB / COM Port Configuration",font=("Arial", 14, "bold"),bg="#f0f0f0"
        ).pack(pady=15)

        frame = tk.Frame(self, bg="#f0f0f0")
        frame.pack(pady=10)

        tk.Label(frame,text="USB Port:",bg="#f0f0f0",font=("Arial", 11)
        ).pack(side="left", padx=5)

        # USB dropdown
        self.combo = ttk.Combobox(frame,width=20,state="readonly"
       )
        self.combo.pack(side="left", padx=5)

        # ---------- BUTTONS ----------
        btns = tk.Frame(self, bg="#f0f0f0")
        btns.pack(pady=20)

        # create buttons as attributes so we can enable/disable them
        self.btn_refresh = tk.Button( btns,text="🔄 REFRESH",width=12,command=self.update_ports,
            state="disabled"
        )
        self.btn_refresh.pack(side="left", padx=5)

        self.btn_connect = tk.Button(btns,text="✓ CONNECT",width=12,command=self.connect,state="disabled"
        )
        self.btn_connect.pack(side="left", padx=5)

        self.btn_disconnect = tk.Button(btns,text="✗ DISCONNECT",width=12,command=self.disconnect,
            state="disabled"
        )
        self.btn_disconnect.pack(side="left", padx=5)

        # ---------- TRANSMITTER ID ----------
        tx_frame = tk.Frame(self, bg="#f0f0f0")
        tx_frame.pack(pady=(5, 10))

        tk.Label(tx_frame,text="Transmitter ID:",bg="#f0f0f0",font=("Arial", 11)
        ).pack(side="left", padx=5)

        self.tx_combo = ttk.Combobox(tx_frame,width=20,state="readonly"
    )
        self.tx_combo.pack(side="left", padx=5)

        self.tx_ids = []
        self.selected_tx = None
        self._is_connected = False
        self.dashboard.is_connected = False

        # If controller has discovered transmitters before opening this window, populate
        if hasattr(self.controller, '_discovered_tx_ids') and self.controller._discovered_tx_ids:
            try:
                self.tx_ids = list(self.controller._discovered_tx_ids)
                self.tx_combo['values'] = self.tx_ids
                if self.tx_ids:
                    self.tx_combo.current(0)
                    self.selected_tx = self.tx_ids[0]
                    self.controller.transmitter_id_val.set(self.selected_tx)
            except Exception:
                pass

        self.tx_combo.bind(
            "<<ComboboxSelected>>",
        self.on_tx_selected
    )

        # small status / instruction area
        self.status_label = tk.Label(self, text="Locked — enter password to enable controls", bg="#f0f0f0")
        self.status_label.pack(pady=(0, 8))

        # populate combo (disabled until password)
        self.update_ports()

        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

        # Ensure popup is shown before the password dialog
        self.lift()
        self.focus_force()
        self.after(100, self.ask_password)  # call after short delay so the Toplevel is visible

    def on_window_close(self):
        """Handle X button click - just close the window, don't destroy permanently"""
        logger.info("Connection Settings window closed")
        self.destroy()

    """def update_ports(self):
        ports = self.controller.port_manager.get_available_ports()
        self.combo["values"] = ports if ports else []
        if ports:
            try:
                self.combo.current(0)
            except Exception:
                pass"""
   
    # In ConnectionSettings class, REPLACE the update_ports() method with:

    def update_ports(self):
        """Update available ports - show ALL ports including the currently connected one.
    
         This allows users to:
         - See which port they're currently connected to
         - Switch to a different port
         - Reconnect to the same port if needed
         """
    # Get all available ports (do NOT exclude the connected port)
        ports = self.controller.port_manager.get_available_ports(exclude_connected=False)
    
        self.combo["values"] = ports if ports else []
    
    # Try to select the currently connected port if available
        connected_port = self.controller.com_port_val.get()
        if connected_port and connected_port != "NOT CONNECTED":
           try:
            # Find and select the connected port in the dropdown
               index = ports.index(connected_port) if ports else -1
               if index >= 0:
                  self.combo.current(index)
                  logger.info(f"Connection Settings: Currently connected to {connected_port}")
               else:
                # Connected port not in list, select first available
                  if ports:
                     self.combo.current(0)
           except (ValueError, tk.TclError):
              if ports:
                try:
                    self.combo.current(0)
                except Exception:
                    pass
        else:
        # Not connected, select first available port
           if ports:
               try:
                  self.combo.current(0)
               except Exception:
                pass
    
        logger.info(f"Connection Settings: Showing {len(ports)} available ports (including connected)")

    def ask_password(self):
        """Prompt for password; enable controls only if correct."""
        pwd = simpledialog.askstring("Security", "Enter Password:", show='*', parent=self)
        if pwd == "1111":
            self.enable_controls()
        elif pwd is None:
            # user cancelled — keep controls disabled
            self.status_label.config(text="Locked — password required", fg="black")
        else:
            messagebox.showerror("Access Denied", "Wrong Password", parent=self)
            self.status_label.config(text="Wrong password — controls locked", fg="red")

    def enable_controls(self):
        self.btn_refresh.config(state="normal")
            # Always sync with dashboard connection state
        self._is_connected = getattr(self.dashboard, 'is_connected', False)
        if self._is_connected:
            self.btn_connect.config(state="disabled")
            self.btn_disconnect.config(state="normal")
        else:
            self.btn_connect.config(state="normal")
            self.btn_disconnect.config(state="disabled")
        self.status_label.config(text="Unlocked — you may connect", fg="green")
        # refresh port list now that controls are enabled
        self.update_ports()
        self.restore_button_states()

    def restore_button_states(self):
        """Restore button states from saved connection status"""
        # Read the saved state from controller
        connection_status = getattr(self.controller, 'connection_status', 'disconnected')
        
        logger.info(f"[WINDOW REOPENED] Connection status from controller: {connection_status}")
        
        if connection_status == "connected":
            # Was CONNECTED before - disable CONNECT, enable DISCONNECT
            self.btn_connect.config(state="disabled")
            self.btn_disconnect.config(state="normal")
            self.status_label.config(text="✓ Connected — ready to disconnect", fg="green")
            logger.info("✓ Restored: CONNECT disabled, DISCONNECT enabled")
            
        else:  # "disconnected" or any other state
            # Was DISCONNECTED - enable CONNECT, disable DISCONNECT
            self.btn_connect.config(state="normal")
            self.btn_disconnect.config(state="disabled")
            self.status_label.config(text="Ready to connect", fg="black")
            logger.info("✓ Restored: CONNECT enabled, DISCONNECT disabled")

    def connect(self):
       port = self.combo.get()
       if not port:
          messagebox.showerror("Error", "Select a COM port", parent=self)
          return

      # Disable connect, enable disconnect
       self.btn_connect.config(state="disabled")
       self.btn_disconnect.config(state="normal")
       self.dashboard.combo = self.combo
    
    # ✅ ADD THIS LINE - Set the port immediately
       self.controller.com_port_val.set(port)
    
       self.dashboard._open_port()
       self._is_connected = True
       self.dashboard.is_connected = True

     # ✅ SAVE CONNECTION STATE to controller
       self.controller.connection_status = "connected"
       self.dashboard.is_connected = True
    
       self.status_label.config(text=f"✓ Connected to {port}", fg="green")
       logger.info(f"[CONNECT] Button state SAVED: connected")
    


    def on_tx_selected(self, event):
        """Handle transmitter ID selection change"""
        self.selected_tx = self.tx_combo.get()
        self.controller.transmitter_id_val.set(self.selected_tx)
        logger.info(f"Transmitter ID selected: {self.selected_tx}")
        
        # Clear UI data buffers when switching transmitters to avoid showing stale data
        if hasattr(self.dashboard, 'tc_fifo'):
            self.dashboard.tc_fifo.clear()
        
        # Reset temperature displays
        self.controller.current_temp.set("--")
        self.controller.rtd_temp.set("--")
        self.controller.thermo_val.set("--")
        self.controller.battery_val.set("--")
        self.controller.rssi_val.set("--")

    def disconnect(self):
       self.dashboard._close_port()

    # Enable connect, disable disconnect
       self.controller.connection_status = "disconnected"
       self.dashboard.is_connected = False
    
    # ✅ ADD THIS LINE - Clear the port value
       self.controller.com_port_val.set("NOT CONNECTED")
    
    # After disconnect, update button states
       self.btn_connect.config(state="normal")
       self.btn_disconnect.config(state="disabled")
       self.status_label.config(text="Disconnected — ready to connect", fg="black")
    

    # Clear TX dropdown
       self.tx_ids.clear()
       self.tx_combo["values"] = []
       self.selected_tx = None

class SettingsFrame(tk.Frame):
    """Settings frame - Configuration"""
    
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f0f0f0")
        self.controller = controller
        
        # Header
        header = tk.Frame(self, bg="#e6e6e6", height=60)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)
        
        tk.Label(header, text="CONFIGURATION - WIRELESS SENSOR SYSTEM", fg="#333333", bg="#e6e6e6", 
                font=("Arial", 18, "bold")).pack(side="left", padx=30, pady=15)
        
        tk.Button(header, text="← BACK TO DASHBOARD", bg="#cccccc", fg="black", font=("Arial", 10, "bold"),
                 command=lambda: controller.show_frame("DashboardFrame"), 
                 activebackground="#000000", activeforeground="#ffffff").pack(side="right", padx=20, pady=12)
        
          # ========== TAB NAVIGATION (HORIZONTAL) ==========
        tab_nav = tk.Frame(self, bg="#d0d0d0", height=50)
        tab_nav.pack(fill="x", padx=0, pady=0)
        tab_nav.pack_propagate(False)
        
        self.tab_buttons = {}
        self.tab_frames = {}
        tabs = ["General", "Graph", "Transmitter", "Outputs", "Troubleshooting", "History", "RTD Compensation"]
        
        for i, tab_name in enumerate(tabs):
            btn = tk.Button(
                tab_nav,
                text=tab_name,
                bg="#cccccc" if i == 0 else "#b0b0b0",
                fg="black",
                font=("Arial", 11, "bold"),
                relief="raised",
                padx=15,
                pady=10,
                command=lambda t=tab_name: self.show_tab(t)
            )
            btn.pack(side="left", padx=2, pady=5)
            self.tab_buttons[tab_name] = btn
        
        # ========== CONTENT AREA ==========
        self.content_container = tk.Frame(self, bg="#f0f0f0")
        self.content_container.pack(fill="both", expand=True, padx=0, pady=0)
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)
        
        # ========== TAB 1: GENERAL ==========
        self.tab_frames["General"] = tk.Frame(self.content_container, bg="#f0f0f0")
        self.tab_frames["General"].grid(row=0, column=0, sticky="nsew")
        gen_content = tk.Frame(self.tab_frames["General"], bg="#f0f0f0")
        gen_content.pack(fill="both", expand=True, padx=30, pady=30)
        
        tk.Label(gen_content, text="General Settings", fg="#333333", bg="#f0f0f0", 
                font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 20))
        self.create_entry_row(gen_content, "Station Name:", controller.station_name)
        self.create_static_row(gen_content, "Sensor Type:", "Type B")
        self.create_combobox_row(gen_content, "Dashboard View:", controller.view_mode, ["Digital View", "Graph View"])
        #w
        # self.create_combobox_row(gen_content, "Units:", controller.units, ["°C", "°F"])

        # ========== TAB 2: GRAPH ==========
        self.tab_frames["Graph"] = tk.Frame(self.content_container, bg="#f0f0f0")
        graph_content = tk.Frame(self.tab_frames["Graph"], bg="#f0f0f0")
        graph_content.pack(fill="both", expand=True, padx=30, pady=30)
        
        tk.Label(graph_content, text="Graph Display Settings", fg="#333333", bg="#f0f0f0", 
                font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 20))
        tk.Label(graph_content, text="Configure time scales and axis modes for live graph display", 
                font=("Arial", 11), bg="#f0f0f0", fg="#666666").pack(anchor="w", pady=10)
        # interactive controls
        self.create_combobox_row(graph_content, "Time Scale:", controller.time_scale_str, ["1 Minute", "5 Minutes", "15 Minutes", "1 Hour"])
        tk.Label(graph_content, text="Y-Axis Mode:", font=("Arial", 12), bg="#f0f0f0").pack(anchor="nw",pady=(10,0))

        # Temperature Range (Min - Max)
        temp_range_frame = tk.Frame(graph_content, bg="#f0f0f0")
        temp_range_frame.pack(fill="x", pady=10)
        tk.Label(temp_range_frame, text="Temperature Range:", width=20, anchor="e", bg="#f0f0f0", 
         font=("Arial", 12, "bold")).pack(side="left")

        range_input_frame = tk.Frame(temp_range_frame, bg="#f0f0f0")
        range_input_frame.pack(side="left", padx=15)

        tk.Label(range_input_frame, text="Min (°C):", bg="#f0f0f0", font=("Arial", 11)).pack(side="left", padx=5)
        min_entry = tk.Entry(range_input_frame, textvariable=controller.y_min, width=10, font=("Arial", 11))
        min_entry.pack(side="left", padx=5)
 
        tk.Label(range_input_frame, text="Max (°C):", bg="#f0f0f0", font=("Arial", 11)).pack(side="left", padx=5)
        max_entry = tk.Entry(range_input_frame, textvariable=controller.y_max, width=10, font=("Arial", 11))
        max_entry.pack(side="left", padx=5)

        """tk.Radiobutton(graph_content, text="Autoscale", variable=controller.y_axis_mode, value="Autoscale", bg="#f0f0f0", font=("Arial", 12)).pack()
        tk.Radiobutton(graph_content, text="Manual", variable=controller.y_axis_mode, value="Manual", bg="#f0f0f0", font=("Arial", 12)).pack()
        fr = tk.Frame(graph_content, bg="#f0f0f0"); fr.pack(pady=5)
        tk.Entry(fr, textvariable=controller.y_min, width=6, font=("Arial", 12)).pack(side="left"); tk.Label(fr, text="-", bg="#f0f0f0").pack(side="left")
        tk.Entry(fr, textvariable=controller.y_max, width=6, font=("Arial", 12)).pack(side="left")"""
        
        # ========== TAB 3: TRANSMITTER ==========
        self.tab_frames["Transmitter"] = tk.Frame(self.content_container, bg="#f0f0f0")
        tx_content = tk.Frame(self.tab_frames["Transmitter"], bg="#f0f0f0")
        tx_content.pack(fill="both", expand=True, padx=30, pady=30)
        
        tk.Label(tx_content, text="Transmitter Information", fg="#333333", bg="#f0f0f0", 
                font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 20))
        
        tx_frame = tk.Frame(tx_content, bg="#f0f0f0")
        tx_frame.pack(fill="x", pady=8)
        tk.Label(tx_frame, text="Paired Device:", width=20, anchor="e", bg="#f0f0f0", 
        font=("Arial", 12, "bold")).pack(side="left")

# ADD TRANSMITTER ID LABEL TO FRAME (NOT to tx_content)
        self.tx_id_label = tk.Label(tx_frame, textvariable=controller.transmitter_id_val, 
         fg="#0055aa", bg="#f0f0f0", font=("Arial", 12, "bold"))
        self.tx_id_label.pack(side="left", padx=15)

# Device Status row (separate)
        self.create_static_row(tx_content, "Device Status:", "Connected")
       
        
        """device_id = controller.transmitter_id_val.get() or "NOT PAIRED"
        self.create_static_row(tx_content, "Paired Device:", device_id)
        self.create_static_row(tx_content, "Firmware Version:", "v2.1.4-beta")

        self.create_static_row(tx_content, "Device Status:", "Connected")"""

        # ========== TAB 4: OUTPUTS ==========
        self.tab_frames["Outputs"] = tk.Frame(self.content_container, bg="#f0f0f0")
        outputs_content = tk.Frame(self.tab_frames["Outputs"], bg="#f0f0f0")
        outputs_content.pack(fill="both", expand=True, padx=30, pady=30)
        
        tk.Label(outputs_content, text="Output Configuration", fg="#333333", bg="#f0f0f0", 
                font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 20))
        
        # COM Port Settings
        com_frame = tk.LabelFrame(outputs_content, text="COM Port Settings", bg="#f0f0f0", 
                                 font=("Arial", 12, "bold"), padx=15, pady=15)
        com_frame.pack(fill="x", pady=10)
        """self.create_combobox_row(com_frame, "Port:", controller.com_port, ["COM1", "COM2", "COM3", "USB-SERIAL"])"""
        
        # ✅ ADD THIS SECTION (Port dropdown with REFRESH button)
        port_select_frame = tk.Frame(com_frame, bg="#f0f0f0")
        port_select_frame.pack(fill="x", pady=8)

        tk.Label(port_select_frame, text="Port:", width=20, anchor="e", bg="#f0f0f0", 
         font=("Arial", 12, "bold")).pack(side="left")

        self.output_port_combo = ttk.Combobox(port_select_frame, width=25, state="readonly")
        self.output_port_combo.pack(side="left", padx=15)

# Refresh button to update available ports
        tk.Button(port_select_frame, text="🔄 REFRESH", bg="#cccccc", fg="black", 
         font=("Arial", 10, "bold"), width=12, 
         command=self.refresh_output_ports).pack(side="left", padx=5)

# Populate ports on tab initialization
        self.refresh_output_ports()
        self.controller.com_port_val.trace_add('write', lambda *args: self.on_port_changed())

# Original baud rate row
        self.create_combobox_row(com_frame, "Baud Rate:", controller.baud_rate, ["9600", "19200", "38400", "115200"])
        
        self.out_notebook = ttk.Notebook(outputs_content)
        self.out_notebook.pack(fill="both", expand=True, padx=0, pady=10)
        
        """tab_rtu = tk.Frame(self.out_notebook, bg="#f0f0f0")
        self.out_notebook.add(tab_rtu, text="Modbus RTU")
        rtu_content = tk.Frame(tab_rtu, bg="#f0f0f0")
        rtu_content.pack(fill="both", expand=True, padx=20, pady=20)
        self.create_entry_row(rtu_content, "Slave ID:", controller.mb_slave_id)"""
        
        tab_tcp = tk.Frame(self.out_notebook, bg="#f0f0f0")
        self.out_notebook.add(tab_tcp, text="Modbus TCP")
        tcp_content = tk.Frame(tab_tcp, bg="#f0f0f0")
        tcp_content.pack(fill="both", expand=True, padx=20, pady=20)
        self.create_entry_row(tcp_content, "IP Address:", controller.eth_ip)
        self.create_entry_row(tcp_content, "Port:", controller.eth_port)
        
        """tab_420 = tk.Frame(self.out_notebook, bg="#f0f0f0")
        self.out_notebook.add(tab_420, text="4-20mA")
        analog_content = tk.Frame(tab_420, bg="#f0f0f0")
        analog_content.pack(fill="both", expand=True, padx=20, pady=20)
        self.create_entry_row(analog_content, "Temp @ 4mA:", controller.analog_low)
        self.create_entry_row(analog_content, "Temp @ 20mA:", controller.analog_high)
        
        tab_prof = tk.Frame(self.out_notebook, bg="#f0f0f0")
        self.out_notebook.add(tab_prof, text="Profibus/Net")
        prof_content = tk.Frame(tab_prof, bg="#f0f0f0")
        prof_content.pack(fill="both", expand=True, padx=20, pady=20)
        self.create_entry_row(prof_content, "Station Address:", controller.prof_station)"""
        
        # ========== TAB 5: TROUBLESHOOTING ==========
        self.tab_frames["Troubleshooting"] = tk.Frame(self.content_container, bg="#f0f0f0")
        debug_content = tk.Frame(self.tab_frames["Troubleshooting"], bg="#f0f0f0")
        debug_content.pack(fill="both", expand=True, padx=30, pady=30)
        
        tk.Label(debug_content, text="Diagnostic Information", fg="#333333", bg="#f0f0f0", 
                font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 20))
        
        diag_frame = tk.LabelFrame(debug_content, text="Sensor Diagnostics", bg="#f0f0f0", 
                                  font=("Arial", 12, "bold"), padx=15, pady=15)
        diag_frame.pack(fill="x", pady=10)
        self.create_diag_row(diag_frame, "Raw ADC Hex:", controller.raw_hex)
        self.create_diag_row(diag_frame, "Battery Voltage:", controller.bat_voltage)

        # ✅ ADD THIS SECTION (Port diagnostics)
        port_diag_frame = tk.LabelFrame(debug_content, text="Port Diagnostics", bg="#f0f0f0", 
                               font=("Arial", 12, "bold"), padx=15, pady=15)
        port_diag_frame.pack(fill="x", pady=10)

        self.create_diag_row(port_diag_frame, "Connected Port:", controller.com_port_val)
        self.create_diag_row(port_diag_frame, "Connection Status:", controller.status_msg)
        self.create_diag_row(port_diag_frame, "Transmitter ID:", controller.transmitter_id_val)
        
        # ========== TAB 6: HISTORY ==========
        self.tab_frames["History"] = tk.Frame(self.content_container, bg="#f0f0f0")
        hist_content = tk.Frame(self.tab_frames["History"], bg="#f0f0f0")
        hist_content.pack(fill="both", expand=True, padx=30, pady=30)
        
        tk.Label(hist_content, text="Measurement History", fg="#333333", bg="#f0f0f0", 
                font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 20))
        
        # Date/Time range inputs for export
        self.date_from_var = tk.StringVar(value="")
        self.date_to_var = tk.StringVar(value="")

        range_frame = tk.Frame(hist_content, bg="#f0f0f0")
        range_frame.pack(fill="x", pady=(0, 10))

        tk.Label(range_frame, text="From:", bg="#f0f0f0", font=("Arial", 10)).pack(side="left")
        from_box = tk.Frame(range_frame, bg="#f0f0f0")
        from_box.pack(side="left", padx=(5, 15))
        tk.Entry(from_box, textvariable=self.date_from_var, width=22, font=("Arial", 10)).pack(side="left")
        tk.Button(from_box, text="📅", width=3, command=lambda: DateTimePopup(self, lambda d: self.date_from_var.set(d))).pack(side="left", padx=(6,0))

        tk.Label(range_frame, text="To:", bg="#f0f0f0", font=("Arial", 10)).pack(side="left")
        to_box = tk.Frame(range_frame, bg="#f0f0f0")
        to_box.pack(side="left", padx=(5, 15))
        tk.Entry(to_box, textvariable=self.date_to_var, width=22, font=("Arial", 10)).pack(side="left")
        tk.Button(to_box, text="📅", width=3, command=lambda: DateTimePopup(self, lambda d: self.date_to_var.set(d))).pack(side="left", padx=(6,0))

        tk.Button(range_frame, text="📥 Export Range to CSV", bg="#0066cc", fg="white",
              font=("Arial", 11, "bold"), command=self.export_csv).pack(side="right")

        """self.history_list = tk.Listbox(hist_content, font=("Courier New", 11), height=12)
        self.history_list.pack(fill="both", expand=True, pady=10)"""

        # ========== TAB: RTD COMPENSATION ==========
        self.tab_frames["RTD Compensation"] = tk.Frame(self.content_container, bg="#f0f0f0")

        rtd_content = tk.Frame(self.tab_frames["RTD Compensation"], bg="#f0f0f0")
        rtd_content.pack(fill="both", expand=True, padx=30, pady=30)

        tk.Label(rtd_content,text="RTD Compensation Settings",fg="#333333",
         bg="#f0f0f0",font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 20))

# Checkbox Row
        rtd_frame = tk.Frame(rtd_content, bg="#f0f0f0")
        rtd_frame.pack(fill="x", pady=10)

        tk.Label(rtd_frame,text="Enable RTD Compensation:",width=25,anchor="e",
         bg="#f0f0f0",font=("Arial", 12, "bold")).pack(side="left")

        tk.Checkbutton(rtd_frame,text="Enable",
            variable=controller.apply_rtd_compensation, command=self.on_rtd_compensation_changed,
               bg="#f0f0f0",font=("Arial", 11)).pack(side="left", padx=15)
        
        # Show first tab
        self.show_tab("General")

        
        # ========== FOOTER BUTTONS ==========
        footer_frame = tk.Frame(self, bg="#f0f0f0", height=60)
        footer_frame.pack(fill="x", side="bottom", padx=0, pady=0)
        footer_frame.pack_propagate(False)
        
        tk.Button(footer_frame, text="✔ SAVE & EXIT", bg="#4caf50", fg="white", font=("Arial", 14, "bold"),
                  padx=30, pady=12, relief="raised", command=self.save_and_exit).pack(pady=10)
    def on_rtd_compensation_changed(self):
        """Handle RTD compensation checkbox toggle - send command in background thread (no lag)"""
        enabled = self.controller.apply_rtd_compensation.get()
        logger.info(f"RTD Compensation checkbox toggled: {enabled}")

        # Send hardware command in background thread to avoid UI lag
        def send_command():
            try:
                if (hasattr(self.controller, 'port_manager') and 
                    self.controller.port_manager.serial and 
                    self.controller.port_manager.serial.is_open):
                    cmd = b'RTD_ON\n' if enabled else b'RTD_OFF\n'
                    self.controller.port_manager.serial.write(cmd)
                    logger.info(f"RTD command sent to hardware: {cmd.decode().strip()}")
            except Exception as e:
                logger.error(f"Error sending RTD command: {e}")

        # Run in background thread (no lag on UI)
        thread = threading.Thread(target=send_command, daemon=True)
        thread.start()
    def show_tab(self, tab_name):
        """Show selected tab and update button colors"""
        # Hide all tabs
        for frame in self.tab_frames.values():
            frame.grid_remove()
        
        # Show selected tab with proper grid config
        self.tab_frames[tab_name].grid(row=0, column=0, sticky="nsew")
        
        # if we just navigated to history, refresh the list
        """if tab_name == "History" and hasattr(self, "refresh_history"):"""
            #self.refresh_history()
        
        # Update button colors
        """for btn_name, btn in self.tab_buttons.items():
            if btn_name == tab_name:
                btn.config(bg="#ffffff", relief="sunken")  # Active button
            else:
                btn.config(bg="#b0b0b0", relief="raised")  # Inactive button"""
    
    # ==================== HELPER METHODS ====================

    def refresh_output_ports(self):
       """Refresh available ports in the Outputs tab, excluding connected port"""
    # Get current connected port
       connected_port = self.controller.com_port_val.get()
    
    # Get all available ports
       all_ports = self.controller.port_manager.get_available_ports(exclude_connected=False)
    
    # Manually filter out the connected port if one is connected
       filtered_ports = []
       if connected_port and connected_port != "NOT CONNECTED":
        # Extract device name (e.g., "COM8" from "COM8 - USB Serial Port")
          connected_device = connected_port.split(" - ")[0].strip()
          filtered_ports = [p for p in all_ports if not p.startswith(connected_device)]
          logger.info(f"Excluded connected port: {connected_device}")
       else:
        # No port connected, show all ports
          filtered_ports = all_ports
    
    # Populate the dropdown
       self.output_port_combo["values"] = filtered_ports if filtered_ports else []
    
    # Clear selection (don't auto-select)
       if not self.output_port_combo.get():
          try:
             self.output_port_combo.current(0)
          except Exception:
             pass
    
       logger.info(f"Output ports refreshed: {len(filtered_ports)} available (connected: {connected_port})")

    # ============================================
# ADD THIS NEW METHOD after refresh_output_ports()
# ============================================
    def on_port_changed(self):
       """Callback when connected port changes - auto-refresh output ports"""
       logger.info("Port changed detected - refreshing output ports")
       self.after(100, self.refresh_output_ports)  # Refresh after short delay

    def create_static_row(self, parent, label, value):
        f = tk.Frame(parent, bg="#f0f0f0")
        f.pack(fill="x", pady=8)
        tk.Label(f, text=label, width=20, anchor="e", bg="#f0f0f0", font=("Arial", 12, "bold")).pack(side="left")
        tk.Label(f, text=str(value), anchor="w", bg="#f0f0f0", font=("Arial", 12), fg="#0055aa").pack(side="left", padx=15)

    def create_combobox_row(self, parent, label, var, options):
        f = tk.Frame(parent, bg="#f0f0f0")
        f.pack(fill="x", pady=8)
        tk.Label(f, text=label, width=20, anchor="e", bg="#f0f0f0", font=("Arial", 12, "bold")).pack(side="left")
        ttk.Combobox(f, textvariable=var, values=options, state="readonly", font=("Arial", 11), width=25).pack(side="left", padx=15)

    def create_entry_row(self, parent, label, var):
        f = tk.Frame(parent, bg="#f0f0f0")
        f.pack(fill="x", pady=8)
        tk.Label(f, text=label, width=20, anchor="e", bg="#f0f0f0", font=("Arial", 12, "bold")).pack(side="left")
        tk.Entry(f, textvariable=var, font=("Arial", 11), width=28).pack(side="left", padx=15)

    def create_diag_row(self, parent, label, var):
        f = tk.Frame(parent, bg="#f0f0f0")
        f.pack(fill="x", pady=8)
        tk.Label(f, text=label, width=20, anchor="e", bg="#f0f0f0", font=("Arial", 12, "bold")).pack(side="left")
        tk.Label(f, textvariable=var, anchor="w", bg="#f0f0f0", font=("Courier New", 12), fg="#0066cc").pack(side="left", padx=15)

    def refresh_history(self):
        """Populate history listbox from the database instead of the in-memory buffer.

        Displays the most recent 30 measurements using the same format as when
        data is received.  Conversions are performed using the raw integer
        fields so that no RTD compensation is accidentally applied.
        """
        if not hasattr(self, "history_list"):
            return
        self.history_list.delete(0, tk.END)
        try:
            self.controller.cursor.execute(
                "SELECT timestamp, device_id, temp_raw, rtd_raw, thermo_raw, batt_raw "
                "FROM measurements ORDER BY id DESC LIMIT 30"
            )
            rows = self.controller.cursor.fetchall()
            for ts, dev_id, temp_raw, rtd_raw, thermo_raw, batt_raw in rows:
                # format time only for display
                try:
                    ts_h = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S")
                except Exception:
                    ts_h = ts

                # convert raw thermocouple to temperature without RTD compensation
                melt_temp = voltage_uV_to_temperature_C(raw_to_voltage_uV(thermo_raw))

                # convert RTD raw to temperature
                rtd_res = (rtd_raw * 400) / (2 ** 15)
                try:
                    rtd_temp_val = RTDTemperatureTable.get_temperature_from_resistance(rtd_res)
                except Exception:
                    rtd_temp_val = "--"

                # battery percent calculation (same as dashboard)
                bat_volt = batt_raw / 1000.0
                bat_pct = int(round(100.0 * (bat_volt - 3.0) / (4.2 - 3.0)))
                bat_pct = max(0, min(100, bat_pct))

                entry = (
                    f"{ts_h} | Melt:{melt_temp}{self.controller.units.get()} | "
                    f"RTD:{rtd_temp_val} | Bat:{bat_pct}%"
                )
                #self.history_list.insert(tk.END, entry)
        except Exception:
            # silently ignore if DB not ready
            pass

    def export_csv(self):
        """Export measurements to CSV with converted values.

        The output columns follow the specification:
            Date, Transmitter ID, Melt °C, RTD °C, Device °C, Battery V
        Conversions are applied using the same formulas as in the display code
        but *without* RTD compensation for the melt temperature.  The timestamp
        is reformatted to use a hyphen between date and time.
        """
        filename = filedialog.asksaveasfilename(
           defaultextension=".csv",
           filetypes=[("CSV Files", "*.csv")]
        )

        if not filename:
            return

        try:
            # Build SQL with optional date range
            s_from = getattr(self, 'date_from_var', tk.StringVar()).get().strip()
            s_to = getattr(self, 'date_to_var', tk.StringVar()).get().strip()

            def parse_input_date(s: str, is_start: bool) -> str:
                # Accepts formats: YYYY-MM-DD-HH:MM:SS, YYYY-MM-DD HH:MM:SS, YYYY-MM-DD
                if not s:
                    return None
                fmts = ["%Y-%m-%d-%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
                for fmt in fmts:
                    try:
                        dt = datetime.strptime(s, fmt)
                        if fmt == "%Y-%m-%d":
                            if is_start:
                                dt = dt.replace(hour=0, minute=0, second=0)
                            else:
                                dt = dt.replace(hour=23, minute=59, second=59)
                        # DB timestamps use 'YYYY-MM-DD HH:MM:SS'
                        return dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        continue
                raise ValueError(f"Invalid date format: {s}")

            params = []
            where_clauses = []
            if s_from:
                from_ts = parse_input_date(s_from, True)
                where_clauses.append("timestamp >= ?")
                params.append(from_ts)
            if s_to:
                to_ts = parse_input_date(s_to, False)
                where_clauses.append("timestamp <= ?")
                params.append(to_ts)

            base_sql = "SELECT timestamp,station_name, device_id, temp_raw, rtd_raw, thermo_raw, batt_raw, rssi FROM measurements"
            if where_clauses:
                sql = base_sql + " WHERE " + " AND ".join(where_clauses) + " ORDER BY id ASC"
                self.controller.cursor.execute(sql, params)
            else:
                self.controller.cursor.execute(base_sql + " ORDER BY id ASC")
            rows = self.controller.cursor.fetchall()

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Date", "Station Name", "Transmitter ID", "MeltTemp_C", "RTDTemp_C",
                    "DeviceTemp_C", "BatteryVolts", "RSSI"
                ])
                for ts, dev_id, station_name_db, temp_raw, rtd_raw, thermo_raw, batt_raw, rssi_db in rows:
                    # date formatting
                    try:
                        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                        date_str = dt.strftime("%Y-%m-%d-%H:%M:%S")
                    except Exception:
                        date_str = ts

                    # compute temperatures/voltages
                    melt_temp = voltage_uV_to_temperature_C(raw_to_voltage_uV(thermo_raw))
                    rtd_res = (rtd_raw * 400) / (2 ** 15)
                    try:
                        rtd_temp_val = RTDTemperatureTable.get_temperature_from_resistance(rtd_res)
                    except Exception:
                        rtd_temp_val = ""
                    device_temp = temp_raw / 10000.0
                    batt_volt = batt_raw / 1000.0
                    rssi_str = f"{rssi_db} dBm" if rssi_db else "--"


                    writer.writerow([
                        date_str, station_name_db, dev_id, melt_temp, rtd_temp_val,
                        device_temp, batt_volt, rssi_str
                    ])

            messagebox.showinfo("Export Success", f"Data exported to {filename}")

        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def save_and_exit(self):
        # apply updated graph buffer size based on time scale
        try:
            self.controller.update_buffer_size()
        except Exception:
            pass
        self.controller.show_frame("DashboardFrame")
     
    
    def check_password_for_exit(self):
        
        password = simpledialog.askstring("Confirm", "Enter Password to Confirm:", show='*')
        if password == "1111":
            self.exit_settings()
        elif password is not None:
            messagebox.showerror("Access Denied", "Wrong Password")
    
    
def main():
    """Main entry point"""
    app = SensorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
