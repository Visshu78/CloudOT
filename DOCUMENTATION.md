# CityShield — Complete Project Documentation

> A real-time IoT Threat Intelligence Dashboard for Smart Cities, built for hackathon demonstration.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Data Flow — End to End](#3-data-flow--end-to-end)
4. [Component Deep Dives](#4-component-deep-dives)
   - 4.1 [Kafka Infrastructure](#41-kafka-infrastructure-docker-composeyml)
   - 4.2 [Kafka Producer](#42-kafka-producer-kafka_producerpy)
   - 4.3 [ML Inference Engine](#43-ml-inference-engine-event_enginepy)
   - 4.4 [FastAPI Backend](#44-fastapi-backend-mainpy)
   - 4.5 [Blockchain Manager](#45-blockchain-manager-blockchainpy)
   - 4.6 [Database Layer](#46-database-layer-databasepy--models_dbpy)
   - 4.7 [React Frontend](#47-react-frontend-appjsx)
   - 4.8 [Frontend Panels](#48-frontend-panels)
5. [Machine Learning Model](#5-machine-learning-model)
6. [API Reference](#6-api-reference)
7. [Database Schema](#7-database-schema)
8. [Key Design Decisions](#8-key-design-decisions)
9. [How to Run the Project](#9-how-to-run-the-project)
10. [File Map](#10-file-map)

---

## 1. Project Overview

**CityShield** is a real-time cybersecurity dashboard that simulates monitoring of IoT devices across 7 zones of a smart city (Downtown, Airport, Harbor, Industrial, Residential, University, Hospital).

The system:
- Simulates thousands of IoT network packets per second using a real-world dataset
- Classifies each packet as a specific attack type using a trained **Random Forest ML model**
- Secures the event log with a **simulated SHA-256 blockchain**
- Displays everything live on a **React cyberpunk dashboard** via WebSockets
- Persists all data to **SQLite** so history survives restarts

**The core goal**: demonstrate how a modern smart-city security operations center (SOC) would look and function.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  DATA SOURCE                                                          │
│  kafka_producer.py                                                    │
│  Reads val_dataset.pt (30,000 preprocessed CICIoT2023 network        │
│  packet feature vectors) and sends ~100 events/second to Kafka       │
└────────────────────────────┬─────────────────────────────────────────┘
                             │  JSON messages → topic: "iot-traffic"
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│  MESSAGE BROKER                                                       │
│  Apache Kafka 3.7.0 (Docker, KRaft mode, no Zookeeper)               │
│  Listens on localhost:9092                                            │
│  Buffers the event stream so the backend never gets overwhelmed      │
└────────────────────────────┬─────────────────────────────────────────┘
                             │  aiokafka async consumer
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│  FASTAPI BACKEND  (main.py)                                          │
│                                                                      │
│  1. Kafka Consumer Loop (background asyncio task)                    │
│     • Reads raw feature vectors from Kafka                           │
│     • Calls predict_event() → attack_type, confidence, severity      │
│     • Saves event to SQLite via SQLAlchemy                           │
│     • Feeds event to BlockchainManager                               │
│     • Throttles to 5 events/sec for WebSocket broadcast              │
│                                                                      │
│  2. WebSocket Server  ws://localhost:8000/ws                         │
│     • Accepts connections from the React frontend                    │
│     • Broadcasts JSON payloads to ALL connected clients              │
│                                                                      │
│  3. REST API                                                         │
│     • GET /api/events/recent  — seed history on frontend refresh     │
│     • GET /api/blocks/recent  — seed blockchain blocks on refresh    │
└──────┬────────────────────────────┬────────────────────────────────┘
       │  SQLAlchemy ORM            │  WebSocket JSON broadcast
       ▼                            ▼
┌─────────────┐          ┌──────────────────────────────────────────┐
│  SQLite DB  │          │  REACT FRONTEND  (Vite, port 5173)       │
│  events     │          │                                          │
│  blocks     │          │  • Connects to ws://localhost:8000/ws    │
└─────────────┘          │  • On mount: fetches REST API for        │
                         │    historical events + blocks            │
                         │  • Falls back to mock data generator     │
                         │    if backend is offline                 │
                         │                                          │
                         │  Dashboard Panels:                       │
                         │  ┌──────────┐  ┌────────────────────┐   │
                         │  │  Header  │  │   Attack Feed      │   │
                         │  └──────────┘  └────────────────────┘   │
                         │  ┌────────────┐ ┌──────────────────────┐│
                         │  │ Threat Map │ │ ML Confidence Panel  ││
                         │  └────────────┘ └──────────────────────┘│
                         │  ┌──────────────────────────────────────┐│
                         │  │        Blockchain Panel              ││
                         │  └──────────────────────────────────────┘│
                         └──────────────────────────────────────────┘
```

---

## 3. Data Flow — End to End

Here is what happens, step by step, for every IoT threat event:

```
Step 1:  kafka_producer.py picks a random row from val_dataset.pt
         (these are real, preprocessed CICIoT2023 network feature vectors)

Step 2:  Producer wraps the features in a JSON payload:
         {
           "id": "uuid-...",
           "timestamp": "2026-03-30T00:00:00Z",
           "device_id": "ARP-007",
           "zone": "Airport",
           "features": [0.12, 3.5, 0.0, ...]  ← 46 numeric features
         }
         → Published to Kafka topic "iot-traffic"

Step 3:  FastAPI's consume_kafka() background task reads the message.

Step 4:  predict_event(features) is called in a thread pool
         (asyncio.to_thread — prevents blocking the async event loop)
         → rf_model.predict_proba(sample) returns probability array
         → Highest probability class → attack_type (e.g., "DDoS")
         → Max probability → confidence score (e.g., 97.3%)
         → severity_from_confidence() maps score to Critical/High/Medium/Low

Step 5:  Event dict is assembled:
         {
           "id": "...", "timestamp": "...", "device_id": "ARP-007",
           "zone": "Airport", "attack_type": "DDoS",
           "confidence": 97.3, "severity": "Critical", "verified": true
         }

Step 6:  Event is written to SQLite (events table).

Step 7:  Event is added to BlockchainManager's pending pool.
         Every 10 events OR 10 seconds, a new block is sealed:
         - All pending events are serialized to JSON
         - SHA-256 hash of (events + prev_block_hash) is computed
         - 5% chance of artificial tampering for demo purposes
         - Block is saved to SQLite (blocks table)

Step 8:  Throttle check: only forward to WebSocket if 200ms have
         elapsed since the last broadcast (limits to 5 events/sec).

Step 9:  JSON payload is sent to all connected React clients:
         { "type": "event", "data": {...}, "block": {...} }

Step 10: React frontend receives the message:
         - Event is prepended to the events array (max 200 kept)
         - Block (if present) is appended to blocks array (max 20 kept)
         - All 5 dashboard panels re-render reactively
```

---

## 4. Component Deep Dives

### 4.1 Kafka Infrastructure (`docker-compose.yml`)

```yaml
image: apache/kafka:3.7.0
```

- Uses **KRaft mode** (Kafka Raft metadata — no separate Zookeeper process needed)
- Single-node broker (`KAFKA_NODE_ID=1`, acting as both broker and controller)
- Topic `iot-traffic` is **auto-created** when the producer first publishes to it (`KAFKA_AUTO_CREATE_TOPICS_ENABLE=true`)
- `KAFKA_CLUSTER_ID` is a fixed string used to initialize the KRaft metadata log

**Why Kafka?** Direct HTTP from 100 producers/second to FastAPI would crash it. Kafka acts as a shock absorber — the producer dumps data in at any rate, and the consumer reads at its own pace without losing a single message.

---

### 4.2 Kafka Producer (`backend/kafka_producer.py`)

```python
producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)
```

- Loads `val_dataset.pt` — a PyTorch tensor file containing **30,000 pre-processed network traffic feature vectors** from the CICIoT2023 dataset.
- Each loop iteration: picks a **random row** from the dataset, randomly assigns a zone and device ID, and publishes the JSON to Kafka.
- Sleeps `0.01s` between messages → **~100 events/second**.
- Prints ~5% of events to the console (random sampling) to show progress without flooding the terminal.

**Device ID format**: `{ZONE_PREFIX}-{INDEX}` (e.g., `ARP-007` = Airport, device 7)

---

### 4.3 ML Inference Engine (`backend/event_engine.py`)

This is the brain of the threat detection system.

**On startup**, it attempts to load three files:
| File | Purpose |
|------|---------|
| `rf_model.joblib` | Trained Random Forest classifier (~370 MB) |
| `preprocessors.joblib` | Contains a `LabelEncoder` to decode numeric class predictions back to string names |
| `val_dataset.pt` | 30,000 validation feature vectors as PyTorch tensors |

If any file fails to load, it falls back to a **mock mode** that generates random attack types with Gaussian-distributed confidence scores.

**`predict_event(features: list) → (attack_type, confidence, severity)`**

```python
sample = np.array(features).reshape(1, -1)
probs = rf_model.predict_proba(sample)[0]   # probability per class
pred_class = rf_model.predict(sample)[0]    # winning class index
confidence = round(max(probs) * 100, 1)    # e.g., 97.3%
attack_type = label_encoder.inverse_transform([pred_class])[0]  # e.g., "DDoS"
```

**Severity mapping:**

| Confidence | Severity |
|-----------|---------|
| ≥ 90% | Critical |
| ≥ 75% | High |
| ≥ 55% | Medium |
| < 55% | Low |

---

### 4.4 FastAPI Backend (`backend/main.py`)

Central hub connecting all parts of the system.

**Startup sequence:**
1. SQLAlchemy creates DB tables if they don't exist
2. `startup_event()` fires → `asyncio.create_task(consume_kafka())` launches the background consumer

**`consume_kafka()` — the core loop:**
- Creates an `AIOKafkaConsumer` connected to `localhost:9092`, group `cityshield-backend`
- Has a **retry loop** on startup — if Kafka isn't ready yet, waits 5 seconds and retries (graceful startup ordering)
- For each Kafka message:
  - Runs `predict_event()` via `asyncio.to_thread()` (non-blocking — keeps the event loop responsive)
  - Saves event to DB
  - Feeds event to `BlockchainManager`
  - **Throttle check**: only proceeds to WebSocket broadcast if `0.2s` has elapsed since last broadcast
  - Sends JSON to all connected WebSocket clients, tracking and removing any that have disconnected

**WebSocket endpoint `GET /ws`:**
- Accepts the connection, adds client to `connected_clients` list
- Simply waits for `websocket.receive_text()` (keeps connection alive)
- On disconnect, cleanly removes from client list

**REST API endpoints:**
- `GET /api/events/recent?limit=50` — queries `EventLog` table, returns latest N events ordered by timestamp
- `GET /api/blocks/recent?limit=20` — queries `BlockChain` table, returns latest N blocks ordered by batch number

---

### 4.5 Blockchain Manager (`backend/blockchain.py`)

A **simulated, in-memory SHA-256 hash chain** that mimics the audit trail properties of a real blockchain.

**How it works:**

1. On init, a **genesis block** is created with `prev_hash = "0" * 64`
2. Every incoming event is added to `pending_events`
3. `try_seal_block()` is called for every event. It seals when:
   - `pending_events` has ≥ 10 events, OR
   - 10 seconds have passed since the last seal (and there's at least 1 event)
4. When sealing:
   ```python
   payload = json.dumps({"batch_num": N, "prev_hash": prev, "timestamp": ts, "event_count": count})
   block_hash = sha256(payload).hexdigest()
   ```
5. **5% of blocks** are artificially tampered (the hash is corrupted mid-string with `"TAMPERED"`) to demonstrate the UI's tamper detection UI state.
6. Only the last **50 blocks** are kept in memory to avoid unbounded growth.

**Why simulate blockchain?** A real Ethereum/Hyperledger integration would require gas fees, wallets, and node infrastructure — overkill for a prototype. The SHA-256 chain simulation demonstrates the *concept* faithfully: if any past event log is altered, its hash no longer matches the next block's `prev_hash`, making tampering immediately visible.

---

### 4.6 Database Layer (`backend/database.py` + `backend/models_db.py`)

**SQLite** is used for simplicity (file-based, no server needed). The DB file is `backend/cityshield.db`.

**`EventLog` table:**

| Column | Type | Description |
|--------|------|-------------|
| id | String (PK) | UUID from the producer |
| timestamp | String | ISO-8601 UTC timestamp |
| device_id | String | e.g., `ARP-007` |
| zone | String | e.g., `Airport` |
| attack_type | String | ML prediction label |
| confidence | Float | e.g., `97.3` |
| severity | String | Critical / High / Medium / Low |
| verified | Boolean | Always `True` (verified by ML) |

**`BlockChain` table:**

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK, auto) | Internal row ID |
| batch_num | Integer | Block sequence number |
| hash | String | SHA-256 hex digest (or tampered variant) |
| prev_hash | String | Hash of the previous block |
| timestamp | String | Block seal time |
| event_count | Integer | Number of events in the block |
| status | String | `VERIFIED` or `TAMPERED` |

---

### 4.7 React Frontend (`frontend/src/App.jsx`)

The root component manages all global state and data connections.

**State:**
- `events` — array of up to 200 most recent threat events (newest first)
- `blocks` — array of up to 20 most recent blockchain blocks
- `isPaused` — toggles whether new live events are added to state
- `connected` — whether the WebSocket connection is live (drives the LIVE/MOCK indicator)

**On mount (two things happen in parallel):**
1. `fetch('/api/events/recent?limit=100')` and `fetch('/api/blocks/recent?limit=20')` — seeds the dashboard with historical data from the DB so it's never blank after a refresh.
2. `new WebSocket('ws://localhost:8000/ws')` — opens the live stream.

**Fallback mock mode:** If the WebSocket connection fails (`onerror` or `onclose`), `startMockInterval()` fires and generates a fake event every ~1.5 seconds using `generateMockEvent()`. This makes the dashboard *always look alive* even when the backend is offline.

**Derived stats (computed from state):**
- `activeThreats` — count of events with Critical or High severity
- `blockchainPct` — percentage of blocks with status VERIFIED
- `deviceCount` — size of the unique `device_id` set across all events

---

### 4.8 Frontend Panels

#### Header (`Header.jsx`)
Displays three live stats at the top:
- **DEVICES** — unique device count (derived from real data)
- **ACTIVE THREATS** — blinks red when > 0
- **CHAIN INTEGRITY** — % of blocks verified (green if ≥90%, orange otherwise)

Also has a **PAUSE/RESUME** button and a **LIVE / MOCK** indicator (green pulse when WebSocket is connected).

---

#### Attack Feed (`AttackFeed.jsx`)
A scrolling table of real-time threat events.

Columns: `TIME | DEVICE | ZONE | ATTACK TYPE | CONFIDENCE% | SEVERITY | VERIFIED`

- Newest event always appears at the top with a CSS `slide-in` animation
- Critical severity rows have a red row highlight
- `verified` column shows a green ✔ checkmark for all ML-verified events

---

#### Threat Map (`ThreatMap.jsx`)
An SVG-based schematic of the 7 city zones (Downtown, Airport, Harbor, Industrial, Residential, University, Hospital).

- Each zone is colored based on the **worst severity** of its recent 20 events
  - Critical → Red, High → Orange, Medium → Yellow, Low → Cyan, None → Dark Navy
- Critical zones pulsate with an animated red dot in the corner
- **Click any zone** → shows a drill-down panel with the 5 most recent events for that zone

---

#### ML Confidence Panel (`MLPanel.jsx`)
Two Recharts charts showing ML model activity:

1. **Event Rate (10s windows)** — AreaChart showing how many events arrived per 10-second bucket (last 20 windows). Shows traffic spikes during attacks.
2. **Attack Type Distribution** — BarChart showing the count of each attack type seen. Fully dynamic — works with any ML class label, auto-assigns colors from a palette for unknown types.

---

#### Blockchain Panel (`BlockchainPanel.jsx`)
Displays the last 6 sealed blocks as linked tiles, visualizing the hash chain.

Each block shows:
- Block number (`#N`)
- Truncated hash (first 8 + last 6 chars)
- Event count + timestamp
- Status badge: `✔ VERIFIED` (green) or `✗ TAMPERED` (red)

Chain links between blocks turn red if the next block is TAMPERED (simulating a broken chain). The newest block slides in with an animation.

---

## 5. Machine Learning Model

**Dataset**: CICIoT2023 (2.8 GB) — a comprehensive IoT attack dataset from the Canadian Institute for Cybersecurity. Contains real network packet captures across multiple attack categories.

**Model**: Scikit-learn `RandomForestClassifier`
- Trained in `backend/train_rf.py` using `train_dataset.pt`
- Serialized to `backend/rf_model.joblib` (~370 MB)
- Preprocessing pipeline (feature scaling, label encoding) saved to `backend/preprocessors.joblib`

**Input**: 46-dimensional feature vector representing network packet statistics:
- Packet lengths (min, max, mean, std)
- Inter-arrival times
- Flag counts (SYN, FIN, RST, ACK...)
- Flow duration, byte rates, etc.

**Output**: Multi-class classification across attack categories including:
`DDoS`, `DoS`, `Mirai`, `BruteForce`, `Spoofing`, `Recon`, `Web attacks`, `BenignTraffic`, and more.

**Validation set**: `val_dataset.pt` — 30,000 held-out samples used by the producer to simulate realistic live traffic.

---

## 6. API Reference

All endpoints are served by the FastAPI backend at `http://localhost:8000`.

### WebSocket

**`GET ws://localhost:8000/ws`**

Persistent connection. Server pushes JSON messages when events arrive:

```json
{
  "type": "event",
  "data": {
    "id": "uuid-...",
    "timestamp": "2026-03-30T00:00:00Z",
    "device_id": "ARP-007",
    "zone": "Airport",
    "attack_type": "DDoS",
    "confidence": 97.3,
    "severity": "Critical",
    "verified": true
  },
  "block": {
    "batch_num": 42,
    "hash": "a3f5c9d2...",
    "prev_hash": "b1e2f3a4...",
    "timestamp": "2026-03-30T00:00:10Z",
    "event_count": 10,
    "status": "VERIFIED"
  }
}
```

> `block` is only included in the payload when a new block is sealed (every ~10 events or ~10 seconds).

---

### REST Endpoints

**`GET /api/events/recent?limit=50`**
Returns the most recent N events from the database, oldest-first.

```json
[
  {
    "id": "...", "timestamp": "...", "device_id": "DWN-003",
    "zone": "Downtown", "attack_type": "Mirai",
    "confidence": 88.5, "severity": "High", "verified": true
  },
  ...
]
```

---

**`GET /api/blocks/recent?limit=20`**
Returns the most recent N blockchain blocks, oldest-first.

```json
[
  {
    "batch_num": 1, "hash": "a3f5c9d2...", "prev_hash": "000...000",
    "timestamp": "...", "event_count": 10, "status": "VERIFIED"
  },
  ...
]
```

---

**`GET /docs`**
Interactive Swagger UI — explore and test all endpoints in the browser.

---

## 7. Database Schema

```sql
-- Event log (populated by Kafka consumer)
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    device_id TEXT,
    zone TEXT,
    attack_type TEXT,
    confidence REAL,
    severity TEXT,
    verified BOOLEAN
);

-- Blockchain blocks (sealed every ~10 events or 10 seconds)
CREATE TABLE blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_num INTEGER UNIQUE,
    hash TEXT,
    prev_hash TEXT,
    timestamp TEXT,
    event_count INTEGER,
    status TEXT   -- 'VERIFIED' or 'TAMPERED'
);
```

---

## 8. Key Design Decisions

| Decision | Rationale |
|---------|-----------|
| **Kafka as message broker** | Decouples the high-speed producer (100 ev/s) from the ML inference backend. No data is lost even during processing spikes. |
| **`asyncio.to_thread()` for ML inference** | `sklearn.predict()` is CPU-bound and blocking. Running it in a thread pool keeps the async event loop free to handle WebSocket connections without lag. |
| **Throttle at 5 ev/sec to WebSocket** | The frontend React state can't re-render at 100 Hz without becoming unresponsive. 5 ev/sec gives a smooth, live feel without janking the browser. All events still saved to DB. |
| **REST API + history on mount** | Without this, every browser refresh shows an empty dashboard. The REST endpoints seed 100 events and 20 blocks from SQLite so the UI is instantly populated. |
| **Frontend mock fallback** | If the backend is offline (e.g., during a demo setup), the UI still animates and shows data. Makes demos resilient. |
| **SHA-256 simulated blockchain** | Real blockchain (Ethereum/Hyperledger) is impractical for a hackathon prototype. The SHA-256 chain simulation demonstrates the *concept* — bulk insertion, prev-hash chaining, tamper detection — without infrastructure overhead. |
| **Dynamic attack colors in MLPanel** | The real ML model returns class labels not known at build time. A hardcoded color map would fail silently. The dynamic resolver with a fallback palette ensures every attack type gets a visible, unique color. |
| **KRaft Kafka (no Zookeeper)** | Modern Kafka 3.x replaced Zookeeper with its own consensus protocol (KRaft). Simpler Docker setup with one container instead of two. |

---

## 9. How to Run the Project

You need **4 things running simultaneously** for the full pipeline:

### Terminal 1 — Kafka (Docker)
```bash
cd CityShield
docker compose up -d
```

### Terminal 2 — FastAPI Backend
```bash
cd CityShield/backend
.\venv\Scripts\activate       # Windows
# source venv/bin/activate    # Mac/Linux
uvicorn main:app --reload
```
> First time: `pip install -r requirements.txt`

### Terminal 3 — Kafka Producer
```bash
cd CityShield/backend
.\venv\Scripts\activate
python kafka_producer.py
```

### Terminal 4 — React Frontend
```bash
cd CityShield/frontend
npm install     # first time only
npm run dev
```

Open **http://localhost:5173** 🚀

### Stopping Everything
```bash
# Terminal 1
docker compose down

# Terminals 2, 3, 4
Ctrl+C
```

---

## 10. File Map

```
CityShield/
│
├── docker-compose.yml          # Kafka broker (apache/kafka:3.7.0, KRaft mode)
├── README.md                   # Quick start guide
├── CityShield_Complete_Vision.md  # Original architectural vision doc
├── CityShield_Current_Status.md   # What was mocked vs real (pre-integration)
├── Kafka_Guide.md              # Kafka concepts guide written for this project
│
├── backend/
│   ├── main.py                 # FastAPI app: Kafka consumer, WebSocket, REST API
│   ├── event_engine.py         # ML inference: loads rf_model, predict_event()
│   ├── kafka_producer.py       # IoT simulator: sends events to Kafka at ~100/sec
│   ├── blockchain.py           # SHA-256 hash chain simulation
│   ├── database.py             # SQLAlchemy engine + session factory (SQLite)
│   ├── models_db.py            # ORM models: EventLog, BlockChain tables
│   ├── models.py               # (PyTorch model definition, used during training)
│   ├── train_model.py          # PyTorch training script (deep learning experiment)
│   ├── train_rf.py             # Random Forest training script (used in production)
│   ├── preprocess.py           # Data preprocessing pipeline script
│   ├── rf_model.joblib         # Trained Random Forest classifier (~370 MB)
│   ├── preprocessors.joblib    # LabelEncoder and preprocessing artifacts
│   ├── train_dataset.pt        # ~23 MB PyTorch tensor: training split
│   ├── val_dataset.pt          # ~5.5 MB PyTorch tensor: validation split (used by producer)
│   ├── model.pth               # (PyTorch model weights, from deep learning experiment)
│   ├── cityshield.db           # SQLite database (auto-created on first run)
│   └── requirements.txt        # Python dependencies
│
└── frontend/
    ├── index.html              # Vite HTML entry point
    ├── vite.config.js          # Vite config
    ├── package.json            # Node dependencies (React, Recharts, etc.)
    └── src/
        ├── main.jsx            # React DOM entry point
        ├── App.jsx             # Root component: state, WebSocket, REST fetch
        ├── App.css             # Dashboard grid layout
        ├── index.css           # Global styles, CSS variables, fonts
        └── components/
            ├── Header.jsx      # Top bar: stats, pause button, live indicator
            ├── Header.css
            ├── AttackFeed.jsx  # Scrolling live event table
            ├── AttackFeed.css
            ├── ThreatMap.jsx   # SVG city zone map with severity coloring
            ├── ThreatMap.css
            ├── MLPanel.jsx     # Event rate AreaChart + attack distribution BarChart
            ├── MLPanel.css
            ├── BlockchainPanel.jsx  # Hash chain visualization (last 6 blocks)
            └── BlockchainPanel.css
```
