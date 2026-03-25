import asyncio
import json
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from event_engine import generate_event
from blockchain import BlockchainManager

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

blockchain = BlockchainManager()
connected_clients: list[WebSocket] = []


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await asyncio.sleep(random.uniform(1.5, 2.0))
            event = generate_event()
            blockchain.add_event(event)
            payload = {
                "type": "event",
                "data": event,
            }
            # Check if a new block was sealed
            new_block = blockchain.try_seal_block()
            if new_block:
                payload["block"] = new_block

            message = json.dumps(payload)
            await websocket.send_text(message)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
