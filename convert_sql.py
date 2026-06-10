"""
SQLite DB Viewer with Date Range Filter
- White background
- Load + Export CSV buttons only
- Decodes 16-byte sensor packets into named fields
"""

import sqlite3
import csv
import calendar
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

# ─────────────────────────────────────────────────────────────
#  Packet decoder — maps b0..b15 columns to named sensor fields
# ─────────────────────────────────────────────────────────────

# Columns that come from the raw-byte table (serial_packets.db)
RAW_BYTE_COLS = {f"b{i}" for i in range(16)}

# Named fields and their display order
DECODED_FIELDS = [
    "OXY ADC",
    "OXY (mV)",
    "RSSI (dBm)",
    "Packet Type",
    "TX ID",
    "TC ADC",
    "TC (mV)",
    "Melt Temp (°C)",
    "Seq No",
]

# ─────────────────────────────────────────────────────────────
#  RTD resistance → temperature lookup table 
# ─────────────────────────────────────────────────────────────
_RTD_VALUES = [
    18.4932, 18.9258, 19.3580, 19.7899, 20.2215, 20.6526, 21.0834, 21.5139,
    21.9439, 22.3737, 22.8031, 23.2321, 23.6608, 24.0891, 24.5171, 24.9447,
    25.3720, 25.7990, 26.2257, 26.6520, 27.0779, 27.5036, 27.9289, 28.3539,
    28.7786, 29.2029, 29.6270, 30.0507, 30.4741, 30.8972, 31.3200, 31.7425,
    32.1646, 32.5865, 33.0081, 33.4294, 33.8503, 34.2710, 34.6914, 35.1115,
    35.5313, 35.9508, 36.3700, 36.7889, 37.2076, 37.6260, 38.0440, 38.4619,
    38.8794, 39.2967, 39.7137, 40.1304, 40.5469, 40.9631, 41.3790, 41.7946,
    42.2101, 42.6252, 43.0401, 43.4547, 43.8691, 44.2832, 44.6971, 45.1107,
    45.5241, 45.9372, 46.3501, 46.7628, 47.1752, 47.5873, 47.9993, 48.4109,
    48.8224, 49.2336, 49.6446, 50.0554, 50.4659, 50.8762, 51.2863, 51.6962,
    52.1058, 52.5152, 52.9244, 53.3334, 53.7422, 54.1507, 54.5591, 54.9672,
    55.3751, 55.7828, 56.1903, 56.5976, 57.0047, 57.4115, 57.8182, 58.2247,
    58.6310, 59.0371, 59.4429, 59.8486, 60.2541, 60.6594, 61.0645, 61.4695,
    61.8742, 62.2787, 62.6831, 63.0873, 63.4912, 63.8950, 64.2987, 64.7021,
    65.1054, 65.5084, 65.9114, 66.3141, 66.7166, 67.1190, 67.5212, 67.9233,
    68.3251, 68.7268, 69.1284, 69.5297, 69.9309, 70.3319, 70.7328, 71.1335,
    71.5340, 71.9344, 72.3346, 72.7347, 73.1346, 73.5343, 73.9339, 74.3334,
    74.7326, 75.1318, 75.5307, 75.9296, 76.3282, 76.7268, 77.1251, 77.5234,
    77.9214, 78.3194, 78.7171, 79.1148, 79.5123, 79.9096, 80.3068, 80.7039,
    81.1008, 81.4976, 81.8943, 82.2908, 82.6871, 83.0834, 83.4795, 83.8754,
    84.2713, 84.6669, 85.0625, 85.4579, 85.8532, 86.2484, 86.6434, 87.0383,
    87.4331, 87.8277, 88.2222, 88.6166, 89.0109, 89.4050, 89.7990, 90.1929,
    90.5866, 90.9802, 91.3737, 91.7671, 92.1603, 92.5535, 92.9465, 93.3394,
    93.7321, 94.1247, 94.5173, 94.9097, 95.3019, 95.6941, 96.0861, 96.4780,
    96.8698, 97.2615, 97.6531, 98.0445, 98.4359, 98.8271, 99.2182, 99.6091,
    100.0000, 100.3907, 100.7814, 101.1719, 101.5623, 101.9526, 102.3427,
    102.7328, 103.1227, 103.5125, 103.9022, 104.2918, 104.6813, 105.0706,
    105.4599, 105.8490, 106.2380, 106.6269, 107.0156, 107.4043, 107.7928,
    108.1813, 108.5696, 108.9578, 109.3458, 109.7338, 110.1216, 110.5094,
    110.8970, 111.2845, 111.6718, 112.0591, 112.4463, 112.8333, 113.2202,
    113.6070, 113.9937, 114.3802, 114.7667, 115.1530, 115.5392, 115.9254,
    116.3113, 116.6972, 117.0830, 117.4686, 117.8541, 118.2395, 118.6248,
    119.0100, 119.3951, 119.7800, 120.1648, 120.5495, 120.9341, 121.3186,
    121.7030, 122.0872, 122.4713, 122.8554, 123.2392, 123.6230, 124.0067,
    124.3902, 124.7737, 125.1570, 125.5402, 125.9233, 126.3063, 126.6891,
    127.0718, 127.4545, 127.8370, 128.2194, 128.6016, 128.9838, 129.3658,
    129.7478, 130.1296, 130.5113, 130.8928, 131.2743, 131.6556, 132.0369,
    132.4180, 132.7990, 133.1799, 133.5606, 133.9413, 134.3218, 134.7022,
    135.0825, 135.4627, 135.8428, 136.2227, 136.6026, 136.9823, 137.3619,
    137.7414, 138.1207, 138.5000, 138.8791, 139.2582, 139.6371, 140.0159,
    140.3945, 140.7731, 141.1515, 141.5299, 141.9081, 142.2862, 142.6642,
    143.0420, 143.4198, 143.7974, 144.1749, 144.5523, 144.9296, 145.3068,
    145.6838, 146.0608, 146.4376, 146.8143, 147.1909, 147.5673, 147.9437,
    148.3199, 148.6960, 149.0721, 149.4479, 149.8237, 150.1994, 150.5749,
    150.9504, 151.3257, 151.7009, 152.0759, 152.4509, 152.8257, 153.2005,
    153.5751, 153.9496, 154.3240, 154.6982, 155.0724, 155.4464, 155.8203,
    156.1941, 156.5678, 156.9414, 157.3149, 157.6882, 158.0614, 158.4345,
    158.8075, 159.1804, 159.5531, 159.9258, 160.2983, 160.6707, 161.0430,
    161.4152, 161.7872, 162.1592, 162.5310, 162.9027, 163.2743, 163.6458,
    164.0172, 164.3884, 164.7596, 165.1306, 165.5015, 165.8723, 166.2429,
    166.6135, 166.9839, 167.3542, 167.7245, 168.0945, 168.4645, 168.8344,
    169.2041, 169.5737, 169.9432, 170.3126, 170.6819, 171.0511, 171.4201,
    171.7890, 172.1579, 172.5266, 172.8951, 173.2636, 173.6319, 174.0002,
    174.3683, 174.7363, 175.1042, 175.4719, 175.8396, 176.2071, 176.5746,
    176.9419, 177.3090, 177.6761, 178.0431, 178.4099, 178.7766, 179.1432,
    179.5097, 179.8761, 180.2424, 180.6085, 180.9745, 181.3405, 181.7063,
    182.0719, 182.4375, 182.8029, 183.1683, 183.5335, 183.8986, 184.2636,
    184.6284, 184.9932, 185.3578, 185.7223, 186.0867, 186.4510, 186.8152,
    187.1793, 187.5432, 187.9070, 188.2707, 188.6343, 188.9978, 189.3611,
    189.7244, 190.0875, 190.4505, 190.8134, 191.1762, 191.5389, 191.9014,
    192.2638, 192.6262, 192.9884, 193.3504, 193.7124, 197.3257, 196.9649,
    196.6040, 196.2429, 195.8818, 195.5205, 195.1591, 194.7976, 194.4360,
    194.0743, 194.0743, 194.4360, 194.7976, 195.1591, 195.5205, 195.8818,
    196.2429, 196.6040, 196.9649, 197.3257, 197.6864, 198.0469, 198.4074,
    198.7677, 199.1280, 199.4881, 199.8481, 200.2079, 200.5677, 200.9274,
    201.2869, 201.6463, 202.0056, 202.3648, 202.7238, 203.0828, 203.4416,
    203.8003, 204.1589, 204.5174, 204.8758, 205.2340, 205.5922, 205.9502,
    206.3081, 206.6659, 207.0236, 207.3811, 207.7386, 208.0959, 208.4531,
    208.8102, 209.1672, 209.5240, 209.8808, 210.2374, 210.5939, 210.9503,
    211.3066, 211.6628, 212.0188, 212.3747, 212.7305, 213.0862, 213.4418,
    213.7973, 214.1527, 214.5079, 214.8630, 215.2180, 215.5729, 215.9277,
    216.2823, 216.6369, 216.9913, 217.3456, 217.6998, 218.0539, 218.4078,
    218.7617, 219.1154, 219.4690, 219.8225, 220.1759, 220.5291, 220.8823,
    221.2353, 221.5882, 221.9410, 222.2937, 222.6463, 222.9987, 223.3511,
    223.7033, 224.0554, 224.4074, 224.7592, 225.1110, 225.4626, 225.8142,
    226.1656, 226.5169, 226.8680, 227.2191, 227.5700, 227.9209, 228.2716,
    228.6222, 228.9726, 229.3230, 229.6733, 229.6733, 230.3734, 230.7233,
    231.0731, 231.4227, 231.7723, 232.1217, 232.4710, 232.8202, 233.1693,
    233.5183, 233.8672, 234.2159, 234.5645, 234.9130, 235.2614, 235.6097,
    235.9578, 236.3059, 236.6538, 237.0016, 237.3493, 237.6969, 238.0443,
    238.3917, 238.7389, 239.0860, 239.4330, 239.7799, 240.1267, 240.4733,
    240.8199, 241.1663, 241.5126, 241.8588, 242.2048, 242.5508, 242.8966,
    243.2423, 243.5879, 243.9334, 244.2788, 244.6241, 244.9692, 245.3142,
    245.6591, 246.0039, 246.3486, 246.6932, 247.0376, 247.3819, 247.7261,
    248.0702, 248.4142, 248.7581, 249.1018, 249.4455, 249.7890, 250.1324,
    250.4757, 250.8188, 251.1619, 251.5048, 251.8476, 252.1903, 252.5329,
    252.8754, 253.2177, 253.5600, 253.9021, 254.2441, 254.5860, 254.9278,
    255.2694, 255.6110, 255.9524, 256.2937, 256.6349, 256.9760, 257.3170,
    257.6578, 257.9985, 258.3392, 258.6797, 259.0200, 259.3603, 259.7005,
    260.0405, 260.3804, 260.7202, 261.0599, 261.3995, 261.7389, 262.0783,
    262.4175, 262.7566, 263.0956, 263.4344, 263.7732, 264.1119, 264.4504,
    264.7888, 265.1271, 265.4653, 265.8033, 266.1413, 266.4791, 266.8168,
    267.1544, 267.4919, 267.8293, 268.1665, 268.5036, 268.8407, 269.1776,
    269.5143, 269.8510, 270.1876, 270.5240, 270.8603, 271.1965, 271.5326,
    271.8686, 272.2044, 272.5402, 272.8758, 273.2113, 273.5467, 273.8820,
    274.2172, 274.5522, 274.8871, 275.2219, 275.5566, 275.8912, 276.2257,
    276.5600, 276.8943, 277.2284, 277.5624, 277.8963, 278.2300, 278.5637,
    278.8972, 279.2306, 279.5639, 279.8971, 280.2302, 280.5632, 280.8960,
    281.2287, 281.5613, 281.8938, 282.2262, 282.5585, 282.8906, 283.2226,
    283.5545, 283.8863, 284.2180, 284.5496, 284.8810, 285.2124, 285.5436,
    285.8747, 286.2057, 286.5365, 286.8673, 287.1979, 287.5284, 287.8588,
    288.1891, 288.5193, 288.8493, 289.1793, 289.5091, 289.8388, 290.1684,
    290.4979, 293.7862, 293.4579, 293.1295, 292.8010, 292.4723, 292.1435,
    291.8146, 291.4856, 291.1565, 290.8272, 290.8272, 291.1565, 291.4856,
    291.8146, 292.1435, 292.4723, 292.8010, 293.1295, 293.4579, 293.7862,
]

