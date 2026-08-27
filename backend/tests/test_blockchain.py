"""
test_blockchain.py — Unit tests for the BlockchainManager.

Tests cover:
  - Genesis block creation on init
  - Adding events to the pending pool
  - Block sealing by event count (every 10 events)
  - Block sealing by time (every 10 seconds)
  - SHA-256 hash chaining (prev_hash linkage)
  - Block memory limit (max 50 blocks kept)
  - Block structure / fields
"""
import time
import pytest
from blockchain import BlockchainManager


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_event(i: int = 0) -> dict:
    return {
        "id": f"evt-{i}",
        "timestamp": "2026-01-01T00:00:00Z",
        "device_id": f"DWN-{i:03d}",
        "zone": "Downtown",
        "attack_type": "DDoS",
        "confidence": 95.0,
        "severity": "Critical",
        "verified": True,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestBlockchainInit:
    def test_genesis_block_created(self):
        """BlockchainManager should create a genesis block on init."""
        bc = BlockchainManager()
        assert len(bc.chain) == 1

    def test_genesis_block_prev_hash_is_zeros(self):
        bc = BlockchainManager()
        genesis = bc.chain[0]
        assert genesis["prev_hash"] == "0" * 64

    def test_genesis_block_has_required_fields(self):
        bc = BlockchainManager()
        genesis = bc.chain[0]
        for field in ("batch_num", "hash", "prev_hash", "timestamp", "event_count", "status"):
            assert field in genesis, f"Missing field: {field}"

    def test_pending_events_empty_on_init(self):
        bc = BlockchainManager()
        assert bc.pending_events == []


class TestAddEvent:
    def test_add_event_increments_pending(self):
        bc = BlockchainManager()
        bc.add_event(make_event(0))
        assert len(bc.pending_events) == 1

    def test_add_multiple_events(self):
        bc = BlockchainManager()
        for i in range(5):
            bc.add_event(make_event(i))
        assert len(bc.pending_events) == 5


class TestSealBlock:
    def test_no_seal_below_batch_size(self):
        bc = BlockchainManager(batch_size=10)
        for i in range(9):
            bc.add_event(make_event(i))
        result = bc.try_seal_block()
        assert result is None

    def test_seal_at_batch_size(self):
        bc = BlockchainManager(batch_size=10)
        for i in range(10):
            bc.add_event(make_event(i))
        block = bc.try_seal_block()
        assert block is not None

    def test_seal_clears_pending(self):
        bc = BlockchainManager(batch_size=5)
        for i in range(5):
            bc.add_event(make_event(i))
        bc.try_seal_block()
        assert len(bc.pending_events) == 0

    def test_sealed_block_appended_to_chain(self):
        bc = BlockchainManager(batch_size=5)
        for i in range(5):
            bc.add_event(make_event(i))
        bc.try_seal_block()
        # chain = genesis + 1 sealed block
        assert len(bc.chain) == 2

    def test_seal_by_time(self):
        """Block should seal after 10 seconds even with < batch_size events."""
        bc = BlockchainManager(batch_size=100)
        bc.add_event(make_event(0))
        # Fake the last seal time to 11 seconds ago
        bc._last_seal_time = time.time() - 11
        block = bc.try_seal_block()
        assert block is not None

    def test_no_seal_on_empty_pending_by_time(self):
        bc = BlockchainManager(batch_size=100)
        bc._last_seal_time = time.time() - 11
        # No events → should not seal
        result = bc.try_seal_block()
        assert result is None

    def test_block_event_count_matches(self):
        bc = BlockchainManager(batch_size=7)
        for i in range(7):
            bc.add_event(make_event(i))
        block = bc.try_seal_block()
        assert block["event_count"] == 7

    def test_block_has_valid_status(self):
        bc = BlockchainManager(batch_size=3)
        for i in range(3):
            bc.add_event(make_event(i))
        block = bc.try_seal_block()
        assert block["status"] in ("VERIFIED", "TAMPERED")


class TestHashChaining:
    def test_second_block_prev_hash_matches_first(self):
        bc = BlockchainManager(batch_size=3)
        for i in range(3):
            bc.add_event(make_event(i))
        block1 = bc.try_seal_block()

        for i in range(3):
            bc.add_event(make_event(i + 10))
        block2 = bc.try_seal_block()

        assert block2["prev_hash"] == block1["hash"]

    def test_hash_is_64_chars_or_tampered(self):
        """Hash should be 64 hex chars (SHA-256) or contain TAMPERED."""
        bc = BlockchainManager(batch_size=3)
        for i in range(3):
            bc.add_event(make_event(i))
        block = bc.try_seal_block()
        h = block["hash"]
        assert len(h) == 64, f"Unexpected hash length: {len(h)}"

    def test_chain_grows_sequentially(self):
        bc = BlockchainManager(batch_size=2)
        for round_ in range(3):
            for i in range(2):
                bc.add_event(make_event(i + round_ * 10))
            bc.try_seal_block()
        # genesis + 3 sealed = 4
        assert len(bc.chain) == 4
        for idx, block in enumerate(bc.chain):
            assert block["batch_num"] == idx + 1


class TestChainMemoryLimit:
    def test_chain_capped_at_50(self):
        """Chain should not grow beyond 50 blocks."""
        bc = BlockchainManager(batch_size=1)
        for i in range(60):
            bc.add_event(make_event(i))
            bc.try_seal_block()
        assert len(bc.chain) <= 50

    def test_get_last_blocks_returns_n(self):
        bc = BlockchainManager(batch_size=1)
        for i in range(10):
            bc.add_event(make_event(i))
            bc.try_seal_block()
        last_6 = bc.get_last_blocks(6)
        assert len(last_6) == 6
