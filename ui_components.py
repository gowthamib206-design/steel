import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import calendar
import logging
import threading

logger = logging.getLogger(__name__)

class CalendarPopup(tk.Toplevel):
    """A minimal calendar popup to choose a date (YYYY-MM-DD)."""
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
    """A calendar and time picker popup to choose a datetime (YYYY-MM-DD HH:MM:SS)."""
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

        self.hour_var = tk.StringVar(value=str(self.hour).zfill(2))
        self.minute_var = tk.StringVar(value=str(self.minute).zfill(2))
        self.second_var = tk.StringVar(value=str(self.second).zfill(2))

        self.body = tk.Frame(self)
        self.body.pack(padx=8, pady=8)

        nav = tk.Frame(self.body)
        nav.pack(fill='x', pady=(0, 10))
        tk.Button(nav, text='<', width=3, command=self._prev_month).pack(side='left')
        self.title_lbl = tk.Label(nav, text='', width=20)
        self.title_lbl.pack(side='left', padx=6)
        tk.Button(nav, text='>', width=3, command=self._next_month).pack(side='right')

        self.cal_frame = tk.Frame(self.body)
        self.cal_frame.pack(pady=(0, 10))

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


class ConnectionSettings(tk.Toplevel):
    """COM Port Configuration Popup — opens immediately, requests password, enables controls on success."""

    def __init__(self, controller, dashboard, is_connected=False, tx_index=1):
        super().__init__(dashboard)
        logger.info(f"Opening ConnectionSettings window TX{tx_index}")

        self.controller = controller
        self.dashboard = dashboard
        self.tx_index = tx_index
        is_tx1 = (tx_index == 1)

        # Point to the correct port manager and state vars
        self._port_manager = controller.port_manager if is_tx1 else controller.port_manager2
        self._packet_processor = controller.packet_processor if is_tx1 else controller.packet_processor2
        self._tx_id_var = controller.transmitter_id_val if is_tx1 else controller.transmitter_id_val2
        self._com_port_var = controller.com_port_val if is_tx1 else controller.com_port_val2
        self._conn_window_attr = "connection_window" if is_tx1 else "connection_window2"
        self._is_connected_attr = "is_connected" if is_tx1 else "is_connected2"
        self._is_reading_attr = "is_reading" if is_tx1 else "is_reading2"
        self._read_data_fn = dashboard._read_data if is_tx1 else dashboard._read_data2
        self._conn_status_key = "connection_status" if is_tx1 else "connection_status2"

        self.title(f"Connection Settings - Transmitter {tx_index}")
        self.state("zoomed")
        self.minsize(900, 600)
        self.configure(bg="#f0f0f0")

        tk.Label(self, text=f"USB / COM Port Configuration — Transmitter {tx_index}", font=("Arial", 14, "bold"), bg="#f0f0f0").pack(pady=15)

        frame = tk.Frame(self, bg="#f0f0f0")
        frame.pack(pady=10)
        tk.Label(frame, text="USB Port:", bg="#f0f0f0", font=("Arial", 11)).pack(side="left", padx=5)
        self.combo = ttk.Combobox(frame, width=20, state="readonly")
        self.combo.pack(side="left", padx=5)

        btns = tk.Frame(self, bg="#f0f0f0")
        btns.pack(pady=20)
        self.btn_refresh = tk.Button(btns, text="🔄 REFRESH", width=12, command=self.update_ports, state="disabled")
        self.btn_refresh.pack(side="left", padx=5)
        self.btn_connect = tk.Button(btns, text="✓ CONNECT", width=12, command=self.connect, state="disabled")
        self.btn_connect.pack(side="left", padx=5)
        self.btn_disconnect = tk.Button(btns, text="✗ DISCONNECT", width=12, command=self.disconnect, state="disabled")
        self.btn_disconnect.pack(side="left", padx=5)

        tx_frame = tk.Frame(self, bg="#f0f0f0")
        tx_frame.pack(pady=(5, 10))
        tk.Label(tx_frame, text="Transmitter ID:", bg="#f0f0f0", font=("Arial", 11)).pack(side="left", padx=5)
        self.tx_combo = ttk.Combobox(tx_frame, width=20, state="readonly")
        self.tx_combo.pack(side="left", padx=5)

        self.tx_ids = []
        self.selected_tx = None

        discovered_attr = "_discovered_tx_ids" if is_tx1 else "_discovered_tx_ids2"
        if hasattr(self.controller, discovered_attr) and getattr(self.controller, discovered_attr):
            try:
                self.tx_ids = list(getattr(self.controller, discovered_attr))
                self.tx_combo['values'] = self.tx_ids
                if self.tx_ids:
                    self.tx_combo.current(0)
                    self.selected_tx = self.tx_ids[0]
                    self._tx_id_var.set(self.selected_tx)
            except Exception:
                pass

        self.tx_combo.bind("<<ComboboxSelected>>", self.on_tx_selected)

        self.status_label = tk.Label(self, text="Locked — enter password to enable controls", bg="#f0f0f0")
        self.status_label.pack(pady=(0, 8))

        self.after(50, self.update_ports)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.lift()
        self.focus_force()
        self.after(100, self.ask_password)

    def update_ports(self):
        ports = self._port_manager.get_available_ports(exclude_connected=False)
        self.combo["values"] = ports if ports else []
        connected_port = self._com_port_var.get()
        if connected_port and connected_port != "NOT CONNECTED":
            try:
                index = ports.index(connected_port)
                self.combo.current(index)
            except (ValueError, tk.TclError):
                if ports: self.combo.current(0)
        elif ports:
            self.combo.current(0)

    def ask_password(self):
        pwd = simpledialog.askstring("Security", "Enter Password:", show='*', parent=self)
        if pwd == "1111":
            self.enable_controls()
        elif pwd is not None:
            messagebox.showerror("Access Denied", "Wrong Password", parent=self)
            self.status_label.config(text="Wrong password — controls locked", fg="red")

    def enable_controls(self):
        self.btn_refresh.config(state="normal")
        is_conn = getattr(self.dashboard, self._is_connected_attr, False)
        if is_conn:
            self.btn_connect.config(state="disabled")
            self.btn_disconnect.config(state="normal")
        else:
            self.btn_connect.config(state="normal")
            self.btn_disconnect.config(state="disabled")
        self.status_label.config(text="Unlocked — you may connect", fg="green")
        self.update_ports()

    def connect(self):
        port = self.combo.get()
        if not port:
            messagebox.showerror("Error", "Select a COM port", parent=self)
            return
        self.btn_connect.config(state="disabled")
        self.btn_disconnect.config(state="normal")
        self._com_port_var.set(port)
        self._open_port_for_tx()
        setattr(self.dashboard, self._is_connected_attr, True)
        setattr(self.controller, self._conn_status_key, "connected")

    def _open_port_for_tx(self):
        port_name = self.combo.get()
        def _bg():
            success, msg = self._port_manager.open_port(port_name)
            if success:
                self._com_port_var.set(port_name)
                if self.tx_index == 1:
                    self.controller.is_reading = True
                    self.controller.is_paired.set(True)
                else:
                    self.controller.is_reading2 = True
                    self.controller.is_paired2.set(True)
                def _ui():
                    self.status_label.config(text=f"✓ Connected to {port_name}", fg="green")
                    self.dashboard.after(0, self._read_data_fn)
                self.dashboard.after(0, _ui)
            else:
                def _ui_err():
                    self.status_label.config(text=f"✗ Failed: {msg}", fg="red")
                self.dashboard.after(0, _ui_err)

        threading.Thread(target=_bg, daemon=True).start()

    def disconnect(self):
        self._port_manager.close_port()
        if self.tx_index == 1:
            self.controller.is_reading = False
            self.controller.is_paired.set(False)
        else:
            self.controller.is_reading2 = False
            self.controller.is_paired2.set(False)

        setattr(self.controller, self._conn_status_key, "disconnected")
        setattr(self.dashboard, self._is_connected_attr, False)
        self._com_port_var.set("NOT CONNECTED")
        self._tx_id_var.set("NOT PAIRED")
        self.btn_connect.config(state="normal")
        self.btn_disconnect.config(state="disabled")
        self.status_label.config(text="Disconnected", fg="black")

    def on_tx_selected(self, event):
        self.selected_tx = self.tx_combo.get()
        self._tx_id_var.set(self.selected_tx)
