// Connect to local Desktop App
let socket = null;
let isConnected = false;

// Store IDs of tabs that have identified themselves as ComfyUI
const knownComfyTabs = new Set();
let lastTitleHadPercentage = false;

// Clean up closed tabs
chrome.tabs.onRemoved.addListener((tabId) => {
    knownComfyTabs.delete(tabId);
});

// Monitor Title Changes for Progress (Backup Strategy)
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.title) {
        // Check if this is a ComfyUI tab (Known or Heuristic)
        let isComfy = knownComfyTabs.has(tabId);
        if (!isComfy && isComfyHeuristic(tab)) {
            isComfy = true;
        }

        if (isComfy && isConnected && socket) {
            // Regex to find percentage: 50%, [50%], (50%)
            const match = changeInfo.title.match(/(\d+)%/);
            if (match) {
                lastTitleHadPercentage = true;
                const pct = parseInt(match[1]);
                if (!isNaN(pct)) {
                    // Send progress event
                    try {
                        socket.send(JSON.stringify({
                            type: "progress",
                            data: { value: pct, max: 100 }
                        }));
                    } catch(e) {}
                }
            } else {
                 // Title does NOT have percentage.
                 // If we previously had percentage, it means we are DONE.
                 if (lastTitleHadPercentage) {
                     console.log("[RunButton Ext] Title implies done (percentage gone)");
                     lastTitleHadPercentage = false;
                     // Send completion signal
                      try {
                         socket.send(JSON.stringify({
                             type: "progress",
                             data: { value: 100, max: 100 }
                         }));
                         socket.send(JSON.stringify({
                             type: "executing",
                             data: { node: null }
                         }));
                     } catch(e) {}
                 }
            }
        }
    }
});

function connect() {
    console.log("[RunButton Ext] Attempting to connect...");
    // We use a different port or path for the extension websocket
    // Let's use the same port 56789 but WS protocol if the python server supports it
    // Or we can implement a simple WS server in Python on a new port like 56790
    try {
        if (socket) {
            try { socket.close(); } catch(e){}
        }
        
        socket = new WebSocket('ws://127.0.0.1:56790');

        socket.onopen = function() {
            console.log("[RunButton Ext] Connected to Desktop App");
            isConnected = true;
            // Keep alive
            setInterval(() => {
                if(socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: 'ping'}));
            }, 30000);
        };

        socket.onmessage = function(event) {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'trigger') {
                    console.log("[RunButton Ext] Trigger received!");
                    triggerComfyUI();
                } else if (msg.type === 'stop') {
                    console.log("[RunButton Ext] Stop received!");
                    stopComfyUI();
                } else if (msg.type === 'execution_success') {
                    // Force complete progress
                    try {
                        socket.send(JSON.stringify({
                            type: "progress",
                            data: { value: 100, max: 100 }
                        }));
                        socket.send(JSON.stringify({
                            type: "executing",
                            data: { node: null }
                        }));
                    } catch(e) {}
                }
            } catch (e) {
                console.error(e);
            }
        };

        socket.onclose = function() {
            console.log("[RunButton Ext] Disconnected. Retrying in 5s...");
            isConnected = false;
            socket = null;
            setTimeout(connect, 5000);
        };

        socket.onerror = function(err) {
            console.error("[RunButton Ext] Socket error:", err);
            // Do not close immediately, let onclose handle it or wait for timeout
            // socket.close(); 
        };
    } catch(e) {
        console.error("[RunButton Ext] Connection failed:", e);
        setTimeout(connect, 5000);
    }
}

async function triggerComfyUI() {
    let targetTab = await findTargetTab();
    
    if (!targetTab) {
        console.log("[RunButton Ext] No ComfyUI tabs found.");
        return;
    }

    // Trigger
    injectTriggerScript(targetTab);
}

async function stopComfyUI() {
    let targetTab = await findTargetTab();
    if (!targetTab) return;
    
    console.log("[RunButton Ext] Sending STOP to tab:", targetTab.id, targetTab.title);
    
    chrome.scripting.executeScript({
        target: { tabId: targetTab.id },
        world: 'MAIN', // Execute in Main World to access window.app
        function: () => {
             console.log("[RunButton In-Page] Attempting to STOP...");
             if (window.app && window.app.api) {
                 window.app.api.interrupt();
                 console.log("[RunButton In-Page] Called app.api.interrupt()");
                 return;
             }
             // Fallback: Click Cancel button
             // .comfy-menu-bg .comfy-list-button text=Cancel
             const menuBtns = document.querySelectorAll(".comfy-menu-bg .comfy-list-button");
             for (let b of menuBtns) {
                 if (b.innerText.includes("Cancel") || b.innerText.includes("Interrupt")) {
                     b.click();
                     return;
                 }
             }
        }
    });
}

