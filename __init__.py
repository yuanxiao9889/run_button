from server import PromptServer
from aiohttp import web
import json
import os

# --- Monkey Patch to Broadcast Progress ---
# By default, ComfyUI sends progress/execution events ONLY to the client that triggered the prompt.
# Since our float_run.py is a *different* client (WebSocket connection), it never sees them.
# We patch send_sync to broadcast these specific events to ALL clients so float_run.py can stay in sync.

original_send_sync = PromptServer.instance.send_sync

def broadcast_send_sync(event, data, sid=None):
    # 1. Perform the original behavior (unicast or broadcast as intended)
    original_send_sync(event, data, sid)
    
    # 2. If it was a unicast message (sid is set) AND it's a status update we care about
    if sid is not None and event in ["progress", "executing", "execution_start", "execution_error", "execution_interrupted", "execution_cached"]:
        # DEBUG: Log that we are broadcasting
        # print(f"[RunButton] Broadcasting intercepted event: {event}")
        
        # Broadcast it to everyone (sid=None)
        original_send_sync(event, data, sid=None)

# Apply the patch
PromptServer.instance.send_sync = broadcast_send_sync
print("[RunButton] Patched PromptServer.send_sync to broadcast progress events.")


# --- API Endpoint ---
async def trigger_run(request):
    try:
        # Broadcast the trigger event to all connected clients
        # We send an empty dictionary as data, but the event name is the key
        print("[RunButton] Trigger request received. Broadcasting 'run_button.trigger'...")
        PromptServer.instance.send_sync("run_button.trigger", {})
        return web.json_response({"status": "triggered", "message": "Broadcast sent"})
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
        print("[RunButton] API route /run_button/trigger registered.")
    else:
        print("[RunButton] API route /run_button/trigger already exists.")
        
except Exception as e:
    print(f"[RunButton] Error registering routes: {e}")

# IMPORTANT: Expose the web directory for ComfyUI to load the JS file
WEB_DIRECTORY = "./js"

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
