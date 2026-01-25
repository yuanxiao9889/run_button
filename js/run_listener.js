import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "RunButton.Listener",
    async setup() {
        console.log("%c[RunButton] Extension Loaded! Waiting for trigger...", "color: green; font-weight: bold;");

        // --- Hook app.queuePrompt to track last execution time ---
        // This prevents double-submission when using shortcuts like Ctrl+Enter
        // which might be handled by BOTH the browser and our global hotkey listener.
        let lastQueueTime = 0;
        const originalQueuePrompt = app.queuePrompt;
        
        app.queuePrompt = async function() {
            lastQueueTime = Date.now();
            // console.log("[RunButton] app.queuePrompt called at", lastQueueTime);
            return originalQueuePrompt.apply(this, arguments);
        };

        // Override api.addEventListener to debug if our event is even firing
        const originalAddEventListener = api.addEventListener;
        
        // Explicitly listen for our event
        api.addEventListener("run_button.trigger", (event) => {
            console.log("%c[RunButton] 🚀 TRIGGER RECEIVED!", "color: red; font-size: 20px; font-weight: bold;");
            
            // Debounce check: If a queue happened < 500ms ago, ignore this trigger
            const timeSinceLastQueue = Date.now() - lastQueueTime;
            if (timeSinceLastQueue < 500) {
                console.log(`[RunButton] ⚠️ Ignoring trigger because queuePrompt was called ${timeSinceLastQueue}ms ago.`);
                return;
            }

            try {
                // Try clicking the physical button first - it's often more reliable than app.queuePrompt(0)
                // because it handles shift/ctrl states and UI updates correctly
                const queueBtn = document.getElementById("queue-button");
                if (queueBtn) {
                    console.log("[RunButton] Clicking #queue-button...");
                    queueBtn.click();
                    return;
                }
                
                // Fallback: search by text
                const buttons = Array.from(document.querySelectorAll("button"));
                const btn = buttons.find(b => b.innerText.includes("Queue Prompt"));
                if (btn) {
                    console.log("[RunButton] Clicking 'Queue Prompt' button found by text...");
                    btn.click();
                    return;
                }

                // Last resort: API call
                console.log("[RunButton] No button found, trying app.queuePrompt(0)...");
                app.queuePrompt(0);
                
            } catch (e) {
                console.error("[RunButton] ❌ Error triggering queue:", e);
            }
        });

        // --- HANDSHAKE: Register with local Desktop App ---
        // This tries to tell the local float_run.py "I am the browser on this machine, here is my ID"
        // so it can target ME specifically instead of broadcasting.
        async function registerWithLocalSidecar() {
            try {
                const clientId = api.clientId;
                if (!clientId) {
                    console.log("[RunButton] No api.clientId yet, retrying handshake in 1s...");
                    setTimeout(registerWithLocalSidecar, 1000);
                    return;
                }

                console.log("[RunButton] Attempting handshake with local Desktop App...", clientId);
                
                // We use 127.0.0.1:56789 (The Sidecar Port)
                // Note: If you use HTTPS for ComfyUI, this might be blocked by Mixed Content policies.
                // But most local users use HTTP.
                const resp = await fetch("http://127.0.0.1:56789/register", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ clientId: clientId })
                });

                if (resp.ok) {
                    console.log("%c[RunButton] ✅ Handshake Successful! Desktop App knows my ID.", "color: green");
                } else {
                    console.warn("[RunButton] Handshake failed (Server error). Retrying...");
                    setTimeout(registerWithLocalSidecar, 5000);
                }
            } catch (e) {
                // This is expected if the desktop app is not running yet
                console.log("[RunButton] Desktop App not found (yet). Retrying handshake in 5s...");
                setTimeout(registerWithLocalSidecar, 5000);
            }
        }
        
        // Start handshake loop
        setTimeout(registerWithLocalSidecar, 1000);

        // --- MANUAL BINDING ---
        // Register a setting in ComfyUI for the user to enter a Pairing Code
        app.ui.settings.addSetting({
            id: "RunButton.BindingCode",
            name: "RunButton Pairing Code (配对码)",
            type: "text",
            defaultValue: "",
            tooltip: "Enter a unique code (e.g. 'ABC') here and in the RunButton Desktop App to bind them together manually.",
            onChange: async (value) => {
                if (!value) return;
                console.log("[RunButton] Binding Code Changed:", value);
                
                // Send registration to server
                try {
                    const clientId = api.clientId;
                    if (!clientId) return;

                    const resp = await fetch("/run_button/register_binding", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ 
                            binding_id: value,
                            client_id: clientId 
                        })
                    });
                    
                    if (resp.ok) {
                        // Optional: Show a toast or log
                        console.log("[RunButton] Binding Registered Successfully!");
                    }
                } catch (e) {
                    console.error("[RunButton] Failed to register binding:", e);
                }
            }
        });

        // Trigger registration on load if value exists
        const currentBinding = app.ui.settings.getSettingValue("RunButton.BindingCode");
        if (currentBinding) {
            // Give it a moment for clientId to be ready
            setTimeout(() => {
                 // Re-trigger the onChange logic
                 const callback = app.ui.settings.getSetting("RunButton.BindingCode").onChange;
                 if(callback) callback(currentBinding);
            }, 2000);
        }
    }
});
