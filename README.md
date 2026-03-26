# Brain Guard Plugin for OpenClaw

A real-time coherence monitoring plugin implementing the SCFL-Quad framework for OpenClaw.

## Features

- **Real-time coherence monitoring**: Detect drift, ruptures, and continuity failures
- **Multi-layer architecture**: Preprocessor, Coherence Monitor, Threshold Engine
- **Session anchoring**: Track key facts and detect contradictions
- **Domain-aware monitoring**: Different thresholds for different conversation types
- **Dashboard API**: Real-time and historical metrics via REST API and SSE
- **Configurable storage**: SQLite or PostgreSQL support

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Configure the plugin
cp config/brain-guard.example.yml config/brain-guard.yml

# Set environment variable
export BRAIN_GUARD_ENABLED=true
```

## Quick Start

```python
from brain_guard import BrainGuardPlugin

# Initialize the plugin
plugin = BrainGuardPlugin()

# Process a message
result = plugin.preprocess_message(
    session_id="session-123",
    user_message="Tell me about Python programming"
)

# Monitor a response
metrics = plugin.monitor_response(
    session_id="session-123",
    response="Python is a high-level programming language..."
)
```

## Configuration

See `config/schema.json` for the full configuration schema.

Key environment variables:
- `BRAIN_GUARD_ENABLED`: Enable/disable the plugin (default: true)
- `BRAIN_GUARD_CONFIG_PATH`: Path to config file (default: ./config/brain-guard.yml)
- `BRAIN_GUARD_DB_URL`: Database connection string

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test category
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/load/ -v
```

## Architecture

See `ARCHITECTURE.md` for detailed system design.

## License

MIT
