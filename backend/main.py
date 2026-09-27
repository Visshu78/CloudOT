import asyncio
import json
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from aiokafka import AIOKafkaConsumer
from event_engine import predict_event, generate_event
from blockchain import BlockchainManager
from hdfs_manager import hdfs_manager
from spark_processor import spark_manager

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

# Sync blockchain counter with highest batch_num in DB to prevent collision
try:
    with SessionLocal() as _init_db:
        max_batch = _init_db.query(models_db.BlockChain.batch_num).order_by(models_db.BlockChain.batch_num.desc()).first()
        if max_batch and max_batch[0]:
            blockchain.block_counter = int(max_batch[0])
            print(f"[Blockchain] Synced block_counter to {blockchain.block_counter}")
except Exception as e:
    print(f"[Blockchain] Init sync notice: {e}")

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


async def periodic_hdfs_flusher():
    """Periodically flushes buffered events into DataNode block files every 3 seconds."""
    while True:
        try:
            await asyncio.sleep(3.0)
            hdfs_manager.flush_buffer()
        except Exception as e:
            print(f"[HDFS Flusher] Error: {e}")


async def periodic_spark_flusher():
    """Periodically evaluates sliding window time and flushes Spark micro-batches."""
    while True:
        try:
            await asyncio.sleep(2.0)
            spark_batch = spark_manager.flush_if_due()
            if spark_batch:
                await broadcast_payload({
                    "type": "spark_batch",
                    "data": spark_batch
                })
        except Exception as e:
            print(f"[Spark Flusher] Error: {e}")


async def process_and_persist_event(event: dict, db):
    """Adds event to blockchain, writes to DataNode storage, throttles DB/WS broadcast, and checks block sealing."""
    blockchain.add_event(event)

    # --- HDFS / DATANODE PERSISTENCE (Unthrottled, Replication Factor = 1) ---
    hdfs_manager.write_event(event)

    # --- APACHE SPARK STRUCTURED STREAMING (Micro-Batch Ingestion) ---
    spark_batch = spark_manager.add_event(event)
    if spark_batch:
        await broadcast_payload({
            "type": "spark_batch",
            "data": spark_batch
        })

    now = time.monotonic()
    if now - _throttle["last_t"] < FORWARD_INTERVAL:
        # Still check for block sealing even when throttling UI broadcast
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
        verified=event["verified"],
        server_id=event.get("server_id", "SRV-DEFAULT"),
        server_ip=event.get("server_ip", "127.0.0.1")
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
        try:
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
        except Exception:
            db.rollback()

    await broadcast_payload(payload)


async def simulate_iot_stream():
    """Fallback generator when Kafka is offline. Uses real ML model & validation dataset."""
    print("[CityShield] Running in Real-Time IoT Simulation Mode (with Random Forest ML inference).")
    db = SessionLocal()
    try:
        while True:
            try:
                # Generate event with real ML inference on val_dataset
                event = await asyncio.to_thread(generate_event)
                await process_and_persist_event(event, db)
                await asyncio.sleep(0.2)
            except Exception as e:
                db.rollback()
                await asyncio.sleep(0.5)
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
                "server_id": data.get("server_id", "EDGE-SRV-EAST-01"),
                "server_ip": data.get("server_ip", "10.240.1.101"),
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
    # Initialize HDFS directories asynchronously
    await asyncio.to_thread(hdfs_manager.init_hdfs_directories)
    # Initialize PySpark Session asynchronously
    await asyncio.to_thread(spark_manager.init_spark)
    # Start periodic HDFS DataNode flusher task
    asyncio.create_task(periodic_hdfs_flusher())
    # Start periodic Spark micro-batch flusher task
    asyncio.create_task(periodic_spark_flusher())
    asyncio.create_task(consume_kafka())


# --- REST API: History & System endpoints ---

@app.get("/api/spark/status")
def get_spark_status():
    """Return PySpark Structured Streaming engine status, session parameters, and micro-batch metrics."""
    return spark_manager.get_status()

@app.get("/api/spark/batches")
def get_spark_batches(limit: int = 15):
    """Return recent Spark micro-batches processed by the streaming engine."""
    return spark_manager.get_recent_batches(limit)

@app.post("/api/spark/trigger")
def trigger_spark_batch():
    """Manually trigger immediate Spark micro-batch processing."""
    batch = spark_manager.trigger_microbatch()
    return {
        "status": "SUCCESS" if batch else "EMPTY_BUFFER",
        "batch": batch,
        "total_batches": spark_manager.processed_batch_count
    }

@app.get("/api/hdfs/status")
def get_hdfs_status():
    """Return Hadoop HDFS connection status, cluster details, and replication settings (replication=1)."""
    return hdfs_manager.get_status()

@app.get("/api/hdfs/blocks")
def get_hdfs_blocks(limit: int = 15):
    """Return the recent DataNode storage block files generated by the simulator or HDFS."""
    return hdfs_manager.get_recent_datanode_blocks(limit)

@app.api_route("/api/hdfs/simulate", methods=["GET", "POST"], operation_id="simulate_hdfs_blocks_op")
def simulate_hdfs_blocks(count: int = 5):
    """Triggers immediate generation of simulated DataNode storage blocks."""
    hdfs_manager.simulate_datanode_block_generation(count)
    return {
        "status": "SUCCESS",
        "message": f"Successfully simulated {count} DataNode storage blocks (dfs.replication=1).",
        "total_blocks_now": hdfs_manager.get_status()["datanode_total_blocks_stored"]
    }


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
