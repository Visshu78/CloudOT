import random
import uuid
from datetime import datetime
import joblib
import torch
import os

ZONES = ["Downtown", "Airport", "Harbor", "Industrial", "Residential", "University", "Hospital"]

# Load the Random Forest Model and Preprocessors
try:
    preprocessors = joblib.load("preprocessors.joblib")
    label_encoder = preprocessors['label_encoder']

    # Load Random Forest model
    rf_model = joblib.load("rf_model.joblib")
    
    # Load Validation Dataset for realistic inference samples
    X_val_tensor, y_val_tensor = torch.load("val_dataset.pt", map_location='cpu')
    X_val_np = X_val_tensor.numpy()
    
    print(f"[Engine] Ready with {len(X_val_np)} validation samples utilizing Random Forest!")
    
    engine_ready = True
except Exception as e:
    print(f"[Warning] ML model failed to load in event_engine: {e}. Falling back to mocks.")
    engine_ready = False
    
    # Mock fallback
    ATTACK_TYPES = ["DDoS", "DoS", "Mirai", "Spoofing", "Recon", "BruteForce", "Web"]

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
    prefix = zone[:3].upper()
    return f"{prefix}-{idx:03d}"

def generate_event() -> dict:
    zone = random.choice(ZONES)
    device_idx = random.randint(1, DEVICES_PER_ZONE)
    device_id = generate_device_id(zone, device_idx)
    
    if engine_ready:
        # Pick a random sample from our preprocessed validation set
        idx = random.randint(0, len(X_val_np) - 1)
        sample = X_val_np[idx].reshape(1, -1)
        
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

    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "device_id": device_id,
        "zone": zone,
        "attack_type": attack_type,
        "confidence": confidence,
        "severity": severity,
        "verified": True,
    }
