class PythojsClient {
    wsPath: string = "";
    ws: WebSocket | null = null;
    handlers: Record<string, Function> = {};
    constructor(
        private server: string, 
        private base: Record<string, any>,
        private logLevel: 0 | 1 | 2 | 3 = 3,
        ) {};
    async method(
        endpoint: string, 
        method: "GET" | "POST" | "WS" = "WS",
        data: Record<string, any> = {}
    ): Promise<any> {
        data = {...this.base, ...data};
        let resp;
        this.log("Sending "+method+" request to "+endpoint, 2);
        switch(method) {
            case "GET":
                resp = await fetch(this.server+endpoint+"?"+new URLSearchParams(data as any).toString());
                break;
            case "POST":
                resp = await fetch(this.server+endpoint, {
                    method: "POST",
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                break;
            case "WS":
                this.ws?.send(JSON.stringify({...data, method: endpoint}));
                break;
        };
        let json = await resp?.json();
        this.log("Received response from "+endpoint+": "+JSON.stringify(json), 3);
        return json;
    };
    log(message: string, level: 0 | 1 | 2 | 3 | null = null): void {
        if (level === null) { level = this.logLevel; }
        if(level > this.logLevel){ return; }
        if(level == 0 && this.logLevel == 0){ return; }
        switch(level) {
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
    };
    async onUpdate(update: string, func: Function): Promise<void> {
        this.handlers[update] = func;
    };
    dispatch(update: string, data: any): void {
        const handler = this.handlers[update] || this.handlers["*"];
        if (!handler) {
            this.log(`No handler for update ${update}`, 2);
            return;
        }
        this.log(`Dispatching update ${update}`, 3);
        try {
            handler(data, update);
        } catch (err) {
            this.log(`Error in handler ${update}: ${(err as Error).message}`, 1);
        }
    };
    async run(): Promise<void> {
        this.log("PythujsClient is running", 3);
        let info = await this.method("info", "GET");
        this.wsPath = info.ws_path;
        const wsURL = this.server.replace(/^http/, "ws") + this.wsPath;
        this.ws = new WebSocket(wsURL);
        this.ws.onopen = (event) => {
            this.log("WebSocket connection opened", 3);
        };
        this.ws.onmessage = (event) => {
            this.log("WebSocket message received: "+event.data, 3);
            let message = JSON.parse(event.data);
            this.dispatch(message.update, message.data);
        }
    }
}; (window as any).PythojsClient = PythojsClient;