def _rtd_resistance_to_temperature(resistance: float) -> int:
    """Convert RTD resistance to temperature using lookup table (index - 200 = °C)."""
    idx = min(range(len(_RTD_VALUES)), key=lambda i: abs(_RTD_VALUES[i] - resistance))
    return idx - 200


# ─────────────────────────────────────────────────────────────
#  Thermocouple raw → µV → °C 
# ─────────────────────────────────────────────────────────────
_TC_COEFFS_LOW  = [9.8423321e1, 6.9971500e-1, -8.4765304e-4, 1.0052644e-6,
                   -8.3345952e-10, 4.5508542e-13, -1.5523037e-16,
                   2.9886750e-20, -2.4742860e-24]
_TC_COEFFS_HIGH = [2.1315071e2, 2.8510504e-1, -5.2742887e-5, 9.9160804e-9,
                   -1.2965303e-12, 1.1195870e-16, -6.0625199e-21,
                   1.8661696e-25, -2.4878585e-30]

# Type-B temp→µV polynomials (kept for optional RTD compensation)
_TC_T2UV_LOW  = [0.0, -2.465081834600e-1, 5.904042111700e-3,
                 -1.325793163600e-6, 1.566829190100e-9,
                 -1.694452924000e-12, 6.229034709400e-16]
