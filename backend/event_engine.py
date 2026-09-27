import random
import uuid
from datetime import datetime
import joblib
import torch
import os
import numpy as np

ZONES = ["Downtown", "Airport", "Harbor", "Industrial", "Residential", "University", "Hospital"]

ATTACK_TYPES = ["DDoS", "DoS", "Mirai", "Spoofing", "Recon", "BruteForce", "Web"]
ZONE_PREFIXES = {
    "Downtown": "DWN",
    "Airport": "AIR",
    "Harbor": "HAR",
    "Industrial": "IND",
    "Residential": "RES",
    "University": "UNI",
    "Hospital": "HOS"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
rf_model = None
label_encoder = None
engine_ready = False
X_val_np = None

# Load the Random Forest Model and Preprocessors
try:
    prep_path = os.path.join(BASE_DIR, "preprocessors.joblib")
    if os.path.exists(prep_path):
        preprocessors = joblib.load(prep_path)
        label_encoder = preprocessors.get('label_encoder')

    # Load Random Forest model
    model_path = os.path.join(BASE_DIR, "rf_model.joblib")
    if os.path.exists(model_path):
        rf_model = joblib.load(model_path)
    
    # Load Validation Dataset for realistic inference samples
    val_path = os.path.join(BASE_DIR, "val_dataset.pt")
    if os.path.exists(val_path):
        X_val_tensor, y_val_tensor = torch.load(val_path, map_location='cpu')
        X_val_np = X_val_tensor.numpy()
        print(f"[Engine] Ready with {len(X_val_np)} validation samples utilizing Random Forest!")
    
    if rf_model is not None and label_encoder is not None:
        engine_ready = True
except Exception as e:
    print(f"[Warning] ML model failed to load in event_engine: {e}. Falling back to mocks.")
    engine_ready = False

DEVICES_PER_ZONE = 15

def severity_from_confidence(confidence: float) -> str:
    if confidence >= 90:
        return "Critical"
    elif confidence >= 75:
        return "High"
    elif confidence >= 55:
        return "Medium"
    else:
        return "Low"

def generate_device_id(zone: str, idx: int) -> str:
    prefix = ZONE_PREFIXES.get(zone, zone[:3].upper())
    return f"{prefix}-{idx:03d}"

def predict_event(features: list) -> tuple[str, float, str]:
    if engine_ready:
        sample = np.array(features).reshape(1, -1)
        
        # Scikit-Learn Prediction
        probs = rf_model.predict_proba(sample)[0]
        pred_class = rf_model.predict(sample)[0]
        
        # Get highest probability score
        confidence_val = max(probs)
        confidence = round(confidence_val * 100, 1)
        attack_type = label_encoder.inverse_transform([pred_class])[0]
    else:
        attack_type = random.choice(ATTACK_TYPES)
        base = random.gauss(72, 18)
        confidence = round(max(20.0, min(99.9, base)), 1)
        
    severity = severity_from_confidence(confidence)
    return attack_type, confidence, severity

SERVERS = [
    {"server_id": "EDGE-SRV-EAST-01", "server_ip": "10.240.1.101", "location": "US-East (Virginia)", "zones": ["Downtown", "Airport"]},
    {"server_id": "EDGE-SRV-WEST-02", "server_ip": "10.240.2.102", "location": "US-West (Oregon)", "zones": ["Harbor", "Industrial"]},
    {"server_id": "EDGE-SRV-CENTRAL-03", "server_ip": "10.240.3.103", "location": "US-Central (Texas)", "zones": ["Residential", "University"]},
    {"server_id": "EDGE-SRV-SOUTH-04", "server_ip": "10.240.4.104", "location": "US-South (Florida)", "zones": ["Hospital", "Downtown"]},
    {"server_id": "EDGE-SRV-EU-05", "server_ip": "10.240.5.105", "location": "EU-Central (Frankfurt)", "zones": ["Airport", "Harbor"]}
]

def generate_event() -> dict:
    server = random.choice(SERVERS)
    zone = random.choice(server["zones"])
    device_idx = random.randint(1, DEVICES_PER_ZONE)
    device_id = generate_device_id(zone, device_idx)
    
    if engine_ready:
        # Pick a random sample from our preprocessed validation set
        idx = random.randint(0, len(X_val_np) - 1)
        features = X_val_np[idx].tolist()
    else:
        features = []
        
    attack_type, confidence, severity = predict_event(features)

    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "device_id": device_id,
        "zone": zone,
        "attack_type": attack_type,
        "confidence": confidence,
        "severity": severity,
        "verified": True,
        "server_id": server["server_id"],
        "server_ip": server["server_ip"]
    }
