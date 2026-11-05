"""Security camera event generator — produces realistic records at a controlled rate."""

import random
import uuid
from datetime import datetime, timezone

CAMERAS = [f"CAM-{i:03d}" for i in range(1, 51)]  # CAM-001 to CAM-050

LOCATIONS = [
    "Building A - Main Entrance",
    "Building B - East Wing",
    "Building C - Server Room",
    "Building D - Parking Structure",
    "Perimeter - North Fence",
]

ZONES = ["LOBBY", "HALLWAY", "PARKING", "STAIRWELL", "ROOFTOP", "ENTRANCE", "SERVER_ROOM", "PERIMETER"]

EVENT_TYPES = [
    "motion_detected",
    "person_detected",
    "vehicle_detected",
    "intrusion_alert",
    "door_access",
    "loitering",
]

# Weighted so most events are benign
EVENT_WEIGHTS = [30, 35, 15, 5, 10, 5]

RESOLUTIONS = ["1080p", "4K", "720p"]
TAGS_POOL = [
    ["daytime", "clear"], ["nighttime", "low-light"], ["high-traffic"],
    ["authorized"], ["flagged"], ["routine"], ["weather-affected"],
]


def make_record() -> dict:
    event_type = random.choices(EVENT_TYPES, weights=EVENT_WEIGHTS, k=1)[0]
    camera_id = random.choice(CAMERAS)
    location = random.choice(LOCATIONS)
    zone = random.choice(ZONES)

    confidence = round(random.uniform(0.55, 0.99), 3)
    object_count = random.randint(1, 6) if event_type in ("person_detected", "vehicle_detected", "loitering") else 1
    duration_ms = random.randint(80, 4500)

    metadata = {
        "resolution": random.choice(RESOLUTIONS),
        "fps": random.choice([15, 24, 30]),
        "tags": random.choice(TAGS_POOL),
        "sensor_temp_c": round(random.uniform(18.0, 45.0), 1),
        "storage_node": f"NVR-{random.randint(1, 8):02d}",
    }

    return {
        "event_id": str(uuid.uuid4()),
        "camera_id": camera_id,
        "location": location,
        "zone": zone,
        "event_type": event_type,
        "confidence": confidence,
        "object_count": object_count,
        "duration_ms": duration_ms,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
    }


def make_batch(size: int = 5) -> list[dict]:
    return [make_record() for _ in range(size)]
