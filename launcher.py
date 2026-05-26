"""
Project Launcher
Click a button to run that file — only one runs at a time.
"""

import tkinter as tk
import subprocess
import sys
import os

PYTHON = sys.executable
BASE   = os.path.dirname(os.path.abspath(__file__))

APPS = [
    ("Wireless Sensor",     "newdrop_sensor.py",   "#0066cc"),
    ("Serial Logger",       "serial_logger.py",    "#7c3aed"),
    ("DB Date Viewer",      "convert_sql.py",      "#059669"),
    ("View Packets",        "view_packets.py",      "#b45309"),
]

class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Project Launcher")
        self.configure(bg="white")
        self.resizable(False, False)

        self._procs = {}   # name -> Popen

        tk.Label(self, text="Select a tool to launch",
                 bg="white", fg="#111111",
                 font=("Arial", 13, "bold"),
                 pady=14).pack()

        for name, script, color in APPS:
            row = tk.Frame(self, bg="white")
            row.pack(fill=tk.X, padx=30, pady=6)

            tk.Button(
                row, text=f"▶  {name}",
                bg=color, fg="white",
                font=("Arial", 11, "bold"),
                width=24, pady=8, relief=tk.FLAT, cursor="hand2",
                command=lambda s=script, n=name: self._launch(n, s)
            ).pack(side=tk.LEFT)

            lbl = tk.Label(row, text="", bg="white",
                           fg="#555555", font=("Arial", 9), width=14)
            lbl.pack(side=tk.LEFT, padx=10)
            # store label reference by name
            setattr(self, f"_lbl_{name}", lbl)

        tk.Frame(self, bg="#eeeeee", height=1).pack(fill=tk.X, padx=20, pady=10)

        tk.Button(
            self, text="✕  Exit Launcher",
            bg="#dc2626", fg="white",
            font=("Arial", 10, "bold"),
            pady=6, relief=tk.FLAT, cursor="hand2",
            command=self.destroy
        ).pack(pady=(0, 16))

        self.after(1000, self._poll)

    def _launch(self, name, script):
        path = os.path.join(BASE, script)
        if not os.path.exists(path):
            tk.messagebox.showerror("Not found", f"{script} not found.")
            return

        # If already running, bring focus (can't on subprocess, just warn)
        proc = self._procs.get(name)
        if proc and proc.poll() is None:
            lbl = getattr(self, f"_lbl_{name}")
            lbl.config(text="already running", fg="#b45309")
            return

        proc = subprocess.Popen([PYTHON, path],
                                 cwd=BASE,
                                 creationflags=subprocess.CREATE_NO_WINDOW
                                 if sys.platform == "win32" else 0)
        self._procs[name] = proc
        lbl = getattr(self, f"_lbl_{name}")
        lbl.config(text="● running", fg="#059669")

    def _poll(self):
        """Check every second if any process has stopped."""
        for name, proc in self._procs.items():
            lbl = getattr(self, f"_lbl_{name}")
            if proc.poll() is not None:
                lbl.config(text="stopped", fg="#6b7280")
            else:
                lbl.config(text="● running", fg="#059669")
        self.after(1000, self._poll)

    def destroy(self):
        for proc in self._procs.values():
            if proc.poll() is None:
                proc.terminate()
        super().destroy()


if __name__ == "__main__":
    app = Launcher()
    app.mainloop()
