# Brain Guard Deployment Guide

## Overview

Brain Guard is now ready to deploy as an OpenClaw plugin. This guide covers installation, configuration, and usage.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/viaramb/brain-guard.git
cd brain-guard
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure the Plugin

```bash
# Copy the example configuration
cp config/brain-guard.example.yml config/brain-guard.yml

# Edit the configuration
nano config/brain-guard.yml
```

### 4. Set Environment Variables

```bash
# Required: Enable the plugin
export BRAIN_GUARD_ENABLED=true

# Optional: Set config path
export BRAIN_GUARD_CONFIG_PATH=/path/to/brain-guard.yml

# Optional: Set database URL
export BRAIN_GUARD_DB_URL=sqlite:///path/to/brain_guard.db

# Optional: Set dashboard port
export BRAIN_GUARD_DASHBOARD_PORT=8080
```

---

## Configuration Options

### Basic Configuration (config/brain-guard.yml)

```yaml
enabled: true
mode: adaptive  # Options: silent | warn | strict | adaptive

# Latency settings
latency:
  target_ms: 50
  max_ms: 100

# Thresholds for interventions
thresholds:
  drift_warning: 0.65      # When to warn about coherence drift
  rupture_alert: 0.85      # When to alert about coherence rupture
  drift_velocity: 0.10     # Speed of coherence degradation
  ambiguity: 0.70          # When input is considered ambiguous

# Embedding service
embedding:
  provider: local          # Options: openai | local | mock
  model: all-MiniLM-L6-v2
  cache_enabled: true

# Dashboard
dashboard:
  enabled: true
  port: 8080
  host: 127.0.0.1

# Storage
storage:
  type: sqlite
  connection_string: "~/.openclaw/brain_guard.db"
```

---

## Usage

### Starting Brain Guard

```python
import asyncio
from src import BrainGuardPlugin

async def main():
    # Initialize the plugin
    plugin = BrainGuardPlugin()
    await plugin.initialize()
    
    print(f"Brain Guard enabled: {plugin.enabled}")
    
    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await plugin.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

### Processing a Conversation

```python
# Step 1: Preprocess user message
result = await plugin.preprocess_message(
    session_id="session-123",
    user_message="Tell me about Python programming",
    context={"domain": "programming"}
)

# Check the preprocessing results
print(f"Ambiguity score: {result['metadata']['ambiguity_score']}")
print(f"Domain detected: {result['metadata']['domain']}")

# Step 2: Send to your AI model
ai_response = "Python is a high-level programming language..."

# Step 3: Monitor the AI response
metrics = await plugin.monitor_response(
    session_id="session-123",
    response=ai_response,
    metadata=result['metadata']
)

# Check coherence metrics
print(f"Continuity score: {metrics['continuity_score']}")
print(f"Drift score: {metrics['drift_score']}")

# Step 4: Check if intervention is needed
if metrics['intervention_triggered']:
    print(f"Intervention: {metrics['intervention_type']}")
    print(f"Reason: {metrics['intervention_reason']}")
```

### Session Management

```python
# Get all active sessions
sessions = await plugin.get_active_sessions()

# Get anchors for a session
anchors = await plugin.get_anchors("session-123")

# Clear a session
await plugin.clear_session("session-123")

# Close a session (stores final metrics)
await plugin.close_session("session-123")
```

---

## Operating Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **silent** | Monitor only, no interventions | Production, observe behavior |
| **warn** | Log warnings but don't block | Development, debugging |
| **strict** | Always intervene on thresholds | High-stakes domains |
| **adaptive** | Escalate based on risk profile | General use (recommended) |

---

## Dashboard

Brain Guard includes a web dashboard for real-time monitoring.

### Access the Dashboard

```bash
# Start the dashboard (runs automatically with plugin)
# Open in browser:
open http://localhost:8080
```

### Dashboard Features

- **Real-time metrics**: See coherence scores as they happen
- **Session list**: View all active conversations
- **Intervention log**: See when and why interventions occurred
- **Historical data**: Review past conversation metrics

### API Endpoints

```bash
# Health check
curl http://localhost:8080/health

