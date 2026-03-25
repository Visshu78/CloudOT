# CityShield: Complete Vision & Architecture

## Overview
**CityShield** is envisioned as a real-time, large-scale IoT Threat Intelligence Dashboard for smart cities. It is designed to act as a centralized command center monitoring thousands of IoT edge devices across various city zones (e.g., Downtown, Airport, Industrial, Hospital). 

The core objective is to ingest live network traffic data, use Machine Learning (ML) to instantly classify malicious behavior, and securely log these events using blockchain technology to ensure auditability and tamper-proofing.

---

## The Complete Architecture (The Grand Vision)

The full implementation of CityShield relies on a robust data pipeline, a trained ML classification model, a real blockchain network, and a responsive frontend dashboard.

### 1. Data Ingestion & Streaming Pipeline
- **Source Data**: Continuous stream of network packets or telemetry from IoT devices. In a simulated environment, this is represented by replaying the massive **CICIoT2023** dataset (a 2.8 GB dataset containing real IoT attack vectors like DDoS, Mirai, BruteForce, etc.).
- **Message Broker (Kafka / RabbitMQ)**: A high-throughput message queue that ingests the massive volume of incoming logs and queues them for the ML inference engine to prevent bottlenecks.

### 2. Machine Learning Inference Engine
- **The Model**: A pre-trained `scikit-learn` Random Forest classifier (or deep learning equivalent) saved as a `.joblib` or `.pkl` file.
- **The Process**: As new data arrives via the message queue, the ML engine extracts the features (e.g., packet size, protocol, duration), runs an inference prediction, and outputs two things:
  1. **Attack Type**: (e.g., DDoS, Spoofing, Safe)
  2. **Confidence Score**: An accuracy percentage (e.g., 95% confident this is Mirai).
- The prediction assigns a **Severity Level** (Critical, High, Medium, Low). 

### 3. Blockchain Integrity & Audit Layer
- **Distributed Ledger**: Instead of trusting a centralized database that hackers could alter to hide their tracks, events are batched together.
- **Hash Chaining**: Every batch of events is hashed using SHA-256 and linked to the previous batch's hash. This creates an immutable chain. If a malicious actor alters a past log, the hashes break, immediately flagging the system with a "TAMPERED" status.

### 4. Real-Time Command Center (Frontend)
- **WebSockets**: A persistent bi-directional connection between the backend and frontend ensures the dashboard UI updates within milliseconds of an attack being detected.
- **Data Visualization (React + D3.js/Recharts)**: 
  - A geographic/schematic **Threat Map** showing active cyber-attacks mapped to physical city zones.
  - A **Live Attack Feed** displaying the raw stream of flagged anomalies.
  - An **ML Confidence Panel** graphing event rates and distribution over time.
  - A **Blockchain Validator** showing the ongoing cryptographic seals of the data.

---

## Real-World Workflow
1. A compromised IoT camera in the "Airport" zone begins sending a flood of UDP packets (Mirai botnet).
2. The packet data is streamed via Kafka into the ML Engine.
3. The Random Forest model flags the traffic as **Mirai** with 98% confidence (Critical Severity).
4. The backend immediately pushes this alert over WebSockets to the React frontend.
5. In the UI, the Airport zone flashes red, the event slides into the Live Feed, and the statistical bar chart ticks up.
6. 10 seconds later, this event is batched with others, cryptographically hashed, and sealed into the simulated Blockchain.
