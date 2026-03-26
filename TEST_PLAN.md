# Brain Guard Test Plan

> **Note:** Brain Guard was formerly known as SCFL-Observatory.

## Overview

This document defines comprehensive testing strategy for the Brain Guard plugin, including unit tests, integration tests, load tests, and failure mode tests.

---

## 1. Unit Tests

### 1.1 Preprocessor (Layer 1)

**Test File:** `tests/unit/test_preprocessor.py`

| Test ID | Description | Input | Expected Output |
|---------|-------------|-------|-----------------|
| PRE-001 | Empty prompt handling | `""` | Empty conditioned input, ambiguity=0 |
| PRE-002 | Simple prompt | `"What is the weather?"` | Conditioned input, ambiguity < 0.3 |
| PRE-003 | Ambiguous prompt | `"Tell me about it"` (no context) | High ambiguity (>0.7), flag for clarification |
| PRE-004 | Multi-sentence prompt | 3+ sentences | Segmented into units, coherence between units |
| PRE-005 | Constraint injection | Prompt with anchors | Constraints prepended to input |
| PRE-006 | Unicode handling | Emoji, CJK, RTL text | Properly segmented, no corruption |
| PRE-007 | Very long prompt | 10k+ tokens | Truncated with warning, or chunked |
| PRE-008 | Special characters | Code, markdown, JSON | Preserved structure, proper segmentation |

**Mock Dependencies:**
- Embedding service (return deterministic vectors)
- Anchor store (in-memory)

---

### 1.2 Coherence Monitor (Layer 3)

**Test File:** `tests/unit/test_coherence_monitor.py`

| Test ID | Description | Input | Expected Output |
|---------|-------------|-------|-----------------|
| CFM-001 | Identical sentences | s1="Hello", s2="Hello" | ΔG ≈ 0 |
| CFM-002 | Related sentences | s1="I like dogs", s2="Dogs are pets" | ΔG ≈ 0.2-0.4 |
| CFM-003 | Unrelated sentences | s1="I like dogs", s2="The moon is cheese" | ΔG > 0.8 |
| CFM-004 | Gradual drift | Sequence of increasingly unrelated sentences | Vd increasing |
| CFM-005 | Sudden rupture | Coherent then completely off-topic | ΔG spike, high Vd |
| CFM-006 | Repetition loop | Same sentence repeated 5x | σ²c < 0.02 |
| CFM-007 | Perfect continuity | Coherent paragraph | ΔG < 0.3 throughout |
| CFM-008 | Empty response | "" | ΔG = -1 (sentinel), log warning |
| CFM-009 | Single sentence | Only one sentence | ΔG = 0 (no comparison) |
| CFM-010 | Embedding failure | Service returns error | Fallback to string similarity |

**Mock Dependencies:**
- Embedding service with controlled responses
- Pre-computed similarity matrices

---

### 1.3 Threshold Engine (Layer 4)

**Test File:** `tests/unit/test_threshold_engine.py`

| Test ID | Description | Input Metrics | Expected Action |
|---------|-------------|---------------|-----------------|
| THR-001 | No thresholds crossed | ΔG=0.3, Vd=0.01 | No action (silent) |
| THR-002 | Drift warning | ΔG=0.7 | Log warning, flag if mode=warn |
| THR-003 | Rupture alert | ΔG=0.9 | Trigger regeneration |
| THR-004 | Accelerating drift | Vd=0.15 | Inject grounding prompt |
| THR-005 | Variance collapse | σ²c=0.01 | Trigger diversity prompt |
| THR-006 | Low recoverability | R=0.2 | Safe fallback mode |
| THR-007 | Multiple triggers | ΔG=0.9, Vd=0.2 | Highest priority action (rupture) |
| THR-008 | Threshold boundary | ΔG=0.649 vs 0.651 | Correct classification |
| THR-009 | Mode: silent | Any trigger | Log only, no user action |
| THR-010 | Mode: strict | ΔG=0.5 (below warning) | Action anyway (strict mode) |
| THR-011 | Circuit breaker | Processing time > max_ms | Skip SCFL, return raw |

