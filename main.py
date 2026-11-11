import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

app = FastAPI(title="Evryfi Core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, phone: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[phone] = websocket

    def disconnect(self, phone: str):
        if phone in self.active_connections:
            del self.active_connections[phone]

    async def send_to_user(self, target: str, message: dict):
        if target in self.active_connections:
            await self.active_connections[target].send_text(json.dumps(message))
            return True
        return False

manager = ConnectionManager()

@app.get("/")
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws/{phone}")
async def websocket_endpoint(websocket: WebSocket, phone: str):
    await manager.connect(phone, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            action = data.get("action")

            if action == "request_auth":
                target = data.get("target")
                delivered = await manager.send_to_user(target, {
                    "event": "auth_challenge",
                    "from": phone,
                    "title": data.get("title"),
                    "amount": data.get("amount")
                })
                if not delivered:
                    await websocket.send_text(json.dumps({"event": "error", "msg": "گوشی مقابل آنلاین نیست"}))

            elif action == "auth_approved":
                await manager.send_to_user(data.get("requester"), {
                    "event": "auth_success",
                    "signature": data.get("signature")
                })

            elif action == "auth_rejected":
                await manager.send_to_user(data.get("requester"), {
                    "event": "auth_failed"
                })

    except WebSocketDisconnect:
        manager.disconnect(phone)