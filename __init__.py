from server import PromptServer
from aiohttp import web
import json
import os

# --- Monkey Patch to Broadcast Progress ---
# By default, ComfyUI sends progress/execution events ONLY to the client that triggered the prompt.
# Since our float_run.py is a *different* client (WebSocket connection), it never sees them.
# We patch send_sync to broadcast these specific events to ALL clients so float_run.py can stay in sync.

# Safe Patching: Check if we already patched it to avoid infinite recursion
if not hasattr(PromptServer.instance.send_sync, "__run_button_patched__"):
    original_send_sync = PromptServer.instance.send_sync

    def broadcast_send_sync(event, data, sid=None):
        # 1. Perform the original behavior (unicast or broadcast as intended)
        original_send_sync(event, data, sid)
        
        # 2. If it was a unicast message (sid is set) AND it's a status update we care about
        # We want to forward this to our Observer Clients (FloatRun App)
        # Note: 'progress' event is high-frequency. Since we fixed the infinite recursion bug,
        # it is now safe to broadcast it again so the float ball shows progress.
        if sid is not None and event in ["progress", "executing", "execution_start", "execution_error", "execution_interrupted", "execution_cached"]:
            
            # Find all observer clients (Run Button App)
            # We identify them by their client_id starting with "run_button_observer"
            sockets = PromptServer.instance.sockets
            
            # Optimization: Check if we have any observers before iterating
            has_observers = False
            # This is O(N) unfortunately, but we can't easily maintain a separate list without hooking connection events.
            # However, removing "progress" event reduces the frequency of this check by 90%.
            
            for obs_sid in list(sockets.keys()):
                # Note: client_id is usually the key in sockets dict
                # But let's be safe and check if it's a string
                if str(obs_sid).startswith("run_button_observer"):
                    # Send a COPY of the event to this observer
                    # We use original_send_sync with the observer's SID
                    # This avoids infinite recursion and avoids broadcasting to everyone
                    try:
                        original_send_sync(event, data, sid=obs_sid)
                    except:
                        pass

    # Mark as patched
    broadcast_send_sync.__run_button_patched__ = True
    
    # Apply the patch
    PromptServer.instance.send_sync = broadcast_send_sync
    print("[RunButton] Patched PromptServer.send_sync to intelligently forward progress events.")
else:
    print("[RunButton] PromptServer.send_sync already patched. Skipping.")


# --- Binding Map ---
# Stores manual pairing codes: { "CODE_123": "socket_id_abc" }
BINDING_MAP = {}

# --- API Endpoint: Register Binding ---
async def register_binding(request):
    try:
        data = await request.json()
        binding_id = data.get("binding_id")
        client_id = data.get("client_id")
        
        if binding_id and client_id:
            BINDING_MAP[binding_id] = client_id
            print(f"[RunButton] 🔗 Registered binding: '{binding_id}' -> '{client_id}'")
            return web.json_response({"status": "ok"})
        else:
            return web.json_response({"status": "error", "message": "Missing fields"}, status=400)
    except Exception as e:
        print(f"[RunButton] Error registering binding: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

# --- API Endpoint: Trigger ---
async def trigger_run(request):
    try:
        data = await request.json()
    except:
        data = {}
        
    client_id = data.get("clientId")
    client_ip = data.get("clientIp") 
    target_client_id = data.get("targetClientId") # The specific browser ID to target (from local handshake)
    target_binding_id = data.get("targetBindingId") # NEW: The manual pairing code
    request_ip = request.remote      
    
    try:
        # Broadcast the trigger event to ONE connected client (Unicast)
        print(f"[RunButton] Trigger request received (from {client_id}). TargetID: {target_client_id}, BindingCode: {target_binding_id}")
        
        target_sid = None
        
        sockets = PromptServer.instance.sockets
        
        # Priority 0: Manual Binding Code (Highest Priority)
        if target_binding_id:
            bound_sid = BINDING_MAP.get(target_binding_id)
            if bound_sid:
                # Verify if this sid is still connected
                if bound_sid in sockets:
                    target_sid = bound_sid
                    print(f"[RunButton] 🔐 Using Manual Binding Code '{target_binding_id}' -> {target_sid}")
                else:
                    print(f"[RunButton] ⚠️ Bound client {bound_sid} (Code: {target_binding_id}) is disconnected.")
            else:
                print(f"[RunButton] ⚠️ Binding Code '{target_binding_id}' not registered on server.")

        # Priority 1: Exact Target ID (Handshake)
        if not target_sid and target_client_id:
            # Check if this target is actually connected
            if target_client_id in sockets:
                target_sid = target_client_id
                print(f"[RunButton] 🎯 Precision Strike: Targeting handshaked client {target_sid}")
            else:
                print(f"[RunButton] ⚠️ Target client {target_client_id} not found in sockets (disconnected?). Falling back...")

        # If no target_sid found yet (or handshake failed/disconnected), use fallbacks
        if not target_sid:
            candidates = []
            ip_matches = []
            
            for sid, handler in sockets.items():
                if str(sid).startswith("run_button_observer"):
                    continue
                
                # Try to get remote IP
                ws_ip = None
                try:
                    if hasattr(handler, 'request') and handler.request:
                         ws_ip = handler.request.remote
                    elif hasattr(handler, 'ws') and hasattr(handler.ws, '_request'):
                         ws_ip = handler.ws._request.remote
                except: pass
                
                # Check IP Match
                if ws_ip and (ws_ip == request_ip or ws_ip == client_ip):
                    ip_matches.append(sid)
                    
                candidates.append(sid)
                
            # Priority 2: IP Match
            if ip_matches:
                target_sid = ip_matches[-1]
                print(f"[RunButton] Found IP-matched client: {target_sid}")
                
            # Priority 3: Most Recent
            elif candidates:
                target_sid = candidates[-1]
                print(f"[RunButton] Fallback to most recent client: {target_sid}")
            
        if target_sid:
            PromptServer.instance.send_sync("run_button.trigger", {}, sid=target_sid)
            return web.json_response({"status": "triggered", "message": f"Sent to {target_sid}"})
        else:
            print("[RunButton] No valid browser client found to trigger.")
            return web.json_response({"status": "warning", "message": "No browser client connected"}, status=200)

    except Exception as e:
        print(f"[RunButton] Error broadcasting trigger: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

try:
    # Register the API endpoint
    routes = PromptServer.instance.app.router
    
    # Check if route already exists to avoid duplicates during reload
    route_exists = False
    for route in routes.routes():
        if route.resource and route.resource.canonical == "/run_button/trigger":
            route_exists = True
            break
            
    if not route_exists:
        routes.add_post("/run_button/trigger", trigger_run)
        routes.add_post("/run_button/register_binding", register_binding)
        print("[RunButton] API routes registered.")
    else:
        print("[RunButton] API route /run_button/trigger already exists.")
        
except Exception as e:
    print(f"[RunButton] Error registering routes: {e}")

# IMPORTANT: Expose the web directory for ComfyUI to load the JS file
WEB_DIRECTORY = "./js"

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
