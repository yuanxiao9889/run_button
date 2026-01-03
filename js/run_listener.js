import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "RunButton.Listener",
    async setup() {
        console.log("%c[RunButton] Extension Loaded! Waiting for trigger...", "color: green; font-weight: bold;");

        // Override api.addEventListener to debug if our event is even firing
        const originalAddEventListener = api.addEventListener;
        
        // Explicitly listen for our event
        api.addEventListener("run_button.trigger", (event) => {
            console.log("%c[RunButton] 🚀 TRIGGER RECEIVED!", "color: red; font-size: 20px; font-weight: bold;");
            
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
    }
});