# Get all sessions
curl http://localhost:8080/api/sessions

# Get session metrics
curl http://localhost:8080/api/sessions/session-123/metrics

# Get real-time events (SSE)
curl http://localhost:8080/api/events
```

---

## Monitoring Brain Guard Behavior

### Logs

```bash
# View logs in real-time
tail -f ~/.openclaw/logs/brain_guard.log

# Or check stdout if running directly
python -m src 2>&1 | grep -E "(INFO|WARNING|ERROR)"
```

### Key Log Messages

| Message | Meaning |
|---------|---------|
| `Coherence drift detected` | Response is losing coherence |
| `Rupture alert triggered` | Severe coherence failure |
| `Intervention: [type]` | Brain Guard took action |
| `Anchor extracted` | New fact remembered |
| `Contradiction detected` | AI response conflicts with known fact |

### Metrics to Watch

| Metric | Good Range | Warning | Critical |
|--------|-----------|---------|----------|
| Continuity Score | >0.8 | 0.6-0.8 | <0.6 |
| Drift Score | <0.3 | 0.3-0.6 | >0.6 |
| Drift Velocity | <0.05 | 0.05-0.1 | >0.1 |
| Ambiguity Score | <0.5 | 0.5-0.7 | >0.7 |

---

## Testing Brain Guard

### Quick Test

```bash
# Run the test suite
pytest tests/unit -v

# Test with a sample conversation
python scripts/test_conversation.py
```

### Manual Testing

```python
# Test preprocessing
test_inputs = [
    "Hello, how are you?",
    "What is the capital of France?",
    "Tell me about quantum computing",
    "[code] def hello(): print('world')",
]

for text in test_inputs:
    result = await plugin.preprocess_message("test-session", text)
    print(f"Input: {text[:40]}...")
    print(f"  Ambiguity: {result['metadata']['ambiguity_score']:.2f}")
    print(f"  Domain: {result['metadata']['domain']}")
```

---

## Troubleshooting

### Plugin Not Loading

```bash
# Check if enabled
echo $BRAIN_GUARD_ENABLED  # Should be: true

# Check logs for errors
grep -i "brain guard" ~/.openclaw/logs/*.log
```

### Dashboard Not Accessible

```bash
# Check if port is in use
lsof -i :8080

# Try different port
export BRAIN_GUARD_DASHBOARD_PORT=8081
```

### High Latency

```bash
# Check embedding service
# If using OpenAI, verify API key
# If using local, check model loading

# Switch to mock embeddings for testing
export BRAIN_GUARD_MOCK_EMBEDDINGS=true
```

### Database Errors

```bash
# Check database permissions
ls -la ~/.openclaw/brain_guard.db

# Reset database (WARNING: loses all data)
rm ~/.openclaw/brain_guard.db
```

---

## Integration with OpenClaw

Brain Guard integrates with OpenClaw as a message processor plugin.

### Hook Points

1. **Before sending to AI**: `preprocess_message()`
2. **After receiving AI response**: `monitor_response()`
3. **Session lifecycle**: `initialize()`, `shutdown()`

### Configuration in OpenClaw

Add to your OpenClaw config:

```json
{
  "plugins": {
    "brain-guard": {
      "enabled": true,
      "config_path": "/path/to/brain-guard.yml"
    }
  }
}
```

---

## Next Steps

1. **Monitor for a week** in `silent` mode to understand baseline behavior
2. **Adjust thresholds** based on your use case
3. **Enable interventions** gradually starting with `warn` mode
4. **Review dashboard** regularly to spot patterns
5. **Fine-tune domains** for your specific conversation types

---

## Support

- GitHub Issues: https://github.com/viaramb/brain-guard/issues
- Documentation: See ARCHITECTURE.md and DOCUMENTATION.md
- Tests: Run `pytest tests/ -v` to verify installation