_TC_T2UV_HIGH = [-3.8938168621e3, 2.8571747470e1, -8.4885104785e-3,
                  1.5785280164e-6, -1.6835344864e-10, 1.1109794013e-14,
                  -4.4515431033e-18, 9.8975640821e-23, -9.3791330289e-28]


def _raw_to_uV(raw: int) -> float:
   
    return (raw * 1_250_000.0) / (32.0 * (2 ** 16))


def _uV_to_temp(uV: float) -> float:
   
    # LOW range: 291 µV – 2431 µV
    if 291.0 <= uV <= 2431.0:
        coeffs = _TC_COEFFS_LOW
    # HIGH range: 2431 µV – 13820 µV
    elif 2431.0 < uV <= 13820.0:
        coeffs = _TC_COEFFS_HIGH
    else:
        # outside range — extrapolate with nearest
        coeffs = _TC_COEFFS_LOW if uV < 291.0 else _TC_COEFFS_HIGH
    return sum(c * (uV ** i) for i, c in enumerate(coeffs))


def _temp_to_uV(t: float) -> float:
   
    if 0.0 <= t <= 630.615:
        coeffs = _TC_T2UV_LOW
    elif 630.615 < t <= 1820.0:
        coeffs = _TC_T2UV_HIGH
    else:
        coeffs = _TC_T2UV_LOW if t < 0.0 else _TC_T2UV_HIGH
    return sum(c * (t ** i) for i, c in enumerate(coeffs))


