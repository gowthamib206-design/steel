"""
Wireless Sensor Data Logger Application
Handles serial communication with wireless sensors and displays temperature/RTD data via GUI
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import struct

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
    
    rtd_values = [ 18.4932,
              18.9258,19.3580,19.7899,20.2215,20.6526,21.0834,21.5139,21.9439,22.3737,22.8031, 
              23.2321,23.6608,24.0891,24.5171,24.9447,25.3720,25.7990,26.2257,26.6520,27.0779,
              27.5036,27.9289,28.3539,28.7786,29.2029,29.6270,30.0507,30.4741,30.8972,31.3200,
              31.7425,32.1646,32.5865,33.0081,33.4294,33.8503,34.2710,34.6914,35.1115,35.5313,
              35.9508,36.3700,36.7889,37.2076,37.6260,38.0440,38.4619,38.8794,39.2967,39.7137,
              40.1304,40.5469,40.9631,41.3790,41.7946,42.2101,42.6252,43.0401,43.4547,43.8691,
              44.2832,44.6971,45.1107,45.5241,45.9372,46.3501,46.7628,47.1752,47.5873,47.9993,
              48.4109,48.8224,49.2336,49.6446,50.0554,50.4659,50.8762,51.2863,51.6962,52.1058,
              52.5152,52.9244,53.3334,53.7422,54.1507,54.5591,54.9672,55.3751,55.7828,56.1903,
              56.5976,57.0047,57.4115,57.8182,58.2247,58.6310,59.0371,59.4429,59.8486,60.2541,
              60.6594,61.0645,61.4695,61.8742,62.2787,62.6831,63.0873,63.4912,63.8950,64.2987,
              64.7021,65.1054,65.5084,65.9114,66.3141,66.7166,67.1190,67.5212,67.9233,68.3251,
              68.7268,69.1284,69.5297,69.9309,70.3319,70.7328,71.1335,71.5340,71.9344,72.3346,
              72.7347,73.1346,73.5343,73.9339,74.3334,74.7326,75.1318,75.5307,75.9296,76.3282,
              76.7268,77.1251,77.5234,77.9214,78.3194,78.7171,79.1148,79.5123,79.9096,80.3068,
              80.7039,81.1008,81.4976,81.8943,82.2908,82.6871,83.0834,83.4795,83.8754,84.2713,
              84.6669,85.0625,85.4579,85.8532,86.2484,86.6434,87.0383,87.4331,87.8277,88.2222,
              88.6166,89.0109,89.4050,89.7990,90.1929,90.5866,90.9802,91.3737,91.7671,92.1603,
              92.5535,92.9465,93.3394,93.7321,94.1247,94.5173,94.9097,95.3019,95.6941,96.0861,
              96.4780,96.8698,97.2615,97.6531,98.0445,98.4359,98.8271,99.2182,99.6091,100.0000,
              100.3907,100.7814,101.1719,101.5623,101.9526,102.3427,102.7328,103.1227,103.5125,  
              103.9022,104.2918,104.6813,105.0706,105.4599,105.8490,106.2380,106.6269,107.0156,107.4043,
              107.7928,108.1813,108.5696,108.9578,109.3458,109.7338,110.1216,110.5094,110.8970,111.2845,
              111.6718,112.0591,112.4463,112.8333,113.2202,113.6070,113.9937,114.3802,114.7667,115.1530,
              115.5392,115.9254,116.3113,116.6972,117.0830,117.4686,117.8541,118.2395,118.6248,119.0100,
              119.3951,119.7800,120.1648,120.5495,120.9341,121.3186,121.7030,122.0872,122.4713,122.8554,
              123.2392,123.6230,124.0067,124.3902,124.7737,125.1570,125.5402,125.9233,126.3063,126.6891,
              127.0718,127.4545,127.8370,128.2194,128.6016,128.9838,129.3658,129.7478,130.1296,130.5113,
              130.8928,131.2743,131.6556,132.0369,132.4180,132.7990,133.1799,133.5606,133.9413,134.3218,
              134.7022,135.0825,135.4627,135.8428,136.2227,136.6026,136.9823,137.3619,137.7414,138.1207,
              138.5000,138.8791,139.2582,139.6371,140.0159,140.3945,140.7731,141.1515,141.5299,141.9081,
              142.2862,142.6642,143.0420,143.4198,143.7974,144.1749,144.5523,144.9296,145.3068,145.6838,
              146.0608,146.4376,146.8143,147.1909,147.5673,147.9437,148.3199,148.6960,149.0721,149.4479,
              149.8237,150.1994,150.5749,150.9504,151.3257,151.7009,152.0759,152.4509,152.8257,153.2005,
              153.5751,153.9496,154.3240,154.6982,155.0724,155.4464,155.8203,156.1941,156.5678,156.9414,
              157.3149,157.6882,158.0614,158.4345,158.8075,159.1804,159.5531,159.9258,160.2983,160.6707,
              161.0430,161.4152,161.7872,162.1592,162.5310,162.9027,163.2743,163.6458,164.0172,164.3884,
              164.7596,165.1306,165.5015,165.8723,166.2429,166.6135,166.9839,167.3542,167.7245,168.0945,
              168.4645,168.8344,169.2041,169.5737,169.9432,170.3126,170.6819,171.0511,171.4201,171.7890,
              172.1579,172.5266,172.8951,173.2636,173.6319,174.0002,174.3683,174.7363,175.1042,175.4719,                                                               175.1042,175.4719,
              175.8396,176.2071,176.5746,176.9419,177.3090,177.6761,178.0431,178.4099,178.7766,179.1432,
              179.5097,179.8761,180.2424,180.6085,180.9745,181.3405,181.7063,182.0719,182.4375,182.8029,
              183.1683,183.5335,183.8986,184.2636,184.6284,184.9932,185.3578,185.7223,186.0867,186.4510,
              186.8152,187.1793,187.5432,187.9070,188.2707,188.6343,188.9978,189.3611,189.7244,190.0875,
              190.4505,190.8134,191.1762,191.5389,191.9014,192.2638,192.6262,192.9884,193.3504,193.7124,
              197.3257,196.9649,196.6040,196.2429,195.8818,195.5205,195.1591,194.7976,194.4360,194.0743,
              197.3257,196.9649,196.6040,196.2429,195.8818,195.5205,195.1591,194.7976,194.4360,194.0743,
              194.0743,194.4360,194.7976,195.1591,195.5205,195.8818,196.2429,196.6040,196.9649,197.3257,
              197.6864,198.0469,198.4074,198.7677,199.1280,199.4881,199.8481,200.2079,200.5677,200.9274,
              201.2869,201.6463,202.0056,202.3648,202.7238,203.0828,203.4416,203.8003,204.1589,204.5174,
              204.8758,205.2340,205.5922,205.9502,206.3081,206.6659,207.0236,207.3811,207.7386,208.0959,
              208.4531,208.8102,209.1672,209.5240,209.8808,210.2374,210.5939,210.9503,211.3066,211.6628,
              212.0188,212.3747,212.7305,213.0862,213.4418,213.7973,214.1527,214.5079,214.8630,215.2180,
              215.5729,215.9277,216.2823,216.6369,216.9913,217.3456,217.6998,218.0539,218.4078,218.7617,
              219.1154,219.4690,219.8225,220.1759,220.5291,220.8823,221.2353,221.5882,221.9410,222.2937,
              222.6463,222.9987,223.3511,223.7033,224.0554,224.4074,224.7592,225.1110,225.4626,225.8142,
              226.1656,226.5169,226.8680,227.2191,227.5700,227.9209,228.2716,228.6222,228.9726,229.3230,
              229.6733,229.6733,230.3734,230.7233,231.0731,231.4227,231.7723,232.1217,232.4710,232.8202,
              233.1693,233.5183,233.8672,234.2159,234.5645,234.9130,235.2614,235.6097,235.9578,236.3059,
              236.6538,237.0016,237.3493,237.6969,238.0443,238.3917,238.7389,239.0860,239.4330,239.7799,
              240.1267,240.4733,240.8199,241.1663,241.5126,241.8588,242.2048,242.5508,242.8966,243.2423,
              243.5879,243.9334,244.2788,244.6241,244.9692,245.3142,245.6591,246.0039,246.3486,246.6932,
              247.0376,247.3819,247.7261,248.0702,248.4142,248.7581,249.1018,249.4455,249.7890,250.1324,
              250.4757,250.8188,251.1619,251.5048,251.8476,252.1903,252.5329,252.8754,253.2177,253.5600,
              253.9021,254.2441,254.5860,254.9278,255.2694,255.6110,255.9524,256.2937,256.6349,256.9760,
              257.3170,257.6578,257.9985,258.3392,258.6797,259.0200,259.3603,259.7005,260.0405,260.3804,
              260.7202,261.0599,261.3995,261.7389,262.0783,262.4175,262.7566,263.0956,263.4344,263.7732, 
              264.1119,264.4504,264.7888,265.1271,265.4653,265.8033,266.1413,266.4791,266.8168,267.1544,
              267.4919,267.8293,268.1665,268.5036,268.8407,269.1776,269.5143,269.8510,270.1876,270.5240,
              270.8603,271.1965,271.5326,271.8686,272.2044,272.5402,272.8758,273.2113,273.5467,273.8820,  
              274.2172,274.5522,274.8871,275.2219,275.5566,275.8912,276.2257,276.5600,276.8943,277.2284, 
              277.5624,277.8963,278.2300,278.5637,278.8972,279.2306,279.5639,279.8971,280.2302,280.5632,
              280.8960,281.2287,281.5613,281.8938,282.2262,282.5585,282.8906,283.2226,283.5545,283.8863, 
              284.2180,284.5496,284.8810,285.2124,285.5436,285.8747,286.2057,286.5365,286.8673,287.1979,
              287.5284,287.8588,288.1891,288.5193,288.8493,289.1793,289.5091,289.8388,290.1684,290.4979,
              293.7862,293.4579,293.1295,292.8010,292.4723,292.1435,291.8146,291.4856,291.1565,290.8272,
              290.8272,291.1565,291.4856,291.8146,292.1435,292.4723,292.8010,293.1295,293.4579,293.7862,
              294.1144,294.4425,294.7705,295.0983,295.4261,295.7537,296.0812,296.4086,296.7359,297.0630,
              297.3901,297.7170,298.0438,298.3705,298.6970,299.0235,299.3498,299.6761,300.0022,300.3282,
              300.6540,300.9798,301.3055,301.6310,301.9564,302.2817,302.6069,302.9319,303.2569,303.5817,
              303.9064,304.2310,304.5555,304.8799,305.2042,305.5283,305.8523,306.1762,306.5000,306.8237,
              307.1472,307.4707,307.7940,308.1172,308.4403,308.7633,309.0861,309.4089,309.7315,310.0540,
              310.3764,310.6987,311.0209,311.3429,311.6648,311.9867,312.3084,312.6299,312.9514,313.2728,
              313.5940,313.9151,314.2361,314.5570,314.8778,315.1984,315.5190,315.8394,316.1597,316.4799,
              316.8000,317.1199,317.4398,317.7595,318.0791,318.3986,318.7180,319.0373,319.3564,319.6754,
              319.9944,320.3132,320.6318,320.9504,321.2689,321.5872,321.9054,322.2235,322.5415,322.8594,
              323.1771,323.4948,323.8123,324.1297,324.4470,324.7642,325.0812,325.3982,325.7150,326.0317,
              326.3483,326.6648,326.9811,327.2974,327.6135,327.9295,328.2454,328.5612,328.8769,329.1924,
              329.5079,329.8232,330.1384,330.4535,330.7684,331.0833,331.3980,331.7126,332.0271,332.3415,
              332.6558,332.9700,333.2840,333.5979,333.9117,334.2254,334.5390,334.8525,335.1658,335.4790,
              335.7922,336.1052,336.4180,336.7308,337.0435,337.3560,337.6684,337.9807,338.2929,338.6050,
              338.9169,339.2287,339.5405,339.8521,340.1636,340.4749,340.7862,341.0973,341.4084,341.7193,
              342.0301,342.3407,342.6513,342.9617,343.2721,343.5823,343.8924,344.2024,344.5122,344.8220,
              345.1316,345.4411,345.7505,346.0598,346.3690,346.6780,346.9870,347.2958,347.6045,347.9131,
              348.2215,348.5299,348.8381,349.1463,349.4543,349.7622,350.0699,350.3776,350.6851,350.9926,
              354.0605,353.7542,353.4478,353.1413,352.8347,352.5280,352.2211,351.9141,351.6071,351.2999,
              351.2999,351.6071,351.9141,352.2211,352.5280,352.8347,353.1413,353.4478,353.7542,354.0605,
              354.3666,354.6726,354.9786,355.2844,355.5900,355.8956,356.2011,356.5064,356.8116,357.1167,
              357.4217,357.7266,358.0314,358.3360,358.6405,358.9449,359.2492,359.5534,359.8575,360.1614,
              363.4972,363.7997,364.1022,364.4045,364.7067,365.0088,365.3107,365.6126,365.9143,366.2160,
              366.5175,366.8189,367.1202,367.4213,367.7224,368.0233,368.3241,368.6248,368.9254,369.2258,
              369.5262,369.8264,370.1265,370.4265,370.7264,371.0262,371.3258,371.6254,371.9248,372.2241,
              372.5233,372.8224,373.1213,373.4202,373.7189,374.0175,374.3160,374.6144,374.9126,375.2108,
              375.5088,375.8067,376.1045,376.4022,376.6998,376.9972,377.2945,377.5917,377.8888,378.1858,
              378.4827,378.7794,379.0761,379.3726,379.6690,379.9653,380.2615,380.5575,380.8535,381.1493,
              381.4450,381.7406,382.0361,382.3314,382.6267,382.9218,383.2168,383.5117,383.8065,384.1011,
              384.3957,384.6901,384.9844,385.2786,385.5727,385.8667,386.1605,386.4543,386.7479,387.0414,   
              387.3348,387.6280,387.9212,388.2142,388.5072,388.8000,389.0926,389.3852,389.6777,389.9700,
              390.2623]
    
    thermos_values = [ 0.000,0.000,0.000,-0.001,-0.001,-0.001,-0.001,-0.001,-0.002,-0.002,-0.002 ,
                  -0.002,-0.002,-0.002,-0.002,-0.002,-0.002,-0.002,-0.002,-0.003,-0.003,-0.003, 
                  -0.003,-0.003,-0.003,-0.003,-0.003,-0.002,-0.002,-0.002,-0.002,-0.002,-0.002, 
                  -0.002,-0.002,-0.002,-0.002,-0.002,-0.001,-0.001,-0.001,-0.001,-0.001,0.000 ,
                   0.000,0.000,0.000,0.000,0.000,0.001,0.001,0.001,0.002,0.002,0.002, 
                   0.002,0.003,0.003,0.003,0.004,0.004,0.004,0.005,0.005,0.006,0.006, 
                   0.006,0.007,0.007,0.008,0.008,0.009,0.009,0.010,0.010,0.011,0.011, 
                   0.011,0.012,0.012,0.013,0.014,0.014,0.015,0.015,0.016,0.017,0.017, 
                   0.017,0.018,0.019,0.020,0.020,0.021,0.022,0.022,0.023,0.024,0.025, 
                   0.025,0.026,0.026,0.027,0.028,0.029,0.030,0.031,0.031,0.032,0.033, 
                   0.033,0.034,0.035,0.036,0.037,0.038,0.039,0.040,0.041,0.042,0.043, 
                   0.043,0.044,0.045,0.046,0.047,0.048,0.049,0.050,0.051,0.052,0.053, 
                   0.053,0.055,0.056,0.057,0.058,0.059,0.060,0.062,0.063,0.064,0.065, 
                   0.065,0.066,0.068,0.069,0.070,0.072,0.073,0.074,0.075,0.077,0.078, 
                   0.078,0.079,0.081,0.082,0.084,0.085,0.086,0.088,0.089,0.091,0.092,
                   0.092,0.094,0.095,0.096,0.098,0.099,0.101,0.102,0.104,0.106,0.107, 
                   0.107,0.109,0.110,0.112,0.113,0.115,0.117,0.118,0.120,0.122,0.123, 
                   0.123,0.125,0.127,0.128,0.130,0.132,0.134,0.135,0.137,0.139,0.141,
                   0.141,0.142,0.144,0.146,0.148,0.150,0.151,0.153,0.155,0.157,0.159,
                   0.159,0.161,0.163,0.165,0.166,0.168,0.170,0.172,0.174,0.176,0.178,
                   0.178,0.180,0.182,0.184,0.186,0.188,0.190,0.192,0.195,0.197,0.199,
                   0.199,0.201,0.203,0.205,0.207,0.209,0.212,0.214,0.216,0.218,0.220,
                   0.220,0.222,0.225,0.227,0.229,0.231,0.234,0.236,0.238,0.241,0.243,
                   0.243,0.245,0.248,0.250,0.252,0.255,0.257,0.259,0.262,0.264,0.267,
                   0.267,0.269,0.271,0.274,0.276,0.279,0.281,0.284,0.286,0.289,0.291,
                   0.431,0.434,0.437,0.440,0.443,0.446,0.449,0.452,0.455,0.458,0.462,
                   0.462,0.465,0.468,0.471,0.474,0.478,0.481,0.484,0.487,0.490,0.494,
                   0.494,0.497,0.500,0.503,0.507,0.510,0.513,0.517,0.520,0.523,0.527,
                   0.527,0.530,0.533,0.537,0.540,0.544,0.547,0.550,0.554,0.557,0.561,
                   0.561,0.564,0.568,0.571,0.575,0.578,0.582,0.585,0.589,0.592,0.596,
                   0.596,0.599,0.603,0.607,0.610,0.614,0.617,0.621,0.625,0.628,0.632,
                   0.632,0.636,0.639,0.643,0.647,0.650,0.654,0.658,0.662,0.665,0.669,
                   0.669,0.673,0.677,0.680,0.684,0.688,0.692,0.696,0.700,0.703,0.707,
                   0.707,0.711,0.715,0.719,0.723,0.727,0.731,0.735,0.738,0.742,0.746,
                   0.746,0.750,0.754,0.758,0.762,0.766,0.770,0.774,0.778,0.782,0.787,
    ]
    
    temperatures = list(range(-200, -200 + len(rtd_values)))

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
            # Extract temperature (bytes 1-4)
            temp = packet[4]
            temp = (temp << 8) | packet[3]
            temp = (temp << 8) | packet[2]
            temp = (temp << 8) | packet[1]
            temp = temp / 10000.0
            
            if temp < -100 or temp > 100:
                logger.warning(f"Temperature out of reasonable range: {temp}")
            
            # Extract device ID (bytes 7-10)
            device_id = f"{packet[7]} {packet[8]} {packet[9]} {packet[10]}"
            
            # Extract RTD (bytes 11-12)
            rtd = packet[12]
            rtd = (rtd << 8) | packet[11]
            rtd_resistance = (rtd * 400) / (2**15)
            
            if rtd_resistance < 0:
                logger.error(f"Negative RTD resistance: {rtd_resistance}")
                raise ValueError("RTD resistance cannot be negative")
            
            # Convert RTD resistance to temperature
            try:
                rtd_temperature = RTDTemperatureTable.get_temperature_from_resistance(rtd_resistance)
            except ValueError as e:
                logger.error(f"Failed to convert RTD: {e}")
                rtd_temperature = 0
            
            # Extract thermocouple (bytes 13-14)
            thermo = packet[14]
            thermo = (thermo << 8) | packet[13]
            
            # Extract battery voltage (bytes 15-16)
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


class SensorGUI:
    """GUI for wireless sensor data logger"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("USB Logger - Wireless Sensor Data")
        self.root.geometry("1200x500")
        
        self.port_manager = SerialPortManager()
        self.packet_processor = PacketProcessor()
        self.data_parser = SensorDataParser()
        
        self.is_reading = False
        
        self._create_widgets()
        self._update_ports()
    
    def _create_widgets(self):
        """Create GUI widgets"""
        container = tk.Frame(self.root)
        container.pack(fill="both", expand=True, pady=15, padx=15)
        
        # Left frame - Controls
        left_frame = tk.Frame(container)
        left_frame.pack(side=tk.LEFT, fill="y", anchor="n", expand=True, padx=10, pady=10)
        
        # Device ID
        device_id_label = tk.Label(left_frame, text="Device ID:", font=("Arial", 14), anchor="w", fg="#333")
        device_id_label.pack(side="top", pady=(10, 5), anchor="w")
        
        self.device_id_value = tk.Label(left_frame, text="--", font=("Arial", 32, "bold"), anchor="w", fg="#0066cc")
        self.device_id_value.pack(side="top", pady=(0, 15), anchor="w")
        
        # Battery Voltage
        battery_voltage_label = tk.Label(left_frame, text="Battery Voltage:", font=("Arial", 14), anchor="w", fg="#333")
        battery_voltage_label.pack(side="top", pady=(10, 5), anchor="w")
        
        self.battery_voltage_value = tk.Label(left_frame, text="--", font=("Arial", 32, "bold"), anchor="w", fg="#0066cc")
        self.battery_voltage_value.pack(side="top", pady=(0, 15), anchor="w")
        
        # Bottom controls
        bottom_frame = tk.Frame(left_frame)
        bottom_frame.pack(side="bottom", fill="x", pady=15)
        
        ports_label = tk.Label(bottom_frame, text="Available Ports:", font=("Arial", 11), fg="#333")
        ports_label.pack(anchor="w", pady=(0, 5))
        
        self.combo = ttk.Combobox(bottom_frame, width=40, state="readonly", font=("Arial", 10))
        self.combo.pack(pady=8, anchor="w")
        
        btn_frame = tk.Frame(bottom_frame)
        btn_frame.pack(pady=10)
        
        self.btn_refresh = tk.Button(btn_frame, text="Refresh", command=self._update_ports, 
                                     font=("Arial", 10), width=10, bg="#e0e0e0")
        self.btn_refresh.pack(side=tk.LEFT, padx=5)
        
        self.btn_open = tk.Button(btn_frame, text="Open", command=self._open_port, 
                                  font=("Arial", 10), width=10, bg="#90EE90")
        self.btn_open.pack(side=tk.LEFT, padx=5)
        
        self.btn_close = tk.Button(btn_frame, text="Close", command=self._close_port, 
                                   font=("Arial", 10), width=10, bg="#FFB6C1", state="disabled")
        self.btn_close.pack(side=tk.LEFT, padx=5)
        
        # Right frame - Display
        right_frame = tk.Frame(container)
        right_frame.pack(side=tk.RIGHT, expand=True, padx=10, pady=10)
        
        self.status_label = tk.Label(right_frame, text="Ready", fg="#006600", font=("Arial", 9))
        self.status_label.pack(pady=(0, 10))
        
        # Main temperature display
        temp_display_frame = tk.Frame(right_frame)
        temp_display_frame.pack(pady=20, expand=True)
        
        temp_label = tk.Label(temp_display_frame, text="Temperature", font=("Arial", 16), fg="#333")
        temp_label.pack(pady=(0, 10))
        
        self.temp_value = tk.Label(temp_display_frame, text="--", font=("Arial", 120, "bold"), fg="#d9534f")
        self.temp_value.pack()
        
        # Secondary sensors
        sensor_frame = tk.Frame(right_frame)
        sensor_frame.pack(pady=10, fill="x")
        
        rtd_label = tk.Label(sensor_frame, text="RTD (Temp):", font=("Arial", 12), anchor="e", fg="#333")
        rtd_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.rtd_value = tk.Label(sensor_frame, text="--", font=("Arial", 28, "bold"), width=8, anchor="w", fg="#5cb85c")
        self.rtd_value.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        thermo_label = tk.Label(sensor_frame, text="Thermocouple:", font=("Arial", 12), anchor="e", fg="#333")
        thermo_label.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.thermo_value = tk.Label(sensor_frame, text="--", font=("Arial", 28, "bold"), width=8, anchor="w", fg="#0275d8")
        self.thermo_value.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
    
    def _update_ports(self):
        """Update available ports dropdown"""
        ports = self.port_manager.get_available_ports()
        if not ports:
            self.combo['values'] = []
            self.status_label.config(text="No ports available", fg="#cc0000")
            messagebox.showwarning("No Ports", "No serial ports found")
        else:
            self.combo['values'] = ports
            self.combo.current(0)
            self.status_label.config(text=f"Found {len(ports)} port(s)", fg="#006600")
    
    def _open_port(self):
        """Open selected serial port"""
        sel = self.combo.get()
        if not sel:
            self.status_label.config(text="No port selected", fg="#cc0000")
            messagebox.showerror("Error", "Please select a port")
            return
        
        success, msg = self.port_manager.open_port(sel)
        if success:
            self.status_label.config(text=f"Opened: {sel}", fg="#006600")
            self.btn_open.config(state="disabled")
            self.btn_refresh.config(state="disabled")
            self.btn_close.config(state="normal")
            self.is_reading = True
            self._read_data()
        else:
            self.status_label.config(text=msg, fg="#cc0000")
            messagebox.showerror("Error", msg)
    
    def _close_port(self):
        """Close serial port"""
        success, msg = self.port_manager.close_port()
        self.is_reading = False
        self.status_label.config(text=msg, fg="#006600" if success else "#cc0000")
        self.btn_close.config(state="disabled")
        self.btn_refresh.config(state="normal")
        self.btn_open.config(state="normal")
        self.packet_processor.reset()
    
    def _read_data(self):
        """Read data from serial port"""
        if not self.is_reading or not self.port_manager.is_open:
            self.status_label.config(text="Waiting for connection...", fg="#999999")
            return
        
        try:
            data = self.port_manager.read_byte()
            if data:
                packet = self.packet_processor.process_byte(data)
                if packet:
                    self._process_sensor_data(packet)
            else:
                self.status_label.config(text="Waiting for data...", fg="#999999")
        except Exception as e:
            logger.error(f"Error in read_data: {e}")
            self.status_label.config(text=f"Error: {e}", fg="#cc0000")
        
        if self.is_reading:
            self.root.after(1, self._read_data)
    
    def _process_sensor_data(self, packet: List[int]):
        """Process and display sensor data"""
        try:
            sensor_data = self.data_parser.parse_packet(packet)
            self.temp_value.config(text=str(sensor_data.temperature))
            self.device_id_value.config(text=sensor_data.device_id)
            self.rtd_value.config(text=str(sensor_data.rtd_temperature))
            self.thermo_value.config(text=str(sensor_data.thermocouple))
            self.battery_voltage_value.config(text=f"{sensor_data.battery_voltage:.2f} V")
            self.status_label.config(text="Receiving data...", fg="#006600")
        except ValueError as e:
            logger.error(f"Data parsing error: {e}")
            self.status_label.config(text=f"Parse error: {e}", fg="#ff9900")
        except Exception as e:
            logger.error(f"Unexpected error processing data: {e}")
            self.status_label.config(text=f"Error: {e}", fg="#cc0000")


def main():
    """Main application entry point"""
    root = tk.Tk()
    gui = SensorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()    