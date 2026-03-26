"""Database Manager - SQLite/PostgreSQL support with connection pooling."""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Raised when input validation fails."""
    pass


def validate_limit(limit: int, max_limit: int = 1000) -> int:
    """
    Validate limit parameter.
    
    Args:
        limit: The limit value to validate
        max_limit: Maximum allowed limit (default 1000)
        
    Returns:
        Validated limit value
        
    Raises:
        ValidationError: If limit is invalid
    """
    if not isinstance(limit, int):
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            raise ValidationError(f"Limit must be a positive integer, got: {limit}")
    
    if limit < 1:
        raise ValidationError(f"Limit must be positive, got: {limit}")
    
    if limit > max_limit:
        raise ValidationError(f"Limit exceeds maximum of {max_limit}, got: {limit}")
    
    return limit


def validate_session_id(session_id: str) -> str:
    """
    Validate session_id parameter.
    
    Args:
        session_id: The session ID to validate
        
    Returns:
        Validated session_id
        
    Raises:
        ValidationError: If session_id is invalid
    """
    if not isinstance(session_id, str):
        raise ValidationError(f"Session ID must be a string, got: {type(session_id).__name__}")
    
    if not session_id:
        raise ValidationError("Session ID cannot be empty")
    
    if len(session_id) > 64:
        raise ValidationError(f"Session ID exceeds maximum length of 64 characters, got: {len(session_id)}")
    
    # Alphanumeric only (plus underscore and hyphen for flexibility)
    if not re.match(r'^[a-zA-Z0-9_-]+$', session_id):
        raise ValidationError(f"Session ID must be alphanumeric (with underscores/hyphens allowed), got: {session_id}")
    
    return session_id


def validate_timestamp(timestamp: Any, param_name: str = "timestamp") -> float:
    """
    Validate timestamp parameter.
    
    Args:
        timestamp: The timestamp to validate
        param_name: Name of the parameter for error messages
        
    Returns:
        Validated timestamp as float
        
    Raises:
        ValidationError: If timestamp is invalid
    """
    if timestamp is None:
        raise ValidationError(f"{param_name} cannot be None")
    
    try:
        ts = float(timestamp)
    except (ValueError, TypeError):
        raise ValidationError(f"{param_name} must be a valid float timestamp, got: {timestamp}")
    
    # Basic sanity check: timestamps should be positive and not unreasonably large
    if ts < 0:
        raise ValidationError(f"{param_name} must be non-negative, got: {ts}")
    
    # Upper bound: year 2100 in Unix timestamp
    if ts > 4102444800:
        raise ValidationError(f"{param_name} is unreasonably large, got: {ts}")
    
    return ts

# Import aiosqlite for async SQLite operations
try:
    import aiosqlite
except ImportError:
    aiosqlite = None
    logger.warning("aiosqlite not installed. SQLite backend will not work.")


class DatabaseBackend(ABC):
    """Abstract database backend."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize database schema."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close database connection."""
        pass
    
    @abstractmethod
    async def execute(self, query: str, params: tuple = ()) -> None:
        """Execute a query."""
        pass
    
    @abstractmethod
    async def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Fetch a single row."""
        pass
    
    @abstractmethod
    async def fetchall(self, query: str, params: tuple = ()) -> List[Dict]:
        """Fetch all rows."""
        pass


