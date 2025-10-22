# Pythujs — Async API Framework (REST + WebSocket)

**PythuJS** is a lightweight asynchronous Python framework inspired by **FastAPI** and **Node.js**.  
It allows you to easily build asynchronous REST and WebSocket servers with clean, modular syntax.

---

## 🚀 Installation

```
pip install https://github.com/wlfrrm/pythujs/raw/main/dist/pythujs-0.1.0-py3-none-any.whl
```

(After PyPI release)

```
pip install pythujs
```

---

## ⚙️ Quick Start

```
from pythujs import PythujsServer

app = PythujsServer()

home_model = app.model(hello=str, world=int)

@app.handler("home")
async def home(data: home_model):
    return {"hello": "world"}
```

```
<script src="/pythujs"></script>
```

```
const app = new PythujsClient("http://localhost:8000/")

app.run()

app.method("home", {hello: "hi", world: 42}).then((data) => { console.log(data) })
```

---

## 🧩 Key Features

### Automatic Model Generation
`PythujsServer.model` automatically creates **Pydantic models** from annotated dictionaries.

### Built-in Ping and Update System
Thanks to persistent WebSocket connections, you can easily send live updates and events from server to client.

### Clean Syntax
Decorators in Python and arrow functions in JS make the code elegant and minimal.

---

## 📘 Server-Side Reference (Python)

### 1. `PythujsServer.__init__`
```
app = PythujsServer(
        request_base: Optional[dict] = {},
        static_folder: Optional[str] = None,
        init_base: bool = True,
        host: str = "0.0.0.0",
        port: int = 8000,
        reload: bool = False,
        log_config: Optional[dict] = None,
        static_origin: str = "/static",
        is_static_folder_html: bool = True,
        show_errors: bool = False,
        allow_origin: list = ["*"], 
        allow_headers: list = ["*"], 
        allowed_credentials: bool = True,
        ws_endpoint: str = "ws"
    )
```

### 2. `PythujsServer.run`
```
await app.run()
```

### 3. `PythujsServer.ws_send`
```
await app.ws_send(connection_uuid, {"update": "pong", "data": {}})
```
- `update` and `data` are required  
- `connection_uuid` — active WebSocket connection id

### 4. `PythujsServer.ws_broadcast`
```
await app.ws_broadcast({"update": "pong", "data": {}})
```

### 5. `PythujsServer.new_handler`
```
await app.new_handler(method, func, model, sig)
```

### 6. `PythujsServer.handler`
```
pingmodel = app.model()

@app.handler("ping")
async def ping_handler(data: pingmodel):
    try:
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error" + (": "+str(e) if app.show_errors else ""))
```

### 7. `PythujsServer.model`
```
model = app.model(arg1=int, arg2=str)
# Equals to:
class model(BaseModel):
    arg1: int
    arg2: str
```

### 8. `PythujsServer.on_connect`
```
@app.on_connect
async def on_connect():
    return {"hello": "world!"}
```

### 9. `PythujsServer.stop`
```
await app.stop()
```

### 10. `Router`
```
rt = Router("api")
# Creates a separate API branch (/api/)
# Inherits handler methods from server
# Added via app.include_router(rt)
```

### 11. `Child`
```
subapp = Child(...)
app.include_child(subapp)
```

---

## ⚠️ Exceptions

| Exception | Description |
|------------|-------------|
| `StartingServerError` | Raised on invalid initialization parameters |
| `HandlerError` | Raised when handler registration fails |
| `SenderError` | Raised on failed WebSocket data transmission |

---

## 🧠 Dependencies

The server part is built on:
- **FastAPI**
- **Pydantic**
- **Starlette**

Basic understanding of these libraries is recommended before using Pythujs.

---

## 💻 Client-Side Reference (JS)

### 1. `PythujsClient.__init__`
```
const app = new PythojsClient(
    server = "http://localhost:8000/",
    base = {...},
    logLevel = 1
)
```
- `server`: backend URL  
- `base`: base payload for every request  
- `logLevel`: 3 = full logs, 2 = important, 1 = errors, 0 = off  

### 2. `PythujsClient.method`
```
app.method("ping", data={...}, method="WS")
```

### 3. `PythujsClient.log`
```
app.log("hello", level=1)
```

### 4. `PythujsClient.run`
```
app.run()
```

### 5. `PythujsClient.onUpdate`
```
app.onUpdate("pong", (data) => {...})
```

---

## ⚠️ Note
This framework is currently in **beta testing**.  
Report issues at [GitHub Issues](https://github.com/wlfrrm/pythujs/issues)

License: MIT  
Author: [M2.128](https://t.me/wlfrm)  
Version: 0.1.0