---

### 1.4 Session Anchoring

**Test File:** `tests/unit/test_anchoring.py`

| Test ID | Description | Input | Expected Output |
|---------|-------------|-------|-----------------|
| ANC-001 | Extract factual anchor | "Paris is in France" | Anchor stored, type=factual |
| ANC-002 | Extract procedural anchor | "First do X, then Y" | Anchor stored, type=procedural |
| ANC-003 | No anchors in text | "Hello, how are you?" | No anchors extracted |
| ANC-004 | Contradiction detection | "Paris is in Germany" (vs France) | Contradiction flagged |
| ANC-005 | Anchor limit reached | 50 anchors already | Oldest anchor evicted |
| ANC-006 | Reference counting | Anchor referenced 3x | reference_count=3 |
| ANC-007 | Anchor deactivation | Contradicted anchor | is_active=FALSE |
| ANC-008 | Temporal anchor | "Meeting at 3pm" | type=temporal, timestamp extracted |
| ANC-009 | Confidence scoring | Uncertain claim | Low confidence (<0.5) |
| ANC-010 | Anchor retrieval | Query for relevant anchor | Most semantically similar returned |

---

### 1.5 Database Layer

**Test File:** `tests/unit/test_database.py`

| Test ID | Description | Test Case |
|---------|-------------|-----------|
| DB-001 | Session creation | Create, verify all fields |
| DB-002 | Metric insertion | Insert metric, verify retrieval |
| DB-003 | Metric batching | Batch 100 metrics, verify atomicity |
| DB-004 | Anchor CRUD | Create, read, update, delete anchor |
| DB-005 | Intervention logging | Log intervention, verify fields |
| DB-006 | Time-series query | Query metrics for time range |
| DB-007 | Aggregation query | Daily stats calculation |
| DB-008 | Cascade delete | Delete session, verify orphans removed |
| DB-009 | Connection failure | Simulate DB down, verify buffering |
| DB-010 | Migration | Apply schema v1→v2, verify data intact |

---

## 2. Integration Tests

### 2.1 Full Pipeline

**Test File:** `tests/integration/test_pipeline.py`

| Test ID | Description | Flow | Assertions |
|---------|-------------|------|------------|
| INT-001 | Happy path | User msg → Preprocess → LLM → Monitor → Response | All layers called, metrics stored |
| INT-002 | Drift detection | Induce drift in conversation | Warning triggered, logged |
| INT-003 | Rupture recovery | Force rupture, verify regeneration | Response regenerated, user sees coherent output |
| INT-004 | Multi-turn session | 20-turn conversation | Continuity tracked, anchors accumulated |
| INT-005 | High-stakes escalation | Keyword triggers full mode | Monitoring escalated, thresholds tightened |
| INT-006 | Session closure | Close session, verify cleanup | State cleared, final stats written |

---

### 2.2 OpenClaw Gateway Integration

**Test File:** `tests/integration/test_gateway.py`

| Test ID | Description | Test Case |
|---------|-------------|-----------|
| GW-001 | Hook registration | Register preprocess and postprocess hooks |
| GW-002 | Message flow | Verify message passes through SCFL |
| GW-003 | Error propagation | SCFL error doesn't break gateway |
| GW-004 | Config reload | Change config, verify hot reload |
| GW-005 | Plugin unload | Unload SCFL, verify graceful shutdown |

---

### 2.3 LCM Integration

**Test File:** `tests/integration/test_lcm.py`

| Test ID | Description | Test Case |
|---------|-------------|-----------|
| LCM-001 | Pre-LCM execution | SCFL runs before LCM compaction |
| LCM-002 | Metric availability | LCM can query SCFL metrics |
| LCM-003 | No interference | LCM compaction unaffected by SCFL |
| LCM-004 | Shared state | Session state consistent between systems |

