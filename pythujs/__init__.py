"""
Pythujs — Lightweight asynchronous framework for REST and WebSocket APIs.

This module provides a minimal yet powerful server framework built on top of FastAPI and Uvicorn,
designed to unify REST endpoints and WebSocket communication under a single routing model.

Main features:
---------------
• Unified async dispatching for REST and WebSocket routes
• Dynamic handler registration via decorators (`@handler`, `@on_connect`)
• Support for Pydantic models (with automatic validation)
• Built-in static file serving and CORS middleware
• Modular structure with Router and Child servers
• Multi-port architecture for sub-domain or microservice style APIs
• Simple dependency resolution through Python type annotations
• Full asyncio support — all servers can run concurrently in one process

Core classes:
--------------
- `PythujsServer` — main entry point; manages routes, websockets, routers, and child nodes
- `Router`        — modular route container with isolated handler registration
- `Child`         — secondary API node that runs on a separate port but shares the same logic
- `HandlerError` and `StartingServerError` — exceptions for initialization and handler binding

Example:
--------
```python
from pythujs import PythujsServer, Router, WebSocket
import asyncio

server = PythujsServer(static_folder="public", show_errors=True)

@server.handler("ping")
async def ping(data):
    return {"status": "ok"}

@server.on_connect
async def on_connect(ws: WebSocket):
    await ws.send_json({"message": "hello world"})

auth = Router("auth")

@auth.handler("login")
async def login(data):
    return {"ok": True}

server.include_router(auth)

asyncio.run(server.run())

After starting the server:
	•	REST:  POST /ping returns {"status": "ok"}
	•	WS:    connect to ws://localhost:8000/ws and send {"method":"ping","data":{}}
	•	Static files are available under /static by default.

Pythujs is intended for projects where simplicity, modularity,
and WebSocket integration are essential without the overhead of large frameworks.
"""

import asyncio
import os, signal, logging, inspect
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Callable, Literal, Optional, Self, Type
from uvicorn import Config, Server
from pydantic import BaseModel

class StartingServerError(Exception):
    """
    Raised when there is an error starting the Pythujs server.
    """
    pass

class HandlerError(Exception):
    """
    Raised when there is an error with a handler function.
    """
    pass

class SenderError(Exception):
    """
    Raised when there is an error sending data over WebSocket.
    """
    pass

