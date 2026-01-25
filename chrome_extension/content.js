// RunButton Helper - Content Script
// This script runs in an isolated environment, but can access the DOM.
// We inject a script into the page context to hook into ComfyUI's API.

(function() {
    // 1. Create a script to run in the Page Context
    const script = document.createElement('script');
    script.textContent = `
    (function() {
        console.log("[RunButton Page] Injected script started.");
        
        // Wait for ComfyUI 'api' to be available
        const checkApi = setInterval(() => {
            if (window.app && window.app.api) {
                clearInterval(checkApi);
                console.log("[RunButton Page] ComfyUI API found. Hooking events...");
                
                // Notify content script that this IS a ComfyUI page
                window.postMessage({ source: "runbutton-page", type: "comfy-detected", data: { url: window.location.href, title: document.title } }, "*");
                
                hookComfy(window.app.api);
            }
        }, 1000);

        // Backup: DOM Check (in case app.api is hidden or slow)
        let foundDom = false;
        const checkDom = setInterval(() => {
            if (foundDom) {
                clearInterval(checkDom);
                return;
            }
            if (document.querySelector('.comfy-menu') || document.querySelector('#comfy-settings-dialog') || document.querySelector('.comfy-menu-bg')) {
                foundDom = true;
                clearInterval(checkDom);
                // We found UI elements, likely ComfyUI
                // console.log("[RunButton Page] ComfyUI DOM detected. Sending signal.");
                window.postMessage({ source: "runbutton-page", type: "comfy-detected", data: { method: "dom" } }, "*");
            }
        }, 1000); // Check every 1s instead of 2s to be faster
        // Stop DOM check after 60s
        setTimeout(() => clearInterval(checkDom), 60000);

        function hookComfy(api) {
            // Forward events to content script via postMessage
            console.log("[RunButton Page] Hooking API events: status, progress, executing...");
            
            api.addEventListener("status", (e) => {
                // console.log("[RunButton Page] Event: status", e.detail);
                window.postMessage({ source: "runbutton-page", type: "status", data: e.detail }, "*");
            });

            api.addEventListener("progress", (e) => {
                // console.log("[RunButton Page] Event: progress", e.detail);
                window.postMessage({ source: "runbutton-page", type: "progress", data: e.detail }, "*");
            });

            api.addEventListener("execution_start", (e) => {
                // console.log("[RunButton Page] Event: execution_start", e.detail);
                window.postMessage({ source: "runbutton-page", type: "execution_start", data: e.detail }, "*");
            });
            
            api.addEventListener("execution_error", (e) => {
                window.postMessage({ source: "runbutton-page", type: "execution_error", data: e.detail }, "*");
            });

            api.addEventListener("executing", (e) => {
                // console.log("[RunButton Page] Event: executing", e.detail);
                window.postMessage({ source: "runbutton-page", type: "executing", data: e.detail }, "*");
                
                // If e.detail is null, it means execution finished for the queue batch
                if (e.detail === null) {
                     // Force update status to idle/done
                     window.postMessage({ 
                         source: "runbutton-page", 
                         type: "status", 
                         data: { status: { exec_info: { queue_remaining: 0 } } } 
                     }, "*");
                }
            });
            
            // Also hook into rgthree if available (optional, but standard API usually covers it)
            // If rgthree provides specific detailed progress, we could add it here.
            
            // POLL for status (fallback if events are missed or not fired)
            setInterval(() => {
                if (window.app && window.app.ui) {
                     // 1. Queue Status
                     const q = window.app.ui.lastQueueRemaining;
                     if (typeof q === 'number') {
                          window.postMessage({ 
                              source: "runbutton-page", 
                              type: "status", 
                              data: { status: { exec_info: { queue_remaining: q } } } 
                          }, "*");
                     }
                     
                     // 2. Progress Status (Backup for title monitoring or direct access)
                     // If ComfyUI doesn't fire progress events (e.g. some custom nodes), 
                     // we might be able to read it from UI elements or app state if exposed.
                     // For now, let's just ensure we are alive.
                }
            }, 1000);
        }
    })();
    `;
    
    // 2. Inject
    (document.head || document.documentElement).appendChild(script);
    script.remove();

    // 3. Listen for messages from the Page Context
    window.addEventListener("message", (event) => {
        // We only accept messages from ourselves
        if (event.source !== window) return;
        if (event.data && event.data.source === "runbutton-page") {
            // Forward to Background Script
            try {
                chrome.runtime.sendMessage({
                    type: "comfy-event",
                    payload: {
                        type: event.data.type,
                        data: event.data.data
                    }
                });
            } catch (e) {
                // Background might be disconnected or sleeping
            }
        }
    });

})();
