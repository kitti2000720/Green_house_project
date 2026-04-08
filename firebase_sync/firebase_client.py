"""
Firebase Realtime Database client.

Wraps the firebase-admin SDK so the rest of the sync service
does not depend on it directly. When credentials are absent or
the SDK is not installed, all write methods silently become no-ops
(demo mode).
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import firebase_admin
    from firebase_admin import credentials, db as firebase_db
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False


class FirebaseClient:
    """
    Manages a single Firebase Realtime Database connection.

    Parameters
    ----------
    credentials_path : str or None
        Path to the service-account JSON file.
        Pass None to run in demo mode (no writes).
    database_url : str
        Firebase Realtime Database URL.
    """

    def __init__(self, credentials_path: Optional[str], database_url: str):
        self.ready = False
        self._app  = None

        if not _SDK_AVAILABLE:
            print("[Firebase] SDK not installed. Run: pip install firebase-admin")
            return

        if not credentials_path:
            print("[Firebase] No credentials path provided. Running in demo mode.")
            return

        try:
            cred       = credentials.Certificate(credentials_path)
            self._app  = firebase_admin.initialize_app(cred, {"databaseURL": database_url})
            self.ready = True
            print(f"[Firebase] Connected to {database_url}")
        except Exception as exc:
            print(f"[Firebase] Init error: {exc}")
            print("[Firebase] Running in demo mode.")

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def write_latest(
        self,
        greenhouse_id: int,
        topic: str,
        value: str,
        timestamp: str,
    ) -> None:
        """Update the 'latest' snapshot for a given topic."""
        if not self.ready:
            return
        try:
            firebase_db.reference(f"greenhouse/{greenhouse_id}/latest").update(
                {topic: {"value": value, "timestamp": timestamp}}
            )
        except Exception as exc:
            print(f"[Firebase] write_latest error: {exc}")

    def write_event(self, greenhouse_id: int, record: Dict[str, Any]) -> None:
        """Append a single timestamped event."""
        if not self.ready:
            return
        try:
            key = int(time.time() * 1000)
            firebase_db.reference(f"greenhouse/{greenhouse_id}/events/{key}").set(record)
        except Exception as exc:
            print(f"[Firebase] write_event error: {exc}")

    def write_batch(self, greenhouse_id: int, events: List[Dict[str, Any]]) -> None:
        """Flush a batch of buffered events."""
        if not self.ready or not events:
            return
        try:
            key = str(int(time.time()))
            firebase_db.reference(
                f"greenhouse/{greenhouse_id}/event_batches/{key}"
            ).set({
                "count":     len(events),
                "timestamp": datetime.now().isoformat(),
                "events":    events[-10:],
            })
            print(f"[Firebase] Batch flushed ({len(events)} events)")
        except Exception as exc:
            print(f"[Firebase] write_batch error: {exc}")

    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Delete the Firebase app and release resources."""
        if self._app:
            firebase_admin.delete_app(self._app)
            self._app  = None
            self.ready = False
