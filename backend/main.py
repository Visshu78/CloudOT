import asyncio
import json
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from aiokafka import AIOKafkaConsumer
from event_engine import predict_event, generate_event
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

# Throttle: forward at most 1 event every FORWARD_INTERVAL seconds to WebSocket clients
FORWARD_INTERVAL = 0.2  # 5 events/sec max
_throttle = {"last_t": 0.0}


async def broadcast_payload(payload: dict):
    """Broadcast JSON payload to all connected WebSocket clients."""
    if not connected_clients:
        return
    message = json.dumps(payload)
    disconnected = []
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.append(client)
    for d in disconnected:
        if d in connected_clients:
            connected_clients.remove(d)


async def process_and_persist_event(event: dict, db):
    """Adds event to blockchain, throttles DB/WS broadcast, and checks block sealing."""
    blockchain.add_event(event)

    now = time.monotonic()
    if now - _throttle["last_t"] < FORWARD_INTERVAL:
        # Still check for block sealing even when throttling
        blockchain.try_seal_block()
        return
    _throttle["last_t"] = now

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

    await broadcast_payload(payload)


async def simulate_iot_stream():
    """Fallback generator when Kafka is offline. Uses real ML model & validation dataset."""
    print("[CityShield] Running in Real-Time IoT Simulation Mode (with Random Forest ML inference).")
    db = SessionLocal()
    try:
        while True:
            # Generate event with real ML inference on val_dataset
            event = await asyncio.to_thread(generate_event)
            await process_and_persist_event(event, db)
            await asyncio.sleep(0.2)
    except Exception as e:
        print(f"[CityShield] Simulation stream error: {e}")
    finally:
        db.close()


async def consume_kafka():
    consumer = AIOKafkaConsumer(
        'iot-traffic',
        bootstrap_servers='localhost:9092',
        group_id="cityshield-backend",
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        request_timeout_ms=3000
    )
    
    # Try connecting to Kafka
    connected = False
    for attempt in range(2):
        try:
            await asyncio.wait_for(consumer.start(), timeout=3.0)
            print("[CityShield] Connected to Kafka broker.")
            connected = True
            break
        except Exception:
            await asyncio.sleep(1)

    if not connected:
        print("[CityShield] Kafka broker not available at localhost:9092. Activating direct IoT generator.")
        asyncio.create_task(simulate_iot_stream())
        return

    db = SessionLocal()
    try:
        async for msg in consumer:
            data = msg.value
            features = data.get("features", [])
            
            # Predict in a thread to prevent blocking the event loop
            attack_type, confidence, severity = await asyncio.to_thread(predict_event, features)
            
            event = {
                "id": data.get("id"),
                "timestamp": data.get("timestamp"),
                "device_id": data.get("device_id"),
                "zone": data.get("zone"),
                "attack_type": attack_type,
                "confidence": confidence,
                "severity": severity,
                "verified": True,
            }

            await process_and_persist_event(event, db)

    except Exception as e:
        print(f"Kafka Consumer Error: {e}")
    finally:
        await consumer.stop()
        db.close()


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(consume_kafka())


# --- REST API: History endpoints ---

@app.get("/api/events/recent")
def get_recent_events(limit: int = 50):
    """Return the most recent N events from the database."""
    db = SessionLocal()
    try:
        rows = db.query(models_db.EventLog).order_by(
            models_db.EventLog.timestamp.desc()
        ).limit(limit).all()
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp,
                "device_id": r.device_id,
                "zone": r.zone,
                "attack_type": r.attack_type,
                "confidence": r.confidence,
                "severity": r.severity,
                "verified": r.verified,
            }
            for r in reversed(rows)  # oldest first so frontend prepends correctly
        ]
    finally:
        db.close()


@app.get("/api/blocks/recent")
def get_recent_blocks(limit: int = 20):
    """Return the most recent N blockchain blocks from the database."""
    db = SessionLocal()
    try:
        rows = db.query(models_db.BlockChain).order_by(
            models_db.BlockChain.batch_num.desc()
        ).limit(limit).all()
        return [
            {
                "batch_num": r.batch_num,
                "hash": r.hash,
                "prev_hash": r.prev_hash,
                "timestamp": r.timestamp,
                "event_count": r.event_count,
                "status": r.status,
            }
            for r in reversed(rows)
        ]
    finally:
        db.close()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            # Just keep the connection open and wait for messages from client if any
            # or just wait for disconnect
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
    except Exception as e:
        print(f"WebSocket Error: {e}")
        if websocket in connected_clients:
            connected_clients.remove(websocket)
