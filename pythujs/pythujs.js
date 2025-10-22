class PythojsClient {
    server;
    base;
    logLevel;
    wsPath = "";
    ws = null;
    handlers = {};
    constructor(server, base, logLevel = 3) {
        this.server = server;
        this.base = base;
        this.logLevel = logLevel;
    }
    ;
    async method(endpoint, method = "WS", data = {}) {
        data = { ...this.base, ...data };
        let resp;
        this.log("Sending " + method + " request to " + endpoint, 2);
        switch (method) {
            case "GET":
                resp = await fetch(this.server + endpoint + "?" + new URLSearchParams(data).toString());
                break;
            case "POST":
                resp = await fetch(this.server + endpoint, {
                    method: "POST",
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                break;
            case "WS":
                this.ws?.send(JSON.stringify({ ...data, method: endpoint }));
                break;
        }
        ;
        let json = await resp?.json();
        this.log("Received response from " + endpoint + ": " + JSON.stringify(json), 3);
        return json;
    }
    ;
    log(message, level = null) {
        if (level === null) {
            level = this.logLevel;
        }
        if (level > this.logLevel) {
            return;
        }
        if (level == 0 && this.logLevel == 0) {
            return;
        }
        switch (level) {
            case 1:
                console.error(message);
                break;
            case 2:
                console.warn(message);
                break;
            case 3:
                console.log(message);
                break;
        }
    }
    ;
    async onUpdate(update, func) {
        this.handlers[update] = func;
    }
    ;
    dispatch(update, data) {
        const handler = this.handlers[update] || this.handlers["*"];
        if (!handler) {
            this.log(`No handler for update ${update}`, 2);
            return;
        }
        this.log(`Dispatching update ${update}`, 3);
        try {
            handler(data, update);
        }
        catch (err) {
            this.log(`Error in handler ${update}: ${err.message}`, 1);
        }
    }
    ;
    async run() {
        this.log("PythujsClient is running", 3);
        let info = await this.method("info", "GET");
        this.wsPath = info.ws_path;
        const wsURL = this.server.replace(/^http/, "ws") + this.wsPath;
        this.ws = new WebSocket(wsURL);
        this.ws.onopen = (event) => {
            this.log("WebSocket connection opened", 3);
        };
        this.ws.onmessage = (event) => {
            this.log("WebSocket message received: " + event.data, 3);
            let message = JSON.parse(event.data);
            this.dispatch(message.update, message.data);
        };
    }
}
window.PythojsClient = PythojsClient;