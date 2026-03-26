# Brain Guard Plugin Architecture

## Executive Summary

Brain Guard is an OpenClaw plugin that implements the SCFL-Quad coherence monitoring framework. It provides real-time detection of drift, ruptures, and continuity failures in LLM conversations without modifying underlying models.

**Note:** Brain Guard was formerly known as SCFL-Observatory. The name was changed to be more user-friendly while maintaining the same technical foundation.

**Key Design Principles:**
- Non-invasive: Hooks into message flow without changing LCM or model behavior
- Lightweight: Target latency <50ms per check
- Gated: Escalates monitoring based on conversation risk profile
- Observable: Full metrics dashboard for debugging and auditing

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenClaw Gateway                            │
├─────────────────────────────────────────────────────────────────┤
│  User Message                                                    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────┐     ┌──────────────────────────────────────┐   │
│  │   Router    │────▶│      Brain Guard Plugin              │   │
│  └─────────────┘     │  ┌────────────────────────────────┐  │   │
│       │              │  │   Preprocessor (Layer 1)       │  │   │
│       │              │  │   - Input conditioning         │  │   │
│       │              │  │   - Ambiguity scoring          │  │   │
│       │              │  └────────────────────────────────┘  │   │
│       │              │                   │                   │   │
│       │              │  ┌────────────────────────────────┐  │   │
│       │              │  │   Coherence Monitor (Layer 3)  │  │   │
│       │              │  │   - ΔG calculation             │  │   │
│       │              │  │   - Drift velocity (Vd)        │  │   │
│       │              │  │   - Variance collapse (σ²c)    │  │   │
│       │              │  └────────────────────────────────┘  │   │
│       │              │                   │                   │   │
│       │              │  ┌────────────────────────────────┐  │   │
│       │              │  │   Threshold Engine (Layer 4)   │  │   │
│       │              │  │   - Trigger evaluation         │  │   │
│       │              │  │   - Intervention decisions     │  │   │
│       │              │  └────────────────────────────────┘  │   │
│       │              └──────────────────────────────────────┘   │
│       │                              │                          │
│       │                              ▼                          │
│       │              ┌──────────────────────────────────────┐   │
│       │              │        Metrics Database              │   │
│       │              │   (SQLite/PostgreSQL for dashboard)  │   │
│       │              └──────────────────────────────────────┘   │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────┐                                                 │
│  │     LLM     │                                                 │
│  └─────────────┘                                                 │
│       │                                                          │
│       ▼                                                          │
│  Response → [Brain Guard monitors output] → User                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Preprocessor (Layer 1 - Input Conditioning)

**Purpose:** Normalize and stabilize input trajectories before LLM processing

**Operations:**
- Prompt segmentation into semantic units
- Ambiguity scoring (0-1 scale)
- Constraint injection based on session anchors
- Operator tag extraction

