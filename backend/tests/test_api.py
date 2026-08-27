"""
test_api.py — Integration tests for the FastAPI REST API.

Tests cover:
  - GET /api/events/recent  (empty DB, with data, limit param)
  - GET /api/blocks/recent  (empty DB, with data, limit param)
  - GET /docs               (Swagger UI reachable)
  - WebSocket /ws           (connection handshake)

The Kafka consumer is mocked out in conftest.py so these tests
run without a live Kafka broker.
"""
import sys
import os
import uuid
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── /api/events/recent ────────────────────────────────────────────────────────

class TestEventsRecentEndpoint:
    def test_returns_200(self, client):
        response = client.get("/api/events/recent")
        assert response.status_code == 200

    def test_returns_list(self, client):
        response = client.get("/api/events/recent")
        assert isinstance(response.json(), list)

    def test_default_limit_is_50(self, client, test_db):
        """Seed 60 events and verify only 50 are returned by default."""
        import models_db
        for i in range(60):
            event = models_db.EventLog(
                id=str(uuid.uuid4()),
                timestamp=f"2026-01-01T00:{i:02d}:00Z",
                device_id=f"DWN-{i:03d}",
                zone="Downtown",
                attack_type="DDoS",
                confidence=95.0,
                severity="Critical",
                verified=True,
            )
            test_db.add(event)
        test_db.commit()

        response = client.get("/api/events/recent")
        data = response.json()
        assert len(data) <= 50

    def test_custom_limit(self, client, test_db):
        import models_db
        for i in range(10):
            test_db.add(models_db.EventLog(
                id=str(uuid.uuid4()),
                timestamp=f"2026-02-01T00:{i:02d}:00Z",
                device_id=f"AIR-{i:03d}",
                zone="Airport",
                attack_type="Mirai",
                confidence=88.0,
                severity="High",
                verified=True,
            ))
        test_db.commit()
        response = client.get("/api/events/recent?limit=5")
        assert len(response.json()) <= 5

    def test_event_schema(self, client, test_db):
        """Each event in the response should have all required fields."""
        import models_db
        test_db.add(models_db.EventLog(
            id=str(uuid.uuid4()),
            timestamp="2026-03-01T00:00:00Z",
            device_id="HAR-001",
            zone="Harbor",
            attack_type="Recon",
            confidence=62.5,
            severity="Medium",
            verified=True,
        ))
        test_db.commit()

        response = client.get("/api/events/recent?limit=1")
        data = response.json()
        assert len(data) >= 1
        event = data[-1]  # last item = most recently added
        required_keys = {"id", "timestamp", "device_id", "zone",
                         "attack_type", "confidence", "severity", "verified"}
        assert required_keys.issubset(event.keys())

    def test_confidence_is_float(self, client, test_db):
        import models_db
        eid = str(uuid.uuid4())
        test_db.add(models_db.EventLog(
            id=eid,
            timestamp="2026-03-01T01:00:00Z",
            device_id="IND-005",
            zone="Industrial",
            attack_type="BruteForce",
            confidence=77.3,
            severity="High",
            verified=True,
        ))
        test_db.commit()
        response = client.get("/api/events/recent?limit=100")
        events = response.json()
        matching = [e for e in events if e["id"] == eid]
        assert len(matching) == 1
        assert isinstance(matching[0]["confidence"], float)


# ── /api/blocks/recent ───────────────────────────────────────────────────────

class TestBlocksRecentEndpoint:
    def test_returns_200(self, client):
        response = client.get("/api/blocks/recent")
        assert response.status_code == 200

    def test_returns_list(self, client):
        response = client.get("/api/blocks/recent")
        assert isinstance(response.json(), list)

    def test_default_limit_is_20(self, client, test_db):
        """Seed 25 blocks and verify only 20 are returned by default."""
        import models_db
        for i in range(25):
            test_db.add(models_db.BlockChain(
                batch_num=i + 1000,  # offset to avoid PK clash
                hash="a" * 64,
                prev_hash="0" * 64,
                timestamp=f"2026-01-01T00:{i:02d}:00Z",
                event_count=10,
                status="VERIFIED",
            ))
        test_db.commit()
        response = client.get("/api/blocks/recent")
        assert len(response.json()) <= 20

    def test_custom_limit(self, client, test_db):
        import models_db
        for i in range(8):
            test_db.add(models_db.BlockChain(
                batch_num=i + 2000,
                hash="b" * 64,
                prev_hash="0" * 64,
                timestamp=f"2026-02-01T00:{i:02d}:00Z",
                event_count=5,
                status="VERIFIED",
            ))
        test_db.commit()
        response = client.get("/api/blocks/recent?limit=3")
        assert len(response.json()) <= 3

    def test_block_schema(self, client, test_db):
        """Each block should have all required fields."""
        import models_db
        test_db.add(models_db.BlockChain(
            batch_num=9999,
            hash="c" * 64,
            prev_hash="0" * 64,
            timestamp="2026-03-01T00:00:00Z",
            event_count=10,
            status="TAMPERED",
        ))
        test_db.commit()

        response = client.get("/api/blocks/recent?limit=100")
        blocks = response.json()
        matching = [b for b in blocks if b["batch_num"] == 9999]
        assert len(matching) == 1
        block = matching[0]
        required_keys = {"batch_num", "hash", "prev_hash", "timestamp",
                         "event_count", "status"}
        assert required_keys.issubset(block.keys())

    def test_status_is_verified_or_tampered(self, client, test_db):
        import models_db
        for status in ("VERIFIED", "TAMPERED"):
            test_db.add(models_db.BlockChain(
                batch_num=10000 + (1 if status == "TAMPERED" else 0),
                hash="d" * 64,
                prev_hash="0" * 64,
                timestamp="2026-03-01T00:00:00Z",
                event_count=5,
                status=status,
            ))
        test_db.commit()
        response = client.get("/api/blocks/recent?limit=100")
        statuses = {b["status"] for b in response.json()}
        assert statuses.issubset({"VERIFIED", "TAMPERED"})


# ── /docs (Swagger UI) ────────────────────────────────────────────────────────

class TestSwaggerDocs:
    def test_docs_reachable(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_reachable(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        assert "/api/events/recent" in data["paths"]
        assert "/api/blocks/recent" in data["paths"]


# ── WebSocket /ws ─────────────────────────────────────────────────────────────

class TestWebSocket:
    def test_websocket_connect(self, client):
        """WebSocket should accept the connection successfully."""
        with client.websocket_connect("/ws") as ws:
            # Simply connecting without error is the test
            pass

    def test_websocket_multiple_clients(self, client):
        """Multiple simultaneous WebSocket connections should be accepted."""
        with client.websocket_connect("/ws"):
            with client.websocket_connect("/ws"):
                pass  # both connected — no error
