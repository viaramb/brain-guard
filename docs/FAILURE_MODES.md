# Brain Guard Failure Modes & Outlier Analysis

> **Note:** Brain Guard was formerly known as SCFL-Observatory.

## Executive Summary

This document analyzes potential failure modes, outliers, and edge cases for the Brain Guard plugin. Each failure mode is categorized by severity, likelihood, and mitigation strategy.

---

## 1. Latency & Performance Failures

### 1.1 Embedding Service Degradation

**Description:** Embedding API (OpenAI, local model) becomes slow or unavailable.

**Impact:**
- ΔG calculation fails or times out
- Coherence monitoring effectively disabled

**Likelihood:** Medium (external dependency)

**Detection:**
- Monitor `embedding_response_time_ms`
- Alert on P95 > 200ms
- Track error rate from embedding calls

**Mitigations:**
1. **Circuit Breaker:** Open after 5 consecutive failures
2. **Fallback:** Use string similarity (Levenshtein, Jaccard) as degraded mode
3. **Caching:** Aggressive caching with extended TTL during outages
4. **Queue:** Defer non-critical metric calculations

**Outlier Scenarios:**
- Very long messages (10k+ tokens) causing embedding timeouts
- Rate limiting from embedding provider
- Network partition to embedding service

---

### 1.2 Database Performance Degradation

**Description:** Metrics database becomes slow or unresponsive.

**Impact:**
- Metrics not persisted
- Dashboard queries timeout
- Potential memory pressure from buffering

**Likelihood:** Low-Medium

**Detection:**
- Query execution time monitoring
- Connection pool exhaustion alerts
- Disk space monitoring

**Mitigations:**
1. **Write Buffering:** In-memory queue with overflow to disk
2. **Sampling:** Store only 1/N metrics under load
3. **Async Writes:** Don't block response on DB write
4. **Fallback to SQLite:** Local file if PostgreSQL unavailable

**Outlier Scenarios:**
- Sudden traffic spike (viral moment)
- Database corruption
- Backup operation locking tables

---

### 1.3 Memory Exhaustion

**Description:** Session state grows unbounded, causing OOM.

**Impact:**
- Plugin crash
- Potential OpenClaw gateway restart
- Session data loss

**Likelihood:** Low (with proper limits)

**Detection:**
- Heap usage per session
- Total memory consumption
- GC pressure metrics

**Mitigations:**
1. **Session TTL:** Auto-close after 24h inactivity
2. **Anchor Limits:** Max 50 anchors per session (evict LRU)
3. **Metric Pruning:** Keep only last 100 turns in memory
4. **Emergency GC:** Force collection at 80% heap

**Outlier Scenarios:**
- Extremely long-running session (1000+ turns)
- Adversarial input designed to create many anchors
- Memory leak in embedding cache

---

## 2. Accuracy & False Signal Failures

### 2.1 False Positives (Over-Triggering)

**Description:** SCFL triggers interventions when conversation is actually coherent.

**Impact:**
- User annoyance
- Unnecessary regenerations (latency, cost)
- Loss of trust in system

**Likelihood:** Medium (threshold tuning phase)

**Root Causes:**
1. Thresholds too aggressive
2. Legitimate topic changes flagged as drift
3. Creative/ambiguous content misclassified
4. Embedding model limitations

**Mitigations:**
1. **Gradual Escalation:** Start with silent mode, collect data
2. **User Feedback:** Track user responses to interventions
3. **Per-Domain Tuning:** Different thresholds for medical vs creative
4. **Context Awareness:** Don't flag drift in first 3 turns

**Outlier Scenarios:**
- User intentionally rapid context-switching
- Brainstorming sessions (high variance is expected)
- Code switching between languages

---

### 2.2 False Negatives (Under-Triggering)

**Description:** SCFL misses actual drift or ruptures.

**Impact:**
- Hallucinations reach user
- Silent degradation of conversation quality
- Institutional risk (medical, legal)

**Likelihood:** Medium-High (inherent difficulty)

**Root Causes:**
1. Thresholds too permissive
2. Subtle drift below detection threshold
3. Sophisticated hallucinations that preserve coherence metrics
4. Embedding blind spots

**Mitigations:**
1. **Multi-Signal Detection:** Don't rely solely on ΔG
2. **Anchor Contradiction:** Check for factual conflicts
3. **Human-in-the-Loop:** High-stakes mode requires confirmation
4. **Continuous Calibration:** A/B test threshold adjustments

**Outlier Scenarios:**
- Gradual drift over 50+ turns (boiling frog)
- Coherent but factually wrong statements
- Semantic drift (words change meaning gradually)

---

### 2.3 Shared Hallucination Detection Failure

**Description:** Both LLM and embedding model share the same false belief.

**Impact:**
- Hallucination appears coherent (high continuity score)
- No intervention triggered
- Particularly dangerous for institutional use

**Likelihood:** Low (but high impact)

**Example:**
- LLM: "The capital of Australia is Sydney"
- Embedding model also trained on same misconception
- ΔG low because both agree

