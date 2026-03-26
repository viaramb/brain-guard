# Brain Guard Plugin

A comprehensive implementation of the Brain Guard plugin for OpenClaw, implementing the SCFL-Quad coherence monitoring framework.

## Project Structure

```
brain-guard/
├── src/                          # Source code
│   ├── __init__.py              # Main plugin entry point
│   ├── components/              # Core components
│   │   ├── preprocessor.py      # Layer 1: Input Conditioning
│   │   ├── coherence_monitor.py # Layer 3: Coherence Monitor
│   │   ├── threshold_engine.py  # Layer 4: Threshold Engine
│   │   ├── session_anchoring.py # Session Anchoring System
│   │   └── domain_detector.py   # Domain Detection
│   ├── database/
│   │   └── db_manager.py        # Database layer (SQLite/PostgreSQL)
│   ├── api/
│   │   └── dashboard.py         # Dashboard API (REST + SSE)
│   └── utils/
│       ├── config.py            # Configuration management
│       └── embedding_service.py # Embedding service with caching
├── tests/
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   ├── fixtures/                # Test fixtures
│   ├── mocks/                   # Mock implementations
│   └── conftest.py              # Pytest configuration
├── config/
│   ├── domains.yml              # Domain configurations
│   ├── schema.json              # JSON schema for config validation
│   └── brain-guard.example.yml  # Example configuration
├── ARCHITECTURE.md              # Architecture documentation
├── TEST_PLAN.md                 # Test plan
├── README.md                    # This file
├── requirements.txt             # Dependencies
├── pyproject.toml               # Project configuration
└── pytest.ini                 # Pytest configuration
```

## Implementation Summary

### 1. Core Plugin Structure (`src/__init__.py`)
- Main `BrainGuardPlugin` class
- OpenClaw integration hooks
- Environment variable support (`BRAIN_GUARD_ENABLED`)
- Hot-reload capability

### 2. Core Components

#### Preprocessor (`src/components/preprocessor.py`)
- Input segmentation into semantic units
- Ambiguity scoring (0-1 scale)
- Constraint injection based on session anchors
- Operator tag extraction (code blocks, URLs)

#### Coherence Monitor (`src/components/coherence_monitor.py`)
- ΔG calculation (coherence deformation)
- Vd calculation (drift velocity)
- σ²c calculation (variance collapse)
- Continuity score computation
- Session-based metric tracking

#### Threshold Engine (`src/components/threshold_engine.py`)
- Trigger evaluation against thresholds
- Intervention decision logic
- Domain-specific threshold overrides
- Multiple operating modes (silent, warn, strict, adaptive)

#### Session Anchoring (`src/components/session_anchoring.py`)
- Anchor extraction (factual, procedural, contextual, temporal)
- Contradiction detection
- Reference counting
- Anchor limit enforcement

#### Domain Detector (`src/components/domain_detector.py`)
- Keyword-based domain detection
- Priority-based conflict resolution
- Cross-domain pattern detection
- Configurable via `domains.yml`

### 3. Database Layer (`src/database/db_manager.py`)
- SQLite support (with PostgreSQL placeholder)
- Connection pooling
- Schema management
- Metric storage and retrieval
- Session management

### 4. Dashboard API (`src/api/dashboard.py`)
- FastAPI-based REST endpoints
- SSE stream for real-time updates
- Health check endpoint
- Authentication support
- CORS support

### 5. Configuration (`src/utils/config.py`)
- YAML/JSON config file support
- Environment variable overrides
- JSON schema validation
- Default configurations

### 6. Testing Suite

#### Unit Tests (11 files, 80+ test cases)
- `test_preprocessor.py` - Input conditioning tests
- `test_coherence_monitor.py` - Metric calculation tests
- `test_threshold_engine.py` - Intervention logic tests
- `test_session_anchoring.py` - Anchor extraction tests
- `test_domain_detector.py` - Domain detection tests
- `test_config.py` - Configuration tests
- `test_embedding_service.py` - Embedding service tests
- `test_database.py` - Database layer tests
- `test_plugin.py` - Main plugin tests

#### Integration Tests (4 files)
- `test_pipeline.py` - Full pipeline tests
- `test_dashboard.py` - Dashboard API tests
- `test_gateway.py` - OpenClaw gateway integration
- `test_e2e.py` - End-to-end conversation tests

#### Test Coverage
- Unit tests: ~80% coverage target
- Integration tests: Critical paths
- E2E tests: Real conversation scenarios
- Mock embedding service for deterministic testing

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BRAIN_GUARD_ENABLED` | Enable/disable plugin | `false` |
| `BRAIN_GUARD_MODE` | Operating mode | `adaptive` |
| `BRAIN_GUARD_CONFIG_PATH` | Config file path | Auto-detect |
| `BRAIN_GUARD_DB_URL` | Database connection string | `~/.openclaw/brain_guard.db` |
| `BRAIN_GUARD_DASHBOARD_PORT` | Dashboard port | `8080` |
| `BRAIN_GUARD_LOG_LEVEL` | Log level | `info` |

## Usage

```python
from src import BrainGuardPlugin

# Initialize
plugin = BrainGuardPlugin()
await plugin.initialize()

# Preprocess message
result = await plugin.preprocess_message(
    session_id="session-123",
    user_message="Tell me about Python"
)

# Monitor response
metrics = await plugin.monitor_response(
    session_id="session-123",
    response="Python is a programming language...",
    metadata=result["metadata"]
)

# Cleanup
await plugin.close_session("session-123")
await plugin.shutdown()
```

## Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run unit tests
pytest tests/unit -v

# Run integration tests
pytest tests/integration -v

# Run all tests with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test
pytest tests/unit/test_coherence_monitor.py -v
```

## Key Features

1. **Non-invasive**: Hooks into message flow without changing model behavior
2. **Lightweight**: Target latency <50ms per check
3. **Gated**: Escalates monitoring based on conversation risk profile
4. **Observable**: Full metrics dashboard for debugging
5. **Configurable**: Domain-specific thresholds and interventions
6. **Tested**: Comprehensive test suite with >80% coverage
