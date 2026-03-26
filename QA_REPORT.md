# Brain Guard QA Test Report

**Generated:** 2026-03-26  
**Test Framework:** pytest 9.0.2 with pytest-cov  
**Target Coverage:** 80% (FAIL - Current: 70.64% for unit tests, 45.65% for integration)

---

## 1. Test Execution Summary

### Overall Results
| Test Category | Passed | Failed | Errors | Total |
|--------------|--------|--------|--------|-------|
| Unit Tests   | 87     | 38     | 0      | 125   |
| Integration  | 7      | 11     | 20     | 38    |
| E2E Tests    | 0      | 0      | 12     | 12    |
| **TOTAL**    | **94** | **49** | **32** | **175** |

### Pass Rate: 53.7% (94/175)

---

## 2. Coverage Report

### Unit Test Coverage by Module
| Module | Statements | Missed | Coverage |
|--------|-----------|--------|----------|
| src/components/coherence_monitor.py | 104 | 4 | **96%** |
| src/components/preprocessor.py | 115 | 10 | **91%** |
| src/components/threshold_engine.py | 111 | 10 | **91%** |
| src/components/domain_detector.py | 93 | 11 | **88%** |
| src/components/session_anchoring.py | 168 | 20 | **88%** |
| src/database/db_manager.py | 147 | 22 | **85%** |
| src/utils/config.py | 151 | 16 | **89%** |
| src/utils/__init__.py | 151 | 51 | 66% |
| src/utils/embedding_service.py | 140 | 60 | 57% |
| src/__init__.py (plugin) | 142 | 103 | 27% |
| src/api/dashboard.py | 139 | 122 | 12% |
| **TOTAL** | **1461** | **429** | **70.64%** |

**Status:** FAIL - Below 80% threshold

---

## 3. Critical Issues

### 3.1 Configuration Schema Mismatch (BLOCKER)
**Impact:** 49 test failures, 32 errors

The `LatencyConfig` dataclass is missing the `circuit_breaker_timeout_ms` field that exists in the YAML config:

```python
# src/utils/config.py (line 18-23)
@dataclass
class LatencyConfig:
    target_ms: int = 50
    max_ms: int = 100
    circuit_breaker_threshold: float = 0.95
    async_metrics: bool = True
    # MISSING: circuit_breaker_timeout_ms
```

```yaml
# config/brain-guard.yml (line 33-36)
latency:
  max_ms: 500
  circuit_breaker_threshold: 5
  circuit_breaker_timeout_ms: 30000  # This field causes TypeError
```

**Affected Tests:**
- All plugin tests (17 failures)
- All config env override tests (8 failures)
- All integration tests requiring plugin initialization (20 errors)
- All E2E tests (12 errors)

### 3.2 Mock Embedding Service API Mismatch
**Impact:** 4 test failures

`MockEmbeddingService` in `tests/mocks/embedding_service.py` doesn't accept `cache_enabled` parameter in `__init__`, but tests try to pass it.

**Fix:** Add `cache_enabled: bool = False` parameter to constructor.

### 3.3 Domain Detection Logic Issues
**Impact:** 2 test failures

- `test_detect_finance_domain`: "What are ETFs?" returns 'general' instead of 'finance'
- `test_detect_ai_domain`: "Tell me about neural networks." returns 'general' instead of 'ai'

The keyword matching is case-sensitive or the keywords are missing from domain configuration.

### 3.4 Coherence Monitor Logic Errors
**Impact:** 3 test failures

- `test_related_sentences`: Expects delta_g < 0.8 but gets 1.0
- `test_perfect_continuity`: Returns False when expecting True
- `test_drift_velocity_calculation`: Negative drift velocity when positive expected

### 3.5 Session Anchoring Issues
**Impact:** 5 test failures

- `test_no_anchors_in_greeting`: Extracts anchor from "Hello, how are you?" when it shouldn't
- `test_contradiction_detection`: No contradictions detected when expected
- `test_anchor_deactivation`: Anchor ordering/retrieval issue
- `test_temporal_anchor`: Temporal anchor type not extracted
- `test_anchor_retrieval`: Similarity-based retrieval not working correctly

### 3.6 Preprocessor Scoring Issues
**Impact:** 2 test failures

- `test_empty_prompt`: Returns 0.2 ambiguity instead of 0.0
- `test_ambiguous_prompt`: Returns 0.1 ambiguity instead of >0.5

---

## 4. Missing Test Cases

