"""
Serial Port Raw Byte Logger
- Uses the same framing protocol as wireless_sensor.py PacketProcessor
- Frame: 0x0D (\r) = start, 0x0A (\n) = end, 0x08 (\b) = escape next byte
- Extracts 16 payload bytes per packet, prints to console and saves to SQLite
"""

import serial
import serial.tools.list_ports
import sqlite3
import threading
import queue
import sys
import os
import subprocess
from datetime import datetime

import tkinter as tk
from tkinter import ttk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

PORT        = "COM8"
BAUDRATE    = 115200
DB_FILE     = "serial_packets.db"
PACKET_SIZE = 16

# Same framing constants as wireless_sensor.py PacketProcessor
FRAME_START = 0x0D   # \r
FRAME_END   = 0x0A   # \n
ESCAPE_BYTE = 0x08   # \b

# ── RTD lookup (same as wireless_sensor.py) ────────────────────────────────────
_RTD_VALUES = [
    18.4932,18.9258,19.3580,19.7899,20.2215,20.6526,21.0834,21.5139,21.9439,
    22.3737,22.8031,23.2321,23.6608,24.0891,24.5171,24.9447,25.3720,25.7990,
    26.2257,26.6520,27.0779,27.5036,27.9289,28.3539,28.7786,29.2029,29.6270,
    30.0507,30.4741,30.8972,31.3200,31.7425,32.1646,32.5865,33.0081,33.4294,
    33.8503,34.2710,34.6914,35.1115,35.5313,35.9508,36.3700,36.7889,37.2076,
    37.6260,38.0440,38.4619,38.8794,39.2967,39.7137,40.1304,40.5469,40.9631,
    41.3790,41.7946,42.2101,42.6252,43.0401,43.4547,43.8691,44.2832,44.6971,
    45.1107,45.5241,45.9372,46.3501,46.7628,47.1752,47.5873,47.9993,48.4109,
    48.8224,49.2336,49.6446,50.0554,50.4659,50.8762,51.2863,51.6962,52.1058,
    52.5152,52.9244,53.3334,53.7422,54.1507,54.5591,54.9672,55.3751,55.7828,
    56.1903,56.5976,57.0047,57.4115,57.8182,58.2247,58.6310,59.0371,59.4429,
    59.8486,60.2541,60.6594,61.0645,61.4695,61.8742,62.2787,62.6831,63.0873,
    63.4912,63.8950,64.2987,64.7021,65.1054,65.5084,65.9114,66.3141,66.7166,
    67.1190,67.5212,67.9233,68.3251,68.7268,69.1284,69.5297,69.9309,70.3319,
    70.7328,71.1335,71.5340,71.9344,72.3346,72.7347,73.1346,73.5343,73.9339,
    74.3334,74.7326,75.1318,75.5307,75.9296,76.3282,76.7268,77.1251,77.5234,
    77.9214,78.3194,78.7171,79.1148,79.5123,79.9096,80.3068,80.7039,81.1008,
    81.4976,81.8943,82.2908,82.6871,83.0834,83.4795,83.8754,84.2713,84.6669,
    85.0625,85.4579,85.8532,86.2484,86.6434,87.0383,87.4331,87.8277,88.2222,
    88.6166,89.0109,89.4050,89.7990,90.1929,90.5866,90.9802,91.3737,91.7671,
    92.1603,92.5535,92.9465,93.3394,93.7321,94.1247,94.5173,94.9097,95.3019,
    95.6941,96.0861,96.4780,96.8698,97.2615,97.6531,98.0445,98.4359,98.8271,
    99.2182,99.6091,100.0000,100.3907,100.7814,101.1719,101.5623,101.9526,
    102.3427,102.7328,103.1227,103.5125,103.9022,104.2918,104.6813,105.0706,
    105.4599,105.8490,106.2380,106.6269,107.0156,107.4043,107.7928,108.1813,
    108.5696,108.9578,109.3458,109.7338,110.1216,110.5094,110.8970,111.2845,
    111.6718,112.0591,112.4463,112.8333,113.2202,113.6070,113.9937,114.3802,
    114.7667,115.1530,115.5392,115.9254,116.3113,116.6972,117.0830,117.4686,
    117.8541,118.2395,118.6248,119.0100,119.3951,119.7800,120.1648,120.5495,
    120.9341,121.3186,121.7030,122.0872,122.4713,122.8554,123.2392,123.6230,
    124.0067,124.3902,124.7737,125.1570,125.5402,125.9233,126.3063,126.6891,
    127.0718,127.4545,127.8370,128.2194,128.6016,128.9838,129.3658,129.7478,
    130.1296,130.5113,130.8928,131.2743,131.6556,132.0369,132.4180,132.7990,
    133.1799,133.5606,133.9413,134.3218,134.7022,135.0825,135.4627,135.8428,
    136.2227,136.6026,136.9823,137.3619,137.7414,138.1207,138.5000,138.8791,
    139.2582,139.6371,140.0159,140.3945,140.7731,141.1515,141.5299,141.9081,
    142.2862,142.6642,143.0420,143.4198,143.7974,144.1749,144.5523,144.9296,
    145.3068,145.6838,146.0608,146.4376,146.8143,147.1909,147.5673,147.9437,
    148.3199,148.6960,149.0721,149.4479,149.8237,150.1994,150.5749,150.9504,
    151.3257,151.7009,152.0759,152.4509,152.8257,153.2005,153.5751,153.9496,
    154.3240,154.6982,155.0724,155.4464,155.8203,156.1941,156.5678,156.9414,
    157.3149,157.6882,158.0614,158.4345,158.8075,159.1804,159.5531,159.9258,
    160.2983,160.6707,161.0430,161.4152,161.7872,162.1592,162.5310,162.9027,
    163.2743,163.6458,164.0172,164.3884,164.7596,165.1306,165.5015,165.8723,
    166.2429,166.6135,166.9839,167.3542,167.7245,168.0945,168.4645,168.8344,
    169.2041,169.5737,169.9432,170.3126,170.6819,171.0511,171.4201,171.7890,
    172.1579,172.5266,172.8951,173.2636,173.6319,174.0002,174.3683,174.7363,
    175.1042,175.4719,175.8396,176.2071,176.5746,176.9419,177.3090,177.6761,
    178.0431,178.4099,178.7766,179.1432,179.5097,179.8761,180.2424,180.6085,
    180.9745,181.3405,181.7063,182.0719,182.4375,182.8029,183.1683,183.5335,
    183.8986,184.2636,184.6284,184.9932,185.3578,185.7223,186.0867,186.4510,
    186.8152,187.1793,187.5432,187.9070,188.2707,188.6343,188.9978,189.3611,
    189.7244,190.0875,190.4505,190.8134,191.1762,191.5389,191.9014,192.2638,
    192.6262,192.9884,193.3504,193.7124,197.3257,196.9649,196.6040,196.2429,
    195.8818,195.5205,195.1591,194.7976,194.4360,194.0743,194.0743,194.4360,
    194.7976,195.1591,195.5205,195.8818,196.2429,196.6040,196.9649,197.3257,
    197.6864,198.0469,198.4074,198.7677,199.1280,199.4881,199.8481,200.2079,
    200.5677,200.9274,201.2869,201.6463,202.0056,202.3648,202.7238,203.0828,
    203.4416,203.8003,204.1589,204.5174,204.8758,205.2340,205.5922,205.9502,
    206.3081,206.6659,207.0236,207.3811,207.7386,208.0959,208.4531,208.8102,
    209.1672,209.5240,209.8808,210.2374,210.5939,210.9503,211.3066,211.6628,
    212.0188,212.3747,212.7305,213.0862,213.4418,213.7973,214.1527,214.5079,
    214.8630,215.2180,215.5729,215.9277,216.2823,216.6369,216.9913,217.3456,
    217.6998,218.0539,218.4078,218.7617,219.1154,219.4690,219.8225,220.1759,
    220.5291,220.8823,221.2353,221.5882,221.9410,222.2937,222.6463,222.9987,
    223.3511,223.7033,224.0554,224.4074,224.7592,225.1110,225.4626,225.8142,
    226.1656,226.5169,226.8680,227.2191,227.5700,227.9209,228.2716,228.6222,
    228.9726,229.3230,229.6733,229.6733,230.3734,230.7233,231.0731,231.4227,
    231.7723,232.1217,232.4710,232.8202,233.1693,233.5183,233.8672,234.2159,
    234.5645,234.9130,235.2614,235.6097,235.9578,236.3059,236.6538,237.0016,
    237.3493,237.6969,238.0443,238.3917,238.7389,239.0860,239.4330,239.7799,
    240.1267,240.4733,240.8199,241.1663,241.5126,241.8588,242.2048,242.5508,
    242.8966,243.2423,243.5879,243.9334,244.2788,244.6241,244.9692,245.3142,
    245.6591,246.0039,246.3486,246.6932,247.0376,247.3819,247.7261,248.0702,
    248.4142,248.7581,249.1018,249.4455,249.7890,250.1324,250.4757,250.8188,
    251.1619,251.5048,251.8476,252.1903,252.5329,252.8754,253.2177,253.5600,
    253.9021,254.2441,254.5860,254.9278,255.2694,255.6110,255.9524,256.2937,
    256.6349,256.9760,257.3170,257.6578,257.9985,258.3392,258.6797,259.0200,
    259.3603,259.7005,260.0405,260.3804,260.7202,261.0599,261.3995,261.7389,
    262.0783,262.4175,262.7566,263.0956,263.4344,263.7732,264.1119,264.4504,
    264.7888,265.1271,265.4653,265.8033,266.1413,266.4791,266.8168,267.1544,
    267.4919,267.8293,268.1665,268.5036,268.8407,269.1776,269.5143,269.8510,
    270.1876,270.5240,270.8603,271.1965,271.5326,271.8686,272.2044,272.5402,
    272.8758,273.2113,273.5467,273.8820,274.2172,274.5522,274.8871,275.2219,
    275.5566,275.8912,276.2257,276.5600,276.8943,277.2284,277.5624,277.8963,
    278.2300,278.5637,278.8972,279.2306,279.5639,279.8971,280.2302,280.5632,
    280.8960,281.2287,281.5613,281.8938,282.2262,282.5585,282.8906,283.2226,
    283.5545,283.8863,284.2180,284.5496,284.8810,285.2124,285.5436,285.8747,
    286.2057,286.5365,286.8673,287.1979,287.5284,287.8588,288.1891,288.5193,
    288.8493,289.1793,289.5091,289.8388,290.1684,290.4979,293.7862,293.4579,
    293.1295,292.8010,292.4723,292.1435,291.8146,291.4856,291.1565,290.8272,
    290.8272,291.1565,291.4856,291.8146,292.1435,292.4723,292.8010,293.1295,
    293.4579,293.7862,
]

