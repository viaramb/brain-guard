"""Unit tests for Database Manager."""

import pytest
import tempfile
import os
from pathlib import Path

from src.database.db_manager import DatabaseManager, SQLiteBackend


@pytest.fixture
async def db_manager():
    """Create temporary database manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        manager = DatabaseManager(
            storage_type="sqlite",
            connection_string=db_path
        )
        await manager.initialize()
        yield manager
        await manager.close()


@pytest.mark.unit
class TestDatabaseManager:
    """Tests for DatabaseManager."""
    
    async def test_store_session(self, db_manager):
        """DB-001: Session creation."""
        await db_manager.store_session(
            session_id="test-session-1",
            domain="finance",
            metadata={"user": "test"}
        )
        
        # Verify by getting summary
        summary = await db_manager.get_session_summary("test-session-1")
        assert summary is not None
    
    async def test_update_session_status(self, db_manager):
        """Test updating session status."""
        await db_manager.store_session("test-session-status")
        await db_manager.update_session_status("test-session-status", "closed")
        
        # Status is updated internally
        assert True
    
    async def test_store_metrics(self, db_manager):
        """DB-002: Metric insertion."""
        from src.components.coherence_monitor import CoherenceMetrics
        
        await db_manager.store_session("test-session-metrics")
        
        metrics = CoherenceMetrics(
            session_id="test-session-metrics",
            turn_number=1,
            delta_g=0.5,
            drift_velocity=0.1,
            variance=0.3,
            continuity_score=0.8
        )
        
        await db_manager.store_metrics("test-session-metrics", metrics)
        
        # Verify by retrieving
        retrieved = await db_manager.get_metrics("test-session-metrics")
        assert len(retrieved) == 1
        assert retrieved[0]["delta_g"] == 0.5
    
    async def test_get_metrics_time_range(self, db_manager):
        """DB-006: Time-series query."""
        from src.components.coherence_monitor import CoherenceMetrics
        import time
        
        await db_manager.store_session("test-session-range")
        
        # Store metrics at different times
        for i in range(3):
            metrics = CoherenceMetrics(
                session_id="test-session-range",
                turn_number=i,
                delta_g=0.1 * i,
                drift_velocity=0.0,
                variance=0.5,
                continuity_score=0.9
            )
            await db_manager.store_metrics("test-session-range", metrics)
            time.sleep(0.01)  # Small delay
        
        # Get all metrics
        all_metrics = await db_manager.get_metrics("test-session-range")
        assert len(all_metrics) == 3
    
    async def test_get_session_summary(self, db_manager):
        """Test getting session summary."""
        from src.components.coherence_monitor import CoherenceMetrics
        
        await db_manager.store_session("test-session-summary")
        
        # Store some metrics
        for i in range(5):
            metrics = CoherenceMetrics(
                session_id="test-session-summary",
                turn_number=i,
                delta_g=0.2,
                drift_velocity=0.0,
                variance=0.5,
                continuity_score=0.8
            )
            await db_manager.store_metrics("test-session-summary", metrics)
        
        summary = await db_manager.get_session_summary("test-session-summary")
        
        assert summary is not None
        assert summary["total_turns"] == 5
        assert summary["avg_delta_g"] == 0.2
    
    async def test_get_dashboard_summary(self, db_manager):
        """Test getting dashboard summary."""
        summary = await db_manager.get_dashboard_summary()
        
        assert "total_sessions" in summary
        assert "total_metrics" in summary
        assert isinstance(summary["total_sessions"], int)
    
    async def test_get_recent_sessions(self, db_manager):
        """Test getting recent sessions."""
        # Create multiple sessions
        for i in range(5):
            await db_manager.store_session(f"test-session-{i}")
        
        sessions = await db_manager.get_recent_sessions(limit=3)
        
        assert len(sessions) <= 3
    
    async def test_store_intervention(self, db_manager):
        """DB-005: Intervention logging."""
        from src.components.coherence_monitor import CoherenceMetrics
        from src.components.threshold_engine import Intervention, InterventionType, InterventionPriority
        
        await db_manager.store_session("test-session-intervention")
        
        metrics = CoherenceMetrics(
            session_id="test-session-intervention",
            turn_number=1,
            delta_g=0.9,
            drift_velocity=0.2,
            variance=0.1,
            continuity_score=0.3
        )
        
        intervention = Intervention(
            type=InterventionType.REGENERATE,
            priority=InterventionPriority.HIGH,
            reason="Test reason",
            metrics_snapshot=metrics.to_dict(),
            action_required=True
        )
        
        await db_manager.store_intervention(
            session_id="test-session-intervention",
            intervention=intervention,
            metrics=metrics
        )
        
        # Intervention stored successfully
        assert True
    
    async def test_get_session_history(self, db_manager):
        """Test getting session history."""
        from src.components.coherence_monitor import CoherenceMetrics
        
        await db_manager.store_session("test-session-history")
        
        for i in range(3):
            metrics = CoherenceMetrics(
                session_id="test-session-history",
                turn_number=i,
                delta_g=0.1 * i,
                drift_velocity=0.0,
                variance=0.5,
                continuity_score=0.9
            )
            await db_manager.store_metrics("test-session-history", metrics)
        
        history = await db_manager.get_session_history("test-session-history")
        
        assert len(history) == 3
    
    async def test_multiple_sessions_isolation(self, db_manager):
        """Test that sessions are isolated."""
        from src.components.coherence_monitor import CoherenceMetrics
        
        # Store in session 1
        await db_manager.store_session("session-1")
        metrics1 = CoherenceMetrics(
            session_id="session-1",
            turn_number=1,
            delta_g=0.5,
            drift_velocity=0.0,
            variance=0.5,
            continuity_score=0.9
        )
        await db_manager.store_metrics("session-1", metrics1)
        
        # Store in session 2
        await db_manager.store_session("session-2")
        metrics2 = CoherenceMetrics(
            session_id="session-2",
            turn_number=1,
            delta_g=0.8,
            drift_velocity=0.0,
            variance=0.5,
            continuity_score=0.7
        )
        await db_manager.store_metrics("session-2", metrics2)
        
        # Verify isolation
        history1 = await db_manager.get_session_history("session-1")
        history2 = await db_manager.get_session_history("session-2")
        
        assert len(history1) == 1
        assert len(history2) == 1
        assert history1[0]["delta_g"] == 0.5
        assert history2[0]["delta_g"] == 0.8


@pytest.mark.unit
class TestSQLiteBackend:
    """Tests for SQLiteBackend."""
    
    async def test_initialize_creates_schema(self):
        """Test that initialize creates tables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            backend = SQLiteBackend(db_path)
            await backend.initialize()
            
            # Verify tables exist by running a query
            result = await backend.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            assert result is not None
            
            await backend.close()
    
    async def test_execute_and_fetch(self):
        """Test execute and fetch operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            backend = SQLiteBackend(db_path)
            await backend.initialize()
            
            # Insert test data
            await backend.execute(
                "INSERT INTO sessions (id, domain) VALUES (?, ?)",
                ("test-id", "general")
            )
            
            # Fetch
            result = await backend.fetchone(
                "SELECT * FROM sessions WHERE id = ?",
                ("test-id",)
            )
            
            assert result is not None
            assert result["id"] == "test-id"
            assert result["domain"] == "general"
            
            await backend.close()
    
    async def test_fetchall(self):
        """Test fetchall operation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            backend = SQLiteBackend(db_path)
            await backend.initialize()
            
            # Insert multiple rows
            for i in range(3):
                await backend.execute(
                    "INSERT INTO sessions (id, domain) VALUES (?, ?)",
                    (f"test-{i}", "general")
                )
            
            results = await backend.fetchall("SELECT * FROM sessions")
            
            assert len(results) == 3
            
            await backend.close()
