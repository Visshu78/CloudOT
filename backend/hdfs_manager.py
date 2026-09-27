import json
import time
import os
import glob
import requests
from datetime import datetime
from typing import List, Dict, Any

# WebHDFS / HDFS Configuration
HDFS_NAMENODE_URL = os.getenv("HDFS_NAMENODE_URL", "http://localhost:9870")
HDFS_USER = os.getenv("HDFS_USER", "root")
HDFS_BASE_DIR = "/cityshield"
HDFS_EVENTS_DIR = f"{HDFS_BASE_DIR}/events"

# Local DataNode Simulator Storage Directory
LOCAL_DATANODE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hdfs_datanode_storage")

# HDFS Replication Factor explicitly set to 1 (No additional replicas)
REPLICATION_FACTOR = 1

class HDFSManager:
    def __init__(self, namenode_url: str = HDFS_NAMENODE_URL, user: str = HDFS_USER):
        self.namenode_url = namenode_url.rstrip("/")
        self.user = user
        self.replication = REPLICATION_FACTOR
        self.connected = False
        self.event_buffer: List[Dict[str, Any]] = []
        self.max_buffer_size = 20  # Flush every 20 events
        self.last_flush_time = time.monotonic()
        self.simulated_block_count = 0
        
        # Ensure local DataNode simulation directories exist
        self._init_local_datanode_storage()
        
        # Test connection to real WebHDFS NameNode
        self.check_connection()

    def _init_local_datanode_storage(self):
        """Creates initial DataNode Block Storage hierarchy on local disk (Replication=1)."""
        try:
            for zone in ["Downtown", "Airport", "Harbor", "Industrial", "Residential", "University", "Hospital"]:
                path = os.path.join(LOCAL_DATANODE_DIR, "cityshield", "events", f"zone={zone}")
                os.makedirs(path, exist_ok=True)
            os.makedirs(os.path.join(LOCAL_DATANODE_DIR, "cityshield", "raw_data"), exist_ok=True)
            print(f"[DataNode Simulator] Local HDFS Block Storage ready at '{LOCAL_DATANODE_DIR}' (dfs.replication=1).")
        except Exception as e:
            print(f"[DataNode Simulator] Error initializing local storage: {e}")

    def check_connection(self) -> bool:
        """Checks WebHDFS NameNode availability."""
        try:
            url = f"{self.namenode_url}/webhdfs/v1/?op=GETFILESTATUS&user.name={self.user}"
            response = requests.get(url, timeout=0.5)
            if response.status_code == 200:
                self.connected = True
                return True
        except Exception:
            self.connected = False
        return False

    def init_hdfs_directories(self) -> bool:
        """Creates initial HDFS directory structure on WebHDFS if connected."""
        self._init_local_datanode_storage()
        if not self.check_connection():
            print("[HDFS] NameNode WebHDFS offline. Using DataNode Storage Simulator (dfs.replication=1).")
            return False
            
        try:
            for path in [HDFS_BASE_DIR, HDFS_EVENTS_DIR, f"{HDFS_BASE_DIR}/raw_data"]:
                url = f"{self.namenode_url}/webhdfs/v1{path}?op=MKDIRS&user.name={self.user}"
                requests.put(url, timeout=3.0)
            print(f"[HDFS] WebHDFS directories initialized at {HDFS_BASE_DIR} (Replication Factor = {self.replication}).")
            return True
        except Exception as e:
            print(f"[HDFS] Error initializing WebHDFS: {e}")
            return False

    def write_event(self, event: Dict[str, Any]):
        """Buffers real-time event and periodically flushes into DataNode blocks."""
        self.event_buffer.append(event)
        now = time.monotonic()
        
        # Flush if buffer reaches max size or 5 seconds elapsed
        if len(self.event_buffer) >= self.max_buffer_size or (now - self.last_flush_time > 5.0):
            self.flush_buffer()

    def flush_buffer(self):
        """Flushes buffered events into DataNode block files (Replication Factor = 1)."""
        if not self.event_buffer:
            return
            
        events_to_flush = list(self.event_buffer)
        self.event_buffer.clear()
        self.last_flush_time = time.monotonic()
        today = datetime.utcnow().strftime("%Y-%m-%d")

        # 1. ALWAYS write block to DataNode Storage Simulator
        try:
            block_timestamp = int(time.time() * 1000)
            block_id = f"blk_{block_timestamp}_1001"
            
            # Write to zone-partitioned local DataNode storage
            for event in events_to_flush:
                zone = event.get("zone", "Downtown")
                target_dir = os.path.join(LOCAL_DATANODE_DIR, "cityshield", "events", f"zone={zone}", f"date={today}")
                os.makedirs(target_dir, exist_ok=True)
                
                block_file = os.path.join(target_dir, f"{block_id}.json")
                with open(block_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event) + "\n")
            
            self.simulated_block_count += 1
            # print(f"[DataNode Simulator] Stored DataNode Block {block_id} ({len(events_to_flush)} events) - dfs.replication=1")
        except Exception as e:
            print(f"[DataNode Simulator] Error writing local DataNode block: {e}")

        # 2. Also write to real WebHDFS if container is connected
        if self.connected or self.check_connection():
            try:
                date_dir = f"{HDFS_EVENTS_DIR}/date={today}"
                mkdir_url = f"{self.namenode_url}/webhdfs/v1{date_dir}?op=MKDIRS&user.name={self.user}"
                requests.put(mkdir_url, timeout=2.0)
                
                file_name = f"events_{int(time.time() * 1000)}.json"
                hdfs_file_path = f"{date_dir}/{file_name}"
                
                create_url = (
                    f"{self.namenode_url}/webhdfs/v1{hdfs_file_path}"
                    f"?op=CREATE&user.name={self.user}&replication={self.replication}&overwrite=true"
                )
                res = requests.put(create_url, allow_redirects=False, timeout=3.0)
                
                if res.status_code == 307: # Redirect to DataNode
                    datanode_url = res.headers.get("Location")
                    if datanode_url:
                        content = "\n".join(json.dumps(e) for e in events_to_flush) + "\n"
                        requests.put(datanode_url, data=content, headers={"Content-Type": "application/octet-stream"}, timeout=5.0)
            except Exception:
                pass

    def get_recent_datanode_blocks(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Returns metadata for the most recently written DataNode storage blocks."""
        blocks = []
        try:
            block_files = glob.glob(os.path.join(LOCAL_DATANODE_DIR, "**", "*.json"), recursive=True)
            # Sort by modification time descending
            block_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
            
            for file_path in block_files[:limit]:
                stat = os.stat(file_path)
                filename = os.path.basename(file_path)
                block_id = filename.replace(".json", "")
                
                # Extract zone from path if present (e.g. zone=Downtown)
                zone = "Downtown"
                parts = file_path.split(os.sep)
                for part in parts:
                    if part.startswith("zone="):
                        zone = part.split("=")[1]
                        break
                
                # Count events in the JSONL block file
                event_count = 0
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            event_count += 1
                            
                blocks.append({
                    "block_id": block_id,
                    "filename": filename,
                    "zone": zone,
                    "size_bytes": stat.st_size,
                    "event_count": event_count,
                    "replication": self.replication,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%H:%M:%S"),
                    "status": "STORED (DataNode Block)"
                })
        except Exception as e:
            print(f"[DataNode Simulator] Error reading recent blocks: {e}")
            
        return blocks

    def simulate_datanode_block_generation(self, block_count: int = 5):
        """Forces immediate simulation of data blocks in DataNode storage."""
        zones = ["Downtown", "Airport", "Harbor", "Industrial", "Residential", "University", "Hospital"]
        attack_types = ["DDoS", "Mirai", "Spoofing", "DoS", "BruteForce"]
        today = datetime.utcnow().strftime("%Y-%m-%d")
        
        for i in range(block_count):
            zone = zones[i % len(zones)]
            block_ts = int(time.time() * 1000) + i * 10
            block_id = f"blk_{block_ts}_1001"
            
            target_dir = os.path.join(LOCAL_DATANODE_DIR, "cityshield", "events", f"zone={zone}", f"date={today}")
            os.makedirs(target_dir, exist_ok=True)
            
            simulated_events = [
                {
                    "id": f"sim-{block_ts}-{j}",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "device_id": f"{zone[:3].upper()}-{100 + j}",
                    "zone": zone,
                    "attack_type": attack_types[j % len(attack_types)],
                    "confidence": round(80.0 + (j * 3.5) % 19, 1),
                    "severity": "High" if j % 2 == 0 else "Critical",
                    "verified": True,
                    "server_id": "EDGE-SRV-EAST-01",
                    "server_ip": "10.240.1.101"
                }
                for j in range(4)
            ]
            
            block_file = os.path.join(target_dir, f"{block_id}.json")
            with open(block_file, "w", encoding="utf-8") as f:
                for ev in simulated_events:
                    f.write(json.dumps(ev) + "\n")
                    
            self.simulated_block_count += 1

    def get_status(self) -> Dict[str, Any]:
        """Returns HDFS connection status, DataNode block storage metrics, and replication settings."""
        is_online = self.check_connection()
        
        # Calculate DataNode Storage Simulator metrics
        total_blocks = 0
        total_bytes = 0
        try:
            block_files = glob.glob(os.path.join(LOCAL_DATANODE_DIR, "**", "*.json"), recursive=True)
            total_blocks = len(block_files)
            total_bytes = sum(os.path.getsize(f) for f in block_files)
        except Exception:
            pass

        return {
            "status": "ONLINE (WebHDFS Docker Container)" if is_online else "ACTIVE (DataNode Storage Simulator)",
            "namenode_url": self.namenode_url,
            "replication_factor": self.replication,
            "replication_policy": "Single-Node (No extra replicas configured)",
            "base_directory": HDFS_BASE_DIR,
            "events_directory": HDFS_EVENTS_DIR,
            "datanode_simulator_directory": LOCAL_DATANODE_DIR,
            "datanode_total_blocks_stored": total_blocks,
            "datanode_total_bytes_stored": total_bytes,
            "buffered_events_in_memory": len(self.event_buffer)
        }

hdfs_manager = HDFSManager()

