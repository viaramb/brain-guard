# Brain Guard Dashboard API Specification

> **Note:** Brain Guard was formerly known as SCFL-Observatory.

## Base URL

```
http://localhost:8080/api/v1
```

## Authentication

All endpoints require Bearer token authentication:

```
Authorization: Bearer <token>
```

Token is configured in plugin settings (`dashboard.auth_token`).

---

## Endpoints

### 1. Session Management

#### List Sessions

```
GET /sessions
```

**Query Parameters:**
| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| status | string | Filter by status (active, closed) | all |
| limit | integer | Max results | 100 |
| offset | integer | Pagination offset | 0 |
| from | datetime | Start date filter | - |
| to | datetime | End date filter | - |

**Response:**
```json
{
  "sessions": [
    {
      "id": "sess_abc123",
      "created_at": "2026-03-25T20:00:00Z",
      "updated_at": "2026-03-25T20:30:00Z",
      "status": "active",
      "total_turns": 15,
      "total_interventions": 2,
      "avg_coherence_score": 0.87,
      "current_delta_g": 0.23,
      "current_continuity": 0.91
    }
  ],
  "total": 150,
  "limit": 100,
  "offset": 0
}
```

---

#### Get Session Details

```
GET /sessions/{id}
```

**Response:**
```json
{
  "id": "sess_abc123",
  "created_at": "2026-03-25T20:00:00Z",
  "updated_at": "2026-03-25T20:30:00Z",
  "user_id": "user_456",
  "channel_id": "chan_789",
  "mode": "adaptive",
  "status": "active",
  "total_turns": 15,
  "total_interventions": 2,
  "avg_coherence_score": 0.87,
  "metadata": {
    "escalated_at_turn": 10,
    "high_stakes_detected": true
  }
}
```

---

#### Close Session

```
POST /sessions/{id}/close
```

**Response:**
```json
{
  "id": "sess_abc123",
  "status": "closed",
  "closed_at": "2026-03-25T20:35:00Z",
  "summary": {
    "total_turns": 16,
    "total_interventions": 2,
    "final_coherence": 0.85,
    "ruptures_detected": 0,
    "drift_warnings": 3
  }
}
```

---

### 2. Real-Time Metrics

#### Get Current Session State

```
GET /sessions/{id}/current
```

**Response:**
```json
{
  "session_id": "sess_abc123",
  "timestamp": "2026-03-25T20:30:00Z",
  "turn_number": 15,
  "metrics": {
    "delta_g": 0.23,
    "drift_velocity": -0.05,
    "variance_collapse": 0.15,
    "continuity_score": 0.91,
    "recoverability_score": 0.78
  },
  "thresholds": {
    "drift_warning": 0.65,
    "rupture_alert": 0.85,
    "current_status": "stable"
  },
  "anchors": {
    "total": 12,
    "active": 10,
    "recently_added": [
      {
        "id": "anc_001",
        "type": "factual",
        "content": "User prefers Python over JavaScript",
        "confidence": 0.92
      }
    ]
  },
  "recent_interventions": [
    {
      "id": "int_001",
      "turn_number": 12,
      "type": "drift_warning",
      "timestamp": "2026-03-25T20:25:00Z",
      "was_successful": true
    }
  ]
}
```

---

#### Stream Real-Time Updates

```
GET /sessions/{id}/stream
```

**Protocol:** Server-Sent Events (SSE)

**Event Types:**

```
event: metric_update
data: {
  "turn_number": 16,
  "delta_g": 0.31,
  "continuity_score": 0.88,
  "timestamp": "2026-03-25T20:31:00Z"
}

event: threshold_violation
data: {
  "type": "drift_warning",
  "metric": "delta_g",
  "value": 0.67,
  "threshold": 0.65,
  "timestamp": "2026-03-25T20:31:05Z"
}

event: intervention
data: {
  "id": "int_002",
  "type": "grounding_prompt",
  "trigger": "drift_warning",
  "timestamp": "2026-03-25T20:31:06Z"
}

event: anchor_added
data: {
  "id": "anc_013",
  "type": "procedural",
  "content": "User wants to deploy on AWS",
  "confidence": 0.89
}
```