**Mitigations:**
1. **External Fact-Checking:** Integrate with knowledge base
2. **Uncertainty Quantification:** Track model confidence
3. **Anchor Verification:** Cross-reference with trusted sources
4. **Human Review:** Flag low-confidence anchors for review

---

## 3. Integration Failures

### 3.1 OpenClaw Gateway Compatibility

**Description:** Plugin incompatible with gateway version or other plugins.

**Impact:**
- Gateway crash on load
- Silent hook failures
- Message loss

**Likelihood:** Low (with proper testing)

**Mitigations:**
1. **Version Pinning:** Declare compatible gateway versions
2. **Graceful Degradation:** Continue without SCFL if hooks fail
3. **Isolation:** Catch all errors, don't propagate to gateway
4. **Health Checks:** Self-test on startup

**Outlier Scenarios:**
- Conflict with LCM compaction timing
- Race condition with gigabrain memory updates
- Plugin load order dependencies

---

### 3.2 LCM/RLM Coordination Issues

**Description:** SCFL and LCM/RLM interfere with each other's state.

**Impact:**
- Inconsistent session view
- Metrics calculated on compacted (lossy) data
- RLM patterns based on corrupted SCFL data

**Likelihood:** Low (clear architectural separation)

**Mitigations:**
1. **Strict Ordering:** SCFL runs pre-LCM, always
2. **Immutable Snapshots:** SCFL captures state before LCM
3. **Event Sourcing:** Log all state changes
4. **Consistency Checks:** Verify state alignment periodically

---

## 4. Security & Privacy Failures

### 4.1 Data Leakage Between Sessions

**Description:** Session A's anchors or metrics visible in Session B.

**Impact:**
- Privacy violation
- Cross-user information leakage
- Compliance failure (GDPR, HIPAA)

**Likelihood:** Low (with proper isolation)

**Mitigations:**
1. **Strict Session Isolation:** No shared state between sessions
2. **User ID Validation:** Verify session ownership on every access
3. **Audit Logging:** Log all cross-session access attempts
4. **Data Sanitization:** Anonymize metrics for aggregate views

---

### 4.2 Dashboard Unauthorized Access

**Description:** Dashboard API accessed without proper authentication.

**Impact:**
- Session content exposure
- Metrics manipulation
- System reconnaissance

**Likelihood:** Low (with auth)

**Mitigations:**
1. **Mandatory Auth:** No unauthenticated endpoints
2. **Token Rotation:** Auto-rotate dashboard tokens
3. **Rate Limiting:** Prevent brute force
4. **IP Whitelisting:** Optional network-level restriction

---

### 4.3 Prompt Injection via Anchors

**Description:** Malicious user crafts input that becomes an anchor and influences later responses.

**Impact:**
- Jailbreak via anchor manipulation
- Persistent prompt injection across turns

**Likelihood:** Medium (adversarial users)

**Mitigations:**
1. **Anchor Sanitization:** Strip special characters, limit length
2. **Confidence Scoring:** Low confidence for unusual anchors
3. **Manual Review:** Flag suspicious anchors for review
4. **Expiration:** Anchors expire after N turns unless reinforced

---

## 5. Operational Failures

### 5.1 Configuration Drift

**Description:** Production config diverges from intended settings.

**Impact:**
- Unexpected behavior
- Threshold changes without audit trail
- Inconsistent monitoring across instances

**Likelihood:** Medium (human error)

**Mitigations:**
1. **Config Validation:** Reject invalid configs on startup
2. **Version Control:** Track config changes in git
3. **Immutable Deployments:** Config baked into deployment
4. **Runtime Verification:** Periodically verify effective config

---

### 5.2 Silent Degradation

**Description:** SCFL gradually becomes less effective without triggering alerts.

**Impact:**
- False sense of security
- Undetected hallucinations
- Gradual threshold creep

**Likelihood:** Medium (over time)

**Mitigations:**
1. **Baseline Monitoring:** Track detection rates over time
2. **Canary Sessions:** Known drift patterns, verify detection
3. **Regular Calibration:** Scheduled threshold reviews
4. **A/B Testing:** Compare intervention strategies

---

## 6. Outlier Scenarios

### 6.1 Extreme Conversation Patterns

| Pattern | Risk | Mitigation |
|---------|------|------------|
| Single-turn session | No drift possible, wasted overhead | Skip SCFL for <3 turns |
| 1000+ turn session | Memory exhaustion, metric overflow | Force session split at 500 turns |
| 100 msg/min burst | Database overload, latency spike | Circuit breaker, sampling |
| All caps / no punctuation | Embedding quality degradation | Preprocess normalization |
| Code-heavy conversation | Syntax affects coherence metrics | Code-aware segmentation |
| Multi-language mixing | Embedding model confusion | Language detection, separate thresholds |

---

### 6.2 Adversarial Attacks

