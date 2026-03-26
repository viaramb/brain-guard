-- Brain Guard Database Schema (formerly SCFL-Observatory)
-- Supports SQLite and PostgreSQL

-- Enable UUID extension for PostgreSQL
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- CORE TABLES
-- =====================================================

-- Sessions table: Tracks conversation sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,  -- UUID or OpenClaw session key
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT,
    channel_id TEXT,
    mode TEXT DEFAULT 'light',  -- light, full, strict
    status TEXT DEFAULT 'active',  -- active, paused, closed
    total_turns INTEGER DEFAULT 0,
    total_interventions INTEGER DEFAULT 0,
    avg_coherence_score REAL,
    metadata JSON  -- Flexible metadata storage
);

-- Metrics table: Time-series coherence measurements
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Use SERIAL for PostgreSQL
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Core SCFL metrics
    delta_g REAL,  -- Coherence deformation (0-1)
    drift_velocity REAL,  -- Rate of change in delta_g
    variance_collapse REAL,  -- Variance in embedding window
    continuity_score REAL,  -- Overall continuity (0-1)
    recoverability_score REAL,  -- Probability of recovery (0-1)
    
    -- Derived metrics
    anchor_count INTEGER,
    contradiction_detected BOOLEAN DEFAULT FALSE,
    ambiguity_score REAL,  -- Input ambiguity (0-1)
    
    -- Performance metrics
    processing_time_ms INTEGER,
    embedding_model TEXT,
    
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Anchors table: Extracted session anchors (facts, procedures, etc.)
CREATE TABLE IF NOT EXISTS anchors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    anchor_type TEXT NOT NULL,  -- factual, procedural, contextual, temporal
    content TEXT NOT NULL,  -- The anchor text
    embedding BLOB,  -- Vector embedding (optional, for similarity search)
    confidence REAL DEFAULT 1.0,  -- Extraction confidence (0-1)
    turn_created INTEGER NOT NULL,
    turn_last_referenced INTEGER,
    reference_count INTEGER DEFAULT 1,
    contradicted_by INTEGER,  -- ID of anchor that contradicts this one
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (contradicted_by) REFERENCES anchors(id)
);

-- Interventions table: Recorded intervention actions
CREATE TABLE IF NOT EXISTS interventions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    intervention_type TEXT NOT NULL,  -- silent, flag, regenerate, fallback, halt
    trigger_condition TEXT NOT NULL,  -- Which threshold was crossed
    threshold_value REAL,  -- The threshold that triggered
    actual_value REAL,  -- The actual metric value
    
    -- Intervention details
    description TEXT,
    user_visible BOOLEAN DEFAULT FALSE,
    user_response TEXT,  -- How user responded (if applicable)
    was_successful BOOLEAN,  -- Did intervention resolve the issue?
    
    -- Performance
    processing_time_ms INTEGER,
    
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Threshold violations table: Alert history
CREATE TABLE IF NOT EXISTS threshold_violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,  -- delta_g, drift_velocity, etc.
    threshold_type TEXT NOT NULL,  -- warning, alert, critical
    threshold_value REAL NOT NULL,
    actual_value REAL NOT NULL,
    turn_number INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    was_intervened BOOLEAN DEFAULT FALSE,
    intervention_id INTEGER,
    
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (intervention_id) REFERENCES interventions(id)
);

-- =====================================================
-- DASHBOARD TABLES
-- =====================================================

-- Aggregated daily statistics (for trend analysis)
CREATE TABLE IF NOT EXISTS daily_stats (
    date DATE PRIMARY KEY,
    total_sessions INTEGER DEFAULT 0,
    total_turns INTEGER DEFAULT 0,
    avg_coherence_score REAL,
    avg_delta_g REAL,
    avg_drift_velocity REAL,
    total_interventions INTEGER DEFAULT 0,
    intervention_rate REAL,  -- interventions / turns
    rupture_count INTEGER DEFAULT 0,
    false_positive_rate REAL,
    p50_latency_ms INTEGER,
    p95_latency_ms INTEGER,
    p99_latency_ms INTEGER
);

-- System health checks
CREATE TABLE IF NOT EXISTS health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    check_type TEXT NOT NULL,  -- db_connection, latency, embedding_service
    status TEXT NOT NULL,  -- ok, warning, critical
    response_time_ms INTEGER,
    error_message TEXT,
    details JSON
);

