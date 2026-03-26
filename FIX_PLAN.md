# Brain Guard Fix Plan

**Generated:** 2026-03-26  
**Based on:** ARCHITECT_REVIEW.md, QA_REPORT.md, SECURITY_AUDIT.md

---

## Executive Summary

This plan addresses the critical issues preventing Brain Guard from reaching a working, testable state. The focus is on unblocking development and achieving basic functionality, not perfection.

**Estimated Timeline:** 3-4 days to working state  
**Total Fixes:** 11 (5 P0, 4 P1, 2 P2)

---

## P0 - Critical (Deploy Blockers)

These issues prevent the plugin from initializing or cause runtime crashes. Must be fixed first.

### FIX-001: LatencyConfig Schema Mismatch (Issue A)
- **Problem:** The `LatencyConfig` dataclass is missing the `circuit_breaker_timeout_ms` field that exists in the YAML config. This causes a `TypeError` on plugin initialization, blocking all tests and runtime usage.
- **Files:** 
  - `src/utils/config.py` (add field to dataclass)
  - `config/brain-guard.yml` (verify field exists)
- **Effort:** small (30 minutes)
- **Agent:** backend-dev
- **Depends on:** None

### FIX-002: Contradiction Dataclass Mismatch (Issue B)
- **Problem:** Two different `Contradiction` dataclasses exist with incompatible fields. `ThresholdEngine` expects `anchor_text` and `new_text`, but `SessionAnchoring` provides `anchor_id`, `anchor_text`, `new_text`. This causes runtime errors when contradictions are detected.
- **Files:**
  - `src/components/threshold_engine.py` (lines 35-48)
  - `src/components/session_anchoring.py` (lines 52-65)
  - Create `src/models.py` (new shared models file)
- **Effort:** small (1 hour)
- **Agent:** backend-dev
- **Depends on:** None

### FIX-003: Synchronous SQLite Blocking Event Loop (Issue C)
- **Problem:** SQLite operations are synchronous and block the async event loop. The `async` methods are just a facade. Under any load, this will freeze the entire application.
- **Files:**
  - `src/database/db_manager.py` (replace with `aiosqlite` or thread pool)
  - `requirements.txt` (add `aiosqlite` dependency)
- **Effort:** medium (1 day)
- **Agent:** backend-dev
- **Depends on:** None

### FIX-004: Duplicate Config Code (Issue D)
- **Problem:** The entire `config.py` content is duplicated in `src/utils/__init__.py`. This creates maintenance nightmares and potential for divergence.
- **Files:**
  - `src/utils/__init__.py` (remove duplicate code, import from config.py)
- **Effort:** small (30 minutes)
- **Agent:** backend-dev
- **Depends on:** None

### FIX-005: Auth Token Exposure in Logs (Issue E)
- **Problem:** Dashboard server logs the first 8 characters of the auth token on startup. This leaks credential information and violates security best practices.
- **Files:**
  - `src/api/dashboard.py` (line 62, remove or mask token logging)
- **Effort:** small (15 minutes)
- **Agent:** security
- **Depends on:** None

---

## P1 - High Priority

These issues cause test failures or significant functional problems. Fix after P0 issues are resolved.

### FIX-006: MockEmbeddingService API Mismatch
- **Problem:** `MockEmbeddingService` doesn't accept `cache_enabled` parameter in `__init__`, but tests try to pass it. Causes 4 test failures.
- **Files:**
  - `tests/mocks/embedding_service.py` (add `cache_enabled: bool = False` parameter)
- **Effort:** small (15 minutes)
- **Agent:** qa-dev
- **Depends on:** FIX-001

### FIX-007: Missing Input Validation on Session IDs
- **Problem:** Session IDs are passed directly to database queries and used in file paths without validation. While SQLite parameters prevent SQL injection, invalid session IDs could cause issues in logging or other contexts.
- **Files:**
  - `src/__init__.py` (add validation in `preprocess_message`)
  - `src/components/coherence_monitor.py` (add validation)
  - Create validation utility in `src/utils/validation.py`
- **Effort:** small (2 hours)
- **Agent:** security
- **Depends on:** FIX-003

### FIX-008: Embedding Service Blocks on Model Load
- **Problem:** `LocalEmbeddingService._load_model()` runs synchronously in an async context. Large models will block the event loop during initialization.
- **Files:**
  - `src/utils/embedding_service.py` (lines 200-210, load in thread pool or pre-load at startup)
- **Effort:** medium (4 hours)
- **Agent:** backend-dev
- **Depends on:** None

### FIX-009: Rate Limiting on Dashboard API
- **Problem:** No rate limiting on API endpoints makes the service vulnerable to DoS attacks and brute force attempts on auth tokens.
- **Files:**
  - `src/api/dashboard.py` (add rate limiting middleware using `slowapi`)
  - `requirements.txt` (add `slowapi` dependency)
- **Effort:** small (2 hours)
- **Agent:** security
- **Depends on:** None

---

## P2 - Medium Priority

These issues affect code quality, test coverage, or have workarounds. Fix after core functionality is working.

### FIX-010: MD5 Used for Cache Keys
- **Problem:** MD5 is cryptographically broken and should not be used. While not a security vulnerability for caching (no crypto use), it's bad practice and suggests potential for collision attacks on cache poisoning.
- **Files:**
  - `src/utils/embedding_service.py` (line 95, replace MD5 with SHA-256 or xxhash)
- **Effort:** small (30 minutes)
- **Agent:** security
- **Depends on:** None

### FIX-011: Missing Processing Time Tracking
- **Problem:** `processing_time_ms` is initialized to 0.0 and never updated during calculation. The timestamp is set but actual processing time is not measured.
- **Files:**
  - `src/components/coherence_monitor.py` (line 82, add timing logic)
- **Effort:** small (30 minutes)
- **Agent:** backend-dev
- **Depends on:** None

---

## Implementation Order

### Day 1: Unblock Development
1. **FIX-001** (LatencyConfig) - Unblocks all tests
2. **FIX-004** (Duplicate Config) - Code cleanup
3. **FIX-002** (Contradiction Dataclass) - Fixes runtime errors

### Day 2: Core Stability
4. **FIX-003** (SQLite Async) - Critical performance fix
5. **FIX-005** (Auth Token Logging) - Security fix
6. **FIX-006** (MockEmbeddingService) - Fix remaining test failures

### Day 3: Hardening
7. **FIX-007** (Input Validation) - Security hardening
8. **FIX-008** (Embedding Service Blocking) - Performance fix
9. **FIX-009** (Rate Limiting) - Security hardening

### Day 4: Polish
10. **FIX-010** (MD5 Cache Keys) - Code quality
11. **FIX-011** (Processing Time) - Feature completion

---

## Success Criteria

After completing P0 and P1 fixes:

- [ ] Plugin initializes without errors
- [ ] Unit test pass rate > 80% (currently 53.7%)
- [ ] Integration tests can run (currently 20 errors blocking)
- [ ] No critical security issues remain
- [ ] Basic coherence monitoring works end-to-end

---

## Out of Scope (Future Work)

These issues are documented but not included in this fix plan:

- Domain detection keyword fixes (test failures for finance/AI domains)
- Coherence monitor drift calculation fixes
- Session anchoring greeting filter
- Preprocessor ambiguity scoring
- CORS origin validation improvements
- HTTPS/TLS configuration
- Comprehensive audit logging
- Dependency scanning setup

---

*End of Fix Plan*
