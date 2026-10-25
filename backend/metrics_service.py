import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List

import threading

METRICS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "metrics.json")
_METRICS_LOCK = threading.Lock()

def _load_metrics() -> Dict[str, Any]:
    os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "total_images_processed": 0,
        "total_events_extracted": 0,
        "total_events_synced": 0,
        "total_conflicts_flagged": 0,
        "total_unique_visitors": 0,
        "unique_sessions": [],
        "recent_activities": [],
        "daily_stats": {},
        "created_at": datetime.now().isoformat()
    }

def _save_metrics(metrics: Dict[str, Any]):
    os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)
    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    os.chmod(METRICS_FILE, 0o600)

def record_visitor(session_id: str):
    with _METRICS_LOCK:
        metrics = _load_metrics()
        if session_id and session_id not in metrics["unique_sessions"]:
            metrics["unique_sessions"].append(session_id)
            metrics["total_unique_visitors"] = len(metrics["unique_sessions"])
            _save_metrics(metrics)

def record_image_scan(event_count: int, avg_confidence: float, conflicts: int = 0):
    with _METRICS_LOCK:
        metrics = _load_metrics()
        metrics["total_images_processed"] += 1
        metrics["total_events_extracted"] += event_count
        metrics["total_conflicts_flagged"] += conflicts
        
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in metrics["daily_stats"]:
            metrics["daily_stats"][today] = {"scans": 0, "synced": 0}
        metrics["daily_stats"][today]["scans"] += 1

        activity = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "IMAGE_SCAN",
            "events_found": event_count,
            "confidence": round(avg_confidence, 1),
            "conflicts": conflicts
        }
        metrics["recent_activities"].insert(0, activity)
        metrics["recent_activities"] = metrics["recent_activities"][:30]
        _save_metrics(metrics)

def record_calendar_sync(event_count: int, sync_type: str = "google"):
    with _METRICS_LOCK:
        metrics = _load_metrics()
        metrics["total_events_synced"] += event_count
        
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in metrics["daily_stats"]:
            metrics["daily_stats"][today] = {"scans": 0, "synced": 0}
        metrics["daily_stats"][today]["synced"] += event_count

        activity = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": f"CALENDAR_SYNC_{sync_type.upper()}",
            "events_synced": event_count
        }
        metrics["recent_activities"].insert(0, activity)
        metrics["recent_activities"] = metrics["recent_activities"][:30]
        _save_metrics(metrics)

def get_metrics_summary() -> Dict[str, Any]:
    metrics = _load_metrics()
    return {
        "total_images_processed": metrics.get("total_images_processed", 0),
        "total_events_extracted": metrics.get("total_events_extracted", 0),
        "total_events_synced": metrics.get("total_events_synced", 0),
        "total_conflicts_flagged": metrics.get("total_conflicts_flagged", 0),
        "total_unique_visitors": metrics.get("total_unique_visitors", 0),
        "recent_activities": metrics.get("recent_activities", []),
        "daily_stats": metrics.get("daily_stats", {})
    }