def _thermocouple_temperature(thermo_raw: int, rtd_temperature: int) -> float:
    """Apply RTD compensation and return thermocouple temperature in °C."""
    thermo_uV = _raw_to_uV(thermo_raw)
    rtd_uV    = _temp_to_uV(rtd_temperature)
    return _uV_to_temp(thermo_uV + rtd_uV)


def _decode_packet_row(row, columns):
    """
    Packet layout:
      0-3:   OXY ADC    (4 bytes, little-endian)
      4:     RSSI
      5:     Packet type
      6-9:   TX ID address
      10-13: TC ADC     (thermocouple, 4 bytes, little-endian)
      14-15: Packet sequence number
    """
    col_lower = [c.lower() for c in columns]
    if not all(f"b{i}" in col_lower for i in range(16)):
        return None

    idx = {c.lower(): i for i, c in enumerate(columns)}

    def b(n):
        v = row[idx[f"b{n}"]]
        return int(v) if v is not None else 0

    # OXY ADC: bytes 0-3 little-endian → mV = (oxy_raw / 2^23) * (2500/8)
    oxy_raw = b(0) | (b(1) << 8) | (b(2) << 16) | (b(3) << 24)
    oxy_mV  = (oxy_raw / (2**23)) * (2500 / 8)
    rtd_temperature = oxy_mV  # display mV as the RTD value

    # RSSI: byte 4, subtract 128
    rssi = b(4) - 128

    # Packet type: byte 5
    pkt_type = b(5)

    # TX ID: bytes 6-9
    tx_id = f"{b(6):02x} {b(7):02x} {b(8):02x} {b(9):02x}"

    # TC ADC: bytes 10-13 little-endian → mV = (tc_raw / 2^23) * (2500/128)
    tc_raw = b(10) | (b(11) << 8) | (b(12) << 16) | (b(13) << 24)
    tc_mV  = (tc_raw / (2**23)) * (2500 / 128)
    thermo_temp = tc_mV

    # Packet sequence: bytes 14-15 little-endian
    seq = b(14) | (b(15) << 8)

    return {
        "OXY ADC":              str(oxy_raw),
        "OXY (mV)":             f"{oxy_mV:.4f}",
        "RSSI (dBm)":           str(rssi),
        "Packet Type":          str(pkt_type),
        "TX ID":                tx_id,
        "TC ADC":               str(tc_raw),
        "TC (mV)":              f"{tc_mV:.4f}",
        "Melt Temp (°C)":       f"{thermo_temp:.4f}",
        "Seq No":               str(seq),
    }


# ─────────────────────────────────────────────────────────────
#  DateTimePopup  — single calendar + time picker
# ─────────────────────────────────────────────────────────────

