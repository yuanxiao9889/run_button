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
import socket
import hashlib
import base64
import struct
import logging
import subprocess
import uuid

# --- Visual Theme Configuration ---
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

# --- Config & Logging Setup ---

def get_config_path():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, "config.json")

CONFIG_FILE = get_config_path()
DEFAULT_CONFIG = {
    "comfy_url": "127.0.0.1:8188",
    "hotkey_toggle": "F9",
    "hotkey_run": "ctrl+enter",
    "control_mode": "api" # api or extension
}

def setup_logging():
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_button_debug.log")
    
    # Create handlers
    file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
    console_handler = logging.StreamHandler()
    
    # Create formatters
    log_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(log_format)
    console_handler.setFormatter(log_format)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return log_file

LOG_FILE = setup_logging()

# --- UI Components ---

class DesignButton(tk.Canvas):
    """
    Custom drawn button with Split (Run/Stop) and Mini modes.
    Handles all drawing and mouse interactions.
    """
    def __init__(self, master, run_cmd, stop_cmd, toggle_mode_cmd, settings_cmd, hotkey_cmd, binding_cmd, switch_mode_cmd, quit_cmd, open_log_cmd, **kwargs):
        self.reload_hotkeys_cmd = kwargs.pop('reload_hotkeys_cmd', None)
        super().__init__(master, **kwargs)
        
        # Commands
        self.run_cmd = run_cmd
        self.stop_cmd = stop_cmd
        self.toggle_mode_cmd = toggle_mode_cmd
        self.settings_cmd = settings_cmd
        self.hotkey_cmd = hotkey_cmd
        self.binding_cmd = binding_cmd
        self.switch_mode_cmd = switch_mode_cmd
        self.quit_cmd = quit_cmd
        self.open_log_cmd = open_log_cmd
        
        # State
        self.is_mini = False
        self.state = "offline" # idle, running, offline
        self.control_mode = "api" 
        self.progress = 0.0
        self.queue_count = 0
        
        # Hover State
        self.hover_zone = None # None, 'run', 'stop', 'mini'
        
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
            content_w = 20 + 10 + 40 
            start_x = (run_w - content_w) / 2
            self._draw_play_icon(start_x + 10, cy, 16)
            self.create_text(start_x + 30, cy, text="RUN", fill="white", font=("Segoe UI", 12, "bold"), anchor="w")
            
        else:
            # Running State
            left_margin = 10
            if self.queue_count > 0:
                self.create_text(left_margin, cy, text=f"({self.queue_count})", fill="white", font=("Segoe UI", 12, "bold"), anchor="w")
                left_margin += 25
            
            pct = int(self.progress * 100)
            p_text = f"{pct}%..." 
            self.create_text(left_margin, cy, text=p_text, fill="white", font=("Segoe UI", 12, "bold"), anchor="w")

        # --- 2. RIGHT ZONE (STOP) ---
        stop_start_x = run_w + gap
        stop_bg = THEME["bg_normal"]
        
        # Determine Stop Button Active State
        is_stop_active = False
        if self.control_mode == "extension":
             if self.state != "offline": is_stop_active = True
        else:
             if self.state == "running": is_stop_active = True
             
        if is_stop_active:
             stop_bg = "#4b4b4b" 
             if self.hover_zone == 'stop': stop_bg = THEME["bg_stop_hover"]
        else:
             stop_bg = "#404040"

        self.create_rectangle(stop_start_x, 0, w, h, fill=stop_bg, outline="")
        
        # Icon X
        if self.state == "offline":
            icon_color = THEME["icon_offline"]
        else:
            icon_color = THEME["icon_stop_enabled"] if is_stop_active else THEME["icon_stop_disabled"]
            
        cx = stop_start_x + (stop_w / 2)
        self._draw_x_icon(cx, cy, 14, icon_color)

    def _draw_mini(self, w, h):
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
            self._draw_x_icon(cx, cy, 18, THEME["icon_mini_x"])

    def _draw_play_icon(self, cx, cy, size):
        r = size / 2
        points = [cx - r/1.5, cy - r, cx - r/1.5, cy + r, cx + r, cy]
        self.create_polygon(points, fill=THEME["icon_play"], outline="")

    def _draw_x_icon(self, cx, cy, size, color):
        r = size / 2
        self.create_line(cx - r, cy - r, cx + r, cy + r, fill=color, width=3, capstyle=tk.ROUND)
        self.create_line(cx + r, cy - r, cx - r, cy + r, fill=color, width=3, capstyle=tk.ROUND)

    # --- Interaction Handlers ---
    def on_motion(self, e):
        w = self.winfo_width()
        if self.is_mini:
            self.hover_zone = 'mini'
        else:
            stop_x = w - THEME["stop_w"]
            self.hover_zone = 'stop' if e.x > stop_x else 'run'
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
        if abs(dx) > 3 or abs(dy) > 3: self.is_dragging = True
            
        root = self.winfo_toplevel()
        root.geometry(f"+{root.winfo_x() + dx}+{root.winfo_y() + dy}")
        self.drag_start = (e.x_root, e.y_root)

    def on_release(self, e):
        if not self.is_dragging: self.handle_click(e)
        self.drag_start = None
        self.is_dragging = False

    def handle_click(self, e):
        if self.is_mini:
            if self.state == "running":
                if self.stop_cmd: self.stop_cmd()
            else:
                if self.run_cmd: self.run_cmd()
        else:
            w = self.winfo_width()
            stop_x = w - THEME["stop_w"]
            if e.x > stop_x:
                if self.stop_cmd: self.stop_cmd()
            else:
                if self.run_cmd: self.run_cmd()

    def on_right_click(self, e):
        m = Menu(self, tearoff=0)
        m.add_command(label="切换迷你模式", command=self.toggle_mode_cmd)
        m.add_separator()
        m.add_command(label="服务器地址设置", command=self.settings_cmd)
        m.add_command(label="快捷键设置", command=self.hotkey_cmd)
        m.add_command(label="重置快捷键 (Fix Hotkeys)", command=self.reload_hotkeys_cmd)
        m.add_command(label="配对码设置", command=self.binding_cmd)
        m.add_command(label="切换控制模式 (API/插件)", command=self.switch_mode_cmd)
        m.add_separator()
        m.add_command(label="查看日志 (View Logs)", command=self.open_log_cmd)
        m.add_command(label="退出程序", command=self.quit_cmd)
        m.tk_popup(e.x_root, e.y_root)