---

### 2.4 Dashboard API

**Test File:** `tests/integration/test_dashboard.py`

| Test ID | Endpoint | Test Case |
|---------|----------|-----------|
| DASH-001 | GET /api/v1/sessions/{id}/current | Returns live metrics |
| DASH-002 | GET /api/v1/sessions/{id}/metrics | Returns time-series |
| DASH-003 | GET /api/v1/sessions/{id}/stream | SSE stream updates |
| DASH-004 | GET /api/v1/dashboard/summary | System-wide stats |
| DASH-005 | Authentication | Reject without valid token |
| DASH-006 | CORS | Accept from configured origins |
| DASH-007 | Rate limiting | 429 after threshold |

---

## 3. Load Tests

### 3.1 Latency Benchmarks

**Test File:** `tests/load/test_latency.py`

| Test ID | Scenario | Target | Max |
|---------|----------|--------|-----|
| LAT-001 | Single user, 100 messages | P50 < 30ms | P95 < 50ms |
| LAT-002 | 10 concurrent users | P50 < 40ms | P95 < 80ms |
| LAT-003 | 100 concurrent users | P50 < 50ms | P95 < 100ms |
| LAT-004 | Burst: 1000 messages in 10s | No errors | P99 < 150ms |
| LAT-005 | With full monitoring | P50 < 80ms | P95 < 150ms |
| LAT-006 | With embedding cache cold | P50 < 100ms | P95 < 200ms |
| LAT-007 | With embedding cache warm | P50 < 20ms | P95 < 40ms |

---

### 3.2 Throughput Tests

**Test File:** `tests/load/test_throughput.py`

| Test ID | Scenario | Target |
|---------|----------|--------|
| THP-001 | Messages per second | > 100 msg/s |
| THP-002 | Dashboard queries per second | > 1000 req/s |
| THP-003 | Metric writes per second | > 1000 writes/s |
| THP-004 | Concurrent sessions | > 1000 active |

---

### 3.3 Resource Usage

**Test File:** `tests/load/test_resources.py`

| Test ID | Resource | Limit | Test |
|---------|----------|-------|------|
| RES-001 | Memory per session | < 5MB | Monitor heap |
| RES-002 | Database size growth | < 1GB/month | Project from load |
| RES-003 | CPU usage | < 10% at 100 msg/s | Profile |
| RES-004 | Embedding API calls | Cache hit rate > 80% | Monitor |

---

## 4. Failure Mode Tests (Chaos Engineering)

### 4.1 Component Failures

**Test File:** `tests/chaos/test_failures.py`

| Test ID | Failure | Expected Behavior |
|---------|---------|-------------------|
| CHA-001 | Embedding service down | Fallback to string similarity, log warning |
| CHA-002 | Database unreachable | Buffer in memory, retry with backoff |
| CHA-003 | Database slow (high latency) | Circuit breaker opens after threshold |
| CHA-004 | Memory exhaustion | Graceful degradation, oldest sessions evicted |
| CHA-005 | Disk full | Log error, continue without persistence |
| CHA-006 | Network partition | Local operation continues, queue for sync |
| CHA-007 | Corrupted config | Use defaults, log error |
| CHA-008 | Invalid metric values | Reject, use sentinel, continue |

---

### 4.2 Edge Cases

**Test File:** `tests/chaos/test_edge_cases.py`

| Test ID | Scenario | Expected Behavior |
|---------|----------|-------------------|
| EDGE-001 | Very long message (100k tokens) | Truncate or chunk, process what fits |
| EDGE-002 | Very short session (1 turn) | No drift possible, minimal overhead |
| EDGE-003 | Rapid context switching | Detect as high drift, flag appropriately |
| EDGE-004 | Circular reasoning | Detect repetition loop (σ²c) |
| EDGE-005 | Contradiction every turn | Escalate to strict mode |
| EDGE-006 | All metrics at boundaries | Correct threshold classification |
| EDGE-007 | Clock skew | Handle out-of-order timestamps |
| EDGE-008 | Special Unicode | No crashes, proper segmentation |