---

### 3. Historical Metrics

#### Get Metric Time-Series

```
GET /sessions/{id}/metrics
```

**Query Parameters:**
| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| from | datetime | Start time | session start |
| to | datetime | End time | now |
| granularity | string | raw, minute, hour | raw |
| metrics | array | Filter specific metrics | all |

**Response:**
```json
{
  "session_id": "sess_abc123",
  "from": "2026-03-25T20:00:00Z",
  "to": "2026-03-25T20:30:00Z",
  "granularity": "raw",
  "data": [
    {
      "turn_number": 1,
      "timestamp": "2026-03-25T20:00:05Z",
      "delta_g": 0.0,
      "drift_velocity": 0.0,
      "continuity_score": 1.0,
      "recoverability_score": 1.0
    },
    {
      "turn_number": 2,
      "timestamp": "2026-03-25T20:02:00Z",
      "delta_g": 0.15,
      "drift_velocity": 0.15,
      "continuity_score": 0.95,
      "recoverability_score": 0.95
    }
    // ... more points
  ]
}
```

---

#### Get Anchors Timeline

```
GET /sessions/{id}/anchors
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| type | string | Filter by anchor type |
| active_only | boolean | Only active anchors | true |

**Response:**
```json
{
  "session_id": "sess_abc123",
  "anchors": [
    {
      "id": "anc_001",
      "type": "factual",
      "content": "User prefers Python",
      "confidence": 0.92,
      "turn_created": 3,
      "turn_last_referenced": 15,
      "reference_count": 5,
      "is_active": true,
      "created_at": "2026-03-25T20:05:00Z"
    },
    {
      "id": "anc_005",
      "type": "factual",
      "content": "User prefers JavaScript",
      "confidence": 0.88,
      "turn_created": 8,
      "turn_last_referenced": 10,
      "reference_count": 2,
      "is_active": false,
      "contradicted_by": "anc_007",
      "created_at": "2026-03-25T20:15:00Z"
    }
  ],
  "contradictions": [
    {
      "anchor_a": "anc_005",
      "anchor_b": "anc_007",
      "detected_at_turn": 12,
      "similarity_score": 0.91
    }
  ]
}
```

---

#### Get Interventions Log

```
GET /sessions/{id}/interventions
```

**Response:**
```json
{
  "session_id": "sess_abc123",
  "interventions": [
    {
      "id": "int_001",
      "turn_number": 12,
      "timestamp": "2026-03-25T20:25:00Z",
      "type": "drift_warning",
      "trigger_condition": "delta_g > 0.65",
      "threshold_value": 0.65,
      "actual_value": 0.71,
      "description": "Detected drift in conversation topic",
      "user_visible": true,
      "user_response": "acknowledged",
      "was_successful": true,
      "processing_time_ms": 12
    }
  ],
  "summary": {
    "total": 2,
    "by_type": {
      "drift_warning": 1,
      "grounding_prompt": 1
    },
    "success_rate": 1.0
  }
}
```

---

### 4. Dashboard Aggregations

#### System Summary

```
GET /dashboard/summary
```

**Query Parameters:**
| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| from | datetime | Start time | -24h |
| to | datetime | End time | now |

**Response:**
```json
{
  "period": {
    "from": "2026-03-24T20:00:00Z",
    "to": "2026-03-25T20:00:00Z"
  },
  "sessions": {
    "total": 150,
    "active": 12,
    "closed": 138,
    "avg_duration_minutes": 18.5
  },
  "coherence": {
    "avg_score": 0.84,
    "min_score": 0.23,
    "max_score": 1.0,
    "p50": 0.87,
    "p95": 0.95
  },
  "interventions": {
    "total": 45,
    "rate_per_session": 0.3,
    "by_type": {
      "drift_warning": 25,
      "rupture_alert": 5,
      "grounding_prompt": 15
    },
    "success_rate": 0.89
  },
  "threshold_violations": {
    "total": 67,
    "drift_warnings": 45,
    "rupture_alerts": 12,
    "variance_collapses": 10
  },
  "performance": {
    "avg_latency_ms": 32,
    "p95_latency_ms": 58,
    "p99_latency_ms": 89,
    "cache_hit_rate": 0.87
  }
}
```

---

#### Coherence Trends

```
GET /dashboard/trends
```

**Query Parameters:**
| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| metric | string | Metric to trend (delta_g, continuity, etc.) | continuity |
| interval | string | hour, day, week | hour |
| from | datetime | Start time | -7d |
| to | datetime | End time | now |

**Response:**
```json
{
  "metric": "continuity_score",
  "interval": "hour",
  "data": [
    {
      "timestamp": "2026-03-25T19:00:00Z",
      "avg": 0.85,
      "min": 0.45,
      "max": 1.0,
      "p95": 0.97,
      "count": 45
    },
    {
      "timestamp": "2026-03-25T20:00:00Z",
      "avg": 0.83,
      "min": 0.32,
      "max": 1.0,
      "p95": 0.96,
      "count": 38
    }
  ]
}
```

---

#### Active Alerts

```
GET /dashboard/alerts
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| severity | string | warning, alert, critical | all |
| session_id | string | Filter by session |

