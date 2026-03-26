"""Integration tests for Dashboard API."""

import pytest
import httpx
import asyncio
from src.api.dashboard import DashboardServer
from src.database.db_manager import DatabaseManager


@pytest.fixture
async def dashboard_server():
    """Create and start dashboard server."""
    db_manager = DatabaseManager(
        storage_type="sqlite",
        connection_string=":memory:"
    )
    await db_manager.initialize()
    
    server = DashboardServer(
        host="127.0.0.1",
        port=18080,  # Use different port to avoid conflicts
        db_manager=db_manager,
        auth_required=False,  # Disable auth for testing
        cors_origins=["*"]
    )
    
    await server.start()
    
    # Give server time to start
    await asyncio.sleep(0.5)
    
    yield server
    
    await server.stop()


@pytest.mark.integration
class TestDashboardAPI:
    """Tests for Dashboard API (DASH-001 to DASH-007)."""
    
    async def test_health_check(self, dashboard_server):
        """Test health check endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:18080/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "brain-guard-dashboard"
    
    async def test_dashboard_summary(self, dashboard_server):
        """DASH-004: System-wide summary endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:18080/api/v1/dashboard/summary")
            
            assert response.status_code == 200
            data = response.json()
            assert "total_sessions" in data
            assert "total_metrics" in data
    
    async def test_list_sessions(self, dashboard_server):
        """Test listing sessions endpoint."""
        # Create some sessions
        await dashboard_server.db_manager.store_session("session-1")
        await dashboard_server.db_manager.store_session("session-2")
        
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:18080/api/v1/sessions")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) >= 2
    
    async def test_get_session(self, dashboard_server):
        """Test getting specific session."""
        # Create session with metrics
        await dashboard_server.db_manager.store_session("test-session-specific")
        
        from src.components.coherence_monitor import CoherenceMetrics
        metrics = CoherenceMetrics(
            session_id="test-session-specific",
            turn_number=1,
            delta_g=0.5,
            drift_velocity=0.0,
            variance=0.5,
            continuity_score=0.8
        )
        await dashboard_server.db_manager.store_metrics("test-session-specific", metrics)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://127.0.0.1:18080/api/v1/sessions/test-session-specific"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == "test-session-specific"
            assert "summary" in data
    
    async def test_get_session_metrics(self, dashboard_server):
        """DASH-002: Get metrics for a session."""
        # Create session with metrics
        await dashboard_server.db_manager.store_session("test-session-metrics")
        
        from src.components.coherence_monitor import CoherenceMetrics
        for i in range(3):
            metrics = CoherenceMetrics(
                session_id="test-session-metrics",
                turn_number=i,
                delta_g=0.1 * i,
                drift_velocity=0.0,
                variance=0.5,
                continuity_score=0.9
            )
            await dashboard_server.db_manager.store_metrics("test-session-metrics", metrics)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://127.0.0.1:18080/api/v1/sessions/test-session-metrics/metrics"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 3
    
    async def test_get_current_metrics(self, dashboard_server):
        """DASH-001: Get current/live metrics for active session."""
        # Create session with metrics
        await dashboard_server.db_manager.store_session("test-session-current")
        
        from src.components.coherence_monitor import CoherenceMetrics
        metrics = CoherenceMetrics(
            session_id="test-session-current",
            turn_number=1,
            delta_g=0.5,
            drift_velocity=0.1,
            variance=0.3,
            continuity_score=0.8
        )
        await dashboard_server.db_manager.store_metrics("test-session-current", metrics)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://127.0.0.1:18080/api/v1/sessions/test-session-current/current"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == "test-session-current"
            assert "latest" in data
            assert "count" in data
    
    async def test_session_not_found(self, dashboard_server):
        """Test 404 for non-existent session."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://127.0.0.1:18080/api/v1/sessions/non-existent-session"
            )
            
            assert response.status_code == 404
    
    async def test_get_trends(self, dashboard_server):
        """Test trends endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://127.0.0.1:18080/api/v1/dashboard/trends?hours=24"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "period_hours" in data
            assert data["period_hours"] == 24
    
    async def test_get_alerts(self, dashboard_server):
        """Test alerts endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://127.0.0.1:18080/api/v1/dashboard/alerts"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)


@pytest.mark.integration
class TestDashboardAuth:
    """Tests for Dashboard authentication (DASH-005)."""
    
    async def test_auth_required(self):
        """Test that auth is required when enabled."""
        db_manager = DatabaseManager(
            storage_type="sqlite",
            connection_string=":memory:"
        )
        await db_manager.initialize()
        
        server = DashboardServer(
            host="127.0.0.1",
            port=18081,
            db_manager=db_manager,
            auth_required=True,
            auth_token="test-token-123"
        )
        
        await server.start()
        await asyncio.sleep(0.5)
        
        try:
            async with httpx.AsyncClient() as client:
                # Without auth - should fail
                response = await client.get("http://127.0.0.1:18081/api/v1/dashboard/summary")
                assert response.status_code == 401
                
                # With auth header - should succeed
                response = await client.get(
                    "http://127.0.0.1:18081/api/v1/dashboard/summary",
                    headers={"Authorization": "Bearer test-token-123"}
                )
                assert response.status_code == 200
                
                # With auth query param - should succeed
                response = await client.get(
                    "http://127.0.0.1:18081/api/v1/dashboard/summary?token=test-token-123"
                )
                assert response.status_code == 200
        finally:
            await server.stop()


@pytest.mark.integration
class TestDashboardCORS:
    """Tests for Dashboard CORS (DASH-006)."""
    
    async def test_cors_headers(self, dashboard_server):
        """Test CORS headers are present."""
        async with httpx.AsyncClient() as client:
            response = await client.options(
                "http://127.0.0.1:18080/api/v1/dashboard/summary",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET"
                }
            )
            
            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers
