import json
import time
import random
import uuid
import torch
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

ZONES = ["Downtown", "Airport", "Harbor", "Industrial", "Residential", "University", "Hospital"]
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

def main():
    producer = get_producer()
    if not producer:
        print("Ensure Kafka is running on localhost:9092")
        return

    print("Starting IoT Event Producer... Press Ctrl+C to stop.")
    
    # Send a massive amount of data continuously
    try:
        while True:
            # Pick a random sample from our preprocessed validation set
            idx = random.randint(0, len(X_val_np) - 1)
            features = X_val_np[idx].tolist()
            
            zone = random.choice(ZONES)
            device_idx = random.randint(1, DEVICES_PER_ZONE)
            device_id = generate_device_id(zone, device_idx)
            
            payload = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "device_id": device_id,
                "zone": zone,
                "features": features, # Raw network packet features
            }
            
            producer.send('iot-traffic', value=payload)
            
            # Print occasionally to show it's working but don't choke the console
            if random.random() < 0.05:
                print(f"Produced event for {device_id} in {zone}")

            # Sleep briefly to simulate high throughput without instantly maxing CPU
            # 0.01s = ~100 events per second. 
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nShutting down Producer...")
    finally:
        producer.close()

if __name__ == "__main__":
    main()
