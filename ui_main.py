import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from PIL import Image, ImageTk
# For Plotting
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import sys
import os
import logging
import threading
from datetime import datetime
from collections import deque
import re
import csv
import time

# Internal imports
from hardware import SerialPortManager, PacketProcessor, SensorDataParser
from conversions import RTDTemperatureTable, voltage_uV_to_temperature_C, raw_to_voltage_uV, apply_rtd_compensation
from database import DatabaseManager
from ui_components import CalendarPopup, DateTimePopup, ConnectionSettings

logger = logging.getLogger(__name__)

class SensorGUI(tk.Tk):
    """GUI for wireless sensor data logger with professional interface"""
    
    def __init__(self):
        super().__init__()
        self.title("WIRELESS SENSOR - MOLTEN METAL CONTINUOUS TEMPERATURE SYSTEM")
        try:
            self.attributes('-fullscreen', True)
        except Exception:
            pass
        self.state('zoomed')
        self.minsize(1024, 600)
        self.configure(bg="#f0f0f0")
        
        # Get screen dimensions for responsive sizing
        self.update_idletasks()
        self.screen_w = self.winfo_screenwidth()
        self.screen_h = self.winfo_screenheight()
        
        # Define responsive fonts
        self.font_large_temp = ("Arial", int(self.screen_h * 0.08), "bold")
        self.font_unit = ("Arial", int(self.screen_h * 0.025), "bold")
        self.font_title = ("Arial", int(self.screen_h * 0.012), "bold")
        self.font_normal = ("Arial", int(self.screen_h * 0.015), "bold")
        self.font_small = ("Arial", int(self.screen_h * 0.008), "bold")
        self.font_header = ("Arial", int(self.screen_h * 0.02), "bold")
        self.font_device = ("Arial", int(self.screen_h * 0.01), "bold")
        self.font_rssi = ("Arial", int(self.screen_h * 0.012), "bold")
        self.font_bold_small = ("Arial", int(self.screen_h * 0.01), "bold")

        # Load logo image
        self.logo_img = None
        self.logo_img_small = None
        try:
            logo_path = 'arrdy-logo.png'
            if getattr(sys, 'frozen', False):
                logo_path = os.path.join(sys._MEIPASS, logo_path)
            pil_image = Image.open(logo_path)
            self.logo_img = ImageTk.PhotoImage(pil_image)
            try:
                self.iconphoto(False, self.logo_img)
            except Exception:
                pass
            
            # Resize for display
            pil_resized = pil_image.resize((int(self.screen_w * 0.03), int(self.screen_h * 0.05)), Image.Resampling.LANCZOS)
            self.logo_img_small = ImageTk.PhotoImage(pil_resized)
        except Exception:
            pass

        self.bind('<Escape>', lambda e: self.attributes('-fullscreen', False))

        # Infrastructure
        self.db_manager = DatabaseManager()
        self.port_manager = SerialPortManager()
        self.packet_processor = PacketProcessor()
        self.port_manager2 = SerialPortManager()
        self.packet_processor2 = PacketProcessor()
        self.data_parser = SensorDataParser()

        # State Variables
        self.station_name = tk.StringVar(value="LADLE STATION 01")
        self.station_name2 = tk.StringVar(value="LADLE STATION 02")
        self.view_mode = tk.StringVar(value="Digital View")
        self.view_mode2 = tk.StringVar(value="Digital View")
        self.units = tk.StringVar(value="°C")
        self.time_scale_str = tk.StringVar(value="1 Minute")
        self.y_axis_mode = tk.StringVar(value="Autoscale")
        self.y_min = tk.DoubleVar(value=1500.0)
        self.y_max = tk.DoubleVar(value=1600.0)
        self.apply_rtd_compensation = tk.BooleanVar(value=False)
        self.apply_rtd_compensation2 = tk.BooleanVar(value=False)
        
        self.eth_ip = tk.StringVar(value="192.168.1.100")
        self.eth_port = tk.StringVar(value="502")

        # TX1 vars
        self.current_temp = tk.StringVar(value="--")
        self.device_id_val = tk.StringVar(value="WAITING")
        self.thermo_val = tk.StringVar(value="--")
        self.rtd_temp = tk.StringVar(value="--")
        self.battery_val = tk.StringVar(value="--")
        self.rssi_val = tk.StringVar(value="--")
        self.status_msg = tk.StringVar(value="Ready")
        self.com_port_val = tk.StringVar(value="NOT CONNECTED")
        self.is_reading = False
        self.is_paired = tk.BooleanVar(value=False)
        self.transmitter_id_val = tk.StringVar(value="WAITING")
        self.raw_hex = tk.StringVar(value="--")
        self.bat_voltage = tk.StringVar(value="--")
        self.bat_pct = tk.StringVar(value="--%")

        # TX2 vars
        self.current_temp2 = tk.StringVar(value="--")
        self.device_id_val2 = tk.StringVar(value="WAITING")
        self.thermo_val2 = tk.StringVar(value="--")
        self.rtd_temp2 = tk.StringVar(value="--")
        self.battery_val2 = tk.StringVar(value="--")
        self.rssi_val2 = tk.StringVar(value="--")
        self.status_msg2 = tk.StringVar(value="Ready")
        self.com_port_val2 = tk.StringVar(value="NOT CONNECTED")
        self.is_reading2 = False
        self.is_paired2 = tk.BooleanVar(value=False)
        self.transmitter_id_val2 = tk.StringVar(value="WAITING")
        self.raw_hex2 = tk.StringVar(value="--")
        self.bat_voltage2 = tk.StringVar(value="--")
        self.bat_pct2 = tk.StringVar(value="--%")

        # Status text for header
        self.tx_status_summary = tk.StringVar(value="WAITING TX1: WAITING TX2: WAITING")

        # Graph buffers
        self.buffer_size = 20
        self.temp_data = deque(maxlen=self.buffer_size)
        self.time_data = deque(maxlen=self.buffer_size)
        self.temp_data2 = deque(maxlen=self.buffer_size)
        self.time_data2 = deque(maxlen=self.buffer_size)
        
        # Trace updates
        self.time_scale_str.trace_add('write', self._on_buffer_update)

        self.container = tk.Frame(self, bg="#f0f0f0")
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.frames = {}
        for F in (DashboardFrame, SettingsFrame):
            frame = F(parent=self.container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        
        self.show_frame("DashboardFrame")

    def _on_buffer_update(self, *args):
        self.update_buffer_size()

    def show_frame(self, name):
        frame = self.frames[name]
        frame.tkraise()
        if hasattr(frame, "refresh_layout"):
            frame.refresh_layout()
        if hasattr(frame, "refresh_active_tx_vars"):
            frame.refresh_active_tx_vars()
        if hasattr(frame, "refresh_graph_view_row"):
            frame.refresh_graph_view_row()

    def update_buffer_size(self):
        scale_map = {"1 Minute": 60, "5 Minutes": 300, "15 Minutes": 900, "1 Hour": 3600}
        seconds = scale_map.get(self.time_scale_str.get(), 60)
        new_len = max(20, int(seconds / 3))
        if new_len != self.buffer_size:
            self.buffer_size = new_len
            self.temp_data = deque(self.temp_data, maxlen=self.buffer_size)
            self.time_data = deque(self.time_data, maxlen=self.buffer_size)
            self.temp_data2 = deque(self.temp_data2, maxlen=self.buffer_size)
            self.time_data2 = deque(self.time_data2, maxlen=self.buffer_size)

class DashboardFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#ffffff")
        self.controller = controller
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Header
        header = tk.Frame(self, bg="#ffffff", height=int(self.controller.screen_h * 0.12))
        header.grid(row=0, column=0, sticky="nsew")
        header.grid_propagate(False)
        
        # Left Header: Logo + Station Info
        left_h = tk.Frame(header, bg="#ffffff")
        left_h.pack(side="left", fill="y", padx=10, pady=5)
        
        if controller.logo_img_small:
            tk.Label(left_h, image=controller.logo_img_small, bg="#ffffff").grid(row=0, column=0, rowspan=3, padx=5)
        
        tk.Label(left_h, textvariable=controller.station_name, bg="#ffffff", fg="#333333", font=("Arial", 12, "bold")).grid(row=0, column=1, sticky="w")
        
        status_line = tk.Frame(left_h, bg="#ffffff")
        status_line.grid(row=1, column=1, sticky="w")
        tk.Label(status_line, text="WAITING ", bg="#ffffff", fg="#333333", font=("Arial", 9, "bold")).pack(side="left")
        tk.Label(status_line, text="TX1: ", bg="#ffffff", fg="#999999", font=("Arial", 9)).pack(side="left")
        tk.Label(status_line, textvariable=controller.transmitter_id_val, bg="#ffffff", fg="#d40000", font=("Arial", 9, "bold")).pack(side="left")
        tk.Label(status_line, text="  TX2: ", bg="#ffffff", fg="#999999", font=("Arial", 9)).pack(side="left")
        tk.Label(status_line, textvariable=controller.transmitter_id_val2, bg="#ffffff", fg="#0055aa", font=("Arial", 9, "bold")).pack(side="left")

        # Center Header: Time/Date
        center_h = tk.Frame(header, bg="#ffffff")
        center_h.pack(side="left", fill="both", expand=True)
        self.lbl_time = tk.Label(center_h, text="", fg="#333333", bg="#ffffff", font=("Arial", 24, "bold"))
        self.lbl_time.pack(pady=(15, 0))
        self.lbl_date = tk.Label(center_h, text="", fg="#666666", bg="#ffffff", font=("Arial", 12))
        self.lbl_date.pack()
        self.update_clock()

        # Right Header: RSSI / BAT Stats
        right_h = tk.Frame(header, bg="#ffffff")
        right_h.pack(side="right", padx=20, pady=10)
        
        # BAT header
        tk.Label(right_h, text="BAT --%", bg="#ffffff", fg="#333333", font=("Arial", 22, "bold")).grid(row=0, column=1, sticky="e")
        
        # TX1 Right Info
        tx1_info = tk.Frame(right_h, bg="#ffffff")
        tx1_info.grid(row=1, column=1, sticky="e")
        tk.Label(tx1_info, text="TX1", bg="#ffffff", fg="#d40000", font=("Arial", 8, "bold")).pack(side="right", padx=(5,0))
        
        tx1_stats = tk.Frame(right_h, bg="#ffffff")
        tx1_stats.grid(row=2, column=1, sticky="e")
        tk.Label(tx1_stats, text="RSSI --", bg="#ffffff", fg="#d40000", font=("Arial", 10, "bold")).pack(side="left")
        
        # TX2 Right Info
        tx2_info = tk.Frame(right_h, bg="#ffffff")
        tx2_info.grid(row=3, column=1, sticky="e")
        tk.Label(tx2_info, text="TX2", bg="#ffffff", fg="#0055aa", font=("Arial", 8, "bold")).pack(side="right", padx=(5,0))
        
        tx2_stats = tk.Frame(right_h, bg="#ffffff")
        tx2_stats.grid(row=4, column=1, sticky="e")
        tk.Label(tx2_stats, text="BAT --", bg="#ffffff", fg="#333333", font=("Arial", 10, "bold")).pack(side="left")
        tk.Label(tx2_stats, text="RSSI --", bg="#ffffff", fg="#0055aa", font=("Arial", 10, "bold")).pack(side="left", padx=(10,0))

        # Main Area
        self.main_container = tk.Frame(self, bg="#ffffff")
        self.main_container.grid(row=1, column=0, sticky="nsew")
        self.main_container.grid_columnconfigure(0, weight=1); self.main_container.grid_columnconfigure(1, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        self.tx1_view = "Digital"; self.tx2_view = "Digital"
        
        self.tx1_panel = tk.Frame(self.main_container, bg="#ffffff", relief="solid", borderwidth=1)
        self.tx1_panel.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self._build_tx_panel(self.tx1_panel, 1)

        self.tx2_panel = tk.Frame(self.main_container, bg="#ffffff", relief="solid", borderwidth=1)
        self.tx2_panel.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        self._build_tx_panel(self.tx2_panel, 2)

    def _build_tx_panel(self, parent, idx):
        is_tx1 = (idx == 1)
        color = "#d40000" if is_tx1 else "#0055aa"
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Panel Header
        p_header = tk.Frame(parent, bg=color, height=40)
        p_header.grid(row=0, column=0, sticky="ew")
        tk.Label(p_header, text=f"TRANSMITTER {idx}", bg=color, fg="white", font=("Arial", 16, "bold")).pack(side="left", padx=10)
        tk.Label(p_header, textvariable=self.controller.transmitter_id_val if is_tx1 else self.controller.transmitter_id_val2, bg=color, fg="white", font=("Arial", 10)).pack(side="right", padx=10)

        # Main Content
        content = tk.Frame(parent, bg="white")
        content.grid(row=1, column=0, sticky="nsew")
        
        # Digital View Frame
        df = tk.Frame(content, bg="white")
        df.pack(fill="both", expand=True)
        
        tk.Label(df, text="MELT TEMPERATURE", bg="white", fg="#333333", font=("Arial", 12, "bold")).pack(pady=(10, 5))
        
        # Large Value Background
        val_bg = tk.Frame(df, bg=color, height=130)
        val_bg.pack(fill="x", padx=15, pady=5)
        val_bg.pack_propagate(False)
        tk.Label(val_bg, textvariable=self.controller.thermo_val if is_tx1 else self.controller.thermo_val2, bg=color, fg="white", font=("Arial", 70, "bold")).pack(expand=True)
        
        tk.Label(df, text="°C", bg="white", fg="#333333", font=("Arial", 18, "bold")).pack()

        # Alert Boxes
        alert_f = tk.Frame(df, bg="white")
        alert_f.pack(fill="x", padx=10, pady=10)
        alert_f.grid_columnconfigure(0, weight=1); alert_f.grid_columnconfigure(1, weight=1); alert_f.grid_columnconfigure(2, weight=1)
        
        self._create_alert_box(alert_f, "BATTERY", 0, idx)
        self._create_alert_box(alert_f, "THERMOCOUPLE", 1, idx)
        self._create_alert_box(alert_f, "RTD", 2, idx)

        # Values Row (RTD Temp, Device Temp, RSSI)
        vals_f = tk.Frame(df, bg="white")
        vals_f.pack(fill="x", padx=10, pady=10)
        vals_f.grid_columnconfigure(0, weight=1); vals_f.grid_columnconfigure(1, weight=1); vals_f.grid_columnconfigure(2, weight=1)
        
        self._create_value_display(vals_f, "RTD TEMP", self.controller.rtd_temp if is_tx1 else self.controller.rtd_temp2, "°C", 0)
        self._create_value_display(vals_f, "DEVICE TEMP", self.controller.thermo_val if is_tx1 else self.controller.thermo_val2, "°C", 1) # Using thermo_val as device temp for now
        self._create_value_display(vals_f, "RSSI", self.controller.rssi_val if is_tx1 else self.controller.rssi_val2, "dBm", 2)

        # Panel Footer (Buttons)
        footer = tk.Frame(parent, bg="#e6e6e6", height=45)
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_propagate(False)
        
        tk.Button(footer, text="⚙ PAIR DEVICE", font=("Arial", 9, "bold"), bg="#d0d0d0", fg="#333333", relief="raised", command=lambda: self.pair(idx)).pack(side="left", fill="y", padx=5, pady=5)
        tk.Button(footer, text="⚙ CONFIGURATION", font=("Arial", 9, "bold"), bg="#d0d0d0", fg="#333333", relief="raised", command=lambda: self.open_config(idx)).pack(side="left", fill="y", padx=5, pady=5)

    def _create_alert_box(self, parent, title, col, idx):
        box = tk.Frame(parent, bg="white", relief="solid", borderwidth=1)
        box.grid(row=0, column=col, sticky="ew", padx=3)
        
        header = tk.Frame(box, bg="white")
        header.pack(pady=2)
        tk.Label(header, text="●", fg="black", bg="white", font=("Arial", 8)).pack(side="left")
        tk.Label(header, text=title, bg="white", font=("Arial", 7, "bold")).pack(side="left", padx=2)
        
        lbl = tk.Label(box, text="Normal", fg="green", bg="white", font=("Arial", 11, "bold"))
        lbl.pack(pady=(0, 5))
        
        # Store refs
        setattr(self, f"{title.lower()}_{idx}_lbl", lbl)
        setattr(self, f"{title.lower()}_{idx}_box", box)

    def _create_value_display(self, parent, label, var, unit, col):
        f = tk.Frame(parent, bg="white")
        f.grid(row=0, column=col, sticky="ew")
        tk.Label(f, text=label, bg="white", fg="#666666", font=("Arial", 7, "bold")).pack()
        tk.Label(f, textvariable=var, bg="white", fg="#0055aa", font=("Arial", 12, "bold")).pack()
        tk.Label(f, text=unit, bg="white", fg="#666666", font=("Arial", 7)).pack()

    def update_clock(self):
        now = datetime.now()
        self.lbl_time.config(text=now.strftime("%H:%M:%S"))
        self.lbl_date.config(text=now.strftime("%d-%b-%Y"))
        self.after(1000, self.update_clock)

    def pair(self, idx): ConnectionSettings(self.controller, self, tx_index=idx)
    
    def open_config(self, idx):
        pwd = simpledialog.askstring("Security", "Enter Password:", show='*')
        if pwd == "1111":
            sf = self.controller.frames["SettingsFrame"]
            sf.active_tx = idx
            self.controller.show_frame("SettingsFrame")

    def refresh_layout(self):
        pass

    def refresh_active_tx_vars(self): pass
    def refresh_graph_view_row(self): pass

    def _process_data(self, pkt, idx):
        is_tx1 = (idx == 1)
        comp = self.controller.apply_rtd_compensation.get() if is_tx1 else self.controller.apply_rtd_compensation2.get()
        try:
            res = self.controller.data_parser.parse_packet(pkt, enable_rtd_compensation=comp)
            if res:
                if is_tx1:
                    self.controller.thermo_val.set(f"{res.thermocouple:.1f}")
                    self.controller.rtd_temp.set(f"{res.rtd_temperature}")
                    self.controller.battery_val.set(f"{res.battery_voltage:.2f}V")
                    self.controller.rssi_val.set(f"{res.rssi}")
                    self.controller.transmitter_id_val.set(res.device_id)
                else:
                    self.controller.thermo_val2.set(f"{res.thermocouple:.1f}")
                    self.controller.rtd_temp2.set(f"{res.rtd_temperature}")
                    self.controller.battery_val2.set(f"{res.battery_voltage:.2f}V")
                    self.controller.rssi_val2.set(f"{res.rssi}")
                    self.controller.transmitter_id_val2.set(res.device_id)
                
                self.controller.db_manager.log_measurement(
                    self.controller.station_name.get() if is_tx1 else self.controller.station_name2.get(),
                    res.device_id, 0, 0, 0, 0, res.rssi, idx
                )
                self._check_alerts(res, idx)
        except Exception as e: logger.error(e)

    def _check_alerts(self, data, idx):
        # Update alert box statuses
        b_lbl = getattr(self, f"battery_{idx}_lbl", None)
        if b_lbl:
            if data.battery_voltage < 3.4: b_lbl.config(text="Low", fg="red")
            else: b_lbl.config(text="Normal", fg="green")

class SettingsFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f0f0f0")
        self.controller = controller
        self.active_tx = 1

        # Layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=200)
        self.grid_columnconfigure(1, weight=1)

        sidebar = tk.Frame(self, bg="#b0b0b0", width=200); sidebar.grid(row=0, column=0, sticky="nsew"); sidebar.grid_propagate(False)
        tk.Label(sidebar, text="SETTINGS", bg="#b0b0b0", font=("Arial", 16, "bold")).pack(pady=20)
        
        self.tabs = ["General", "Graph", "Transmitter", "Outputs", "Troubleshooting", "History", "RTD Compensation"]
        self.btns = {}
        for t in self.tabs:
            b = tk.Button(sidebar, text=t.upper(), bg="#b0b0b0", relief="flat", anchor="w", padx=20, command=lambda name=t: self.show_tab(name))
            b.pack(fill="x", pady=2)
            self.btns[t] = b
        
        tk.Button(sidebar, text="← BACK", bg="#d40000", fg="white", font=("Arial", 10, "bold"), command=lambda: controller.show_frame("DashboardFrame")).pack(side="bottom", fill="x", pady=10)

        self.container = tk.Frame(self, bg="white"); self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1); self.container.grid_columnconfigure(0, weight=1)

        # Temp vars
        self.temp_name = tk.StringVar(); self.temp_rtd = tk.BooleanVar(); self.temp_vmode = tk.StringVar()
        self.temp_yscale = tk.StringVar(); self.temp_ymin = tk.StringVar(); self.temp_ymax = tk.StringVar(); self.temp_ymode = tk.StringVar()
        self.date_from = tk.StringVar(); self.date_to = tk.StringVar()

        self.frames = {}
        self._init_tabs()
        self.show_tab("General")

    def _init_tabs(self):
        # General
        f = tk.Frame(self.container, bg="white"); self.frames["General"] = f
        tk.Label(f, text="General Settings", font=("Arial", 14, "bold"), bg="white").pack(anchor="w", padx=20, pady=20)
        self._create_row(f, "Station Name:", self.temp_name)
        tk.Button(f, text="SAVE", bg="#4caf50", fg="white", command=lambda: self.save("General")).pack(pady=20)

        # Graph
        f = tk.Frame(self.container, bg="white"); self.frames["Graph"] = f
        tk.Label(f, text="Graph Configuration", font=("Arial", 14, "bold"), bg="white").pack(anchor="w", padx=20, pady=20)
        self.row_vmode = tk.Frame(f, bg="white"); self.row_vmode.pack(fill="x", padx=20)
        tk.Label(self.row_vmode, text="View Mode:", width=15, bg="white").pack(side="left")
        ttk.Combobox(self.row_vmode, textvariable=self.temp_vmode, values=["Digital View", "Graph View"]).pack(side="left")
        
        self._create_combo(f, "Time Scale:", self.temp_yscale, ["1 Minute", "5 Minutes", "15 Minutes", "1 Hour"])
        self._create_row(f, "Y Min:", self.temp_ymin)
        self._create_row(f, "Y Max:", self.temp_ymax)
        self._create_combo(f, "Y Mode:", self.temp_ymode, ["Autoscale", "Manual"])
        tk.Button(f, text="SAVE", bg="#4caf50", fg="white", command=lambda: self.save("Graph")).pack(pady=20)

        # Transmitter
        f = tk.Frame(self.container, bg="white"); self.frames["Transmitter"] = f
        tk.Label(f, text="Transmitter Pairing", font=("Arial", 14, "bold"), bg="white").pack(anchor="w", padx=20, pady=20)
        self.lbl_paired = tk.Label(f, text="Paired ID: --", bg="white", font=("Arial", 12))
        self.lbl_paired.pack(pady=10)

        # Outputs
        f = tk.Frame(self.container, bg="white"); self.frames["Outputs"] = f
        tk.Label(f, text="Output Port Settings", font=("Arial", 14, "bold"), bg="white").pack(anchor="w", padx=20, pady=20)
        self._create_row(f, "Modbus TCP IP:", self.controller.eth_ip)
        self._create_row(f, "Modbus TCP Port:", self.controller.eth_port)

        # Troubleshooting
        f = tk.Frame(self.container, bg="white"); self.frames["Troubleshooting"] = f
        tk.Label(f, text="Diagnostics", font=("Arial", 14, "bold"), bg="white").pack(anchor="w", padx=20, pady=20)
        self.diag_hex = tk.Label(f, text="Raw:", bg="white"); self.diag_hex.pack(pady=5)
        self.diag_bat = tk.Label(f, text="Battery:", bg="white"); self.diag_bat.pack(pady=5)

        # History
        f = tk.Frame(self.container, bg="white"); self.frames["History"] = f
        tk.Label(f, text="Data Logs", font=("Arial", 14, "bold"), bg="white").pack(anchor="w", padx=20, pady=20)
        rf = tk.Frame(f, bg="white"); rf.pack(fill="x", padx=20)
        tk.Entry(rf, textvariable=self.date_from, width=15).pack(side="left")
        tk.Button(rf, text="📅", command=lambda: DateTimePopup(self, lambda d: self.date_from.set(d))).pack(side="left")
        tk.Label(rf, text=" to ", bg="white").pack(side="left")
        tk.Entry(rf, textvariable=self.date_to, width=15).pack(side="left")
        tk.Button(rf, text="📅", command=lambda: DateTimePopup(self, lambda d: self.date_to.set(d))).pack(side="left")
        tk.Button(rf, text="EXPORT CSV", command=self.export_csv).pack(side="right")

        # RTD
        f = tk.Frame(self.container, bg="white"); self.frames["RTD Compensation"] = f
        tk.Label(f, text="RTD Compensation", font=("Arial", 14, "bold"), bg="white").pack(anchor="w", padx=20, pady=20)
        tk.Checkbutton(f, text="Enable Professional RTD Correction", variable=self.temp_rtd, bg="white").pack(pady=20)
        tk.Button(f, text="SAVE", bg="#4caf50", fg="white", command=lambda: self.save("RTD Compensation")).pack(pady=20)

        for fr in self.frames.values(): fr.grid(row=0, column=0, sticky="nsew")

    def _create_row(self, p, l, v):
        row = tk.Frame(p, bg="white"); row.pack(fill="x", padx=20, pady=5)
        tk.Label(row, text=l, width=15, anchor="w", bg="white").pack(side="left")
        tk.Entry(row, textvariable=v, width=30).pack(side="left", padx=10)

    def _create_combo(self, p, l, v, opts):
        row = tk.Frame(p, bg="white"); row.pack(fill="x", padx=20, pady=5)
        tk.Label(row, text=l, width=15, anchor="w", bg="white").pack(side="left")
        ttk.Combobox(row, textvariable=v, values=opts, width=28).pack(side="left", padx=10)

    def show_tab(self, name):
        for b in self.btns.values(): b.config(bg="#b0b0b0")
        self.btns[name].config(bg="white")
        self.frames[name].tkraise()

    def refresh_active_tx_vars(self):
        c = self.controller; tx = self.active_tx
        if tx == 1:
            self.temp_name.set(c.station_name.get()); self.temp_vmode.set(c.view_mode.get()); self.temp_rtd.set(c.apply_rtd_compensation.get())
            if hasattr(self, 'lbl_paired'): self.lbl_paired.config(text=f"Paired ID: {c.transmitter_id_val.get()}")
            if hasattr(self, 'diag_hex'): self.diag_hex.config(text=f"Raw HEX: {c.raw_hex.get()}")
            if hasattr(self, 'diag_bat'): self.diag_bat.config(text=f"Battery: {c.bat_voltage.get()}")
        else:
            self.temp_name.set(c.station_name2.get()); self.temp_vmode.set(c.view_mode2.get()); self.temp_rtd.set(c.apply_rtd_compensation2.get())
            if hasattr(self, 'lbl_paired'): self.lbl_paired.config(text=f"Paired ID: {c.transmitter_id_val2.get()}")
            if hasattr(self, 'diag_hex'): self.diag_hex.config(text=f"Raw HEX: {c.raw_hex2.get()}")
            if hasattr(self, 'diag_bat'): self.diag_bat.config(text=f"Battery: {c.bat_voltage2.get()}")
        
        self.temp_yscale.set(c.time_scale_str.get()); self.temp_ymode.set(c.y_axis_mode.get())
        self.temp_ymin.set(str(c.y_min.get())); self.temp_ymax.set(str(c.y_max.get()))

    def refresh_layout(self): pass
    def refresh_graph_view_row(self): pass

    def save(self, tab):
        c = self.controller; tx = self.active_tx
        try:
            if tab == "General":
                if tx == 1: c.station_name.set(self.temp_name.get())
                else: c.station_name2.set(self.temp_name.get())
            elif tab == "Graph":
                if tx == 1: c.view_mode.set(self.temp_vmode.get())
                else: c.view_mode2.set(self.temp_vmode2.get())
                c.time_scale_str.set(self.temp_yscale.get())
                c.y_axis_mode.set(self.temp_ymode.get())
                c.y_min.set(float(self.temp_ymin.get())); c.y_max.set(float(self.temp_ymax.get()))
                c.update_buffer_size()
            elif tab == "RTD Compensation":
                if tx == 1: c.apply_rtd_compensation.set(self.temp_rtd.get())
                else: c.apply_rtd_compensation2.set(self.temp_rtd.get())
            messagebox.showinfo("Success", f"{tab} settings saved.")
        except Exception as e: messagebox.showerror("Error", str(e))

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not path: return
        try:
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Station", "Device ID", "RSSI", "TX Index"])
                # For simplicity, export last 1000 logs
                self.controller.db_manager.cursor.execute("SELECT timestamp, station_name, device_id, rssi, tx_index FROM measurements ORDER BY id DESC LIMIT 1000")
                writer.writerows(self.controller.db_manager.cursor.fetchall())
            messagebox.showinfo("Success", "Log exported to CSV.")
        except Exception as e: messagebox.showerror("Error", str(e))
