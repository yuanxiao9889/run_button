import tkinter as tk
from tkinter import messagebox, simpledialog, Menu
import requests
import threading
import keyboard
import websocket
import json
import time
import os

import sys

# Visual Theme (Split Design)
THEME = {
    # Dimensions
    "norm_w": 160,
    "norm_h": 46,
    "mini_s": 46,
    "stop_w": 46, # Width of the stop button area
    "gap": 3,     # Gap between Run and Stop zones
    
    # Colors
    "bg_normal": "#57606f",     # Dark Grey
    "bg_hover": "#747d8c",      # Lighter Grey
    "bg_progress": "#2ecc71",   # Green Progress
    "bg_stop_hover": "#ff4757", # Red for Stop Hover
    "bg_offline": "#2f3542",    # Darker Grey for Offline
    
    "text": "#FFFFFF",
    
    "icon_play": "#7bed9f",         # Light Green
    "icon_stop_disabled": "#a4b0be",# Greyed out
    "icon_stop_enabled": "#FFFFFF", # White
    "icon_mini_x": "#ff6b6b",       # Red X for mini mode
    "icon_offline": "#747d8c"       # Grey icon for offline
}

def get_config_path():
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        base_path = os.path.dirname(sys.executable)
    else:
        # Running as script
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, "config.json")

CONFIG_FILE = get_config_path()
DEFAULT_CONFIG = {
    "comfy_url": "127.0.0.1:8188",
    "hotkey_toggle": "F9",
    "hotkey_run": "ctrl+enter"
}

class DesignButton(tk.Canvas):
    def __init__(self, master, run_cmd, stop_cmd, toggle_mode_cmd, settings_cmd, **kwargs):
        super().__init__(master, **kwargs)
        self.run_cmd = run_cmd
        self.stop_cmd = stop_cmd
        self.toggle_mode_cmd = toggle_mode_cmd
        self.settings_cmd = settings_cmd
        
        # State
        self.is_mini = False
        self.state = "offline" # idle, running, offline
        self.progress = 0.0
        self.queue_count = 0
        
        # Hover State
        self.hover_zone = None # None, 'run', 'stop'
        
        # Bind events
        self.bind("<Motion>", self.on_motion)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Configure>", self.draw)
        
        # Drag & Click Logic
        self.bind("<Button-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Button-3>", self.on_right_click)

        self.drag_start = None
        self.is_dragging = False

    def set_state(self, state, progress=0.0, queue=0):
        self.state = state
        self.progress = progress
        self.queue_count = queue
        self.draw()

    def set_mode(self, is_mini):
        self.is_mini = is_mini
        self.draw()

    def draw(self, event=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        
        if self.is_mini:
            self._draw_mini(w, h)
        else:
            self._draw_normal(w, h)

    def _draw_normal(self, w, h):
        stop_w = THEME["stop_w"]
        gap = THEME["gap"]
        run_w = w - stop_w - gap
        
        # --- 1. LEFT ZONE (RUN) ---
        # Background
        if self.state == "offline":
            run_bg = THEME["bg_offline"]
        else:
            run_bg = THEME["bg_normal"]
            if self.hover_zone == 'run':
                run_bg = THEME["bg_hover"]
            
        self.create_rectangle(0, 0, run_w, h, fill=run_bg, outline="")
        
        # Progress Bar (Overlay)
        if self.state == "running" and self.progress > 0:
            prog_pixel = run_w * self.progress
            self.create_rectangle(0, 0, prog_pixel, h, fill=THEME["bg_progress"], outline="")

        # Content (Icon + Text)
        cy = h / 2
        
        if self.state == "offline":
            self.create_text(run_w/2, cy, text="OFFLINE", fill="#a4b0be", font=("Segoe UI", 12, "bold"))
            
        elif self.state == "idle":
            # Icon Play + "RUN"
            content_w = 20 + 10 + 40 # approx
            start_x = (run_w - content_w) / 2
            
            # Icon
            self._draw_play_icon(start_x + 10, cy, 16)
            # Text
            self.create_text(start_x + 30, cy, text="RUN", fill="white", font=("Segoe UI", 12, "bold"), anchor="w")
            
        else:
            # Running State
            # Queue Badge
            left_margin = 10
            if self.queue_count > 0:
                self.create_text(left_margin, cy, text=f"({self.queue_count})", fill="white", font=("Segoe UI", 12, "bold"), anchor="w")
                left_margin += 25
            
            # Progress Text (Percentage only)
            pct = int(self.progress * 100)
            p_text = f"{pct}%..." 
            self.create_text(left_margin, cy, text=p_text, fill="white", font=("Segoe UI", 12, "bold"), anchor="w")

        # --- 2. RIGHT ZONE (STOP) ---
        stop_start_x = run_w + gap
        
        # Background
        stop_bg = THEME["bg_normal"]
        if self.state == "offline":
            stop_bg = THEME["bg_offline"]
        else:
            # Only hover if active
            is_stop_active = (self.state == "running")
            if is_stop_active:
                stop_bg = "#4b4b4b" 
                if self.hover_zone == 'stop':
                    stop_bg = THEME["bg_stop_hover"]
            else:
                stop_bg = "#404040"

        self.create_rectangle(stop_start_x, 0, w, h, fill=stop_bg, outline="")
        
        # Icon X
        if self.state == "offline":
            icon_color = THEME["icon_offline"]
        else:
            is_stop_active = (self.state == "running")
            icon_color = THEME["icon_stop_enabled"] if is_stop_active else THEME["icon_stop_disabled"]
            
        cx = stop_start_x + (stop_w / 2)
        self._draw_x_icon(cx, cy, 14, icon_color)

    def _draw_mini(self, w, h):
        # Background
        bg = THEME["bg_normal"]
        if self.state == "offline":
            bg = THEME["bg_offline"]
        elif self.hover_zone == 'mini':
            bg = THEME["bg_hover"]
        self.create_rectangle(0, 0, w, h, fill=bg, outline="")
        
        cx, cy = w/2, h/2
        
        if self.state == "offline":
             self._draw_x_icon(cx, cy, 18, THEME["icon_offline"])
        elif self.state == "idle":
            self._draw_play_icon(cx, cy, 20)
        else:
            # Running -> Show X (Stop)
            self._draw_x_icon(cx, cy, 18, THEME["icon_mini_x"])

    # --- Icon Helpers ---
    def _draw_play_icon(self, cx, cy, size):
        r = size / 2
        points = [
            cx - r/1.5, cy - r,
            cx - r/1.5, cy + r,
            cx + r, cy
        ]
        self.create_polygon(points, fill=THEME["icon_play"], outline="")

    def _draw_x_icon(self, cx, cy, size, color):
        r = size / 2
        # Draw two lines
        self.create_line(cx - r, cy - r, cx + r, cy + r, fill=color, width=3, capstyle=tk.ROUND)
        self.create_line(cx + r, cy - r, cx - r, cy + r, fill=color, width=3, capstyle=tk.ROUND)

    # --- Interaction Logic ---
    def on_motion(self, e):
        w = self.winfo_width()
        
        if self.is_mini:
            self.hover_zone = 'mini'
        else:
            stop_x = w - THEME["stop_w"]
            if e.x > stop_x:
                self.hover_zone = 'stop'
            else:
                self.hover_zone = 'run'
        
        self.draw()

    def on_leave(self, e):
        self.hover_zone = None
        self.draw()

    def on_press(self, e):
        self.drag_start = (e.x_root, e.y_root)
        self.is_dragging = False

    def on_drag(self, e):
        if not self.drag_start: return
        
        dx = e.x_root - self.drag_start[0]
        dy = e.y_root - self.drag_start[1]
        
        if abs(dx) > 3 or abs(dy) > 3:
            self.is_dragging = True
            
        root = self.winfo_toplevel()
        root.geometry(f"+{root.winfo_x() + dx}+{root.winfo_y() + dy}")
        self.drag_start = (e.x_root, e.y_root)

    def on_release(self, e):
        if not self.is_dragging:
            self.handle_click(e)
        self.drag_start = None
        self.is_dragging = False

    def handle_click(self, e):
        if self.state == "offline":
            return # Ignore clicks when offline

        if self.is_mini:
            if self.state == "running":
                if self.stop_cmd: self.stop_cmd()
            else:
                if self.run_cmd: self.run_cmd()
        else:
            w = self.winfo_width()
            stop_x = w - THEME["stop_w"]
            
            if e.x > stop_x:
                if self.state == "running":
                    if self.stop_cmd: self.stop_cmd()
            else:
                if self.run_cmd: self.run_cmd()

    def on_right_click(self, e):
        # Create Context Menu
        m = Menu(self, tearoff=0)
        m.add_command(label="Toggle Mini Mode", command=self.toggle_mode_cmd)
        m.add_separator()
        m.add_command(label="Settings (IP)", command=self.settings_cmd)
        m.tk_popup(e.x_root, e.y_root)


class FloatApp:
    def __init__(self):
        self.root = tk.Tk()
        self.is_mini = False
        self.ws = None
        self.ws_connected = False
        
        self.load_config()
        self.setup_urls()
        
        self.setup_window()
        self.setup_ui()
        self.setup_hotkey()
        
        # Start Heartbeat & WS
        threading.Thread(target=self.connection_manager_loop, daemon=True).start()

        # Check config on startup
        if "comfy_url" not in self.config or not self.config["comfy_url"]:
             self.root.after(500, self.prompt_for_ip)

    def load_config(self):
        self.config = DEFAULT_CONFIG.copy()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    user_config = json.load(f)
                    self.config.update(user_config)
            except: pass

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
        except: pass

    def setup_urls(self):
        base = self.config.get("comfy_url", "127.0.0.1:8188")
        if "://" not in base:
            base = f"{base}" # Assume IP:Port
        
        # Strip protocol if user added it
        clean_base = base.replace("http://", "").replace("https://", "").replace("ws://", "")
        
        self.trigger_url = f"http://{clean_base}/run_button/trigger"
        self.interrupt_url = f"http://{clean_base}/interrupt"
        self.ws_url = f"ws://{clean_base}/ws"
        self.stats_url = f"http://{clean_base}/system_stats" # Used for ping

    def setup_window(self):
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg="#2C2C2C")
        self.root.geometry(f"{THEME['norm_w']}x{THEME['norm_h']}+100+100")

    def setup_ui(self):
        self.btn = DesignButton(
            self.root, 
            run_cmd=self.send_trigger,
            stop_cmd=self.send_interrupt,
            toggle_mode_cmd=self.toggle_mode,
            settings_cmd=self.prompt_for_ip,
            bg="#2C2C2C", highlightthickness=0
        )
        self.btn.pack(fill=tk.BOTH, expand=True)

    def prompt_for_ip(self):
        current = self.config.get("comfy_url", "127.0.0.1:8188")
        new_ip = simpledialog.askstring("Server Settings", "Enter ComfyUI IP:Port (e.g. 192.168.1.5:8188)", initialvalue=current, parent=self.root)
        if new_ip:
            self.config["comfy_url"] = new_ip
            self.save_config()
            self.setup_urls()
            # Reset connection state to trigger immediate reconnect attempt
            self.ws_connected = False
            # If we had an open WS, it will close naturally or timeout, loop will create new one

    def toggle_mode(self):
        if self.is_mini:
            self.root.geometry(f"{THEME['norm_w']}x{THEME['norm_h']}")
            self.is_mini = False
        else:
            self.root.geometry(f"{THEME['mini_s']}x{THEME['mini_s']}")
            self.is_mini = True
        self.btn.set_mode(self.is_mini)

    def toggle_smart(self):
        if self.btn.state == "running":
            self.send_interrupt()
        else:
            self.send_trigger()

    def send_trigger(self):
        if self.btn.state == "offline": return
        try: requests.post(self.trigger_url, timeout=1)
        except: pass

    def send_interrupt(self):
        if self.btn.state == "offline": return
        try: requests.post(self.interrupt_url, timeout=1)
        except: pass

    def setup_hotkey(self):
        self._register_hotkey("hotkey_toggle", self.toggle_smart)
        self._register_hotkey("hotkey_run", self.send_trigger)

    def _register_hotkey(self, key_name, callback):
        hotkey = self.config.get(key_name)
        try: keyboard.add_hotkey(hotkey, callback)
        except Exception as e:
            self.handle_hotkey_conflict(key_name, hotkey, str(e))

    def handle_hotkey_conflict(self, key_name, hotkey, error_msg):
        self.root.after(0, lambda: self._show_hotkey_dialog(key_name, hotkey, error_msg))

    def _show_hotkey_dialog(self, key_name, hotkey, error_msg):
        msg = f"Failed to register hotkey '{hotkey}'.\nError: {error_msg}\nEnter new hotkey:"
        new_hotkey = simpledialog.askstring("Hotkey Conflict", msg, parent=self.root)
        if new_hotkey:
            self.config[key_name] = new_hotkey
            self.save_config()
            self._register_hotkey(key_name, getattr(self, "toggle_smart" if key_name == "hotkey_toggle" else "send_trigger"))

    # --- Connection & WebSocket ---
    def connection_manager_loop(self):
        while True:
            # 1. Ping HTTP to check if server is reachable
            try:
                requests.get(self.stats_url, timeout=2)
                # If we get here, server is up.
                if not self.ws_connected:
                    # Start WebSocket
                    self.start_ws()
            except:
                # Ping failed
                self.ws_connected = False
                self.root.after(0, lambda: self.btn.set_state("offline"))
            
            time.sleep(3)

    def start_ws(self):
        # Don't block the connection manager
        threading.Thread(target=self._ws_worker, daemon=True).start()

    def _ws_worker(self):
        try:
            # Reset UI to idle (connected) tentatively
            self.root.after(0, lambda: self.btn.set_state("idle"))
            
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self.on_ws_open,
                on_message=self.on_ws_message,
                on_error=self.on_ws_error,
                on_close=self.on_ws_close
            )
            self.ws.run_forever()
        except:
            pass
        self.ws_connected = False

    def on_ws_open(self, ws):
        self.ws_connected = True
        # Request initial status
        self.root.after(0, lambda: self.btn.set_state("idle"))

    def on_ws_error(self, ws, error):
        self.ws_connected = False

    def on_ws_close(self, ws, close_status_code, close_msg):
        self.ws_connected = False
        self.root.after(0, lambda: self.btn.set_state("offline"))

    def on_ws_message(self, ws, message):
        try:
            msg = json.loads(message)
            self.root.after(0, lambda: self.handle_ws_event(msg.get("type"), msg.get("data", {})))
        except: pass

    def handle_ws_event(self, mtype, data):
        if mtype == "status":
            queue = data.get("status", {}).get("exec_info", {}).get("queue_remaining", 0)
            if queue > 0:
                self.btn.set_state("running", self.btn.progress, queue)
            else:
                if self.btn.state == "running" and self.btn.queue_count == 0: pass
                elif self.btn.state == "running" and queue == 0:
                     self.btn.set_state("running", self.btn.progress, 0)

        elif mtype == "execution_start":
            self.btn.set_state("running", 0.0, self.btn.queue_count)

        elif mtype == "execution_error" or mtype == "execution_interrupted":
             self.btn.set_state("idle", 0.0, 0)

        elif mtype == "progress":
            val = data.get("value", 0)
            max_val = data.get("max", 100)
            pct = 0.0
            if max_val > 0: pct = val / max_val
            self.btn.set_state("running", pct, self.btn.queue_count)

        elif mtype == "executing":
            node = data.get("node")
            if node is None:
                self.btn.set_state("idle", 0.0, 0)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = FloatApp()
    app.run()