**Input:** Raw user message + session context
**Output:** Conditioned input (I') + metadata

**Latency Budget:** 10-20ms

---

### 2. Coherence Monitor (Layer 3 - CFM)

**Purpose:** Real-time measurement of trajectory integrity

**Core Metrics:**

#### ΔG (Coherence Deformation)
```
ΔG_i = 1 - cos_similarity(embedding(s_i), embedding(s_{i-1}))
```
- Range: 0 (identical) to 1 (orthogonal)
- Thresholds: 0.65 (warning), 0.85 (rupture)

#### Vd (Drift Velocity)
```
Vd(i) = ΔG_i - ΔG_{i-1}
```
- Positive: accelerating drift
- Negative: stabilizing
- Threshold: +0.10 (accelerating drift alert)

#### σ²c (Variance Collapse)
```
σ²c = Var(embedding_window(s_{i-k}...s_i))
```
- Low variance indicates repetition/mode collapse
- Threshold: < 0.02 (collapse detected)

#### Continuity Score (CS)
```
CS = weighted_average(ΔG, Vd, σ²c, anchor_preservation)
```
- Range: 0-1 (1 = perfect continuity)

**Input:** Response sequence R = {s_1, ..., s_n}
**Output:** Metrics vector M = {(ΔG_i, Vd_i, σ²_i, CF_i)}

**Latency Budget:** 20-30ms

---

### 3. Threshold Engine (Layer 4 - RCE)

**Purpose:** Evaluate triggers and decide interventions

**Trigger Conditions:**
| Condition | Threshold | Action |
|-----------|-----------|--------|
| Drift Warning | ΔG > 0.65 | Log, flag for review |
| Rupture Alert | ΔG > 0.85 | Request regeneration |
| Accelerating Drift | Vd > +0.10 | Inject grounding prompt |
| Variance Collapse | σ²c < 0.02 | Trigger diversity prompt |
| Low Recoverability | R < 0.30 | Safe fallback mode |

**Intervention Types:**
1. **Silent:** Log only, no user-visible action
2. **Flag:** Surface warning to user ("I may be drifting")
3. **Regenerate:** Rewind and regenerate response
4. **Fallback:** Switch to safe, conservative mode
5. **Halt:** Request user clarification

**Latency Budget:** 5-10ms

---

### 4. Session Anchoring System

**Purpose:** Track key facts and detect contradictions

**Anchor Types:**
- **Factual Anchors:** Claims about objective reality
- **Procedural Anchors:** Steps, sequences, processes
- **Contextual Anchors:** User preferences, constraints
- **Temporal Anchors:** Time-based commitments

**Operations:**
- Extract anchors from each response
- Store with confidence score
- Check new responses against anchor set
- Detect contradictions (semantic entailment check)

**Storage:** In-memory per session + persistence to DB

---

### 5. Metrics Database

**Purpose:** Store time-series metrics for dashboard and analysis

**Schema:** See `schema.sql`

**Tables:**
- `sessions`: Session metadata
- `metrics`: Time-series coherence metrics
- `anchors`: Extracted session anchors
- `interventions`: Recorded interventions
- `threshold_violations`: Alert history

**Retention:**
- Raw metrics: 30 days
- Aggregated summaries: 1 year
- Anonymized trends: Indefinite

---

### 6. Dashboard API

**Purpose:** Provide real-time and historical visibility

**Endpoints:**

#### Real-time
- `GET /api/v1/sessions/{id}/current` - Live metrics for active session
- `GET /api/v1/sessions/{id}/stream` - SSE stream of metric updates

#### Historical
- `GET /api/v1/sessions/{id}/metrics` - Full metric history
- `GET /api/v1/sessions/{id}/anchors` - Session anchor timeline
- `GET /api/v1/sessions/{id}/interventions` - Intervention log

#### Aggregated
- `GET /api/v1/dashboard/summary` - System-wide statistics
- `GET /api/v1/dashboard/trends` - Coherence trends over time
- `GET /api/v1/dashboard/alerts` - Active threshold violations

---

## Integration Points

### With OpenClaw Gateway

**Hook Registration:**
```typescript
// Register as pre-processor hook
gateway.registerHook('message:preprocess', scfl.preprocess);
gateway.registerHook('response:postprocess', scfl.monitor);
```

**Event Flow:**
1. User message arrives
2. Gateway calls `scfl.preprocess()`
3. SCFL returns conditioned input
4. Gateway sends to LLM
5. LLM response arrives
6. Gateway calls `scfl.monitor()`
7. SCFL computes metrics, stores to DB
8. Response delivered to user

### With LCM (Lossless-Claw)

**Relationship:** SCFL runs *before* LCM compaction

**Rationale:**
- SCFL needs raw conversation flow for accurate drift detection
- LCM compaction loses fine-grained timing/sequencing
- RLM (post-LCM) handles pattern recognition at summary level

**Data Sharing:**
- SCFL stores metrics to DB
- LCM can query SCFL for "high-coherence" segments to prioritize
- Gigabrain can use SCFL metrics for memory importance scoring

### With Gigabrain

**Integration:**
- Gigabrain consumes SCFL continuity scores
- Low-continuity segments marked as lower priority for recall
- High-drift periods flagged for attention

---

## Failure Modes & Mitigations

### 1. Latency Budget Overrun

**Risk:** SCFL processing exceeds 50ms target

**Mitigations:**
- Circuit breaker: Skip SCFL if processing time > 100ms
- Degraded mode: Run only Layer 1 (preprocessing) under load
- Async metrics: Compute expensive metrics (σ²c) asynchronously
- Caching: Cache embeddings for repeated semantic units

**Detection:**
- Metrics: `scfl_processing_time_ms`
- Alert: P95 > 50ms for 5 minutes

---

### 2. Database Connection Issues

**Risk:** Metrics DB unavailable, causing cascade failure

**Mitigations:**
- Local buffering: Queue metrics in memory if DB down
- Graceful degradation: Continue without persistence
- Retry with backoff: Reconnect to DB with exponential backoff
- Fallback to SQLite: Use local SQLite if PostgreSQL unavailable

**Detection:**
- Health check endpoint
- Alert on connection pool exhaustion

---

### 3. Metric Calculation Errors

**Risk:** Embedding failures, NaN values, calculation bugs

**Mitigations:**
- Validation: Check all metric values before storage
- Defaults: Use sentinel values (-1) for failed calculations
- Fallback metrics: Simpler string-based similarity if embeddings fail
- Circuit breaker: Disable problematic metric after N errors

**Detection:**
- Log validation failures
- Alert on metric calculation error rate > 1%

---

### 4. False Positives/Negatives

**Risk:** Over-triggering (annoying users) or under-triggering (missing drift)

**Mitigations:**
- Threshold tuning: Per-domain calibration
- User feedback: Track user responses to interventions
- A/B testing: Compare intervention strategies
- Gradual escalation: Start with silent logging, escalate based on data

**Detection:**
- Track intervention → user clarification patterns
- Measure user satisfaction post-intervention

---

### 5. Memory Leaks

**Risk:** Session state grows unbounded

**Mitigations:**
- Session TTL: Auto-cleanup after 24h inactivity
- Anchor limits: Max 50 anchors per session
- Metric sampling: Store only every Nth metric for long sessions
- Periodic GC: Force garbage collection on session close

**Detection:**
- Monitor heap usage per session
- Alert on sessions > 10MB state

---

## Configuration Schema

See `config.schema.json` for full specification.

**Key Options:**

```yaml
brain-guard:
  enabled: true
  mode: adaptive  # silent | warn | strict | adaptive
  
  latency:
    target_ms: 50
    max_ms: 100
    circuit_breaker_threshold: 0.95
  
  thresholds:
    drift_warning: 0.65
    rupture_alert: 0.85
    drift_velocity: 0.10
    variance_collapse: 0.02
    recoverability: 0.30
  
  monitoring:
    default_level: light  # light | full
    escalation_turns: 10
    high_stakes_keywords:
      - medical
      - legal
      - financial
      - contract
  
  storage:
    type: sqlite  # sqlite | postgresql
    connection_string: "~/.openclaw/scfl.db"
    retention_days: 30
  
  dashboard:
    enabled: true
    port: 8080
    auth_required: true
  
  anchoring:
    enabled: true
    max_anchors: 50
    contradiction_check: true
```

---

## Testing Strategy

See `TEST_PLAN.md` for comprehensive test specifications.

**Test Categories:**
1. Unit tests (per component)
2. Integration tests (full pipeline)
3. Load tests (latency under pressure)
4. Failure mode tests (chaos engineering)
5. Calibration tests (threshold validation)

---

## Deployment Phases

### Phase 1: Silent Mode (Week 1-2)
- Enable with `mode: silent`
- Log all metrics, no interventions
- Validate latency budget
- Tune thresholds based on real data

### Phase 2: Warning Mode (Week 3-4)
- Enable `mode: warn`
- Surface drift warnings to users
- Collect feedback on false positives
- Refine thresholds

### Phase 3: Full Intervention (Week 5-6)
- Enable regeneration on rupture detection
- Deploy dashboard
- Monitor system-wide metrics

### Phase 4: Adaptive Mode (Ongoing)
- Enable `mode: adaptive`
- ML-based threshold tuning
- Per-user calibration

---

## Success Metrics

**Technical:**
- P95 latency < 50ms
- Uptime > 99.9%
- False positive rate < 5%
- Drift detection recall > 80%

**User Experience:**
- User-reported hallucinations down 30%
- Clarification requests reduced
- Session continuity satisfaction up

**Operational:**
- Dashboard adoption by ops team
- Alert response time < 5 minutes
- MTTR for issues < 1 hour

---

## Open Questions

1. **Embedding Model:** Which embedding model for ΔG calculation? (OpenAI, local, hybrid?)
2. **UCMS Integration:** How much of the "proprietary UCMS" can be approximated with existing tools?
3. **Multi-Modal:** How to extend to image/audio inputs?
4. **Federation:** Can SCFL metrics be shared across distributed OpenClaw instances?

---

## References

- SCFL-Quad White Paper (conversation_1)
- SCFL-Quad Tech Spec v1.2 (conversation_1)
- OpenClaw Plugin Development Guide
- LCM Architecture Documentation
