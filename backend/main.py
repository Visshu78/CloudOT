import asyncio
import json
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from event_engine import generate_event
from blockchain import BlockchainManager

import models_db
from database import engine, SessionLocal

# Create database tables natively on app startup
models_db.Base.metadata.create_all(bind=engine)

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
    db = SessionLocal()  # Open a database session
    try:
        while True:
            await asyncio.sleep(random.uniform(1.5, 2.0))
            event = generate_event()
            
            # --- DATABASE PERSISTENCE: EVENT ---
            db_event = models_db.EventLog(
                id=event["id"],
                timestamp=event["timestamp"],
                device_id=event["device_id"],
                zone=event["zone"],
                attack_type=event["attack_type"],
                confidence=event["confidence"],
                severity=event["severity"],
                verified=event["verified"]
            )
            db.add(db_event)
            db.commit()

            blockchain.add_event(event)

            payload = {
                "type": "event",
                "data": event,
            }
            # Check if a new block was sealed
            new_block = blockchain.try_seal_block()
            if new_block:
                payload["block"] = new_block
                
                # --- DATABASE PERSISTENCE: BLOCK ---
                db_block = models_db.BlockChain(
                    batch_num=new_block["batch_num"],
                    hash=new_block["hash"],
                    prev_hash=new_block["prev_hash"],
                    timestamp=new_block["timestamp"],
                    event_count=new_block["event_count"],
                    status=new_block["status"]
                )
                db.add(db_block)
                db.commit()

            message = json.dumps(payload)
            await websocket.send_text(message)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception as e:
        print(f"WebSocket Loop Database Error: {e}")
        if websocket in connected_clients:
            connected_clients.remove(websocket)
    finally:
        db.close()