**Response:**
```json
{
  "alerts": [
    {
      "id": "alt_001",
      "session_id": "sess_abc123",
      "severity": "warning",
      "type": "drift_detected",
      "message": "Delta-G exceeded warning threshold (0.71 > 0.65)",
      "metric": "delta_g",
      "value": 0.71,
      "threshold": 0.65,
      "turn_number": 12,
      "timestamp": "2026-03-25T20:25:00Z",
      "status": "active",
      "intervention_id": "int_001"
    },
    {
      "id": "alt_002",
      "session_id": "sess_def456",
      "severity": "alert",
      "type": "rupture_detected",
      "message": "Conversation rupture detected (0.91 > 0.85)",
      "metric": "delta_g",
      "value": 0.91,
      "threshold": 0.85,
      "turn_number": 8,
      "timestamp": "2026-03-25T20:28:00Z",
      "status": "resolved",
      "resolved_at": "2026-03-25T20:29:00Z",
      "intervention_id": "int_003"
    }
  ],
  "summary": {
    "total_active": 1,
    "by_severity": {
      "warning": 1,
      "alert": 0,
      "critical": 0
    }
  }
}
```

---

#### Intervention Effectiveness

```
GET /dashboard/interventions
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| type | string | Filter by intervention type |
| from | datetime | Start time |

**Response:**
```json
{
  "summary": {
    "total_interventions": 150,
    "overall_success_rate": 0.87,
    "avg_processing_time_ms": 15
  },
  "by_type": [
    {
      "type": "drift_warning",
      "count": 80,
      "success_rate": 0.92,
      "avg_processing_time_ms": 12,
      "user_acknowledgment_rate": 0.75
    },
    {
      "type": "rupture_alert",
      "count": 20,
      "success_rate": 0.85,
      "avg_processing_time_ms": 25,
      "regeneration_success_rate": 0.90
    },
    {
      "type": "grounding_prompt",
      "count": 50,
      "success_rate": 0.84,
      "avg_processing_time_ms": 10
    }
  ],
  "trends": [
    {
      "date": "2026-03-20",
      "success_rate": 0.85,
      "count": 20
    },
    {
      "date": "2026-03-21",
      "success_rate": 0.88,
      "count": 22
    }
    // ... more days
  ]
}
```

---

### 5. Health & Diagnostics

#### Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-25T20:30:00Z",
  "version": "1.0.0",
  "checks": {
    "database": {
      "status": "ok",
      "response_time_ms": 2,
      "connection_pool": {
        "active": 3,
        "idle": 7,
        "max": 20
      }
    },
    "embedding_service": {
      "status": "ok",
      "response_time_ms": 45,
      "cache_hit_rate": 0.87
    },
    "metrics_buffer": {
      "status": "ok",
      "buffered_count": 12,
      "flush_interval_ms": 1000
    }
  },
  "performance": {
    "requests_per_minute": 450,
    "avg_response_time_ms": 28,
    "error_rate": 0.001
  }
}
```

