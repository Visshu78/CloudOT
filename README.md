# CityShield ⬡
> Real-Time IoT Threat Intelligence Dashboard for Smart Cities

CityShield ingests live network traffic telemetry from thousands of IoT devices across smart city zones, classifies threats in real time using a trained Random Forest ML model, and displays live analytics on a cyberpunk command dashboard — secured by a SHA-256 blockchain audit trail.

---

## 🚀 Architecture

```
kafka_producer.py  →  Kafka Broker (Docker)  →  FastAPI (main.py)  →  WebSocket  →  React Dashboard
  (IoT Simulator)         :9092                (ML Inference +                     (Recharts UI)
                                                DB Persistence)
                                                SQLite (cityshield.db)
```

---

## ⚡ Big Data Concepts & Techniques

CityShield leverages modern **Big Data infrastructure, real-time stream processing, distributed messaging, and high-performance machine learning** to process massive IoT traffic streams without latency degradation.

### 1. High-Throughput Distributed Event Streaming
- **Message Queueing & Buffering (Apache Kafka)**: Ingests thousands of high-velocity IoT network telemetry events per second over the `iot-traffic` topic. Kafka acts as a distributed shock absorber, decoupling telemetry producers from downstream analytical consumers to prevent backpressure.
- **KRaft Consensus Engine**: Deploys Kafka 3.7.0 in KRaft (Kafka Raft) metadata mode, eliminating Zookeeper dependency for lightweight, high-performance containerized broker orchestration.
- **Asynchronous Producer-Consumer Pipeline**: Implements non-blocking `aiokafka` consumer loops in Python `asyncio` to read telemetry vectors concurrently with API and WebSocket execution.

### 2. Massive Dataset Processing & Feature Engineering
- **CICIoT2023 Benchmark Dataset**: Built on the 2.8 GB multi-class **CICIoT2023** cybersecurity dataset featuring millions of real IoT network attack instances across 34 multi-class attack categories (DDoS, DoS, Mirai botnets, Reconnaissance, Brute Force, Web Attacks).
- **Feature Normalization & Imputation Pipeline**: Uses `scikit-learn` preprocessors (`preprocess.py`, `preprocessors.joblib`) including `StandardScaler` for variance normalization, `SimpleImputer` for missing feature value handling, and `LabelEncoder` for attack taxonomy mapping across 46 network flow features.
- **Tensor Vectorization & Memory Optimization**: Preprocessed datasets are serialized into binary PyTorch tensors (`train_dataset.pt`, `val_dataset.pt`) for fast memory-mapped dataset loading and high-efficiency feature vectorization during training and evaluation.

### 3. Real-Time Stream Analytics & Machine Learning Inference
- **Ensemble Supervised Classification (Random Forest)**: Evaluates incoming 46-dimensional network flow vectors against a pre-trained Random Forest model (`rf_model.joblib`) to predict attack type, confidence score, and severity level (Critical, High, Medium, Low) in sub-milliseconds.
- **Stream Throttling & Adaptive Backpressure**: Implements sliding window rate-limiting (5 events/sec maximum WebSocket push interval) to handle backpressure between high-frequency backend ingestion (~100 events/sec) and browser UI rendering capabilities.
- **Fallback Resiliency Architecture**: Includes a circuit-breaker fallback loop (`simulate_iot_stream()`) that seamlessly transitions to an in-memory direct vector generator if the Kafka broker is offline.

### 4. Cryptographic Blockchain Audit Trail
- **Micro-Batch Block Aggregation**: Groups verified threat detection events into 10-second micro-batches and seals them into cryptographic blocks (`blockchain.py`).
- **SHA-256 Hash Chaining & Tamper Detection**: Links each sealed block to the preceding block's hash (`prev_hash`), guaranteeing ledger immutability and instant cryptographic detection of unauthorized data modifications.

### 5. Persistent Storage & Real-Time Visualization
- **Relational Data Warehousing (SQLAlchemy + SQLite)**: Persists all event logs (`EventLog`) and sealed block hashes (`BlockChain`) for audit retention, historical trend analysis, and dashboard seed initialization.
- **Bi-Directional WebSocket Streaming**: Streams JSON event feeds to React clients for real-time aggregation, dynamic threat heatmaps, and sliding-window statistical charts.

---

## 📋 Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| Docker Desktop | Latest (Optional for Kafka mode) |

---

## 🛠️ Quick Start

### Step 1 — Start Kafka (Optional for Kafka Mode)
```bash
docker compose up -d
```
This pulls and starts an `apache/kafka:3.7.0` container on `localhost:9092`.
*(Note: If Kafka is not running, CityShield automatically activates its direct real-time ML IoT generator fallback).*

---

### Step 2 — Set up the Python backend

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

---

### Step 3 — Start the FastAPI backend
```bash
# Inside backend/ with venv active
uvicorn main:app --reload
```
The server starts at **http://localhost:8000**.

- WebSocket: `ws://localhost:8000/ws`
- Recent events API: `http://localhost:8000/api/events/recent`
- Recent blocks API: `http://localhost:8000/api/blocks/recent`
- Interactive API docs: `http://localhost:8000/docs`

---

### Step 4 — Start the Kafka Producer (If using Kafka)
Open a **new terminal** (keep uvicorn running):
```bash
cd backend
.\venv\Scripts\activate   # or source venv/bin/activate on Mac/Linux
python kafka_producer.py
```
This loads the `val_dataset.pt` validation set and streams ~100 IoT network events/second into Kafka.

---

### Step 5 — Start the React Frontend
Open another **new terminal**:
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173** in your browser.

---

## 🧩 Component Overview

| File | Purpose | Big Data / Tech Concept |
|------|---------|-------------------------|
| `backend/main.py` | FastAPI server — Kafka consumer, WebSocket broadcast, REST API | Stream Consumer, WebSockets, Rate Throttling |
| `backend/event_engine.py` | ML inference engine — loads `rf_model.joblib`, runs predictions | Random Forest Classification, Flow Feature Scoring |
| `backend/kafka_producer.py` | IoT simulator — sends features from `val_dataset.pt` to Kafka | Stream Producer, Event Generation |
| `backend/preprocess.py` | Feature preprocessing pipeline for CICIoT2023 | Scaling (`StandardScaler`), Imputation, Label Encoding |
| `backend/train_rf.py` | Random Forest model training script | Ensemble ML, Multi-class Classification |
| `backend/blockchain.py` | SHA-256 hash chaining, block sealing, tamper detection | Immutable Ledger, Cryptographic Hashing |
| `backend/models_db.py` | SQLAlchemy ORM models for events and blocks | Database Warehousing, Schema Persistence |
| `docker-compose.yml` | Kafka broker configuration | Distributed Streaming Broker, KRaft Mode |
| `frontend/src/App.jsx` | Main React app — WebSocket client, history fetch | Real-Time State Aggregation, Client Re-rendering |
| `frontend/src/components/` | Dashboard panels (Header, AttackFeed, ThreatMap, MLPanel, BlockchainPanel) | Visual Stream Analytics, Sliding Window Recharts |

---

## 🛑 Stopping Everything

```bash
# Stop Kafka
docker compose down

# Stop uvicorn and kafka_producer with Ctrl+C in their respective terminals
```