class PythujsServer:
    """
    Main server class for the Pythujs framework.

    Handles REST and WebSocket routes, static file serving, CORS,
    dynamic handler registration, and concurrent execution of child servers.
    """

    def __init__(self: Self, *, 
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
                ws_endpoint: str = "ws"):
        self.show_errors = show_errors
        self._api = FastAPI()
        self.init_base = init_base
        self._run_config = Config(
            app=self._api,
            host=host,
            port=port,
            reload=reload,
            log_config=log_config,
        )
        self.ws_endpoint = ws_endpoint

        try:
            self._api.add_middleware(
                CORSMiddleware,
                allow_origins=allow_origin,
                allow_credentials=allowed_credentials,
                allow_methods=["GET", "POST"],
                allow_headers=allow_headers,
            )
        except Exception as e:
            raise StartingServerError("Error while adding CORS middleware!") from e

        if static_folder:
            if not os.path.exists(static_folder):
                raise StartingServerError(f"Static folder does not exist: {static_folder}")
            if not static_origin.startswith("/"):
                static_origin = "/" + static_origin
            self._api.mount(static_origin, StaticFiles(directory=static_folder, html=is_static_folder_html), name="static")
        self.logger = logging.getLogger("pythujs")
        self.request_base = request_base
        self.handlers: dict = {}
        self.ws_handlers: dict[str, Callable] = {}
        self.active_sockets: dict[str, WebSocket] = {}
        self._api.websocket("/"+ws_endpoint)(self._ws_dispatcher)
        self.children: list[Child] = []

    async def run(self: Self):
        tasks = []
        for i in self.children:
            await i._init_base()
            task = asyncio.create_task(i.run())
            tasks.append(task)
        if self.init_base:
            await self._init_base()
        self._api.api_route("/{path:path}", methods=["GET", "POST"])(self._distpatcher)

        self.server = Server(config=self._run_config)
        self.logger.info("Starting Pythujs server...")
        return await asyncio.gather(self.server.serve(), *tasks)

    async def _ws_dispatcher(self, websocket: WebSocket):
        await websocket.accept()
        uid = str(id(websocket))
        self.active_sockets[uid] = websocket
        try:
            if hasattr(self, "_on_connect_handler"):
                try:
                    await self._on_connect_handler(websocket)
                except Exception as e:
                    self.logger.error(f"Error in on_connect: {e}")
                    await websocket.close()
                    return

            while True:
                payload = await websocket.receive_json()
                method = payload.get("method")
                data = payload.get("data", {})
                handler = self.handlers.get(method)
                if not handler:
                    await websocket.send_json({"error": f"Handler not found: {method}"})
                    continue
                model: Type[BaseModel] = handler["model"]
                try:
                    model_data = self.validate(model, data) if model else None
                    kwds = self.resolve_annotations(handler["sig"], {WebSocket: websocket})
                    kwds.pop("data", None)
                    result = await handler["func"](data=model_data, **kwds)
                    await websocket.send_json(result)
                except Exception as e:
                    await websocket.send_json({"error": str(e) if self.show_errors else "Internal server error"})
        except WebSocketDisconnect:
            self.active_sockets.pop(uid, None)
        except Exception:
            self.active_sockets.pop(uid, None)
            await websocket.close()

    async def _distpatcher(self, path: str, request: Request):
        handler = self.handlers.get(path, None)
        if not handler:
            raise HTTPException(status_code=404, detail=f"Handler not found for path: {path}")
        model: Type[BaseModel] = handler["model"]
        if model:
            try:
                if request.method == "GET":
                    data = dict(request.query_params)
                else:
                    data = await request.json()
            except Exception as e:
                raise HTTPException(status_code=422, detail="Field validation error: "+str(e))
        data = self.validate(model, data) if model else None
        if isinstance(data, HTTPException):
            return data
        try:
            self.logger.info(f"Handling request for path: {path} with data: {data}")
            kwds = self.resolve_annotations(handler["sig"], {Request: request})
            kwds.pop("data", None)
            response = await handler["func"](data=data, **kwds)
            return response
        except Exception as e:
            self.logger.error(f"Error while handling request for path: {path}\n{str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error" + (": "+str(e) if self.show_errors else ""))

    async def _init_base(self: Self):
        pingmodel = self.model()
        @self.handler("ping")
        async def ping_handler(data: pingmodel):
            try:
                return {"status": "ok"}
            except Exception as e:
                raise HTTPException(status_code=500, detail="Internal server error" + (": "+str(e) if self.show_errors else ""))
            
        @self.handler("info")
        async def info_handler(data):
            try:
                return {
                    "handlers": list(self.handlers.keys()),
                    "ws_path": self.ws_endpoint
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail="Internal server error" + (": "+str(e) if self.show_errors else ""))
        
        @self._api.get("/pythujs", response_class=Response)
        async def pythujs():
            return Response(
                content=open("pythujs.js", "r", encoding="utf-8").read(),
                media_type="text/javascript"
            )

    async def ws_send(self, uuid: str, data: dict):
        if data.get("update") is None:
            raise SenderError("Data must contain an 'update' field.")
        if data.get("data") is None:
            raise SenderError("Data must contain a 'data' field.")
        ws = self.active_sockets.get(uuid)
        if ws:
            if isinstance(data, dict):
                await ws.send_json(data)
            else:
                await ws.send_text(data)

    async def ws_broadcast(self, data: dict):
        if data.get("update") is None:
            raise SenderError("Data must contain an 'update' field.")
        if data.get("data") is None:
            raise SenderError("Data must contain a 'data' field.")
        for ws in list(self.active_sockets.values()):
            try:
                if isinstance(data, dict):
                    await ws.send_json(data)
                else:
                    await ws.send_text(data)
            except Exception:
                self.active_sockets.pop(str(id(ws)), None)

    def resolve_annotations(self, annot_dict: dict[str, Any], obj_dict: dict[type, Any]) -> dict[str, Any]:
        result = {}
        for name, annot_type in annot_dict.items():
            if annot_type in obj_dict and obj_dict[annot_type] is not None:
                result[name] = obj_dict[annot_type]
            else:
                result[name] = None
        return result

    def validate(self, model: Type[BaseModel], json: dict | list):
        try:
            return model.model_validate(json)
        except Exception as e:
            return HTTPException(status_code=422, detail="Field validation error: "+str(e) if self.show_errors else "Field validation error")

    def new_handler(self: Self, method: str, func: Callable, /, model: Optional[Type[BaseModel]], sig: dict):
        self.handlers[method] = {
            "model": model, "sig": sig, "func": func
        }

    def handler(self: Self, method: str):
        def wrapper(func):
            sig = inspect.signature(func)
            annot = sig.parameters["data"].annotation
            if not issubclass(annot, BaseModel):
                if not annot == inspect._empty:
                    raise HandlerError(f"Handler function must have a pydantic BaseModel as data parameter annotation!")
                else:
                    annot = None
            self.new_handler(method, func, model=annot, sig=func.__annotations__)
            return func
        return wrapper

    def model(self, **fields):
        annotations = {}
        defaults = {}
        for key, value in fields.items():
            if isinstance(value, tuple) and len(value) == 2:
                annotations[key] = value[0]
                defaults[key] = value[1]
            else:
                annotations[key] = value
        return type(
            "DynamicModel",
            (BaseModel,),
            {**defaults, "__annotations__": annotations, **self.request_base}
        )

    def on_connect(self: Self, func: Callable):
        self._on_connect_handler = func
        return func

    async def stop(self: Self):
        self.server.shutdown()
        os.kill(os.getpid(), signal.SIGINT)
        self.logger.info(f"Pythujs server stopped.") 

    def include_router(self, router: 'Router'):
        self.handlers.update({
            f"{router.name}/{k}": v for k, v in router.handlers.items()
        })

    def include_child(self, child: 'Child'):
        child._parent = self
        self.children.append(child)