---

#### Plugin Configuration

```
GET /config
```

**Response:**
```json
{
  "enabled": true,
  "mode": "adaptive",
  "thresholds": {
    "drift_warning": 0.65,
    "rupture_alert": 0.85,
    "drift_velocity": 0.10,
    "variance_collapse": 0.02,
    "recoverability": 0.30
  },
  "latency": {
    "target_ms": 50,
    "max_ms": 100,
    "circuit_breaker_threshold": 0.95
  },
  "monitoring": {
    "default_level": "light",
    "escalation_turns": 10
  },
  "storage": {
    "type": "sqlite",
    "retention_days": 30
  },
  "dashboard": {
    "enabled": true,
    "port": 8080
  }
}
```

---

#### Update Configuration (Partial)

```
PATCH /config
```

**Request Body:**
```json
{
  "mode": "strict",
  "thresholds": {
    "drift_warning": 0.60
  }
}
```

**Response:**
```json
{
  "status": "updated",
  "changes": {
    "mode": "strict",
    "thresholds.drift_warning": 0.60
  },
  "effective_immediately": true
}
```

---

## Error Responses

### Standard Error Format

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session sess_abc123 not found",
    "details": {
      "session_id": "sess_abc123"
    },
    "timestamp": "2026-03-25T20:30:00Z",
    "request_id": "req_xyz789"
  }
}
```

### Error Codes

| HTTP Status | Code | Description |
|-------------|------|-------------|
| 400 | INVALID_REQUEST | Malformed request |
| 401 | UNAUTHORIZED | Missing or invalid token |
| 403 | FORBIDDEN | Valid token, insufficient permissions |
| 404 | SESSION_NOT_FOUND | Session ID doesn't exist |
| 409 | SESSION_CLOSED | Operation on closed session |
| 422 | VALIDATION_ERROR | Invalid parameters |
| 429 | RATE_LIMITED | Too many requests |
| 500 | INTERNAL_ERROR | Server error |
| 503 | SERVICE_UNAVAILABLE | Database or embedding service down |

---

## Rate Limiting

| Endpoint | Limit |
|----------|-------|
| All GET | 1000 req/min |
| POST /sessions | 100 req/min |
| SSE streams | 10 concurrent per client |

**Headers:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1711392600
```

---

## WebSocket Alternative (Future)

For lower-latency real-time updates, WebSocket support may be added:

```
WS /ws/sessions/{id}
```

**Message Types:** Same as SSE events

---

## SDK Examples

### Python

```python
import requests

client = requests.Session()
client.headers.update({"Authorization": "Bearer token123"})

# Get current session state
response = client.get("http://localhost:8080/api/v1/sessions/sess_abc123/current")
state = response.json()
print(f"Continuity: {state['metrics']['continuity_score']}")

# Stream real-time updates
import sseclient
response = client.get("http://localhost:8080/api/v1/sessions/sess_abc123/stream", stream=True)
for event in sseclient.SSEClient(response).events():
    print(f"Event: {event.event}, Data: {event.data}")
```

### JavaScript

```javascript
// Get current state
const response = await fetch('/api/v1/sessions/sess_abc123/current', {
  headers: { 'Authorization': 'Bearer token123' }
});
const state = await response.json();

// Stream updates
const eventSource = new EventSource('/api/v1/sessions/sess_abc123/stream');
eventSource.addEventListener('metric_update', (e) => {
  const data = JSON.parse(e.data);
  updateDashboard(data);
});
```

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-25 | Initial API release |
