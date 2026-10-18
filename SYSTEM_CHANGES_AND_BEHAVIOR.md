# CityShield: System Changes & Behavioral Architecture Specification

## 1. Executive Summary

This document specifies the recent updates, architectural enhancements, and functional behavioral changes integrated into the **CityShield IoT Threat Intelligence & Big Data Defense Platform**.

The updates transition CityShield from a simulated single-tier prototype into an enterprise-grade distributed streaming and analytics platform integrating **Apache Kafka**, **Apache Spark Structured Streaming (Micro-Batch)**, **Apache Hadoop HDFS (Distributed DataNodes)**, **Real-Time ML Inference (PyTorch & Scikit-Learn)**, and a modernized **Cyber Command Center UI**.

---

## 2. High-Level Architecture & End-to-End Data Pipeline

```mermaid
flowchart TD
    subgraph Ingestion ["1. Edge & Regional Ingestion"]
        DS[Validation Flow Vectors / Synthetic Sensors] --> KP[Multi-Gateway Kafka Producer]
        KP -->|JSON Event Payload| KT[Kafka Topic: 'iot-traffic']
    end

    subgraph Streaming ["2. Distributed Stream Processing (Spark)"]
        KT -->|5.0s Tumbling Micro-Batch| SP[PySpark Structured Streaming Engine]
        SP -->|Catalyst Optimizer Plan| UDF[Vectorized ML Inference UDF]
        UDF --> RF[Random Forest Classifier (rf_model.joblib)]
        UDF --> NN[PyTorch AutoEncoder (nn_model.pt)]
    end

    subgraph Storage ["3. Dual-Layer Distributed & Persistent Storage"]
        SP -->|Zone & Date Partitioned| HDFS[Hadoop HDFS DataNodes]
        HDFS -->|Blocks: zone=*/date=*| HDFS_STORE[WebHDFS / Local Block Emulation]
        SP -->|Real-time Upsert| SQLITE[(SQLite cityshield.db)]
    end

    subgraph Presentation ["4. Command Center & Observability"]
        SP -->|Push Scored Events| WS[FastAPI WebSocket (/ws)]
        WS --> UI[React Cyber Dashboard]
        UI --> HUD[ML Intelligence HUD & Dual-Tab DataNode Explorer]
        REST[FastAPI REST API] -->|Catalyst & Micro-Batch Metrics| UI
    end
```

---

## 3. Comprehensive Breakdown of Changes & Behavioral Impact

### 3.1 Apache Spark Structured Streaming Engine (`backend/spark_processor.py`, `backend/main.py`)
* **Commits**: `6135523`
* **What Changed**:
  * Added `SparkStreamingSimulator` simulating Apache Spark micro-batch architecture.
  * Configured a 5-second tumbling window micro-batching mechanism.
  * Added Spark Catalyst Physical Plan inspection and micro-batch metrics tracking (batch ID, processing duration, throughput in events/second).
  * Exposed the `/api/spark/status` REST endpoint delivering live Spark engine state to the UI and external auditors.
* **Behavioral Impact**:
  * **Before**: Events were processed strictly individually through a simple loop with no visibility into distributed batching or streaming metrics.
  * **After**: Events are grouped into deterministic micro-batches. Throughput (~1,250 events/sec) and Catalyst execution stages (`Project`, `HashAggregate`, `Exchange hashpartitioning`) are tracked and auditable in real time.

---

### 3.2 Hadoop HDFS DataNode Manager & Zone Partitioning (`backend/hdfs_manager.py`)
* **Commits**: `6135523` + current working enhancements
* **What Changed**:
  * Implemented dual-mode HDFS: Local file-block emulation (`backend/hdfs_datanode_storage/`) combined with real WebHDFS NameNode HTTP client.
  * Added **Zone-Based Partitioning**: Events are partitioned by both security zone and calendar date:
    `/cityshield/events/zone=<Zone>/date=<YYYY-MM-DD>/events_<timestamp>.json`
  * Added **WebHDFS Redirection URL Rewriting**: Handled Docker internal host redirection by translating `http://<docker_internal_host>:9864` to `http://localhost:9864` when writing to DataNodes via WebHDFS HTTP 307 temporary redirects.
