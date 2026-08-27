"""
test_event_engine.py — Unit tests for event_engine.py

Tests cover:
  - severity_from_confidence() thresholds
  - generate_device_id() format
  - predict_event() mock fallback (when ML model is not loaded)
  - predict_event() with real model (if loaded)
  - generate_event() output structure
"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_engine import (
    severity_from_confidence,
    generate_device_id,
    predict_event,
    generate_event,
    ZONES,
    DEVICES_PER_ZONE,
)


# ── severity_from_confidence ──────────────────────────────────────────────────

class TestSeverityFromConfidence:
    @pytest.mark.parametrize("score,expected", [
        (99.9, "Critical"),
        (90.0, "Critical"),
        (89.9, "High"),
        (75.0, "High"),
        (74.9, "Medium"),
        (55.0, "Medium"),
        (54.9, "Low"),
        (20.0, "Low"),
        (0.0,  "Low"),
    ])
    def test_thresholds(self, score, expected):
        assert severity_from_confidence(score) == expected

    def test_boundary_90_is_critical(self):
        assert severity_from_confidence(90.0) == "Critical"

    def test_boundary_75_is_high(self):
        assert severity_from_confidence(75.0) == "High"

    def test_boundary_55_is_medium(self):
        assert severity_from_confidence(55.0) == "Medium"


# ── generate_device_id ────────────────────────────────────────────────────────

class TestGenerateDeviceId:
    @pytest.mark.parametrize("zone,idx,expected", [
        ("Downtown",    1,  "DWN-001"),
        ("Airport",     15, "AIR-015"),
        ("Harbor",      7,  "HAR-007"),
        ("Industrial",  10, "IND-010"),
        ("Residential", 3,  "RES-003"),
        ("University",  12, "UNI-012"),
        ("Hospital",    5,  "HOS-005"),
    ])
    def test_format(self, zone, idx, expected):
        assert generate_device_id(zone, idx) == expected

    def test_prefix_is_3_chars(self):
        device_id = generate_device_id("Downtown", 1)
        prefix = device_id.split("-")[0]
        assert len(prefix) == 3

    def test_index_zero_padded_to_3(self):
        device_id = generate_device_id("Harbor", 5)
        idx_part = device_id.split("-")[1]
        assert len(idx_part) == 3
        assert idx_part == "005"


# ── predict_event — mock mode ─────────────────────────────────────────────────

class TestPredictEventMockMode:
    """Tests for predict_event() when the ML model is NOT loaded (mock fallback)."""

    def test_returns_tuple_of_3(self):
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", ["DDoS", "Mirai"]):
            result = predict_event([])
            assert isinstance(result, tuple)
            assert len(result) == 3

    def test_attack_type_from_mock_list(self):
        mock_attacks = ["DDoS", "Mirai", "Recon"]
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", mock_attacks):
            attack_type, _, _ = predict_event([])
            assert attack_type in mock_attacks

    def test_confidence_in_valid_range(self):
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", ["DDoS"]):
            for _ in range(50):
                _, confidence, _ = predict_event([])
                assert 20.0 <= confidence <= 99.9, f"Out of range: {confidence}"

    def test_severity_is_valid_label(self):
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", ["DDoS"]):
            _, _, severity = predict_event([])
            assert severity in ("Critical", "High", "Medium", "Low")

    def test_severity_matches_confidence(self):
        """Verify severity label is consistent with the returned confidence."""
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", ["DDoS"]):
            for _ in range(30):
                _, confidence, severity = predict_event([])
                expected = severity_from_confidence(confidence)
                assert severity == expected


# ── predict_event — real model mode ──────────────────────────────────────────

class TestPredictEventRealModel:
    """Tests for predict_event() when the ML model IS loaded."""

    def test_real_model_returns_attack_type_string(self):
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([[0.05, 0.90, 0.05]])
        mock_model.predict.return_value = np.array([1])

        mock_encoder = MagicMock()
        mock_encoder.inverse_transform.return_value = ["DDoS"]

        with patch("event_engine.engine_ready", True), \
             patch("event_engine.rf_model", mock_model), \
             patch("event_engine.label_encoder", mock_encoder):
            attack_type, confidence, severity = predict_event([0.1, 0.2, 0.3])
            assert attack_type == "DDoS"

    def test_real_model_confidence_is_max_proba(self):
        probs = [0.05, 0.90, 0.05]
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([probs])
        mock_model.predict.return_value = np.array([1])

        mock_encoder = MagicMock()
        mock_encoder.inverse_transform.return_value = ["Mirai"]

        with patch("event_engine.engine_ready", True), \
             patch("event_engine.rf_model", mock_model), \
             patch("event_engine.label_encoder", mock_encoder):
            _, confidence, _ = predict_event([0.0] * 10)
            assert confidence == round(max(probs) * 100, 1)

    def test_real_model_severity_derived_from_confidence(self):
        probs = [0.02, 0.96, 0.02]  # 96% → Critical
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([probs])
        mock_model.predict.return_value = np.array([1])

        mock_encoder = MagicMock()
        mock_encoder.inverse_transform.return_value = ["DDoS"]

        with patch("event_engine.engine_ready", True), \
             patch("event_engine.rf_model", mock_model), \
             patch("event_engine.label_encoder", mock_encoder):
            _, confidence, severity = predict_event([0.0] * 10)
            assert severity == "Critical"
            assert confidence >= 90.0


# ── generate_event ────────────────────────────────────────────────────────────

class TestGenerateEvent:
    """Tests for generate_event() output structure."""

    def test_returns_dict(self):
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", ["DDoS"]):
            event = generate_event()
            assert isinstance(event, dict)

    def test_required_keys_present(self):
        required = {"id", "timestamp", "device_id", "zone", "attack_type",
                    "confidence", "severity", "verified"}
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", ["DDoS"]):
            event = generate_event()
            assert required.issubset(event.keys())

    def test_zone_is_valid(self):
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", ["DDoS"]):
            event = generate_event()
            assert event["zone"] in ZONES

    def test_device_id_format(self):
        """device_id should be PREFIX-NNN format."""
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", ["DDoS"]):
            event = generate_event()
            parts = event["device_id"].split("-")
            assert len(parts) == 2
            assert len(parts[0]) == 3
            assert parts[1].isdigit()

    def test_device_index_in_range(self):
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", ["DDoS"]):
            for _ in range(20):
                event = generate_event()
                idx = int(event["device_id"].split("-")[1])
                assert 1 <= idx <= DEVICES_PER_ZONE

    def test_verified_is_true(self):
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", ["DDoS"]):
            event = generate_event()
            assert event["verified"] is True

    def test_id_is_string(self):
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", ["DDoS"]):
            event = generate_event()
            assert isinstance(event["id"], str)
            assert len(event["id"]) > 0

    def test_timestamp_ends_with_z(self):
        with patch("event_engine.engine_ready", False), \
             patch("event_engine.ATTACK_TYPES", ["DDoS"]):
            event = generate_event()
            assert event["timestamp"].endswith("Z")