### 4.1 Error Handling & Edge Cases
- **Database connection failures** - No tests for SQLite/PostgreSQL connection errors
- **Malformed config files** - Missing tests for invalid YAML/JSON
- **Embedding service failures** - No tests for OpenAI API errors or network timeouts
- **Memory exhaustion scenarios** - No tests for large session handling
- **Concurrent access** - Missing thread-safety tests for shared components

### 4.2 Integration Gaps
- **Real embedding service tests** - All tests use mocks; no validation against actual OpenAI/SentenceTransformers
- **Database migration tests** - Schema versioning not tested
- **Dashboard API authentication** - Only basic auth tests exist
- **Plugin lifecycle edge cases** - Shutdown during active processing not tested

### 4.3 Performance Tests
- **Latency budget enforcement** - No tests verifying <50ms target
- **Memory usage under load** - No memory profiling tests
- **Cache eviction policies** - Embedding cache behavior not tested

### 4.4 Security Tests
- **Input sanitization** - SQL injection, XSS prevention not tested
- **Auth token validation** - Dashboard token handling not fully tested
- **CORS policy enforcement** - Partial coverage only

---

## 5. Mock Services Assessment

### 5.1 Working Correctly
- `MockDatabaseManager` - Full implementation, all methods functional
- `MockThresholdEngine` - Basic implementation sufficient for unit tests
- `MockCoherenceMonitor` - Returns predictable mock metrics
- `MockSessionAnchoring` - Basic anchor extraction works

### 5.2 Needs Fixes
- `MockEmbeddingService` (tests/mocks/embedding_service.py)
  - Missing `cache_enabled` parameter in constructor
  - Missing `cache_size` parameter handling
  - Cache stats methods present but untested with caching enabled

### 5.3 Missing Mock Services
- `MockDashboardAPI` - No mock for dashboard endpoints
- `MockOpenClawGateway` - Gateway integration relies on real (failing) plugin init

---

## 6. Recommendations

### Immediate Actions (Priority 1)
1. **Fix LatencyConfig schema** - Add `circuit_breaker_timeout_ms: int = 30000` field
2. **Fix MockEmbeddingService** - Add missing `cache_enabled` parameter
3. **Fix domain detector keywords** - Add "ETFs", "neural networks" to respective domains

### Short-term (Priority 2)
4. **Fix coherence monitor drift calculation** - Review delta_g and drift_velocity formulas
5. **Fix session anchoring greeting filter** - Add greeting phrase detection
6. **Fix preprocessor ambiguity scoring** - Adjust scoring for empty/ambiguous prompts
7. **Add error handling tests** - Database failures, network timeouts, malformed inputs

### Medium-term (Priority 3)
8. **Improve coverage** - Focus on:
   - `src/__init__.py` (plugin) - currently 27%
   - `src/api/dashboard.py` - currently 12%
   - `src/utils/embedding_service.py` - currently 57%
9. **Add performance benchmarks** - Latency, memory usage tests
10. **Add chaos tests** - Failure injection, circuit breaker behavior

### Testing Infrastructure
11. **Separate test configs** - Create `config/brain-guard.test.yml` for testing
12. **Add CI pipeline** - Automated test runs on commits
13. **Add coverage gates** - Block PRs below 80% coverage

---

## 7. Files Requiring Attention

| File | Issue |
|------|-------|
| `src/utils/config.py` | Add `circuit_breaker_timeout_ms` to LatencyConfig |
| `tests/mocks/embedding_service.py` | Add `cache_enabled` parameter |
| `src/components/domain_detector.py` | Fix keyword matching for finance/AI domains |
| `src/components/coherence_monitor.py` | Fix drift velocity calculation |
| `src/components/session_anchoring.py` | Fix greeting filter, contradiction detection |
| `src/components/preprocessor.py` | Fix ambiguity scoring logic |
| `tests/unit/test_plugin.py` | All tests blocked by config issue |
| `tests/integration/test_*.py` | Most tests blocked by config issue |
| `tests/e2e/test_*.py` | All tests blocked by config issue |

---

## 8. Conclusion

The Brain Guard test suite has **critical configuration issues** preventing the majority of tests from running. Once the `LatencyConfig` schema mismatch is resolved, the true state of test coverage can be assessed. 

**Current State:** 53.7% pass rate with 70.64% coverage (below 80% target)  
**After Config Fix (estimated):** ~75% pass rate possible, coverage may improve to ~78%

**Recommendation:** Address the Priority 1 issues immediately to unblock development, then systematically work through Priority 2 and 3 items.
