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
    def __init__(self, master, run_cmd, stop_cmd, toggle_mode_cmd, settings_cmd, hotkey_cmd, binding_cmd, switch_mode_cmd, quit_cmd, **kwargs):
        self.reload_hotkeys_cmd = kwargs.pop('reload_hotkeys_cmd', None)
        super().__init__(master, **kwargs)
        self.run_cmd = run_cmd
        self.stop_cmd = stop_cmd
        self.toggle_mode_cmd = toggle_mode_cmd
        self.settings_cmd = settings_cmd
        self.hotkey_cmd = hotkey_cmd
        self.binding_cmd = binding_cmd
        self.switch_mode_cmd = switch_mode_cmd
        self.quit_cmd = quit_cmd
        
        # State
        self.is_mini = False
        self.state = "offline" # idle, running, offline
        self.control_mode = "api" # api, extension
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
        
        # Check if extension mode is active
        if self.control_mode == "extension":
             # Always allow hover on stop button if not offline in extension mode
             if self.state != "offline":
                 stop_bg = "#4b4b4b" 
                 if self.hover_zone == 'stop':
                     stop_bg = THEME["bg_stop_hover"]
        else:
             # API Mode: Only active if running
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
            if self.control_mode == "extension":
                icon_color = THEME["icon_stop_enabled"]
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
        # We allow clicking even in offline state, to let the App logic decide (e.g. for Extension mode)
        # if self.state == "offline": return 

        if self.is_mini:
            if self.state == "running":
                if self.stop_cmd: self.stop_cmd()
            else:
                if self.run_cmd: self.run_cmd()
        else:
            w = self.winfo_width()
            stop_x = w - THEME["stop_w"]
            
            if e.x > stop_x:
                if self.control_mode == "extension":
                     if self.stop_cmd: self.stop_cmd()
                else:
                     if self.state == "running":
                         if self.stop_cmd: self.stop_cmd()
            else:
                if self.run_cmd: self.run_cmd()

    def on_right_click(self, e):
        # Create Context Menu
        m = Menu(self, tearoff=0)
        m.add_command(label="切换迷你模式", command=self.toggle_mode_cmd)
        m.add_separator()
        m.add_command(label="服务器地址设置", command=self.settings_cmd)
        m.add_command(label="快捷键设置", command=self.hotkey_cmd)
        m.add_command(label="配对码设置", command=self.binding_cmd)
        m.add_command(label="切换控制模式 (API/插件)", command=self.switch_mode_cmd)
        m.add_separator()
        m.add_command(label="退出程序", command=self.quit_cmd)
        m.tk_popup(e.x_root, e.y_root)


