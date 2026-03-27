"""Dashboard API - REST endpoints and SSE stream for real-time monitoring."""

import json
import logging
import time
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import os

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from ..database.db_manager import DatabaseManager, validate_limit, validate_session_id, validate_timestamp, ValidationError
from ..metrics import get_metrics_exporter

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple in-memory token bucket rate limiter per IP.
    100 requests per minute per IP.
    """
    
    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_second = requests_per_minute / 60.0
        self.buckets: Dict[str, Dict[str, Any]] = {}
        self.max_tokens = requests_per_minute
    
    def _get_bucket(self, client_ip: str) -> Dict[str, Any]:
        """Get or create token bucket for client IP."""
        now = time.time()
        
        if client_ip not in self.buckets:
            self.buckets[client_ip] = {
                "tokens": self.max_tokens,
                "last_update": now
            }
        
        return self.buckets[client_ip]
    
    def _cleanup_old_buckets(self) -> None:
        """Remove buckets older than 5 minutes to prevent memory leaks."""
        now = time.time()
        cutoff = now - 300  # 5 minutes
        
        stale_ips = [
            ip for ip, bucket in self.buckets.items()
            if bucket["last_update"] < cutoff
        ]
        
        for ip in stale_ips:
            del self.buckets[ip]
    
    def is_allowed(self, client_ip: str) -> bool:
        """
        Check if request is allowed and consume a token.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()
        bucket = self._get_bucket(client_ip)
        
        # Add tokens based on time elapsed
        elapsed = now - bucket["last_update"]
        bucket["tokens"] = min(
            self.max_tokens,
            bucket["tokens"] + (elapsed * self.tokens_per_second)
        )
        bucket["last_update"] = now
        
        # Check if we have tokens available
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        
        return False
    
    def get_retry_after(self, client_ip: str) -> int:
        """Get seconds until next token is available."""
        bucket = self._get_bucket(client_ip)
        if bucket["tokens"] >= 1:
            return 0
        
        # Time until next token
        return int((1 - bucket["tokens"]) / self.tokens_per_second) + 1


# Global rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=100)