class Router:
    """
    Router — modular route container for grouping related handlers.

    A Router allows you to organize multiple API handlers under a common name prefix.
    It can later be included into the main PythujsServer or a Child instance
    using the `include_router()` method.

    Attributes:
        name (str): Router name used as a prefix for all routes.
        handlers (dict): Dictionary of registered route handlers.
        route (str): Formatted route prefix (e.g., "auth/").
    """
    def __init__(self: Self, name: str = "", /):
        self.name = name
        self.handlers: dict = {}
        self.route = f"{name}/"

    def new_handler(self: Self, method: str, func: Callable, /, model: Optional[Type[BaseModel]], sig: dict):
        self.handlers[self.route+method] = {
            "model": model, "sig": sig, "func": func
        }

    def handler(self: Self, method: str):
        def wrapper(func):
            sig = inspect.signature(func)
            annot = sig.parameters["data"].annotation
            if not issubclass(annot, BaseModel):
                if not annot == inspect._empty:
                    raise HandlerError(f"Handler function must have a pydantic BaseModel as data parameter annotation!")
                else:
                    annot = None
            self.new_handler(method, func, model=annot, sig=func.__annotations__)
            return func
        return wrapper

class Child:
    async def _ws_dispatcher(self, websocket: WebSocket):
        await websocket.accept()
        uid = str(id(websocket))
        self.active_sockets[uid] = websocket
        try:
            if hasattr(self, "_on_connect_handler"):
                try:
                    await self._on_connect_handler(websocket)
                except Exception as e:
                    self.logger.error(f"Error in on_connect: {e}")
                    await websocket.close()
                    return

            while True:
                payload = await websocket.receive_json()
                method = payload.get("method")
                data = payload.get("data", {})
                handler = self.handlers.get(method)
                if not handler:
                    await websocket.send_json({"error": f"Handler not found: {method}"})
                    continue
                model: Type[BaseModel] = handler["model"]
                try:
                    model_data = self.validate(model, data) if model else None
                    kwds = self.resolve_annotations(handler["sig"], {WebSocket: websocket})
                    kwds.pop("data", None)
                    result = await handler["func"](data=model_data, **kwds)
                    await websocket.send_json(result)
                except Exception as e:
                    await websocket.send_json({"error": str(e) if self.show_errors else "Internal server error"})
        except WebSocketDisconnect:
            self.active_sockets.pop(uid, None)
        except Exception:
            self.active_sockets.pop(uid, None)
            await websocket.close()

    async def _distpatcher(self, path: str, request: Request):
        handler = self.handlers.get(path, None)
        if not handler:
            raise HTTPException(status_code=404, detail=f"Handler not found for path: {path}")
        model: Type[BaseModel] = handler["model"]
        if model:
            try:
                if request.method == "GET":
                    data = dict(request.query_params)
                else:
                    data = await request.json()
            except Exception as e:
                raise HTTPException(status_code=422, detail="Field validation error: "+str(e))
        data = self.validate(model, data) if model else None
        if isinstance(data, HTTPException):
            return data
        try:
            self.logger.info(f"Handling request for path: {path} with data: {data}")
            kwds = self.resolve_annotations(handler["sig"], {Request: request})
            kwds.pop("data", None)
            response = await handler["func"](data=data, **kwds)
            return response
        except Exception as e:
            self.logger.error(f"Error while handling request for path: {path}\n{str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error" + (": "+str(e) if self.show_errors else ""))

    def resolve_annotations(self, annot_dict: dict[str, Any], obj_dict: dict[type, Any]) -> dict[str, Any]:
        result = {}
        for name, annot_type in annot_dict.items():
            if annot_type in obj_dict and obj_dict[annot_type] is not None:
                result[name] = obj_dict[annot_type]
            else:
                result[name] = None
        return result

    def validate(self, model: Type[BaseModel], json: dict | list):
        try:
            return model.model_validate(json)
        except Exception as e:
            return HTTPException(status_code=422, detail="Field validation error: "+str(e))

    def new_handler(self: Self, method: str, func: Callable, /, model: Optional[Type[BaseModel]], sig: dict):
        self.handlers[method] = {
            "model": model, "sig": sig, "func": func
        }
    
    def handler(self: Self, method: str):
        def wrapper(func):
            sig = inspect.signature(func)
            annot = sig.parameters["data"].annotation
            if not issubclass(annot, BaseModel):
                if not annot == inspect._empty:
                    raise HandlerError(f"Handler function must have a pydantic BaseModel as data parameter annotation!")
                else:
                    annot = None
            self.new_handler(method, func, model=annot, sig=func.__annotations__)
            return func
        return wrapper

    def model(self, **fields):
        annotations = {}
        defaults = {}
        for key, value in fields.items():
            if isinstance(value, tuple) and len(value) == 2:
                annotations[key] = value[0]
                defaults[key] = value[1]
            else:
                annotations[key] = value
        return type(
            "DynamicModel",
            (BaseModel,),
            {**defaults, "__annotations__": annotations, **self.request_base}
        )
    
    def on_connect(self: Self, func: Callable):
        self._on_connect_handler = func
        return func

    async def _init_base(self: Self):
        pingmodel = self.model()
        @self.handler("ping")
        async def ping_handler(data: pingmodel):
            try:
                return {"status": "ok"}
            except Exception as e:
                raise HTTPException(status_code=500, detail="Internal server error" + (": "+str(e) if self.show_errors else ""))
            
        @self.handler("info")
        async def info_handler(data):
            try:
                return {
                    "handlers": list(self.handlers.keys()),
                    "allowed_methods": self.allowed_methods,
                    "ws_path": self.ws_endpoint
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail="Internal server error" + (": "+str(e) if self.show_errors else ""))

    def include_router(self, router: 'Router'):
        self.handlers.update({
            f"{router.name}/{k}": v for k, v in router.handlers.items()
        })

    def __init__(self: Self, *, 
                request_base: Optional[dict] = {},
                static_folder: Optional[str] = None,
                init_base: bool = True,
                host: str = "0.0.0.0",
                port: int = 4000,
                reload: bool = False,
                static_origin: str = "/static",
                is_static_folder_html: bool = True,
                show_errors: bool = False,
                allow_origin: list = ["*"], 
                allow_headers: list = ["*"], 
                allowed_credentials: bool = True,
                ws_endpoint: str = "/ws"):

        self.show_errors = show_errors
        self._api = FastAPI()
        self.init_base = init_base
        self._run_config = Config(
            app=self._api,
            host=host,
            port=port,
            reload=reload,
        )
        self.ws_endpoint = ws_endpoint
        self._parent: PythujsServer

        try:
            self._api.add_middleware(
                CORSMiddleware,
                allow_origins=allow_origin,
                allow_credentials=allowed_credentials,
                allow_methods=["GET", "POST"],
                allow_headers=allow_headers,
            )
        except Exception as e:
            raise StartingServerError("Error while adding CORS middleware!") from e

        if static_folder:
            if not os.path.exists(static_folder):
                raise StartingServerError(f"Static folder does not exist: {static_folder}")
            if not static_origin.startswith("/"):
                static_origin = "/" + static_origin
            self._api.mount(static_origin, StaticFiles(directory=static_folder, html=is_static_folder_html), name="static")

        self.logger = logging.getLogger("pythujs")
        self.request_base = request_base
        self.handlers: dict = {}
        self.ws_handlers: dict[str, Callable] = {}
        self.active_sockets: dict[str, WebSocket] = {}
        self._api.websocket(ws_endpoint)(self._ws_dispatcher)

    async def run(self: Self):
        if self.init_base:
            await self._init_base()
        self._api.api_route("/{path:path}", methods=["GET", "POST"])(self._distpatcher)
        self.server = Server(config=self._run_config)
        self.logger.info(f"Starting Child server on port {self._run_config.port}...")
        return await self.server.serve()

    async def stop(self: Self):
        self.server.shutdown()
        os.kill(os.getpid(), signal.SIGINT)
        self.logger.info(f"Pythujs server stopped.") 


__all__ = ["PythujsServer", "Router", "WebSocket", "HTTPException", "Request", "BaseModel", "HandlerError", "StartingServerError", "Child", "FileResponse", "HTMLResponse"]
__version__ = (0, 1, 0)
__version_str__ = ".".join(map(str, __version__))
__author__ = "M2.128 (Mark)"
__requires__ = ["fastapi", "uvicorn", "pydantic"]
__license__ = "MIT"
logging.getLogger("pythujs").setLevel(logging.INFO)