| Attack | Description | Defense |
|--------|-------------|---------|
| Metric Gaming | Craft responses to always show low ΔG | Multi-signal detection |
| Anchor Flooding | Create thousands of fake anchors | Rate limiting, anchor limits |
| Latency Amplification | Force expensive calculations | Circuit breaker, timeouts |
| Session Hijacking | Access another user's session | Strict auth, session validation |
| Dashboard DoS | Overwhelm dashboard API | Rate limiting, IP blocking |

---

### 6.3 Environmental Edge Cases

| Scenario | Risk | Mitigation |
|----------|------|------------|
| Clock skew | Out-of-order timestamps | NTP sync, monotonic clocks |
| Timezone confusion | Incorrect aggregation | Store all times in UTC |
| Leap second | Timestamp anomalies | Handle sub-second precision |
| DST transition | Missing/extra hour in aggregations | Use UTC for all internals |
| Year 2038 | 32-bit timestamp overflow | Use 64-bit timestamps |

---

## 7. Testing Outliers

### 7.1 Chaos Engineering Scenarios

```python
# Example chaos tests to implement

class ChaosTests:
    def test_embedding_service_outage(self):
        """Simulate embedding API failure"""
        with mock_embedding_failure():
            response = process_message("Test message")
            assert response.fallback_mode == "string_similarity"
            assert response.coherence_score is not None

    def test_database_partition(self):
        """Simulate network partition to DB"""
        with network_partition_to_db():
            for i in range(1000):
                process_message(f"Message {i}")
            assert metrics_buffer_size() > 0  # Buffered in memory
        # After partition heals
        assert_all_metrics_flushed()

    def test_memory_pressure(self):
        """Simulate low memory condition"""
        with memory_limit(100 * MB):
            session = create_session()
            for i in range(1000):
                session.add_anchor(f"Anchor {i}")
            assert session.anchor_count <= 50  # LRU eviction

    def test_rapid_context_switching(self):
        """User rapidly changes topics"""
        topics = ["sports", "politics", "cooking", "physics"] * 25
        for topic in topics:
            response = process_message(f"Tell me about {topic}")
        # Should not trigger false ruptures
        assert rupture_count() < 5
```

---

## 8. Monitoring & Alerting

### 8.1 Key Metrics to Watch

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| P95 latency | > 50ms | > 100ms | Enable circuit breaker |
| Embedding error rate | > 1% | > 5% | Switch to fallback |
| DB write latency | > 100ms | > 500ms | Enable buffering |
| Memory usage | > 70% | > 90% | Force GC, evict sessions |
| False positive rate | > 10% | > 20% | Raise thresholds |
| False negative rate | > 30% | > 50% | Lower thresholds |
| Session count | > 1000 | > 5000 | Reject new sessions |

### 8.2 Alert Routing

| Severity | Channel | Response Time |
|----------|---------|---------------|
| Warning | Slack #alerts | 1 hour |
| Critical | PagerDuty | 15 minutes |
| Emergency | Phone call | 5 minutes |

---

## 9. Recovery Procedures

### 9.1 Emergency Procedures

**Circuit Breaker Triggered:**
1. Switch to degraded mode (string similarity)
2. Alert on-call engineer
3. Investigate embedding service
4. Gradual ramp-up after recovery

**Database Unavailable:**
1. Buffer metrics in memory
2. Alert operations team
3. If buffer > 80%, sample metrics (store 1/10)
4. Replay buffer after DB recovery

**Memory Exhaustion:**
1. Force garbage collection
2. Evict oldest 20% of sessions
3. Reject new sessions temporarily
4. Investigate for memory leaks

---

## 10. Lessons from Similar Systems

### 10.1 Prometheus/Grafana Alerting
- False positive alerts cause alert fatigue
- Solution: Multi-condition alerts, require N consecutive failures

### 10.2 Netflix Chaos Monkey
- Random failures expose hidden dependencies
- Solution: Regular chaos testing in staging

### 10.3 Google SRE Error Budgets
- 100% reliability is impossible and expensive
- Solution: Define acceptable error rates, prioritize features

---

## Summary Table

| Failure Mode | Severity | Likelihood | Detection | Mitigation |
|--------------|----------|------------|-----------|------------|
| Embedding degradation | High | Medium | Latency monitoring | Circuit breaker, fallback |
| Database slowdown | Medium | Low | Query timing | Async writes, buffering |
| Memory exhaustion | Critical | Low | Heap monitoring | Limits, eviction |
| False positives | Medium | Medium | User feedback | Gradual escalation |
| False negatives | High | Medium | Baseline testing | Multi-signal detection |
| Config drift | Medium | Medium | Config validation | Immutable deployments |
| Security breach | Critical | Low | Audit logs | Strict auth, isolation |
| Adversarial attack | Medium | Low | Anomaly detection | Rate limiting, sanitization |

---

## Recommendations

1. **Start Conservative:** Begin with high thresholds, lower gradually based on data
2. **Measure Everything:** You can't improve what you don't measure
3. **Test Failures:** Regular chaos engineering exercises
4. **Plan for Degradation:** System should work (less well) when components fail
5. **Human Override:** Always provide escape hatches for operators