-- =====================================================
-- INDEXES
-- =====================================================

-- For fast session lookups
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);

-- For time-series queries
CREATE INDEX IF NOT EXISTS idx_metrics_session_turn ON metrics(session_id, turn_number);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_metrics_session_time ON metrics(session_id, timestamp);

-- For anchor queries
CREATE INDEX IF NOT EXISTS idx_anchors_session ON anchors(session_id);
CREATE INDEX IF NOT EXISTS idx_anchors_type ON anchors(anchor_type);
CREATE INDEX IF NOT EXISTS idx_anchors_active ON anchors(session_id, is_active);

-- For intervention analysis
CREATE INDEX IF NOT EXISTS idx_interventions_session ON interventions(session_id);
CREATE INDEX IF NOT EXISTS idx_interventions_type ON interventions(intervention_type);
CREATE INDEX IF NOT EXISTS idx_interventions_success ON interventions(was_successful);

-- For violation tracking
CREATE INDEX IF NOT EXISTS idx_violations_session ON threshold_violations(session_id);
CREATE INDEX IF NOT EXISTS idx_violations_metric ON threshold_violations(metric_name);

-- =====================================================
-- VIEWS
-- =====================================================

-- Current session status view
CREATE VIEW IF NOT EXISTS v_session_current_status AS
SELECT 
    s.id as session_id,
    s.status,
    s.total_turns,
    s.total_interventions,
    m.delta_g as last_delta_g,
    m.drift_velocity as last_drift_v,
    m.continuity_score as last_continuity,
    m.timestamp as last_metric_time,
    (SELECT COUNT(*) FROM anchors WHERE session_id = s.id AND is_active = TRUE) as active_anchors,
    (SELECT COUNT(*) FROM threshold_violations WHERE session_id = s.id AND timestamp > datetime('now', '-1 hour')) as recent_violations
FROM sessions s
LEFT JOIN metrics m ON s.id = m.session_id
WHERE m.turn_number = (SELECT MAX(turn_number) FROM metrics WHERE session_id = s.id)
   OR m.turn_number IS NULL;

-- Intervention effectiveness view
CREATE VIEW IF NOT EXISTS v_intervention_effectiveness AS
SELECT 
    intervention_type,
    trigger_condition,
    COUNT(*) as total_count,
    SUM(CASE WHEN was_successful = TRUE THEN 1 ELSE 0 END) as success_count,
    ROUND(100.0 * SUM(CASE WHEN was_successful = TRUE THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate,
    AVG(processing_time_ms) as avg_processing_time
FROM interventions
GROUP BY intervention_type, trigger_condition;

-- Coherence trend view (last 24 hours)
CREATE VIEW IF NOT EXISTS v_coherence_trend_24h AS
SELECT 
    strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
    AVG(delta_g) as avg_delta_g,
    AVG(continuity_score) as avg_continuity,
    AVG(recoverability_score) as avg_recoverability,
    COUNT(*) as metric_count
FROM metrics
WHERE timestamp > datetime('now', '-24 hours')
GROUP BY hour
ORDER BY hour;

-- =====================================================
-- MAINTENANCE PROCEDURES
-- =====================================================

-- Procedure to archive old data (run daily)
-- For SQLite:
CREATE TRIGGER IF NOT EXISTS archive_old_metrics
AFTER INSERT ON metrics
BEGIN
    DELETE FROM metrics 
    WHERE timestamp < datetime('now', '-30 days');
END;

-- Note: For PostgreSQL, use a cron job or pg_cron instead:
-- DELETE FROM metrics WHERE timestamp < NOW() - INTERVAL '30 days';

-- Procedure to update session statistics
CREATE TRIGGER IF NOT EXISTS update_session_stats
AFTER INSERT ON metrics
BEGIN
    UPDATE sessions 
    SET total_turns = NEW.turn_number,
        updated_at = CURRENT_TIMESTAMP,
        avg_coherence_score = (
            SELECT AVG(continuity_score) 
            FROM metrics 
            WHERE session_id = NEW.session_id
        )
    WHERE id = NEW.session_id;
END;

-- =====================================================
-- INITIAL DATA
-- =====================================================

-- Default configuration (can be overridden)
INSERT OR IGNORE INTO daily_stats (date) VALUES (date('now'));
