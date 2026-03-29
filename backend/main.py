import asyncio
import json
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from aiokafka import AIOKafkaConsumer
from event_engine import predict_event
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


async def consume_kafka():
    consumer = AIOKafkaConsumer(
        'iot-traffic',
        bootstrap_servers='localhost:9092',
        group_id="cityshield-backend",
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    
    # Wait for Kafka to be ready (retry loop)
    while True:
        try:
            await consumer.start()
            print("Connected to Kafka.")
            break
        except Exception as e:
            print(f"Waiting for Kafka: {e}")
            await asyncio.sleep(5)

    db = SessionLocal()
    try:
        async for msg in consumer:
            data = msg.value
            features = data.get("features", [])
            
            # Predict in a thread to prevent blocking the event loop
            attack_type, confidence, severity = await asyncio.to_thread(predict_event, features)
            
            event = {
                "id": data["id"],
                "timestamp": data["timestamp"],
                "device_id": data["device_id"],
                "zone": data["zone"],
                "attack_type": attack_type,
                "confidence": confidence,
                "severity": severity,
                "verified": True,
            }

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
            
            # Broadcast to all connected clients
            disconnected = []
            for client in connected_clients:
                try:
                    await client.send_text(message)
                except Exception:
                    disconnected.append(client)
            for d in disconnected:
                if d in connected_clients:
                    connected_clients.remove(d)

    except Exception as e:
        print(f"Kafka Consumer Error: {e}")
    finally:
        await consumer.stop()
        db.close()


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(consume_kafka())

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
