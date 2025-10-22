# Pythujs: API-2end Фреймворк

**PythuJS** — лёгкий серверный фреймворк на Python, вдохновлённый архитектурой FastAPI и Node.js.  
Он позволяет быстро поднимать асинхронные API-сервера с понятным и лаконичным синтаксисом.

---

## 🚀 Установка

```bash
pip install https://github.com/wlfrrm/pythujs/raw/main/dist/pythujs-0.1.0-py3-none-any.whl
```

## ⚙️ Использование

```Python
from pythujs import PythujsServer

app = PythujsServer()

home_model = app.model(hello=str, world=int)

@app.handler("home")
async def home(data: home_model):
    return {"hello": "world"}
```

```HTML
<script src="/pythujs"></script>
```


```JavaScript
const app = new PythujsClient("http://localhost:8000/")

app.run()

app.method("home", {hello: "hi", world: 42}).then((data) => { console.log(data) })
```

## 🧩 Сильные стороны фреймворки

#### Автогенерация моделей
PythujsServer.model позволяет автоматически генерировать Pydantic модели из словарей с аннотациями
#### Готовые механики пинг, апдейты
С помощью ws постоянного соденения можно легко отправлять апдейты с сервера, и отслеживать с клиента
#### Красивый синтаксис
Использование декораций а также стрелочных функций обеспечивают красивый и удобный синтаксис

## Подробное описание методов

### Python

1. `Инициализация сервера (PythujsServer.\_\_init\_\_)`
```Python

app = PythujsServer(
        request_base: Optional[dict] = {},
        # Параметры, которые остлеживаются при каждом запросе, если их нет то возвращает 422
        static_folder: Optional[str] = None,
        # Папка с статичeскими файлами
        init_base: bool = True,
        # Запуск встроенных хэндлеров
        host: str = "0.0.0.0",
        # Хост для запуска апи
        port: int = 8000,
        # Порт для запуска апи
        reload: bool = False,
        # Uvicorn reload
        log_config: Optional[dict] = None,
        # Конфигурация логгирования
        static_origin: str = "/static",
        # Ветка для статических файлов, если есть
        is_static_folder_html: bool = True,
        # Выдает index.html автоматически, если True
        show_errors: bool = False,
        # Показывает в апи ответах все ошибки, включать только при дебаггинге
        allow_origin: list = ["*"], 
        # CORS Параметр
        allow_headers: list = ["*"], 
        # CORS Параметр
        allowed_credentials: bool = True,
        # CORS Параметр
        ws_endpoint: str = "ws"
        # эндпоинт резервирующийся для вебсокета
    )
```

2. `Запуск Сервера (PythujsServer.run)`
```Python
await app.run() # Не принимает аргументов
```

3. `Отправка обновлений (PythujsServer.ws_send)`
```Python
await app.ws_send(connection_uuid, {"update": "pong", "data": {}})
# update и data - обязательные парметры
# connection_uuid - айди подключения к клиенту 
```

4. `Отправка сообщения всем клиентам (PythujsServer.ws_broadcast)`
```Python
await app.ws_broadcast({"update": "pong", "data": {}})
# update и data - обязательные парметры
```

5. `Ручная настройка хэндлера (PythujsServer.new_handler)`
```Python
await app.new_handler(method, func, model, sig)
# method - метод апи
# func - функция хэндлера
# model - Pydantic модель для валидации
# sig - сигнатура хэнддера
```

6. `Создание хэндлера (PythujsServer.handler)`
```Python
pingmodel = app.model() # Создание минимальной модели
@app.handler("ping") # Cоздание хэндлера
async def ping_handler(data: pingmodel): 
    try:
        return {"status": "ok"} # Возвращение JSON
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error" + (": "+str(e) if app.show_errors else "")) # Возвращение ошибки, можно return / raise
```

7.` Создание Pydantic Модели (PythujsServer.model)`
```Python
model = app.model(arg1=int, arg2=str)
=
class model(BaseModel):
    arg1: int
    arg2: str
```

8. `Создание on_connect хэндлера (Pythujs.on_connect)`
```Python
@app.on_connect
async def on_connect():
    return {"hello": "world!"} # При запуске клиента отправляет ему JSON
```

9. `Остановка сервера (PythujsServer.stop)`
```Python
await app.stop() # Заканчивает процесс и выключает сервер
```

10. `Роутеры (Router)`
```Python
rt = Router("api")

# Содздает отдельную ветку апи по /api/
# Наследует методы new_handler, handler от Сервера
# Добавляется с помощью app.include_router(rt)
```

11. `Чайлд-воркеры (Child)`
```Python
subapp = Child(request_base: Optional[dict] = {},
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
    ws_endpoint: str = "/ws")
    # Значения наследуются от сервера
    # Наследует методы от сервера
    # Добавляется с помощью
    # app.include_child(subapp)
```

12. `Исключения (StartingServerError, HandlerError, SenderError)`

| Исключение            | Случай                |
|-----------------------|-----------------------|      
| StartingServerError   | Возникает при передаче неправильных параметров при инициализации |
| HandlerError          | Возникает при неправильной регистрации Хэндлера |
| SenderError           | Возникает при неудачной отправке WS сообщения |

13. `FastAPI, Pydantic, Starlette`

Серверная часть библиотеки работает на базе этих 3 библиотек, и без базовых знаний по ним будет очень сложно пользоватся Pythujs

14. `Инициализация Клиентской части (PythujsClient)`
```JavaScript
const app = new PythojsClient(server="http://localhost:8000/", // Адрес сервера
                    base={...}, // База запроса
                    logLevel=1) // Уровень логирования - 3: Полное, 2: Важное, 1: Ошибки, 0: Отключено
```

15. Реализация API Метода (PythujsClient.method)
```JavaScript
app.method("ping", data={...}, method="WS") // data - JSON, method - GET/POST/WS
```

16. Умное логгирование (PythujsClient.log)
```JavaScript
app.log("hello", level=1) // Сообщение и уровень лога, об уровнях в пункте 14.
```

17. Запуск Клиента (PythujsClient.run)
```JavaScript
app.run() // Не принимает аргументов
```

18. Регистрация хэндлера апдейта с сервера (PythujsClient.onUpdate)
```JavaScript
app.onUpdate("pong", (data) => {...})
```

# Обратите внимание!
## Данная библиотека находится в бета тестировании, возможны ошибки. Сообщайте в Github issues

License: MIT
Author: [M2.128](t.me/wlfrm)
Version: 0.1.0