---

## 5. Calibration Tests

### 5.1 Threshold Validation

**Test File:** `tests/calibration/test_thresholds.py`

| Test ID | Test | Method |
|---------|------|--------|
| CAL-001 | Drift warning threshold | Manually label 1000 transitions, optimize for F1 |
| CAL-002 | Rupture alert threshold | A/B test: 0.80 vs 0.85 vs 0.90 |
| CAL-003 | Variance collapse | Synthetic repetition data |
| CAL-004 | Per-domain calibration | Medical vs casual conversation thresholds |
| CAL-005 | User feedback integration | User marks "this was helpful/unhelpful" |

---

### 5.2 Embedding Model Comparison

**Test File:** `tests/calibration/test_embeddings.py`

| Test ID | Model | Test |
|---------|-------|------|
| EMB-001 | text-embedding-3-small | Baseline accuracy |
| EMB-002 | text-embedding-3-large | Accuracy vs latency tradeoff |
| EMB-003 | Local model (all-MiniLM) | Accuracy vs cost tradeoff |
| EMB-004 | Hybrid approach | Fast path vs slow path accuracy |

---

## 6. Test Infrastructure

### 6.1 Test Data

**Fixtures:**
- `fixtures/coherent_conversations.json` - Known good conversations
- `fixtures/drift_conversations.json` - Conversations with known drift points
- `fixtures/rupture_conversations.json` - Conversations with ruptures
- `fixtures/edge_cases.json` - Boundary cases

### 6.2 Mock Services

**Mocks:**
- `mocks/embedding_service.py` - Deterministic embedding responses
- `mocks/llm_service.py` - Controlled LLM responses
- `mocks/database.py` - In-memory DB for unit tests

### 6.3 Test Configuration

```yaml
# tests/config/test.yaml
brain-guard:
  mode: strict  # Stricter for testing
  latency:
    target_ms: 10  # Tighter for CI
  embedding:
    provider: mock  # Use mocks
  storage:
    type: sqlite
    connection_string: ":memory:"
  testing:
    mock_embeddings: true
    calibration_mode: true
```

---

## 7. CI/CD Integration

### 7.1 Pre-commit Checks

```bash
# Run on every commit
pytest tests/unit/ -x --cov=src --cov-fail-under=80
```

### 7.2 PR Checks

```bash
# Run on every PR
pytest tests/unit/ tests/integration/ -x --cov=src --cov-fail-under=75
mypy src/
pylint src/
```

### 7.3 Nightly Tests

```bash
# Run nightly
pytest tests/load/ -m "not slow" --tb=short
pytest tests/chaos/ --tb=short
```

### 7.4 Release Tests

```bash
# Run before release
pytest tests/ -x --tb=short --runslow
```

---

## 8. Success Criteria

| Category | Metric | Target |
|----------|--------|--------|
| Unit Test Coverage | Line coverage | > 80% |
| Integration Test Coverage | Critical paths | 100% |
| Latency | P95 at 100 msg/s | < 100ms |
| Reliability | Pass rate | > 99% |
| False Positive Rate | User-reported | < 5% |
| False Negative Rate | Detected drift / actual drift | > 80% |

---

## 9. Test Execution

### Run All Tests
```bash
pytest tests/ -v --tb=short
```

### Run Unit Tests Only
```bash
pytest tests/unit/ -v
```

### Run with Coverage
```bash
pytest tests/ --cov=src --cov-report=html
```

### Run Load Tests
```bash
pytest tests/load/ -m load --tb=short
```

### Run Chaos Tests
```bash
pytest tests/chaos/ --tb=short
```

### Run Specific Test
```bash
pytest tests/unit/test_coherence_monitor.py::CFM-003 -v
```
