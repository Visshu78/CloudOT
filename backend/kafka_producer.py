import json
import time
import random
import uuid
import torch
import threading
from kafka import KafkaProducer
from datetime import datetime

# Load Validation Dataset for realistic inference samples
try:
    X_val_tensor, y_val_tensor = torch.load("val_dataset.pt", map_location='cpu')
    X_val_np = X_val_tensor.numpy()
    print(f"[Producer] Loaded {len(X_val_np)} validation samples.")
except Exception as e:
    print(f"[Producer] Error loading dataset: {e}. Ensure val_dataset.pt is present.")
    exit(1)

# Multi-Server / Regional Gateway Node Definitions
SERVERS = [
    {"server_id": "EDGE-SRV-EAST-01", "server_ip": "10.240.1.101", "location": "US-East (Virginia)", "zones": ["Downtown", "Airport"]},
    {"server_id": "EDGE-SRV-WEST-02", "server_ip": "10.240.2.102", "location": "US-West (Oregon)", "zones": ["Harbor", "Industrial"]},
    {"server_id": "EDGE-SRV-CENTRAL-03", "server_ip": "10.240.3.103", "location": "US-Central (Texas)", "zones": ["Residential", "University"]},
    {"server_id": "EDGE-SRV-SOUTH-04", "server_ip": "10.240.4.104", "location": "US-South (Florida)", "zones": ["Hospital", "Downtown"]},
    {"server_id": "EDGE-SRV-EU-05", "server_ip": "10.240.5.105", "location": "EU-Central (Frankfurt)", "zones": ["Airport", "Harbor"]}
]

ZONE_PREFIXES = {
    "Downtown": "DWN",
    "Airport": "AIR",
    "Harbor": "HAR",
    "Industrial": "IND",
    "Residential": "RES",
    "University": "UNI",
    "Hospital": "HOS"
}
DEVICES_PER_ZONE = 15

def generate_device_id(zone: str, idx: int) -> str:
    prefix = ZONE_PREFIXES.get(zone, zone[:3].upper())
    return f"{prefix}-{idx:03d}"

def get_producer():
    try:
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        return producer
    except Exception as e:
        print(f"Failed to connect to Kafka: {e}")
        return None

def run_server_worker(server: dict, producer: KafkaProducer, stop_event: threading.Event):
    """Simulates an individual Edge Server streaming real-time IoT events to Kafka."""
    server_id = server["server_id"]
    server_ip = server["server_ip"]
    zones = server["zones"]
    
    print(f"[{server_id}] Gateway active on IP {server_ip} servicing zones {zones}")
    
    while not stop_event.is_set():
        # Pick a random sample from our preprocessed validation set
        idx = random.randint(0, len(X_val_np) - 1)
        features = X_val_np[idx].tolist()
        
        zone = random.choice(zones)
        device_idx = random.randint(1, DEVICES_PER_ZONE)
        device_id = generate_device_id(zone, device_idx)
        
        payload = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "device_id": device_id,
            "zone": zone,
            "server_id": server_id,
            "server_ip": server_ip,
            "features": features, # Raw network packet features
        }
        
        producer.send('iot-traffic', value=payload)
        
        if random.random() < 0.05:
            print(f"[{server_id} @ {server_ip}] Sent event for {device_id} ({zone})")
            
        # Simulate realistic multi-server jitter and high-speed streaming
        time.sleep(random.uniform(0.01, 0.05))

def main():
    producer = get_producer()
    if not producer:
        print("Ensure Kafka is running on localhost:9092")
        return

    print("Starting Multi-Server Distributed IoT Event Producer... Press Ctrl+C to stop.")
    stop_event = threading.Event()
    threads = []
    
    # Spawn a thread for each Edge Server
    for server_info in SERVERS:
        t = threading.Thread(target=run_server_worker, args=(server_info, producer, stop_event), daemon=True)
        t.start()
        threads.append(t)
        
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down Multi-Server Producer...")
        stop_event.set()
        producer.close()

if __name__ == "__main__":
    main()