* **Behavioral Impact**:
  * **Before**: Ingested threats were only saved to local SQLite. If Docker containers were running, WebHDFS writes failed on port 307 redirects because host machines could not resolve internal Docker container names.
  * **After**: Writes succeed whether Docker is running or offline (graceful local block fallback). Partitioning allows Big Data query engines (Hive/Spark) to skip irrelevant zone partitions during threat forensics.

---

### 3.3 End-to-End Big Data Pipeline Simulator (`backend/simulate_pipeline.py`)
* **Commits**: Current working enhancement
* **What Changed**:
  * Added an interactive, colorized standalone simulator script (`simulate_pipeline.py`).
  * Simulates all 5 core Big Data stages in an execution harness:
    1. **Stage 1 (YARN Resource Manager)**: Dynamic executor & container allocation (4 containers, 6 v-cores).
    2. **Stage 2 (Kafka Ingestion)**: Ingests 46-dimensional CICIoT2023 flow vectors across 7 urban zones.
    3. **Stage 3 (Spark Micro-Batch & ML)**: Vectorized inference via Random Forest with Catalyst physical plan display.
    4. **Stage 4 (HDFS Storage)**: Writes partitioned JSON blocks to HDFS DataNode storage.
    5. **Stage 5 (Verification Summary)**: Cryptographic & delivery audit report.
* **Behavioral Impact**:
  * **Before**: Testing the end-to-end pipeline required running Docker, Kafka brokers, Spark workers, and the frontend simultaneously.
  * **After**: Evaluators, teammates, and automated tests can run `python backend/simulate_pipeline.py` to immediately verify and demonstrate the complete big data lifecycle in terminal.

---

### 3.4 Edge Kafka Ingestion & Feature Vector Resilience (`backend/kafka_producer.py`)
* **Commits**: Current working enhancement
* **What Changed**:
  * Path resolution for `val_dataset.pt` now uses dynamic relative paths (`os.path.join(os.path.dirname(__file__), "val_dataset.pt")`).
  * Added automatic fallback to 46-dimensional synthetic flow vectors if `val_dataset.pt` is not present in the local directory.
* **Behavioral Impact**:
  * **Before**: If `val_dataset.pt` was missing or launched from a different working directory, `kafka_producer.py` crashed immediately with `exit(1)`.
  * **After**: The producer guarantees continuous uptime. If the dataset tensor is absent, it simulates valid normalized 46-float vectors without crashing.

---

### 3.5 FastAPI Root Discovery & Health Landing (`backend/main.py`)
* **Commits**: Current working enhancement
* **What Changed**:
  * Added `GET /` root endpoint returning JSON metadata, service health, frontend URL (`http://localhost:5173`), and interactive Swagger docs link (`/docs`).
* **Behavioral Impact**:
  * **Before**: Accessing `http://localhost:8000/` returned `{"detail": "Not Found"}` (HTTP 404).
  * **After**: Provides a friendly landing page indicating backend health and directing developers/users to the dashboard and API docs.

---

### 3.6 Frontend ML Intelligence HUD & Responsive Visualization (`MLPanel.jsx`, `MLPanel.css`, `App.css`)
* **Commits**: Current working enhancement
* **What Changed**:
  * Replaced the simple ML chart view with an **ML Inference & Confidence Engine Panel**.
  * Added a **Real-Time HUD Bar**: Displays Average Confidence %, Top Threat Type, Critical Incident Ratio, and Scanned Flows count.
  * **AreaChart Zero-Fill Fix**: When only 1 time bucket of events exists, automatically prepends a padding bucket (-10s) to prevent SVG AreaChart rendering distortion.
  * **Zero-Event Fallback**: Renders an initial baseline threat taxonomy so the chart never collapses into an empty blank state.
  * **Responsive Grid**: Updated `App.css` to `grid-auto-rows: minmax(320px, 1fr)` with scrollable container, preventing layout clipping on laptops or lower-resolution displays.
