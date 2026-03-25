import hashlib
import json
import time
from datetime import datetime


class BlockchainManager:
    def __init__(self, batch_size: int = 10):
        self.chain: list[dict] = []
        self.pending_events: list[dict] = []
        self.batch_size = batch_size
        self.block_counter = 0
        self._last_seal_time = time.time()

        # Genesis block
        genesis = self._create_block([], "0" * 64, force=True)
        self.chain.append(genesis)

    def add_event(self, event: dict):
        self.pending_events.append(event)

    def try_seal_block(self) -> dict | None:
        """Seal a new block every batch_size events OR every 10 seconds."""
        now = time.time()
        if len(self.pending_events) >= self.batch_size or (
            now - self._last_seal_time >= 10 and len(self.pending_events) > 0
        ):
            prev_hash = self.chain[-1]["hash"] if self.chain else "0" * 64
            block = self._create_block(self.pending_events, prev_hash)
            self.chain.append(block)
            self.pending_events = []
            self._last_seal_time = now
            # Keep only last 50 blocks in memory
            if len(self.chain) > 50:
                self.chain = self.chain[-50:]
            return block
        return None

    def _create_block(self, events: list[dict], prev_hash: str, force: bool = False) -> dict:
        self.block_counter += 1
        batch_num = self.block_counter
        timestamp = datetime.utcnow().isoformat() + "Z"
        event_count = len(events)

        # Occasionally inject a tampered block (5% chance) for realism
        import random
        tampered = (not force) and (random.random() < 0.05)

        payload = json.dumps({
            "batch_num": batch_num,
            "prev_hash": prev_hash,
            "timestamp": timestamp,
            "event_count": event_count,
        }, sort_keys=True)

        block_hash = hashlib.sha256(payload.encode()).hexdigest()

        if tampered:
            # Corrupt the hash slightly
            block_hash = block_hash[:8] + "TAMPERED" + block_hash[16:]
            status = "TAMPERED"
        else:
            status = "VERIFIED"

        return {
            "batch_num": batch_num,
            "hash": block_hash,
            "prev_hash": prev_hash,
            "timestamp": timestamp,
            "event_count": event_count,
            "status": status,
        }

    def get_last_blocks(self, n: int = 6) -> list[dict]:
        return self.chain[-n:]