class SQLiteBackend(DatabaseBackend):
    """SQLite database backend using aiosqlite for true async operations."""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def initialize(self) -> None:
        """Initialize SQLite database."""
        if aiosqlite is None:
            raise RuntimeError(
                "aiosqlite is not installed. "
                "Install it with: pip install aiosqlite>=0.20.0"
            )
        
        # Expand path and create directory if needed
        path = Path(self.connection_string).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open connection with aiosqlite (truly async)
        self._connection = await aiosqlite.connect(str(path))
        self._connection.row_factory = aiosqlite.Row
        
        await self._create_schema()
        logger.info(f"SQLite database initialized: {path}")
    
    async def _create_schema(self) -> None:
        """Create database schema."""
        # Sessions table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                domain TEXT DEFAULT 'general',
                status TEXT DEFAULT 'active',
                created_at REAL DEFAULT (unixepoch()),
                updated_at REAL DEFAULT (unixepoch()),
                metadata TEXT
            )
        """)
        
        # Metrics table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                turn_number INTEGER NOT NULL,
                delta_g REAL,
                drift_velocity REAL,
                variance REAL,
                continuity_score REAL,
                processing_time_ms REAL,
                embedding_time_ms REAL,
                timestamp REAL DEFAULT (unixepoch()),
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        
        # Anchors table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS anchors (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                text TEXT NOT NULL,
                anchor_type TEXT,
                confidence REAL,
                timestamp REAL,
                is_active INTEGER DEFAULT 1,
                reference_count INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        
        # Interventions table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS interventions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                type TEXT,
                priority TEXT,
                reason TEXT,
                message TEXT,
                action_required INTEGER,
                metrics_snapshot TEXT,
                timestamp REAL DEFAULT (unixepoch()),
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        
        # Threshold violations table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS threshold_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                violation_type TEXT,
                threshold_value REAL,
                actual_value REAL,
                timestamp REAL DEFAULT (unixepoch()),
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_session ON metrics(session_id)"
        )
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)"
        )
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_anchors_session ON anchors(session_id)"
        )
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_interventions_session ON interventions(session_id)"
        )
        
        await self._connection.commit()
    
    async def close(self) -> None:
        """Close SQLite connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
    
    async def execute(self, query: str, params: tuple = ()) -> None:
        """Execute a query."""
        await self._connection.execute(query, params)
        await self._connection.commit()
    
    async def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Fetch a single row."""
        async with self._connection.execute(query, params) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    async def fetchall(self, query: str, params: tuple = ()) -> List[Dict]:
        """Fetch all rows."""
        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


class DatabaseManager:
    """
    Database Manager
    
    Manages database connections and provides high-level operations.
    """
    
    def __init__(self, storage_type: str = "sqlite", connection_string: str = ""):
        self.storage_type = storage_type
        self.connection_string = connection_string or "~/.openclaw/brain_guard.db"
        self._backend: Optional[DatabaseBackend] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the database."""
        if self._initialized:
            return
        
        if self.storage_type == "sqlite":
            self._backend = SQLiteBackend(self.connection_string)
        elif self.storage_type == "postgresql":
            # PostgreSQL support would be implemented here
            raise NotImplementedError("PostgreSQL support not yet implemented")
        else:
            raise ValueError(f"Unknown storage type: {self.storage_type}")
        
        await self._backend.initialize()
        self._initialized = True
    
    async def close(self) -> None:
        """Close database connection."""
        if self._backend:
            await self._backend.close()
            self._initialized = False
    
    async def store_session(
        self,
        session_id: str,
        domain: str = "general",
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Store or update session information.
        
        Args:
            session_id: Unique session ID
            domain: Conversation domain
            metadata: Optional metadata dict
        """
        if not self._initialized:
            return
        
        import time
        
        # Check if session exists
        existing = await self._backend.fetchone(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,)
        )
        
        if existing:
            await self._backend.execute(
                """UPDATE sessions 
                   SET domain = ?, updated_at = ?, metadata = ?
                   WHERE id = ?""",
                (domain, time.time(), json.dumps(metadata or {}), session_id)
            )
        else:
            await self._backend.execute(
                """INSERT INTO sessions (id, domain, metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, domain, json.dumps(metadata or {}), time.time(), time.time())
            )
    
    async def update_session_status(
        self,
        session_id: str,
        status: str
    ) -> None:
        """Update session status."""
        if not self._initialized:
            return
        
        import time
        
        await self._backend.execute(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            (status, time.time(), session_id)
        )
    
    async def store_metrics(self, session_id: str, metrics: Any) -> None:
        """
        Store coherence metrics.
        
        Args:
            session_id: Session ID
            metrics: CoherenceMetrics object
        """
        if not self._initialized:
            return
        
        # Handle both old and new metrics objects (embedding_time_ms may not exist)
        embedding_time_ms = getattr(metrics, 'embedding_time_ms', 0.0)
        
        await self._backend.execute(
            """INSERT INTO metrics 
               (session_id, turn_number, delta_g, drift_velocity, variance, 
                continuity_score, processing_time_ms, embedding_time_ms, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                metrics.turn_number,
                metrics.delta_g,
                metrics.drift_velocity,
                metrics.variance,
                metrics.continuity_score,
                metrics.processing_time_ms,
                embedding_time_ms,
                metrics.timestamp
            )
        )
    
    async def store_intervention(
        self,
        session_id: str,
        intervention: Any,
        metrics: Any
    ) -> None:
        """
        Store intervention record.
        
        Args:
            session_id: Session ID
            intervention: Intervention object
            metrics: CoherenceMetrics object
        """
        if not self._initialized:
            return
        
        await self._backend.execute(
            """INSERT INTO interventions
               (session_id, type, priority, reason, message, action_required, metrics_snapshot)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                intervention.type.value,
                intervention.priority.name,
                intervention.reason,
                intervention.message,
                1 if intervention.action_required else 0,
                json.dumps(metrics.to_dict())
            )
        )
    
    async def get_session_history(self, session_id: str) -> List[Dict]:
        """
        Get session history.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of previous responses/metrics
            
        Raises:
            ValidationError: If session_id is invalid
        """
        if not self._initialized:
            return []
        
        # Validate session_id
        validate_session_id(session_id)
        
        return await self._backend.fetchall(
            """SELECT * FROM metrics 
               WHERE session_id = ? 
               ORDER BY turn_number ASC""",
            (session_id,)
        )
    
    async def get_metrics(
        self,
        session_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Dict]:
        """
        Get metrics for a session with optional time range.
        
        Args:
            session_id: Session ID
            start_time: Optional start timestamp
            end_time: Optional end timestamp
            
        Returns:
            List of metrics
            
        Raises:
            ValidationError: If input parameters are invalid
        """
        if not self._initialized:
            return []
        
        # Validate session_id
        validate_session_id(session_id)
        
        query = "SELECT * FROM metrics WHERE session_id = ?"
        params: List[Any] = [session_id]
        
        if start_time is not None:
            validate_timestamp(start_time, "start_time")
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time is not None:
            validate_timestamp(end_time, "end_time")
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        query += " ORDER BY timestamp ASC"
        
        return await self._backend.fetchall(query, tuple(params))
    
    async def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """
        Get summary statistics for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Summary dict or None
            
        Raises:
            ValidationError: If session_id is invalid
        """
        if not self._initialized:
            return None
        
        # Validate session_id
        validate_session_id(session_id)
        
        result = await self._backend.fetchone(
            """SELECT 
                COUNT(*) as total_turns,
                AVG(delta_g) as avg_delta_g,
                MAX(delta_g) as max_delta_g,
                AVG(continuity_score) as avg_continuity,
                AVG(processing_time_ms) as avg_processing_time
               FROM metrics 
               WHERE session_id = ?""",
            (session_id,)
        )
        
        if result:
            # Get intervention count
            intervention_count = await self._backend.fetchone(
                "SELECT COUNT(*) as count FROM interventions WHERE session_id = ?",
                (session_id,)
            )
            
            result['intervention_count'] = intervention_count['count'] if intervention_count else 0
        
        return result
    
    async def get_dashboard_summary(self) -> Dict:
        """
        Get system-wide dashboard summary.
        
        Returns:
            Summary statistics
        """
        if not self._initialized:
            return {}
        
        # Total sessions
        sessions_result = await self._backend.fetchone(
            "SELECT COUNT(*) as count FROM sessions"
        )
        
        # Active sessions (updated in last hour)
        import time
        hour_ago = time.time() - 3600
        active_result = await self._backend.fetchone(
            "SELECT COUNT(*) as count FROM sessions WHERE updated_at > ?",
            (hour_ago,)
        )
        
        # Total metrics
        metrics_result = await self._backend.fetchone(
            "SELECT COUNT(*) as count FROM metrics"
        )
        
        # Total interventions
        interventions_result = await self._backend.fetchone(
            "SELECT COUNT(*) as count FROM interventions"
        )
        
        # Recent violations (last hour)
        violations_result = await self._backend.fetchone(
            "SELECT COUNT(*) as count FROM threshold_violations WHERE timestamp > ?",
            (hour_ago,)
        )
        
        return {
            "total_sessions": sessions_result['count'] if sessions_result else 0,
            "active_sessions_last_hour": active_result['count'] if active_result else 0,
            "total_metrics": metrics_result['count'] if metrics_result else 0,
            "total_interventions": interventions_result['count'] if interventions_result else 0,
            "recent_violations": violations_result['count'] if violations_result else 0
        }
    
    async def get_recent_sessions(self, limit: int = 100) -> List[Dict]:
        """
        Get recent sessions.
        
        Args:
            limit: Maximum number of sessions
            
        Returns:
            List of session records
            
        Raises:
            ValidationError: If limit is invalid
        """
        if not self._initialized:
            return []
        
        # Validate limit parameter
        validated_limit = validate_limit(limit)
        
        return await self._backend.fetchall(
            """SELECT * FROM sessions 
               ORDER BY updated_at DESC 
               LIMIT ?""",
            (validated_limit,)
        )
