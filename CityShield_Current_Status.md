# CityShield: Current Implementation Status

## Overview
This document outlines the **current state** of the CityShield repository. The foundation of the system (Frontend UI, Backend API, and WebSocket streaming) is fully built and functioning. However, because this is an MVP (Minimum Viable Product) / Hackathon prototype, the heavy ML and Data Pipeline components are currently **mocked (simulated)**.

---

## 1. Frontend Dashboard (Fully Implemented)
**Stack:** React, Vite, Recharts, Custom CSS
**Status:** **100% Complete for Prototype**
- **UI/UX**: The dark cyberpunk theme with neon accents (Cyan, Red, Orange) and monospace fonts is fully styled and responsive.
- **WebSocket Connection**: The frontend successfully connects to `ws://localhost:8000/ws` and listens for incoming payload events. If the backend is unreachable, it seamlessly falls back to a frontend-only mock interval generator so the UI never appears broken.
- **Components Built & Working:**
  - **Header**: Live metrics, live/paused toggles, and blinking status indicators.
  - **Attack Feed**: A real-time, scrolling virtual table showing device IDs, zones, attack types, and severity badges with slide-in animations.
  - **Threat Map**: An SVG-based layout of 7 city zones that dynamically pulse colors based on incoming threat severity.
  - **ML Panel**: Live Recharts implementations (AreaChart for event rates over 10s windows, BarChart for attack type distribution).
  - **Blockchain Panel**: UI representation of the cryptographic hash chain, showing blocks sealing every 10 seconds and reacting visually if a "TAMPERED" block arrives.

---

## 2. Backend Server (Implemented with Mocks)
**Stack:** Python, FastAPI, Uvicorn, WebSockets
**Status:** **Architecture Built; Data & ML are Simulated**
- **FastAPI / WebSockets** (`main.py`): Completely functional. It accepts WebSocket connections from the React app and continuously broadcasts JSON payloads containing attack events and new blockchain blocks.

### What is Currently Mocked (Simulated):

**A. The Data Stream & ML Inference** (`event_engine.py`)
- *Currently:* We are **not** reading the massive 2.8GB CICIoT2023 `archive.zip` dataset, nor are we running it through Kafka.
- *Currently:* We are **not** loading a trained `.joblib` scikit-learn model.
- *How it works right now:* A Python generator loop randomly creates an event every 1.5 to 2.0 seconds. It randomly selects a city zone, assigns a device ID, picks a random attack type (e.g., "DDoS"), and assigns a random fake "Confidence Score". The backend then calculates the severity based on that fake score and broadcasts it.

**B. The Blockchain** (`blockchain.py`)
- *Currently:* We are **not** using a real distributed ledger (like Ethereum or Hyperledger).
- *How it works right now:* We implemented a localized, in-memory SHA-256 hashing algorithm. It collects the mock events in memory, and every 10 seconds, it hashes the JSON payload along with the previous block's hash to simulate a chain. For presentation purposes, it randomly intentionally corrupts 5% of the blocks to demonstrate the frontend's "TAMPERED" UI state.

---

## Next Steps for Full Realization
To upgrade this repository from a "Prototype" to the "Complete Vision", the following steps are required:
1. **Train the ML Model**: Process the `archive.zip` CICIoT2023 dataset in a Jupyter Notebook, train a Random Forest classifier, and export the weights to `model.joblib`.
2. **Replace the Engine**: Rewrite `event_engine.py` to strip out the `random.choice()` logic. Instead, have it read rows from the CSV dataset in real-time and pass them to the loaded `joblib` model for actual inference.
3. **Database Integration**: Persist the blockchain hashes and logs to a real database (e.g., PostgreSQL or MongoDB) instead of keeping them purely in Python's local RAM.