_COEFFS_LOW  = [9.8423321e1,6.9971500e-1,-8.4765304e-4,1.0052644e-6,
                -8.3345952e-10,4.5508542e-13,-1.5523037e-16,
                2.9886750e-20,-2.4742860e-24]
_COEFFS_HIGH = [2.1315071e2,2.8510504e-1,-5.2742887e-5,9.9160804e-9,
                -1.2965303e-12,1.1195870e-16,-6.0625199e-21,
                1.8661696e-25,-2.4878585e-30]

def _rtd_temp(resistance):
    idx = min(range(len(_RTD_VALUES)), key=lambda i: abs(_RTD_VALUES[i] - resistance))
    return idx - 200

def _raw_to_uV(raw):
    return (raw * 1_250_000.0) / (32.0 * (2 ** 16))

def _uV_to_temp(uV):
    coeffs = _COEFFS_LOW if uV <= 2431.0 else _COEFFS_HIGH
    return sum(c * (uV ** i) for i, c in enumerate(coeffs))

def decode(packet):
    """Decode 16 payload bytes per new packet layout:
       0-3:  OXY ADC (4 bytes, little-endian)
       4:    RSSI
       5:    Packet type
       6-9:  TX ID
       10-13: TC ADC (thermocouple, 4 bytes, little-endian)
       14-15: Packet sequence number
    """
    # TC ADC: bytes 10-13 little-endian → mV = (tc_raw / 2^23) * (2500/128)
    tc_raw = packet[10] | (packet[11] << 8) | (packet[12] << 16) | (packet[13] << 24)
    tc_mV  = (tc_raw / (2**23)) * (2500 / 128)
    melt   = tc_mV  # use mV directly on melt temp graph axis

    # OXY ADC: bytes 0-3 little-endian → mV = (oxy_raw / 2^23) * (2500/8)
    oxy_raw = packet[0] | (packet[1] << 8) | (packet[2] << 16) | (packet[3] << 24)
    oxy_mV  = (oxy_raw / (2**23)) * (2500 / 8)
    rtd     = oxy_mV  # use mV value on RTD graph axisi
    
    return rtd, melt


