import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, Optional

REPORT_DIR = "validation_reports"

def _ensure_dir() -> None:
    os.makedirs(REPORT_DIR, exist_ok=True)

def compute_hash(payload: Dict[str, Any]) -> str:
    # Stable hashing: sort keys, no whitespace noise
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(canon.encode("utf-8")).hexdigest()

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def save_run(run_id: str, payload: Dict[str, Any]) -> str:
    _ensure_dir()
    path = os.path.join(REPORT_DIR, f"{run_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path

def load_run(run_id: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(REPORT_DIR, f"{run_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