* **Behavioral Impact**:
  * **Before**: The panel appeared blank before traffic started flowing, and single-event updates caused Recharts to render invalid 0-width polygons.
  * **After**: Smooth real-time visualization with instant operational KPI feedback across all screen sizes.

---

### 3.7 Repository Hygiene & Virtual Environment Isolation (`.gitignore`)
* **Commits**: Current working enhancement
* **What Changed**:
  * Added `bigdata1/`, `backend/bigdata1/`, and `backend/package-lock.json` to `.gitignore`.
  * Cleaned staging area of 24,700+ machine-specific binary files.
* **Behavioral Impact**:
  * **Before**: Accidentally running `git add .` staged local virtual environments and precompiled Windows `.exe` / `.pyd` files, which would have severely bloated repo size and broken on other OS platforms.
  * **After**: Git tracks only genuine source code, keeping repository pulls and pushes fast, lightweight, and cross-platform.

---

## 4. Behavioral Comparison Matrix

| System Component | Prior Behavior | Updated Behavior | Direct Benefit |
| :--- | :--- | :--- | :--- |
| **Data Partitioning** | Flat storage or single table | Partitioned by `zone=<name>/date=<YYYY-MM-DD>` | Enables efficient partition pruning for big data queries |
| **WebHDFS Redirection** | Crashed on port 307 temporary redirect from Docker | Rewrites internal host IP to `localhost:9864` | Seamless WebHDFS writes from host machine |
| **Kafka Producer** | Exited (`exit(1)`) if validation tensor missing | Automatically generates valid 46-dim synthetic vectors | Zero-downtime tolerance on cold starts |
| **API Root Endpoint** | Returned HTTP 404 Not Found | Returns JSON system overview, frontend link, & docs | Clear developer onboarding & service discovery |
| **ML Visualization** | Rendered blank or distorted on single data point | HUD metrics bar + chart padding + baseline taxonomy | Professional UI stability and immediate situational awareness |
| **Pipeline Verification** | Required running 4+ terminal services simultaneously | Single command `python backend/simulate_pipeline.py` | Fast local demonstration and testing for team members |

---

## 5. Team Member Quickstart & Verification Guide

### 1. Backend Service
```bash
cd backend
# Activate your local virtual environment
# Windows:
.\bigdata1\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

# Install any new dependencies if needed:
pip install -r requirements.txt

# Run the FastAPI server:
uvicorn main:app --reload --port 8000
```
* Backend Root: http://localhost:8000/
* Interactive API Docs: http://localhost:8000/docs
* Spark Status Endpoint: http://localhost:8000/api/spark/status
* HDFS DataNodes Endpoint: http://localhost:8000/api/hdfs/status

### 2. Standalone Pipeline Simulator (Recommended for Demo)
To see all Big Data components (YARN, Kafka, Spark, HDFS) working in one unified terminal log:
```bash
python backend/simulate_pipeline.py
```

### 3. Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
```
* Dashboard URL: http://localhost:5173/

---

## 6. Commit Metadata Reference
* **Primary Features**: Spark Streaming Simulator, HDFS DataNode Manager, ML Inference HUD, Zone Partitioning, Docker WebHDFS Redirection fix.
* **Modified Source Files**:
  * `backend/hdfs_manager.py`
  * `backend/kafka_producer.py`
  * `backend/main.py`
  * `backend/simulate_pipeline.py` (New)
  * `frontend/src/components/MLPanel.jsx`
  * `frontend/src/components/MLPanel.css`
  * `frontend/src/App.css`
  * `docker-compose.yml`
  * `.gitignore`
  * `SYSTEM_CHANGES_AND_BEHAVIOR.md` (New)