# ── DB ─────────────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS packets (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            b0  INTEGER, b1  INTEGER, b2  INTEGER, b3  INTEGER,
            b4  INTEGER, b5  INTEGER, b6  INTEGER, b7  INTEGER,
            b8  INTEGER, b9  INTEGER, b10 INTEGER, b11 INTEGER,
            b12 INTEGER, b13 INTEGER, b14 INTEGER, b15 INTEGER
        )
    """)
    conn.commit()
    return conn


def save(conn, packet):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    conn.execute(
        "INSERT INTO packets VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ts, *packet)
    )
    conn.commit()


# ── GUI ────────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Serial Logger")
        self.geometry("900x560")
        self.configure(bg="white")

        self._melt    = []
        self._rtd     = []
        self._running = False
        self._thread  = None
        self._conn    = init_db()
        self._queue   = queue.Queue()

        self._build_ui()

    def _build_ui(self):
        # ── Top bar — port selector + refresh only ────────────
        bar = tk.Frame(self, bg="white", pady=6, padx=10)
        bar.pack(fill=tk.X)

        tk.Label(bar, text="Port:", bg="white", font=("Arial", 10)).pack(side=tk.LEFT)
        self._port_var = tk.StringVar()
        self._port_cb  = ttk.Combobox(bar, textvariable=self._port_var,
                                       width=12, font=("Arial", 10), state="readonly")
        self._port_cb.pack(side=tk.LEFT, padx=(4, 4))
        tk.Button(bar, text="⟳", font=("Arial", 10, "bold"), width=2,
                  command=self._refresh_ports).pack(side=tk.LEFT, padx=(0, 12))

        tk.Button(bar, text="📂 Open DB", bg="#4caf50", fg="white",
                  font=("Arial", 10, "bold"), padx=10,
                  command=self._open_db).pack(side=tk.LEFT, padx=4)

        self._status_lbl = tk.Label(bar, text="Select a port", bg="white",
                                    fg="#555555", font=("Arial", 9))
        self._status_lbl.pack(side=tk.LEFT, padx=8)

        self._refresh_ports()

        # ── Two separate graphs side by side ──────────────────
        fig = Figure(figsize=(10, 4.2), dpi=100, facecolor="white")

        # Left graph — Melt Temp (TC ADC mV)
        self._ax = fig.add_subplot(121)
        self._ax.set_facecolor("#f8f8f8")
        self._ax.set_xlabel("Sample", fontsize=10)
        self._ax.set_ylabel("Melt Temp (mV)", fontsize=10, color="#0066cc")
        self._ax.set_ylim(0, 25)
        self._ax.tick_params(axis="y", labelcolor="#0066cc")
        self._ax.grid(True, linestyle="--", alpha=0.4)
        self._ax.set_title("Melt Temperature", fontsize=11, fontweight="bold")
        self._line_melt, = self._ax.plot([], [], color="#0066cc", linewidth=1.5)
        self._txt_melt = self._ax.text(
            0.98, 0.95, "Melt: --", transform=self._ax.transAxes,
            fontsize=11, fontweight="bold", color="#0066cc",
            ha="right", va="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#0066cc", alpha=0.9)
        )

        # Right graph — OXY ADC mV
        self._ax2 = fig.add_subplot(122)
        self._ax2.set_facecolor("#f8f8f8")
        self._ax2.set_xlabel("Sample", fontsize=10)
        self._ax2.set_ylabel("OXY ADC (mV)", fontsize=10, color="#cc0000")
        self._ax2.set_ylim(0, 600)
        self._ax2.tick_params(axis="y", labelcolor="#cc0000")
        self._ax2.grid(True, linestyle="--", alpha=0.4)
        self._ax2.set_title("OXY ADC", fontsize=11, fontweight="bold")
        self._line_rtd, = self._ax2.plot([], [], color="#cc0000", linewidth=1.5)
        self._txt_rtd = self._ax2.text(
            0.98, 0.95, "OXY: --", transform=self._ax2.transAxes,
            fontsize=11, fontweight="bold", color="#cc0000",
            ha="right", va="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#cc0000", alpha=0.9)
        )

        fig.tight_layout(pad=2.0)
        self._canvas = FigureCanvasTkAgg(fig, master=self)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        # auto-start on first available port
        self.after(100, self._restart)

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self._port_cb["values"] = ports
        if ports:
            if self._port_var.get() not in ports:
                self._port_var.set(ports[0])
        else:
            self._port_var.set("")
        self._port_cb.bind("<<ComboboxSelected>>", lambda _: self._restart())

    def _open_db(self):
        """Let user pick a .db file then open it in convert_sql.py."""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select SQLite Database",
            filetypes=[("SQLite databases", "*.db *.sqlite *.sqlite3"),
                       ("All files", "*.*")]
        )
        if path:
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "convert_sql.py")
            subprocess.Popen([sys.executable, script, path])

    # ── Serial thread ──────────────────────────────────────────
    def _serial_loop(self, port):
        try:
            ser = serial.Serial(port, BAUDRATE, timeout=1)
        except serial.SerialException as e:
            self._queue.put(("error", str(e)))
            self._running = False
            return

        packet = []
        escape = False
        count  = 0

        while self._running:
            try:
                raw = ser.read(1)
            except serial.SerialException:
                break

            if not raw:
                continue

            byte_val = raw[0]


            if not escape:
                if byte_val == ESCAPE_BYTE:
                    escape = True
                    continue
                if byte_val == FRAME_START:

                    
                    packet = []

                    continue
                if byte_val == FRAME_END:
                    if len(packet) == PACKET_SIZE:
                        count += 1
                        save(self._conn, packet)
                        rtd, melt = decode(packet)
                        # send to main thread
                        self._queue.put(("packet", count, list(packet), rtd, melt))
                    packet = []
                    continue

                
                packet.append(byte_val)
            else:
                packet.append(byte_val)
                escape = False

        if ser.is_open:
            ser.close()

    # ── Controls ───────────────────────────────────────────────
    def _restart(self):
        """Stop any running thread and start fresh on selected port."""
        self._running = False
        port = self._port_var.get()
        if not port:
            self._status_lbl.config(text="Select a port", fg="#555555")
            return
        self._melt.clear()
        self._rtd.clear()
        self._line_melt.set_data([], [])
        self._line_rtd.set_data([], [])
        self._txt_melt.set_text("Melt: --")
        self._txt_rtd.set_text("OXY: --")
        self._canvas.draw_idle()
        self._running = True
        self._status_lbl.config(text=f"Reading {port}...", fg="#0066cc")
        self._thread = threading.Thread(
            target=self._serial_loop, args=(port,), daemon=True)
        self._thread.start()
        self._poll()

    def _stop(self):
        self._running = False
    # ── Poll queue on main thread (prints bytes + updates graph) ──
    def _poll(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                if msg[0] == "packet":
                    _, count, pkt, rtd, melt = msg
                    # Raw hex
                    hex_str = " ".join(f"{b:02X}" for b in pkt)
                    # Decoded fields from the packet
                    oxy_raw = pkt[0] | (pkt[1]<<8) | (pkt[2]<<16) | (pkt[3]<<24)
                    oxy_mV  = (oxy_raw / (2**23)) * (2500 / 8)
                    rssi    = pkt[4] - 128
                    pkt_type= pkt[5]
                    tx_id   = f"{pkt[6]:02X}:{pkt[7]:02X}:{pkt[8]:02X}:{pkt[9]:02X}"
                    tc_raw  = pkt[10] | (pkt[11]<<8) | (pkt[12]<<16) | (pkt[13]<<24)
                    tc_mV   = (tc_raw / (2**23)) * (2500 / 128)
                    seq     = pkt[14] | (pkt[15]<<8)
                    print(f"[{count:04d}] {hex_str}")
                    print(f"       OXY ADC={oxy_raw}  OXY={oxy_mV:.4f}mV  "
                          f"RSSI={rssi}dBm  Type={pkt_type}  "
                          f"TX={tx_id}  "
                          f"TC ADC={tc_raw}  TC={tc_mV:.4f}mV  "
                          f"Seq={seq}")
                    self._melt.append(melt)
                    self._rtd.append(rtd)
                elif msg[0] == "error":
                    self._status_lbl.config(text=f"Error: {msg[1]}", fg="red")
                    print(f"Serial error: {msg[1]}")
        except queue.Empty:
            pass

        if self._melt:
            samples = list(range(len(self._melt)))
            self._line_melt.set_data(samples, self._melt)
            self._ax.set_xlim(0, max(len(samples), 1))
            self._line_rtd.set_data(samples, self._rtd)
            self._ax2.set_xlim(0, max(len(samples), 1))
            self._txt_melt.set_text(f"Melt: {self._melt[-1]:.4f} mV")
            self._txt_rtd.set_text(f"OXY:  {self._rtd[-1]:.4f} mV")
            self._canvas.draw_idle()

        if self._running:
            self.after(200, self._poll)

    def destroy(self):
        self._running = False
        if self._conn:
            self._conn.close()
        super().destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