class FloatApp:
    def __init__(self):
        # --- Single Instance Check ---
        # Bind a local socket to ensure only one instance is running
        import socket
        try:
            self._lock_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Bind to a high port on localhost. If it fails, another instance is running.
            self._lock_socket.bind(('127.0.0.1', 65432))
        except socket.error:
            # Another instance is likely running
            try:
                # Optional: Show alert using minimal tkinter (since root isn't created yet)
                temp_root = tk.Tk()
                temp_root.withdraw()
                messagebox.showerror("错误", "Run Button 程序已在运行中！")
                temp_root.destroy()
            except: pass
            sys.exit(0)

        self.root = tk.Tk()
        self.is_mini = False
        self.ws = None
        self.ws_connected = False
        self.extension_connected = False
        
        # Debounce for trigger
        self.last_trigger_time = 0
        self.browser_client_id = None # Stored from sidecar handshake
        
        self.load_config()
        self.setup_urls()
        
        self.setup_window()
        self.setup_ui()
        self.setup_hotkey()
        self.start_hotkey_watch()
        
        # Init control mode
        self.btn.control_mode = self.config.get("control_mode", "api")
        
        # Start Heartbeat & WS
        threading.Thread(target=self.connection_manager_loop, daemon=True).start()
        
        # Start Local Sidecar Server
        threading.Thread(target=self.start_sidecar_server, daemon=True).start()

        # Check config on startup
        if "comfy_url" not in self.config or not self.config["comfy_url"]:
             self.root.after(500, self.prompt_for_ip)

    def start_sidecar_server(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import json
        
        # We need a separate thread for the Extension WebSocket Server
        threading.Thread(target=self.start_extension_ws_server, daemon=True).start()

        # We need a reference to self to store the client_id
        app_instance = self
        
        class SidecarHandler(BaseHTTPRequestHandler):
            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()

            def do_POST(self):
                if self.path == '/register':
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    try:
                        data = json.loads(post_data.decode('utf-8'))
                        browser_id = data.get('clientId')
                        if browser_id:
                            app_instance.browser_client_id = browser_id
                            # print(f"Received Browser ID: {browser_id}")
                            
                        self.send_response(200)
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
                    except Exception as e:
                        self.send_response(500)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                return # Silence logs

        # Bind to localhost only
        # Using port 56789 as agreed
        try:
            server = HTTPServer(('127.0.0.1', 56789), SidecarHandler)
            server.serve_forever()
        except:
            # Port might be busy, but we fail silently or log it
            print("Failed to start sidecar server on 56789")

    def start_extension_ws_server(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        # We assume socket, hashlib, base64, struct are imported at top level now
        
        HOST, PORT = '127.0.0.1', 56790
        
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_socket.bind((HOST, PORT))
            server_socket.listen(1)
            # print(f"Extension WS Server started on {PORT}")
        except:
            return

        while True:
            client_socket, addr = server_socket.accept()
            # print(f"Extension connected from {addr}")
            threading.Thread(target=self.handle_extension_client, args=(client_socket,), daemon=True).start()

    def handle_extension_client(self, client_socket):
        try:
            data = client_socket.recv(1024)
            headers = data.decode().split('\r\n')
            key = None
            for header in headers:
                if 'Sec-WebSocket-Key' in header:
                    key = header.split(': ')[1]
                    break
            
            if key:
                response_key = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                response = (
                    "HTTP/11 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {response_key}\r\n\r\n"
                )
                client_socket.send(response.encode())
                
                self.extension_socket = client_socket
                self.extension_connected = True
                
                # Keep alive loop
                while True:
                    try:
                        # Read Frame Header
                        # Byte 0: FIN(1) RSV(3) Opcode(4)
                        data = self.extension_socket.recv(2)
                        if not data or len(data) < 2: break
                        
                        byte0 = data[0]
                        byte1 = data[1]
                        
                        opcode = byte0 & 0x0F
                        if opcode == 8: # Close
                            break
                            
                        masked = (byte1 & 0x80) >> 7
                        payload_len = byte1 & 0x7F
                        
                        if payload_len == 126:
                            data = self.extension_socket.recv(2)
                            payload_len = struct.unpack(">H", data)[0]
                        elif payload_len == 127:
                            data = self.extension_socket.recv(8)
                            payload_len = struct.unpack(">Q", data)[0]
                            
                        mask_key = None
                        if masked:
                            mask_key = self.extension_socket.recv(4)
                            
                        payload = bytearray()
                        remaining = payload_len
                        while remaining > 0:
                            chunk_size = 4096 if remaining > 4096 else remaining
                            chunk = self.extension_socket.recv(chunk_size)
                            if not chunk: break
                            payload.extend(chunk)
                            remaining -= len(chunk)
                            
                        if masked:
                            # Unmask
                            for i in range(len(payload)):
                                payload[i] ^= mask_key[i % 4]
                                
                        # Parse JSON
                        if opcode == 1: # Text
                            try:
                                msg_str = payload.decode('utf-8')
                                # print(f"Ext Msg: {msg_str}")
                                msg = json.loads(msg_str)
                                self.root.after(0, lambda: self.handle_ws_event(msg.get("type"), msg.get("data", {})))
                            except: pass
                            
                    except Exception as e:
                        # print(f"WS Error: {e}")
                        break
        except:
            pass
        
        # Cleanup when client disconnects
        # Only clear self.extension_socket if it matches this client
        current_socket = getattr(self, 'extension_socket', None)
        if current_socket == client_socket:
             self.extension_connected = False
             self.extension_socket = None
        try: client_socket.close()
        except: pass

    def send_extension_trigger(self, action="trigger"):
        if not hasattr(self, 'extension_socket') or not self.extension_socket:
            messagebox.showwarning("插件未连接", "浏览器插件未连接！\n请确保已在浏览器中安装并启用了 ComfyUI Run Button Helper 插件。")
            return

        try:
            msg = json.dumps({"type": action})
            # Frame it: Fin=1, Opcode=1 (text), Mask=0
            # Length < 126
            header = bytearray()
            header.append(0x81)
            header.append(len(msg))
            self.extension_socket.send(header + msg.encode())
        except:
            self.extension_connected = False
            self.extension_socket = None

    def toggle_mode_control(self):
        # Toggle between API Mode and Extension Mode
        current = self.config.get("control_mode", "api")
        new_mode = "extension" if current == "api" else "api"
        self.config["control_mode"] = new_mode
        self.btn.control_mode = new_mode
        self.btn.draw() # Force redraw to update Stop button state
        self.save_config()
        
        mode_name = "浏览器插件模式" if new_mode == "extension" else "API 直连模式"
        messagebox.showinfo("控制模式切换", f"已切换为：{mode_name}")

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
        
        # Robust cleaning
        # Remove common protocols
        for proto in ["http://", "https://", "ws://", "wss://"]:
            if base.lower().startswith(proto):
                base = base[len(proto):]
        
        # Remove trailing slash
        base = base.rstrip("/")
        
        clean_base = base
        
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
            hotkey_cmd=self.prompt_for_hotkeys,
            binding_cmd=self.prompt_for_binding,
            switch_mode_cmd=self.toggle_mode_control,
            quit_cmd=self.quit_app,
            reload_hotkeys_cmd=self.reload_hotkeys,
            bg="#2C2C2C", highlightthickness=0
        )
        self.btn.pack(fill=tk.BOTH, expand=True)

    def quit_app(self):
        # Clean shutdown
        try: self.ws.close()
        except: pass
        try: self.root.destroy()
        except: pass
        os._exit(0)

    def prompt_for_binding(self):
        curr_code = self.config.get("binding_code", "")
        msg = ("请输入配对码 (Pairing Code)：\n\n"
               "该代码必须与 ComfyUI 网页设置中的\n"
               "'RunButton Pairing Code' 保持一致。\n\n"
               "例如: ABC, MY_PC_1")
               
        new_code = simpledialog.askstring("配对码设置", msg, initialvalue=curr_code, parent=self.root)
        if new_code is not None: # Allow empty string to clear
            self.config["binding_code"] = new_code
            self.save_config()
            # Force reload to update memory
            self.load_config()

    def prompt_for_hotkeys(self):
        # Ask for Run Hotkey
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
                try:
                    self._hotkey_combo_keys = self._parse_hotkey(self.config.get("hotkey_run", "ctrl+enter"))
                except:
                    pass
            except: pass
            
        self.save_config()

    def prompt_for_ip(self):
        current = self.config.get("comfy_url", "127.0.0.1:8188")
        msg = ("请输入 ComfyUI 服务器地址：\n"
               "例如：192.168.1.5:8188\n\n"
               "注意：为了确保触发您本机的浏览器会话，\n"
               "如果是在本机运行，请使用 '127.0.0.1' 或 'localhost'。\n"
               "使用局域网 IP (如 192.168...) 可能会导致触发其他会话。")
               
        new_ip = simpledialog.askstring("服务器设置", msg, initialvalue=current, parent=self.root)
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

    def get_local_ip(self):
        try:
            # Method 1: Connect to the ComfyUI server IP to see which interface we use
            target_host = self.config.get("comfy_url", "127.0.0.1").split(":")[0]
            if "://" in target_host:
                target_host = target_host.split("://")[1].split(":")[0]
                
            # If server is localhost, our IP is 127.0.0.1
            if target_host in ["localhost", "127.0.0.1", "0.0.0.0"]:
                return "127.0.0.1"
                
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((target_host, 80)) # Port doesn't matter much for DGRAM
            IP = s.getsockname()[0]
            s.close()
            return IP
        except:
            # Fallback
            try:
                import socket
                return socket.gethostbyname(socket.gethostname())
            except:
                return "127.0.0.1"

    def send_trigger(self):
        # Debounce: Prevent double-triggering from keyboard or fast clicks
        if time.time() - self.last_trigger_time < 0.5:
            return
        self.last_trigger_time = time.time()
        
        # Run in thread to avoid blocking the hotkey hook
        threading.Thread(target=self._trigger_worker, daemon=True).start()

    def _trigger_worker(self):
        # Check Control Mode
        if self.config.get("control_mode") == "extension":
            self.send_extension_trigger()
            return
            
        # API Mode Check
        if self.btn.state == "offline": return

        try: 
            # Priority 1: Manual Binding Code
            binding_code = self.config.get("binding_code", "")
            
            # Priority 2: Use the browser ID we got from the local handshake
            target_id = self.browser_client_id
            
            # Priority 3: Fallback to sending our own ID/IP if handshake hasn't happened yet
            local_ip = self.get_local_ip()
            
            payload = {
                "clientId": self.client_id, # Our observer ID
                "clientIp": local_ip,
                "targetClientId": target_id, # The precise target (if known)
                "targetBindingId": binding_code # Manual binding code
            }
            resp = requests.post(self.trigger_url, json=payload, timeout=1)
            
            if resp.status_code == 404:
                self.safe_alert("连接错误", 
                    "找不到触发端点 (404)。\n\n"
                    "请确保此 'run_button' 插件已安装在：\n"
                    "ComfyUI/custom_nodes/run_button\n\n"
                    "并重启 ComfyUI。", "error")
        except Exception as e:
            print(f"Trigger request failed: {e}")

    def send_interrupt(self):
        # Run in thread to avoid blocking
        threading.Thread(target=self._interrupt_worker, daemon=True).start()

    def _interrupt_worker(self):
        # Check Control Mode
        if self.config.get("control_mode") == "extension":
            self.send_extension_trigger(action="stop")
            return

        try: requests.post(self.interrupt_url, timeout=1)
        except: pass

    def setup_hotkey(self):
        # Only register the Run/Queue hotkey
        hotkey = self.config.get("hotkey_run", "ctrl+enter")
        
        try: keyboard.add_hotkey(hotkey, self.send_trigger)
        except Exception as e:
            self.handle_hotkey_conflict("hotkey_run", hotkey, str(e))

    def start_hotkey_watch(self):
        try:
            self._hotkey_combo_keys = self._parse_hotkey(self.config.get("hotkey_run", "ctrl+enter"))
        except:
            self._hotkey_combo_keys = ["ctrl", "enter"]
        def _watch_loop():
            last_active = False
            while True:
                try:
                    active = self._combo_active(self._hotkey_combo_keys)
                    if active and not last_active:
                        self.send_trigger()
                    last_active = active
                    time.sleep(0.03)
                except:
                    time.sleep(0.2)
        threading.Thread(target=_watch_loop, daemon=True).start()

    def _parse_hotkey(self, s):
        try:
            s = (s or "").strip().lower().replace(" ", "")
            if not s:
                return ["ctrl", "enter"]
            return [p for p in s.split("+") if p]
        except:
            return ["ctrl", "enter"]

    def _combo_active(self, keys):
        try:
            return all(keyboard.is_pressed(k) for k in keys)
        except:
            return False

    def _register_hotkey(self, key_name, callback):
        # Legacy helper, kept for compatibility if needed by dialog
        hotkey = self.config.get(key_name)
        try: keyboard.add_hotkey(hotkey, callback)
        except: pass

    def handle_hotkey_conflict(self, key_name, hotkey, error_msg):
        self.root.after(0, lambda: self._show_hotkey_dialog(key_name, hotkey, error_msg))

    def reload_hotkeys(self):
        try:
            keyboard.unhook_all()
            self.setup_hotkey()
            messagebox.showinfo("快捷键", "快捷键已重新加载！")
            try:
                self._hotkey_combo_keys = self._parse_hotkey(self.config.get("hotkey_run", "ctrl+enter"))
            except:
                pass
        except Exception as e:
            messagebox.showerror("错误", f"重新加载失败：{e}")

    def _show_hotkey_dialog(self, key_name, hotkey, error_msg):
        msg = f"注册快捷键 '{hotkey}' 失败。\n错误信息：{error_msg}\n请输入新的快捷键："
        new_hotkey = simpledialog.askstring("快捷键冲突", msg, parent=self.root)
        if new_hotkey:
            self.config[key_name] = new_hotkey
            self.save_config()
            self._register_hotkey(key_name, getattr(self, "toggle_smart" if key_name == "hotkey_toggle" else "send_trigger"))

    # --- Connection & WebSocket ---
    def connection_manager_loop(self):
        while True:
            # Check Control Mode
            is_ext_mode = self.config.get("control_mode") == "extension"
            
            if is_ext_mode:
                # Extension Mode: Completely ignore ComfyUI address/connectivity
                # Force IDLE state so user can click
                # We do NOT ping stats_url here.
                # We also do NOT force WS connection here (it might fail due to auth).
                
                # If we are in "Offline" visual state, switch to Idle immediately
                if self.btn.state == "offline":
                     self.root.after(0, lambda: self.btn.set_state("idle"))
                     
                # Optional: We could try to connect WS 'best effort' in background, 
                # but let's respect "completely detach". 
                # If user wants progress, they should ensure ComfyUI is accessible or use API mode.
                # For now, we just ensure it's clickable.
                
                time.sleep(1) # Check less frequently
                continue

            # API Mode: Ping HTTP to check if server is reachable
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
            
            # Generate a specific Client ID to identify this script
            import uuid
            self.client_id = f"run_button_observer_{uuid.uuid4()}"
            
            # Append clientId to URL
            # ws://host/ws -> ws://host/ws?clientId=...
            ws_url_with_id = f"{self.ws_url}?clientId={self.client_id}"
            
            self.ws = websocket.WebSocketApp(
                ws_url_with_id,
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
        
        is_ext_mode = self.config.get("control_mode") == "extension"
        if is_ext_mode:
             self.root.after(0, lambda: self.btn.set_state("idle"))
        else:
             self.root.after(0, lambda: self.btn.set_state("offline"))

    def on_ws_message(self, ws, message):
        try:
            msg = json.loads(message)
            self.root.after(0, lambda: self.handle_ws_event(msg.get("type"), msg.get("data", {})))
        except: pass

    def handle_ws_event(self, mtype, data):
        # Handle cases where data might be nested oddly from extension proxy
        if mtype == "status":
            # Sometimes data is {status: {exec_info: ...}}
            # Other times it might be direct
            status_obj = data.get("status", {})
            exec_info = status_obj.get("exec_info", {})
            queue = exec_info.get("queue_remaining", 0)
            
            # Robustness: sometimes queue is null
            if queue is None: queue = 0
            
            if queue > 0:
                self.btn.set_state("running", self.btn.progress, queue)
            else:
                if self.btn.state == "running" and self.btn.queue_count == 0: pass
                elif self.btn.state == "running" and queue == 0:
                     # Check if we should really go idle (maybe executing?)
                     # But status event usually means idle if queue is 0
                     self.btn.set_state("running", self.btn.progress, 0)
                     # Wait, if queue is 0, we might still be executing the last node.
                     # Let's rely on 'executing' event to clear state, 
                     # OR if we get a status update that says not executing?
                     pass

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
                # Finished executing a prompt
                # Only go idle if queue is also empty
                if self.btn.queue_count == 0:
                    self.btn.set_state("idle", 0.0, 0)
            else:
                self.btn.set_state("running", self.btn.progress, self.btn.queue_count)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = FloatApp()
    app.run()