class DateTimePopup(tk.Toplevel):
    def __init__(self, parent, select_callback):
        super().__init__(parent)
        self.withdraw()
        self.transient(parent)
        self.title('Select Date and Time')
        self.select_callback = select_callback
        self.resizable(False, False)

        now = datetime.now()
        self.year   = now.year
        self.month  = now.month
        self.day    = None
        self.hour_var   = tk.StringVar(value=str(now.hour).zfill(2))
        self.minute_var = tk.StringVar(value=str(now.minute).zfill(2))
        self.second_var = tk.StringVar(value=str(now.second).zfill(2))

        body = tk.Frame(self, bg="white")
        body.pack(padx=10, pady=10)

        # Navigation
        nav = tk.Frame(body, bg="white")
        nav.pack(fill='x', pady=(0, 6))
        tk.Button(nav, text='<', width=3,
                  command=self._prev_month).pack(side='left')
        self.title_lbl = tk.Label(nav, text='', width=20, bg="white",
                                  font=("Arial", 10, "bold"))
        self.title_lbl.pack(side='left', padx=6)
        tk.Button(nav, text='>', width=3,
                  command=self._next_month).pack(side='right')

        self.cal_frame = tk.Frame(body, bg="white")
        self.cal_frame.pack(pady=(0, 10))

        # Time
        tf = tk.Frame(body, bg="white")
        tf.pack(fill='x', pady=6)
        tk.Label(tf, text='Time:', font=('Arial', 10, 'bold'),
                 bg="white").pack(anchor='w')
        ti = tk.Frame(tf, bg="white")
        ti.pack(anchor='w', pady=(4, 0))
        tk.Label(ti, text='HH:', bg="white").pack(side='left')
        tk.Spinbox(ti, from_=0, to=23, width=3,
                   textvariable=self.hour_var).pack(side='left', padx=(2, 8))
        tk.Label(ti, text='MM:', bg="white").pack(side='left')
        tk.Spinbox(ti, from_=0, to=59, width=3,
                   textvariable=self.minute_var).pack(side='left', padx=(2, 8))
        tk.Label(ti, text='SS:', bg="white").pack(side='left')
        tk.Spinbox(ti, from_=0, to=59, width=3,
                   textvariable=self.second_var).pack(side='left', padx=(2, 0))

        # Buttons
        bf = tk.Frame(body, bg="white")
        bf.pack(fill='x', pady=(10, 0))
        tk.Button(bf, text='OK', width=10,
                  command=self._confirm).pack(side='left', padx=5)
        tk.Button(bf, text='Cancel', width=10,
                  command=self.destroy).pack(side='left')

        self._build_calendar()
        self.update_idletasks()
        self.deiconify()

    def _build_calendar(self):
  
        for w in self.cal_frame.winfo_children():
            w.destroy()
        self.title_lbl.config(
            text=f"{calendar.month_name[self.month]} {self.year}")

        for c, name in enumerate(['Mo','Tu','We','Th','Fr','Sa','Su']):
            tk.Label(self.cal_frame, text=name, width=3, bg="white",
                     font=("Arial", 9, "bold")).grid(row=0, column=c, padx=1)

        for r, week in enumerate(
                calendar.monthcalendar(self.year, self.month), start=1):
            for c, day in enumerate(week):
                if day == 0:
                    tk.Label(self.cal_frame, text='', width=3,
                             bg="white").grid(row=r, column=c)
                else:
                    kw = {'bg': '#4caf50', 'fg': 'white'} if day == self.day else {}
                    tk.Button(
                        self.cal_frame, text=str(day), width=3,
                        font=("Arial", 9),
                        command=lambda d=day: self._select_day(d), **kw
                    ).grid(row=r, column=c, padx=1, pady=1)

    def _select_day(self, day):
        self.day = day
        self._build_calendar()

    def _prev_month(self):
        if self.month == 1:
            self.month, self.year = 12, self.year - 1
        else:
            self.month -= 1
        self._build_calendar()

    def _next_month(self):
        if self.month == 12:
            self.month, self.year = 1, self.year + 1
        else:
            self.month += 1
        self._build_calendar()

    def _confirm(self):
        if self.day is None:
            messagebox.showwarning('Select Date', 'Please select a date.')
            return
        try:
            dt = datetime(self.year, self.month, self.day,
                          int(self.hour_var.get()),
                          int(self.minute_var.get()),
                          int(self.second_var.get()))
            self.select_callback(dt.strftime('%Y-%m-%d %H:%M:%S'))
            self.destroy()
        except ValueError:
            messagebox.showerror('Invalid Time', 'Please enter valid time values.')


