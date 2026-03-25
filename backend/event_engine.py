import random
import uuid
from datetime import datetime

ZONES = ["Downtown", "Airport", "Harbor", "Industrial", "Residential", "University", "Hospital"]
ATTACK_TYPES = ["DDoS", "DoS", "Mirai", "Spoofing", "Recon", "BruteForce", "Web"]

DEVICES_PER_ZONE = 15  # 7 zones × 15 = 105 devices


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
    attack_type = random.choice(ATTACK_TYPES)

    # Weighted confidence distribution to feel realistic
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