async function findTargetTab() {
    let targetTab = null;
    const activeTabs = await chrome.tabs.query({active: true, currentWindow: true});
    const activeTab = activeTabs[0];

    // Strategy 1 & 2: Active Tab
    if (activeTab) {
        if (knownComfyTabs.has(activeTab.id)) {
            targetTab = activeTab;
        } else if (isComfyHeuristic(activeTab)) {
            targetTab = activeTab;
        }
    }

    // Strategy 3: Known Comfy Tabs (Background)
    if (!targetTab && knownComfyTabs.size > 0) {
        const ids = Array.from(knownComfyTabs);
        try {
            const tabs = await chrome.tabs.get(ids[ids.length - 1]);
            targetTab = tabs;
        } catch(e) {
            knownComfyTabs.delete(ids[ids.length - 1]);
        }
    }

    // Strategy 4: Search All (Fallback)
    if (!targetTab) {
        const allTabs = await chrome.tabs.query({});
        for (const tab of allTabs) {
            if (isComfyHeuristic(tab)) {
                targetTab = tab;
                break;
            }
        }
    }
    return targetTab;
}

function isComfyHeuristic(tab) {
    if (!tab.url) return false;
    return tab.title.includes("ComfyUI") || 
           tab.url.includes(":8188") || 
           tab.url.includes("127.0.0.1") || 
           tab.url.includes("localhost") ||
           tab.url.includes("ngrok") || 
           tab.url.includes("gradio"); // Some webuis
}

async function injectTriggerScript(tab) {
    console.log("[RunButton Ext] Sending click to tab:", tab.id, tab.title);
    try {
        chrome.scripting.executeScript({
            target: { tabId: tab.id },
            function: () => {
                // This runs in the page context
                console.log("[RunButton In-Page] Attempting to click...");
                
                // 1. Try ID
                const btn = document.getElementById('queue-button');
                if (btn) {
                    btn.click();
                    console.log("[RunButton In-Page] Clicked #queue-button");
                    return;
                } 
                
                // 2. Try Class (ComfyUI standard class for menu buttons)
                const menuBtns = document.querySelectorAll(".comfy-menu-bg .comfy-list-button");
                for (let b of menuBtns) {
                    if (b.innerText.includes("Queue Prompt")) {
                        b.click();
                        console.log("[RunButton In-Page] Clicked .comfy-list-button");
                        return;
                    }
                }

                // 3. Fallback: Any button with text
                const buttons = Array.from(document.querySelectorAll("button"));
                const textBtn = buttons.find(b => b.innerText.includes("Queue Prompt"));
                if (textBtn) {
                    textBtn.click();
                    console.log("[RunButton In-Page] Clicked button by text");
                }
            }
        });
    } catch (e) {
        console.error("[RunButton Ext] Failed to inject script:", e);
    }
}

// Start connection immediately
try {
    connect();
} catch(e) {
    console.error("Failed to start connection:", e);
}

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        // Register ComfyUI Tabs
        if (request.type === "comfy-event" && request.payload.type === "comfy-detected") {
            if (sender.tab && sender.tab.id) {
                if (!knownComfyTabs.has(sender.tab.id)) {
                    console.log(`[RunButton Ext] Registered ComfyUI Tab: ${sender.tab.id} (${sender.tab.title})`);
                    knownComfyTabs.add(sender.tab.id);
                }
            }
            return;
        }

        if (request.type === "comfy-event" && isConnected && socket) {
            // Forward to Desktop App via WebSocket
            // We wrap it in a JSON structure
            // { type: "status" | "progress" ..., data: ... }
            try {
                // The python backend expects: { type: "type", data: {} }
                const msg = {
                    type: request.payload.type,
                    data: request.payload.data
                };
                socket.send(JSON.stringify(msg));
            } catch (e) {
                console.error("[RunButton Ext] Failed to forward message:", e);
            }
        }
    });