# ─────────────────────────────────────────────────────────────
#  Main Application
# ─────────────────────────────────────────────────────────────

class DBDateViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DB Viewer — Date Range Filter")
        self.geometry("1150x680")
        self.configure(bg="white")
        self.resizable(True, True)

        self._conn          = None
        self._all_rows      = []
        self._columns       = []
        self._display_cols  = []
        self._timestamp_col = None
        self._is_packet_table = False

        self.date_from_var = tk.StringVar(value="")
        self.date_to_var   = tk.StringVar(value="")

        self._build_ui()

    def _build_ui(self):

        # ── File selector ─────────────────────────────────────
        row1 = tk.Frame(self, bg="white", pady=8, padx=10)
        row1.pack(fill=tk.X)

        tk.Button(
            row1, text="📂  Select DB File",
            command=self._select_file,
            bg="#0066cc", fg="white",
            font=("Arial", 10, "bold"),
            padx=12, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT)

        self._file_label = tk.Label(
            row1, text="No file selected",
            bg="white", fg="#555555",
            font=("Arial", 10)
        )
        self._file_label.pack(side=tk.LEFT, padx=12)

        # ── Controls ──────────────────────────────────────────
        row2 = tk.Frame(self, bg="white", pady=6, padx=10)
        row2.pack(fill=tk.X)

        # Table
        tk.Label(row2, text="Table:", bg="white",
                 font=("Arial", 10)).pack(side=tk.LEFT)
        self._table_var = tk.StringVar()
        self._table_combo = ttk.Combobox(
            row2, textvariable=self._table_var,
            state="readonly", width=22, font=("Arial", 10)
        )
        self._table_combo.pack(side=tk.LEFT, padx=(4, 16))
        self._table_combo.bind("<<ComboboxSelected>>",
                               lambda _: self._load_table())

        # From
        tk.Label(row2, text="From:", bg="white",
                 font=("Arial", 10)).pack(side=tk.LEFT)
        from_box = tk.Frame(row2, bg="white")
        from_box.pack(side=tk.LEFT, padx=(4, 12))
        tk.Entry(from_box, textvariable=self.date_from_var,
                 width=18, font=("Arial", 10)).pack(side=tk.LEFT)
        tk.Button(from_box, text="📅", width=3,
                  command=lambda: DateTimePopup(
                      self, lambda d: self.date_from_var.set(d))
                  ).pack(side=tk.LEFT, padx=(4, 0))

        # To
        tk.Label(row2, text="To:", bg="white",
                 font=("Arial", 10)).pack(side=tk.LEFT)
        to_box = tk.Frame(row2, bg="white")
        to_box.pack(side=tk.LEFT, padx=(4, 12))
        tk.Entry(to_box, textvariable=self.date_to_var,
                 width=18, font=("Arial", 10)).pack(side=tk.LEFT)
        tk.Button(to_box, text="📅", width=3,
                  command=lambda: DateTimePopup(
                      self, lambda d: self.date_to_var.set(d))
                  ).pack(side=tk.LEFT, padx=(4, 0))

        # Load + Export
        tk.Button(
            row2, text="🔍 Load",
            bg="#0066cc", fg="white",
            font=("Arial", 10, "bold"),
            command=self._load_with_filter
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            row2, text="📥 Export CSV",
            bg="#4caf50", fg="white",
            font=("Arial", 10, "bold"),
            command=self._export_csv
        ).pack(side=tk.LEFT, padx=4)

        # ── Info bar ──────────────────────────────────────────
        row3 = tk.Frame(self, bg="#eeeeee", pady=3, padx=10)
        row3.pack(fill=tk.X)

        self._info_label = tk.Label(
            row3, text="", bg="#eeeeee", fg="#333333",
            font=("Arial", 9), anchor=tk.W
        )
        self._info_label.pack(side=tk.LEFT)

        self._row_label = tk.Label(
            row3, text="", bg="#eeeeee", fg="#0066cc",
            font=("Arial", 9, "bold"), anchor=tk.E
        )
        self._row_label.pack(side=tk.RIGHT)

        # ── Treeview ──────────────────────────────────────────
        tree_frame = tk.Frame(self, bg="white")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 0))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background="white", foreground="#222222",
                        rowheight=24, fieldbackground="white",
                        font=("Arial", 9))
        style.configure("Treeview.Heading",
                        background="#dddddd", foreground="#111111",
                        font=("Arial", 9, "bold"))
        style.map("Treeview", background=[("selected", "#0066cc")],
                  foreground=[("selected", "white")])

        self._tree = ttk.Treeview(tree_frame, show="headings",
                                  selectmode="browse")
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                             command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL,
                             command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set,
                             xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._tree.pack(fill=tk.BOTH, expand=True)

        self._tree.tag_configure("odd",  background="#f5f5f5")
        self._tree.tag_configure("even", background="white")

        # ── Status bar ────────────────────────────────────────
        self._status = tk.Label(
            self, text="Ready — select a .db file to begin",
            bg="#dddddd", fg="#555555",
            font=("Arial", 8), anchor=tk.W,
            padx=8, pady=3, relief=tk.SUNKEN
        )
        self._status.pack(fill=tk.X, side=tk.BOTTOM)

    # ── File selection ────────────────────────────────────────

    def _load_from_path(self, path):
        """Load a DB file directly by path (used when path passed via argv)."""
        if self._conn:
            self._conn.close()
            self._conn = None
        try:
            self._conn = sqlite3.connect(path)
            name = path.replace("\\", "/").split("/")[-1]
            self._file_label.config(text=f"📄 {name}", fg="#0066cc")
            self._status.config(text=f"Opened: {path}")
            tables = [
                r[0] for r in self._conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' ORDER BY name"
                ).fetchall()
                if r[0] != "sqlite_sequence"
            ]
            if not tables:
                messagebox.showinfo("Empty", "No tables found.")
                return
            self._table_combo["values"] = tables
            self._table_combo.current(0)
            self._load_table()
        except sqlite3.DatabaseError as e:
            messagebox.showerror("Error", f"Cannot open file:\n{e}")

    def _select_file(self):
        path = filedialog.askopenfilename(
            title="Open SQLite Database File",
            filetypes=[
                ("SQLite databases", "*.db *.sqlite *.sqlite3"),
                ("All files", "*.*")
            ]
        )
        if not path:
            return

        if self._conn:
            self._conn.close()
            self._conn = None

        try:
            self._conn = sqlite3.connect(path)
            name = path.replace("\\", "/").split("/")[-1]
            self._file_label.config(text=f"📄 {name}", fg="#0066cc")
            self._status.config(text=f"Opened: {path}")

            tables = [
                r[0] for r in self._conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' ORDER BY name"
                ).fetchall()
                if r[0] != "sqlite_sequence"   # skip internal SQLite table
            ]
            if not tables:
                messagebox.showinfo("Empty", "No tables found.")
                return

            self._table_combo["values"] = tables
            self._table_combo.current(0)
            self._load_table()

        except sqlite3.DatabaseError as e:
            messagebox.showerror("Error", f"Cannot open file:\n{e}")

    # ── Table loading ─────────────────────────────────────────

    def _load_table(self):
        if not self._conn:
            return
        table = self._table_var.get()
        if not table:
            return

        try:
            cur = self._conn.execute(f"SELECT * FROM [{table}]")
            self._columns  = [d[0] for d in cur.description]
            self._all_rows = cur.fetchall()
        except sqlite3.OperationalError as e:
            messagebox.showerror("Error", str(e))
            return

        # Detect whether this is a raw-byte packet table (has b0..b15)
        col_lower = [c.lower() for c in self._columns]
        self._is_packet_table = all(f"b{i}" in col_lower for i in range(16))

        self._timestamp_col = None
        for col in self._columns:
            if any(k in col.lower()
                   for k in ("time", "date", "ts", "stamp", "created")):
                self._timestamp_col = col
                break

        self.date_from_var.set("")
        self.date_to_var.set("")

        self._setup_columns()
        self._populate([])   # empty until user picks dates and clicks Load

        if self._is_packet_table:
            extra = "  |  ⚡ Packet table — bytes decoded to sensor fields"
        else:
            extra = ""
        ts = (f"  |  Date column: '{self._timestamp_col}'"
              if self._timestamp_col else "  |  No date column detected")
        self._info_label.config(
            text=f"Table: {table}  |  {len(self._all_rows)} rows available  |  "
                 f"{len(self._columns)} columns{ts}{extra}"
        )
        self._status.config(
            text=f"Table '{table}' ready — pick From / To dates then click 🔍 Load"
        )

    def _setup_columns(self):
        if self._is_packet_table:
            # Build display columns: non-byte columns first, then decoded sensor fields
            non_byte = [c for c in self._columns
                        if c.lower() not in RAW_BYTE_COLS]
            display_cols = non_byte + DECODED_FIELDS
        else:
            display_cols = self._columns

        self._display_cols = display_cols
        self._tree["columns"] = display_cols
        for col in display_cols:
            self._tree.heading(col, text=col,
                               command=lambda c=col: self._sort(c, False))
            w = max(100, min(220, len(col) * 11 + 20))
            self._tree.column(col, width=w, anchor=tk.W, minwidth=60)

    # ── Load with date filter ─────────────────────────────────

    def _load_with_filter(self):
        if not self._conn:
            messagebox.showwarning("No File", "Please select a DB file first.")
            return

        s_from = self.date_from_var.get().strip()
        s_to   = self.date_to_var.get().strip()

        def parse_dt(s):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(s, fmt)
                except ValueError:
                    continue
            return None

        from_ts = parse_dt(s_from) if s_from else None
        to_ts   = parse_dt(s_to)   if s_to   else None

        rows = self._all_rows

        if self._timestamp_col and (from_ts or to_ts):
            idx = self._columns.index(self._timestamp_col)
            filtered = []
            for row in rows:
                val = row[idx]
                if not val:
                    filtered.append(row)
                    continue
                dt = self._parse_dt(str(val))
                if dt is None:
                    filtered.append(row)
                    continue
                if from_ts and dt < from_ts:
                    continue
                if to_ts and dt > to_ts:
                    continue
                filtered.append(row)
            rows = filtered

        self._populate(rows)
        self._status.config(
            text=f"Showing {len(rows)} of {len(self._all_rows)} rows")

    @staticmethod
    def _parse_dt(value: str):
        for fmt in (
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(value[:len(fmt) + 2], fmt)
            except ValueError:
                continue
        return None

    # ── Treeview populate ─────────────────────────────────────

    def _populate(self, rows):
        self._tree.delete(*self._tree.get_children())

        # Pre-compute non-byte column info once (not per row)
        if self._is_packet_table:
            non_byte_cols = [c for c in self._columns if c.lower() not in RAW_BYTE_COLS]
            col_idx = {c.lower(): j for j, c in enumerate(self._columns)}

        for i, row in enumerate(rows):
            tag = "odd" if i % 2 else "even"

            if self._is_packet_table:
                display = []
                for col in non_byte_cols:
                    v = row[col_idx[col.lower()]]
                    display.append("" if v is None else v)

                decoded = _decode_packet_row(row, self._columns)
                if decoded:
                    for field in DECODED_FIELDS:
                        display.append(decoded.get(field, ""))
                else:
                    display.extend([""] * len(DECODED_FIELDS))
            else:
                display = ["" if v is None else v for v in row]

            self._tree.insert("", tk.END, values=tuple(display), tags=(tag,))

        self._row_label.config(text=f"Showing {len(rows)} row(s)")

        self._row_label.config(text=f"Showing {len(rows)} row(s)")

    # ── Sort ──────────────────────────────────────────────────

    def _sort(self, col, desc):
        """Sort by any visible column — works for both raw DB cols and decoded fields."""

        def _sort_key(display_val):
            v = str(display_val) if display_val is not None else ""
            try:
                return (0, float(v))
            except (ValueError, TypeError):
                return (1, v.lower())

        if self._is_packet_table and col in DECODED_FIELDS:
            try:
                self._all_rows = sorted(
                    self._all_rows,
                    key=lambda r: _sort_key(
                        (_decode_packet_row(r, self._columns) or {}).get(col, "")
                    ),
                    reverse=desc
                )
            except Exception:
                pass
        elif col in self._columns:
            idx = self._columns.index(col)
            try:
                self._all_rows = sorted(
                    self._all_rows,
                    key=lambda r: _sort_key(r[idx]),
                    reverse=desc
                )
            except Exception:
                pass

        self._load_with_filter()
        self._tree.heading(col, command=lambda c=col: self._sort(c, not desc))

    # ── Export CSV ────────────────────────────────────────────

    def _export_csv(self):
        if not self._display_cols:
            messagebox.showinfo("Nothing to export", "Load a table first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"{self._table_var.get()}_export.csv"
        )
        if not path:
            return
        rows = [self._tree.item(i)["values"]
                for i in self._tree.get_children()]
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self._display_cols)
                writer.writerows(rows)
            messagebox.showinfo("Exported",
                                f"Saved {len(rows)} rows to:\n{path}")
            self._status.config(text=f"Exported → {path}")
        except OSError as e:
            messagebox.showerror("Export Failed", str(e))

    def destroy(self):
        if self._conn:
            self._conn.close()
        super().destroy()


if __name__ == "__main__":
    app = DBDateViewer()
    # If a db path was passed as argument, load it immediately
    if len(sys.argv) == 2:
        app.after(100, lambda: app._load_from_path(sys.argv[1]))
    app.mainloop()