class DashboardServer:
    """
    Dashboard API Server
    
    Provides:
    - REST endpoints for real-time and historical data
    - SSE stream for live updates
    - Health check endpoint
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        db_manager: Optional[DatabaseManager] = None,
        auth_required: bool = True,
        auth_token: str = "",
        cors_origins: Optional[List[str]] = None
    ):
        self.host = host
        self.port = port
        self.db_manager = db_manager
        self.auth_required = auth_required
        self.auth_token = auth_token or self._generate_token()
        self.cors_origins = cors_origins or ["http://localhost:3000"]
        
        self._app: Optional[FastAPI] = None
        self._server_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # SSE subscribers
        self._subscribers: List[asyncio.Queue] = []
    
    def _generate_token(self) -> str:
        """Generate a random auth token."""
        import secrets
        return secrets.token_urlsafe(32)
    
    def _create_app(self) -> FastAPI:
        """Create FastAPI application."""
        # Initialize rate limiter (slowapi for additional protection)
        limiter = Limiter(key_func=get_remote_address)
        
        app = FastAPI(
            title="Brain Guard Dashboard API",
            description="Real-time coherence monitoring dashboard",
            version="1.0.0"
        )
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Rate limiting middleware (in-memory token bucket)
        @app.middleware("http")
        async def rate_limit_middleware(request: Request, call_next):
            # Skip rate limiting for health endpoint
            if request.url.path == "/health":
                return await call_next(request)
            
            # Get client IP
            client_ip = request.client.host if request.client else "unknown"
            
            # Cleanup old buckets periodically
            if len(rate_limiter.buckets) > 1000:
                rate_limiter._cleanup_old_buckets()
            
            # Check rate limit
            if not rate_limiter.is_allowed(client_ip):
                retry_after = rate_limiter.get_retry_after(client_ip)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "retry_after": retry_after,
                        "limit": f"{rate_limiter.requests_per_minute} requests per minute"
                    },
                    headers={"Retry-After": str(retry_after)}
                )
            
            return await call_next(request)
        
        # Auth dependency
        async def verify_token(request: Request) -> bool:
            if not self.auth_required:
                return True
            
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                return token == self.auth_token
            
            # Also check query param
            token = request.query_params.get("token")
            return token == self.auth_token
        
        # Static files directory
        static_dir = os.path.join(os.path.dirname(__file__), "dashboard_static")
        if os.path.exists(static_dir):
            app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/")
        async def root():
            """Serve the dashboard HTML."""
            index_path = os.path.join(static_dir, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            raise HTTPException(status_code=404, detail="Dashboard not found")

        @app.get("/health")
        @limiter.limit("60/minute")
        async def health_check(request: Request) -> Dict[str, Any]:
            """Health check endpoint."""
            return {
                "status": "healthy",
                "service": "brain-guard-dashboard",
                "version": "1.0.0"
            }
        
        @app.get("/api/v1/dashboard/summary")
        @limiter.limit("30/minute")
        async def get_dashboard_summary(
            request: Request,
            authorized: bool = Depends(verify_token)
        ) -> Dict[str, Any]:
            """Get system-wide summary statistics."""
            if not authorized:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            if not self.db_manager:
                return {"error": "Database not available"}
            
            return await self.db_manager.get_dashboard_summary()
        
        @app.get("/api/v1/sessions")
        @limiter.limit("30/minute")
        async def list_sessions(
            request: Request,
            limit: int = 100,
            authorized: bool = Depends(verify_token)
        ) -> List[Dict[str, Any]]:
            """List recent sessions."""
            if not authorized:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            if not self.db_manager:
                return []
            
            # Validate limit parameter
            try:
                validated_limit = validate_limit(limit)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=str(e))
            
            return await self.db_manager.get_recent_sessions(validated_limit)
        
        @app.get("/api/v1/sessions/{session_id}")
        @limiter.limit("60/minute")
        async def get_session(
            request: Request,
            session_id: str,
            authorized: bool = Depends(verify_token)
        ) -> Dict[str, Any]:
            """Get session details."""
            if not authorized:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            if not self.db_manager:
                raise HTTPException(status_code=503, detail="Database not available")
            
            # Validate session_id
            try:
                validate_session_id(session_id)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=str(e))
            
            summary = await self.db_manager.get_session_summary(session_id)
            if not summary:
                raise HTTPException(status_code=404, detail="Session not found")
            
            return {
                "session_id": session_id,
                "summary": summary
            }
        
        @app.get("/api/v1/sessions/{session_id}/metrics")
        @limiter.limit("60/minute")
        async def get_session_metrics(
            request: Request,
            session_id: str,
            start_time: Optional[float] = None,
            end_time: Optional[float] = None,
            authorized: bool = Depends(verify_token)
        ) -> List[Dict[str, Any]]:
            """Get metrics for a session."""
            if not authorized:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            if not self.db_manager:
                return []
            
            # Validate session_id
            try:
                validate_session_id(session_id)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=str(e))
            
            # Validate timestamp parameters if provided
            try:
                if start_time is not None:
                    validate_timestamp(start_time, "start_time")
                if end_time is not None:
                    validate_timestamp(end_time, "end_time")
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=str(e))
            
            return await self.db_manager.get_metrics(session_id, start_time, end_time)
        
        @app.get("/api/v1/sessions/{session_id}/current")
        @limiter.limit("60/minute")
        async def get_current_metrics(
            request: Request,
            session_id: str,
            authorized: bool = Depends(verify_token)
        ) -> Dict[str, Any]:
            """Get current/live metrics for a session."""
            if not authorized:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            if not self.db_manager:
                raise HTTPException(status_code=503, detail="Database not available")
            
            # Validate session_id
            try:
                validate_session_id(session_id)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=str(e))
            
            # Get latest metrics
            metrics = await self.db_manager.get_metrics(session_id)
            if not metrics:
                raise HTTPException(status_code=404, detail="No metrics found")
            
            return {
                "session_id": session_id,
                "latest": metrics[-1],
                "count": len(metrics)
            }
        
        @app.get("/api/v1/sessions/{session_id}/stream")
        @limiter.limit("10/minute")
        async def stream_metrics(
            request: Request,
            session_id: str,
            authorized: bool = Depends(verify_token)
        ) -> StreamingResponse:
            """SSE stream of real-time metrics."""
            if not authorized:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            # Validate session_id
            try:
                validate_session_id(session_id)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=str(e))
            
            async def event_generator():
                queue: asyncio.Queue = asyncio.Queue()
                self._subscribers.append(queue)
                
                try:
                    while not self._shutdown_event.is_set():
                        try:
                            # Wait for data with timeout
                            data = await asyncio.wait_for(queue.get(), timeout=30)
                            
                            # Filter for this session
                            if data.get("session_id") == session_id:
                                yield f"data: {json.dumps(data)}\n\n"
                        except asyncio.TimeoutError:
                            # Send keepalive
                            yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
                finally:
                    if queue in self._subscribers:
                        self._subscribers.remove(queue)
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        
        @app.get("/api/v1/sessions/{session_id}/interventions")
        @limiter.limit("30/minute")
        async def get_interventions(
            request: Request,
            session_id: str,
            authorized: bool = Depends(verify_token)
        ) -> List[Dict[str, Any]]:
            """Get interventions for a session."""
            if not authorized:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            # Validate session_id
            try:
                validate_session_id(session_id)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=str(e))
            
            # This would query the database for interventions
            # Implementation depends on db_manager capabilities
            return []
        
        @app.get("/api/v1/dashboard/trends")
        @limiter.limit("20/minute")
        async def get_trends(
            request: Request,
            hours: int = 24,
            authorized: bool = Depends(verify_token)
        ) -> Dict[str, Any]:
            """Get coherence trends over time."""
            if not authorized:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            # Placeholder for trend analysis
            return {
                "period_hours": hours,
                "trends": []
            }
        
        @app.get("/api/v1/dashboard/alerts")
        @limiter.limit("30/minute")
        async def get_active_alerts(
            request: Request,
            authorized: bool = Depends(verify_token)
        ) -> List[Dict[str, Any]]:
            """Get active threshold violations."""
            if not authorized:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            # Placeholder for active alerts
            return []
        
        @app.get("/metrics")
        @limiter.limit("60/minute")
        async def get_prometheus_metrics(request: Request) -> Response:
            """Prometheus metrics endpoint."""
            exporter = get_metrics_exporter()
            return Response(
                content=exporter.get_metrics(),
                media_type=exporter.get_content_type()
            )
        
        return app
    
    async def start(self) -> None:
        """Start the dashboard server."""
        import uvicorn
        
        if self._app is None:
            self._app = self._create_app()
        
        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        self._server_task = asyncio.create_task(server.serve())
        
        logger.info(f"Dashboard server started on http://{self.host}:{self.port}")
        logger.info(f"Auth token configured: {'yes' if self.auth_token else 'no'}")
    
    async def stop(self) -> None:
        """Stop the dashboard server."""
        self._shutdown_event.set()
        
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Dashboard server stopped")
    
    async def broadcast_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        Broadcast metrics to all SSE subscribers.
        
        Args:
            metrics: Metrics dictionary to broadcast
        """
        for queue in self._subscribers:
            try:
                queue.put_nowait(metrics)
            except asyncio.QueueFull:
                # Remove full queues
                self._subscribers.remove(queue)