# --- Main Application Logic ---

class FloatApp:
    def __init__(self):
        # 1. Single Instance Check & Auto-Kill
        # We bind a local socket to ensure only one instance is running.
        # If binding fails, it means another instance is holding the port.
        # We will try to find and kill that process, then start ourselves.
        import psutil
        
        self.lock_port = 65432
        self._lock_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        try:
            self._lock_socket.bind(('127.0.0.1', self.lock_port))
        except socket.error:
            # Port is busy -> Another instance is running
            print(f"Port {self.lock_port} is busy. Attempting to kill previous instance...")
            
            # 1. Identify current process ID
            my_pid = os.getpid()
            
            # 2. Iterate over all processes to find who is holding our port
            target_pid = None
            try:
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        # Check connections of this process
                        for conn in proc.connections(kind='udp'):
                            if conn.laddr.port == self.lock_port:
                                target_pid = proc.pid
                                break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                    if target_pid: break
            except: pass
            
            # 3. If found, kill it
            if target_pid and target_pid != my_pid:
                try:
                    p = psutil.Process(target_pid)
                    p.terminate()
                    p.wait(timeout=3) # Wait for it to die
                    print(f"Killed previous instance (PID: {target_pid})")
                except Exception as e:
                    print(f"Failed to kill process {target_pid}: {e}")
            
            # 4. Try to bind again
            try:
                self._lock_socket.bind(('127.0.0.1', self.lock_port))
                print("Successfully bound to lock port after cleanup.")
            except socket.error:
                # Still failing? Maybe it wasn't the port, or permissions issue.
                # Fallback to old behavior: Alert and Exit
                try:
                    root = tk.Tk()
                    root.withdraw()
                    messagebox.showerror("错误", "无法关闭旧程序，请手动在任务管理器中结束 python/run_button 进程。")
                    root.destroy()
                except: pass
                sys.exit(0)

        # 2. Init Root
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg="#2C2C2C")
        self.root.geometry(f"{THEME['norm_w']}x{THEME['norm_h']}+100+100")
        
        # 3. State Variables
        self.is_mini = False
        self.ws = None
        self.ws_connected = False
        self.extension_socket = None
        self.extension_connected = False
        
        self.browser_client_id = None
        self.last_trigger_time = 0
        self.is_request_pending = False
        
        # 4. Config
        self.load_config()
        self.setup_urls()
        
        # 5. UI Setup
        self.setup_ui()
        
        # 6. Hotkeys
        self.setup_hotkey()
        
        # 7. Apply Mode
        self.btn.control_mode = self.config.get("control_mode", "api")
        
        # 8. Start Background Threads
        # Connection Manager (Ping / Reconnect)
        threading.Thread(target=self.connection_manager_loop, daemon=True).start()
        # Sidecar Server (Browser Handshake)
        threading.Thread(target=self.start_sidecar_server, daemon=True).start()
        # Extension WebSocket Server
        threading.Thread(target=self.start_extension_ws_server, daemon=True).start()

        # Check config on startup
        if "comfy_url" not in self.config or not self.config["comfy_url"]:
             self.root.after(500, self.prompt_for_ip)

    def setup_ui(self):
        self.btn = DesignButton(
            self.root, 
            run_cmd=self.send_trigger,
            stop_cmd=self.send_interrupt,
            toggle_mode_cmd=self.toggle_mode,
            settings_cmd=self.prompt_for_ip,
            hotkey_cmd=self.prompt_for_hotkeys,
            binding_cmd=self.prompt_for_binding,
            switch_mode_cmd=self.toggle_mode_control,
            quit_cmd=self.quit_app,
            reload_hotkeys_cmd=self.reload_hotkeys,
            open_log_cmd=self.open_log_file,
            bg="#2C2C2C", highlightthickness=0
        )
        self.btn.pack(fill=tk.BOTH, expand=True)

    # --- Configuration Methods ---
    def load_config(self):
        self.config = DEFAULT_CONFIG.copy()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.config.update(json.load(f))
            except: pass

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
        except: pass

    def setup_urls(self):
        base = self.config.get("comfy_url", "127.0.0.1:8188")
        for proto in ["http://", "https://", "ws://", "wss://"]:
            if base.lower().startswith(proto): base = base[len(proto):]
        base = base.rstrip("/")
        self.trigger_url = f"http://{base}/run_button/trigger"
        self.interrupt_url = f"http://{base}/interrupt"
        self.ws_url = f"ws://{base}/ws"
        self.stats_url = f"http://{base}/system_stats"

    # --- Trigger / Action Logic ---
    def send_trigger(self):
        """
        Called by Hotkey Hook or UI Click.
        MUST be non-blocking and thread-safe.
        """
        try:
            # Dispatch to main thread to avoid blocking the hook
            self.root.after(0, self._handle_trigger_dispatch)
        except:
            # If root is dead, do nothing
            pass

    def _handle_trigger_dispatch(self):
        """Main thread handler for trigger"""
        # 1. Visual Feedback
        try:
            self.btn.create_rectangle(0, 0, self.btn.winfo_width(), self.btn.winfo_height(), 
                                    fill="#FFFFFF", stipple="gray25", outline="", tag="flash")
            self.root.after(100, lambda: self.btn.delete("flash"))
        except: pass

        # 2. Debounce
        if time.time() - self.last_trigger_time < 0.5:
            return
            
        # 3. Pending Check
        if self.is_request_pending:
            return

        self.last_trigger_time = time.time()
        self.is_request_pending = True
        
        # 4. Start Worker Thread
        threading.Thread(target=self._trigger_worker, daemon=True).start()

    def _trigger_worker(self):
        try:
            logging.info("Trigger initiated (Worker Thread)")
            
            # Extension Mode
            if self.config.get("control_mode") == "extension":
                self.send_extension_trigger()
                return
                
            # API Mode
            if self.btn.state == "offline": 
                logging.warning("Trigger ignored (Offline Mode)")
                return

            # Prepare Payload
            binding_code = self.config.get("binding_code", "")
            target_id = self.browser_client_id
            local_ip = self.get_local_ip()
            
            payload = {
                "clientId": self.client_id,
                "clientIp": local_ip,
                "targetClientId": target_id,
                "targetBindingId": binding_code
            }
            
            logging.info(f"Sending API trigger to {self.trigger_url}. Payload: {payload}")
            
            resp = requests.post(self.trigger_url, json=payload, timeout=2)
            logging.info(f"API Trigger Response: {resp.status_code}")
            
            if resp.status_code == 404:
                logging.error("API Trigger 404 Not Found")
                self.safe_alert("连接错误", "找不到触发端点 (404)。\n请确保已安装 RunButton 节点并重启 ComfyUI。", "error")
            
            # Log server warnings if any
            try:
                r_json = resp.json()
                if r_json.get("status") == "warning":
                    logging.warning(f"Server Warning: {r_json.get('message')}")
            except: pass
                    
        except Exception as e:
            logging.error(f"Trigger request failed: {e}")
        finally:
            self.is_request_pending = False

    def send_interrupt(self):
        threading.Thread(target=self._interrupt_worker, daemon=True).start()

    def _interrupt_worker(self):
        if self.config.get("control_mode") == "extension":
            self.send_extension_trigger(action="stop")
            return
        try: requests.post(self.interrupt_url, timeout=1)
        except: pass

    # --- Hotkey Management ---
    def setup_hotkey(self):
        hotkey = self.config.get("hotkey_run", "ctrl+enter")
        try: keyboard.unhook_all()
        except: pass
        
        try: 
            keyboard.add_hotkey(hotkey, self.send_trigger, suppress=False)
            
            toggle_hotkey = self.config.get("hotkey_toggle", "F9")
            keyboard.add_hotkey(toggle_hotkey, self.toggle_smart, suppress=False)
            
            logging.info(f"Hotkeys registered: Run='{hotkey}', Toggle='{toggle_hotkey}'")
        except Exception as e:
            logging.error(f"Hotkey registration failed: {e}")
            self.handle_hotkey_conflict("hotkey_run", hotkey, str(e))

    def handle_hotkey_conflict(self, key_name, hotkey, error_msg):
        logging.error(f"Hotkey conflict detected for {key_name} ({hotkey}): {error_msg}")
        self.root.after(0, lambda: self._show_hotkey_dialog(key_name, hotkey, error_msg))

    def reload_hotkeys(self):
        try:
            keyboard.unhook_all()
            self.setup_hotkey()
            logging.info("Hotkeys reloaded manually.")
            messagebox.showinfo("快捷键", "快捷键已重新加载！")
        except Exception as e:
            logging.error(f"Hotkey reload failed: {e}")
            messagebox.showerror("错误", f"重新加载失败：{e}")

    def _show_hotkey_dialog(self, key_name, hotkey, error_msg):
        msg = f"注册快捷键 '{hotkey}' 失败。\n错误信息：{error_msg}\n请输入新的快捷键："
        new_hotkey = simpledialog.askstring("快捷键冲突", msg, parent=self.root)
        if new_hotkey:
            self.config[key_name] = new_hotkey
            self.save_config()
            self.setup_hotkey()

    # --- Connectivity & Network ---
    
    def connection_manager_loop(self):
        """Monitors connection state and handles auto-reconnect"""
        while True:
            is_ext_mode = self.config.get("control_mode") == "extension"
            
            if is_ext_mode:
                # Extension Mode Logic
                if self.ws:
                    try: self.ws.close()
                    except: pass
                    self.ws = None
                    self.ws_connected = False
                
                if self.btn.state == "offline":
                     self.root.after(0, lambda: self.btn.set_state("idle"))
                
                time.sleep(1)
                continue

            # API Mode Logic
            try:
                requests.get(self.stats_url, timeout=2)
                # Server is Up
                if not self.ws_connected:
                    self.start_ws()
            except:
                # Server is Down
                self.ws_connected = False
                self.root.after(0, lambda: self.btn.set_state("offline"))
            
            time.sleep(3)

    def start_ws(self):
        threading.Thread(target=self._ws_worker, daemon=True).start()

    def _ws_worker(self):
        try:
            self.client_id = f"run_button_observer_{uuid.uuid4()}"
            ws_url = f"{self.ws_url}?clientId={self.client_id}"
            
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_open=self.on_ws_open,
                on_message=self.on_ws_message,
                on_error=self.on_ws_error,
                on_close=self.on_ws_close
            )
            self.ws.run_forever()
        except: pass
        self.ws_connected = False

    def on_ws_open(self, ws):
        self.ws_connected = True
        self.root.after(0, lambda: self.btn.set_state("idle"))

    def on_ws_error(self, ws, error):
        self.ws_connected = False

    def on_ws_close(self, ws, close_status_code, close_msg):
        self.ws_connected = False
        if self.config.get("control_mode") != "extension":
             self.root.after(0, lambda: self.btn.set_state("offline"))

    def on_ws_message(self, ws, message):
        try:
            msg = json.loads(message)
            self.root.after(0, lambda: self.handle_ws_event(msg.get("type"), msg.get("data", {})))
        except: pass

    def handle_ws_event(self, mtype, data):
        # Dispatch status updates to UI
        if mtype == "status":
            exec_info = data.get("status", {}).get("exec_info", {})
            queue = exec_info.get("queue_remaining", 0) or 0
            if queue > 0:
                self.btn.set_state("running", self.btn.progress, queue)
            # If queue is 0, we rely on executing/progress events
            
        elif mtype == "execution_start":
            self.btn.set_state("running", 0.0, self.btn.queue_count)

        elif mtype == "execution_error" or mtype == "execution_interrupted":
             self.btn.set_state("idle", 0.0, 0)

        elif mtype == "progress":
            val = data.get("value", 0)
            max_val = data.get("max", 100)
            pct = val / max_val if max_val > 0 else 0.0
            self.btn.set_state("running", pct, self.btn.queue_count)

        elif mtype == "executing":
            if data.get("node") is None:
                if self.btn.queue_count == 0:
                    self.btn.set_state("idle", 0.0, 0)
            else:
                self.btn.set_state("running", self.btn.progress, self.btn.queue_count)

        elif mtype == "ext_log":
            level = data.get("level", "info")
            msg = data.get("message", "")
            if level == "error": logging.error(f"[ChromeExt] {msg}")
            elif level == "warn": logging.warning(f"[ChromeExt] {msg}")
            else: logging.info(f"[ChromeExt] {msg}")

    # --- Extension Server (Sidecar) ---
    def start_sidecar_server(self):
        """HTTP Server for Chrome Extension Handshake"""
        from http.server import BaseHTTPRequestHandler, HTTPServer
        
        class SidecarHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path == '/register':
                    content_length = int(self.headers['Content-Length'])
                    try:
                        data = json.loads(self.rfile.read(content_length).decode('utf-8'))
                        app.browser_client_id = data.get('clientId')
                        self.send_response(200)
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(b'{"status": "ok"}')
                    except:
                        self.send_response(500)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()
            def log_message(self, format, *args): return

        try:
            server = HTTPServer(('127.0.0.1', 56789), SidecarHandler)
            server.serve_forever()
        except:
            print("Sidecar server failed to start (Port 56789 busy?)")

    def start_extension_ws_server(self):
        """Raw WebSocket Server for Extension Communication"""
        HOST, PORT = '127.0.0.1', 56790
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_socket.bind((HOST, PORT))
            server_socket.listen(1)
        except Exception as e:
            # logging.error(f"Failed to bind Extension WS Server on {PORT}: {e}")
            return

        while True:
            try:
                client_socket, addr = server_socket.accept()
                threading.Thread(target=self.handle_extension_client, args=(client_socket,), daemon=True).start()
            except Exception as e:
                # logging.error(f"Accept failed: {e}")
                time.sleep(1) # Wait before retry if accept fails

    def handle_extension_client(self, client_socket):
        try:
            # Handshake
            data = client_socket.recv(1024)
            key = None
            for line in data.decode().split('\r\n'):
                if 'Sec-WebSocket-Key' in line:
                    key = line.split(': ')[1]
                    break
            
            if key:
                resp_key = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                response = f"HTTP/11 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {resp_key}\r\n\r\n"
                client_socket.send(response.encode())
                
                self.extension_socket = client_socket
                self.extension_connected = True
                
                # Frame Loop
                while True:
                    data = self.extension_socket.recv(2)
                    if not data: break
                    
                    length = data[1] & 127
                    if length == 126: 
                        self.extension_socket.recv(2) # Skip extended length
                    elif length == 127:
                        self.extension_socket.recv(8)
                        
                    mask = self.extension_socket.recv(4)
                    # We assume short messages for now, just read payload
                    # This is a simplified parser for control messages
                    # Real implementation should read exact length.
                    # Since we only receive small JSONs, basic read is okay for now.
                    payload = self.extension_socket.recv(1024)
                    
                    # Decode (XOR with mask)
                    decoded = bytearray()
                    for i in range(len(payload)):
                        decoded.append(payload[i] ^ mask[i % 4])
                        
                    try:
                        msg = json.loads(decoded.decode('utf-8'))
                        self.root.after(0, lambda: self.handle_ws_event(msg.get("type"), msg.get("data", {})))
                    except: pass
                    
        except: pass
        finally:
            if self.extension_socket == client_socket:
                self.extension_socket = None
                self.extension_connected = False
            try: client_socket.close()
            except: pass

    def send_extension_trigger(self, action="trigger"):
        if not self.extension_socket:
            logging.warning("Extension trigger failed: Socket not connected")
            self.safe_alert("插件未连接", "浏览器插件未连接！\n请检查 Chrome 插件状态。", "warning")
            return

        try:
            msg = json.dumps({"type": action})
            header = bytearray([0x81, len(msg)])
            self.extension_socket.send(header + msg.encode())
            logging.info(f"Extension trigger sent: {action}")
        except Exception as e:
            logging.error(f"Extension send failed: {e}")
            self.extension_socket = None

    # --- Utils ---
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            IP = s.getsockname()[0]
            s.close()
            return IP
        except: return "127.0.0.1"

    def safe_alert(self, title, msg, type="info"):
        self.root.after(0, lambda: messagebox.showerror(title, msg) if type=="error" else messagebox.showwarning(title, msg))

    def prompt_for_ip(self):
        new_ip = simpledialog.askstring("服务器设置", "请输入 ComfyUI 地址 (例如 127.0.0.1:8188):", parent=self.root)
        if new_ip:
            self.config["comfy_url"] = new_ip
            self.save_config()
            self.setup_urls()
            self.ws_connected = False

    def prompt_for_hotkeys(self):
        curr_run = self.config.get("hotkey_run", "ctrl+enter")
        new_run = simpledialog.askstring("快捷键设置", 
            f"请输入运行/提交任务的快捷键：\n当前：{curr_run}\n(例如: ctrl+enter, F10)", 
            initialvalue=curr_run, parent=self.root)
        
        if new_run:
            self.config["hotkey_run"] = new_run
            # Re-register
            try:
                keyboard.unhook_all()
                self.setup_hotkey()
            except: pass
            
        self.save_config()

    def prompt_for_binding(self):
        new_code = simpledialog.askstring("配对码", "请输入配对码:", initialvalue=self.config.get("binding_code",""), parent=self.root)
        if new_code is not None:
            self.config["binding_code"] = new_code
            self.save_config()

    def toggle_mode_control(self):
        current = self.config.get("control_mode", "api")
        new_mode = "extension" if current == "api" else "api"
        self.config["control_mode"] = new_mode
        self.btn.control_mode = new_mode
        self.btn.draw()
        self.save_config()
        messagebox.showinfo("模式切换", f"已切换为: {new_mode}")

    def toggle_mode(self):
        self.is_mini = not self.is_mini
        self.root.geometry(f"{THEME['mini_s']}x{THEME['mini_s']}" if self.is_mini else f"{THEME['norm_w']}x{THEME['norm_h']}")
        self.btn.set_mode(self.is_mini)

    def toggle_smart(self):
        if self.btn.state == "running": self.send_interrupt()
        else: self.send_trigger()

    def open_log_file(self):
        try:
            if os.name == 'nt': os.startfile(LOG_FILE)
            else: subprocess.call(('open', LOG_FILE))
        except: pass

    def quit_app(self):
        try: keyboard.unhook_all()
        except: pass
        os._exit(0)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = FloatApp()
    app.run()
