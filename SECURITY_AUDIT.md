# Brain Guard Security Audit Report

**Date:** 2026-03-26  
**Auditor:** Security Engineer Subagent  
**Scope:** /home/ubuntu/brain-guard/  
**Version:** 1.0.0

---

## Executive Summary

This security audit covers the Brain Guard plugin, an OpenClaw plugin for monitoring LLM conversation coherence. The codebase is written in Python and uses SQLite/PostgreSQL for storage, FastAPI for the dashboard, and embedding services for semantic analysis.

**Overall Risk Level:** MEDIUM-HIGH

The plugin handles sensitive conversation data but lacks several critical security controls. While the core architecture is sound, there are authentication weaknesses, input validation gaps, and configuration security issues that should be addressed before deployment in production environments.

---

## 1. Critical Security Issues (Must Fix Before Deployment)

### CRITICAL-001: Hardcoded Auth Token Generation in Dashboard
**Location:** `src/api/dashboard.py:47-48`

```python
def _generate_token(self) -> str:
    import secrets
    return secrets.token_urlsafe(32)
```

**Issue:** While the token generation uses `secrets`, the token is logged at startup:
```python
logger.info(f"Auth token: {self.auth_token[:8]}...")
```

**Risk:** Partial token exposure in logs could aid brute-force attacks.

**Fix:** Remove token logging entirely or log only a hash of the token for verification purposes.

---

### CRITICAL-002: SQL Injection via String Concatenation in Dynamic Queries
**Location:** `src/database/db_manager.py:244-260`

```python
async def get_metrics(
    self,
    session_id: str,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None
) -> List[Dict]:
    query = "SELECT * FROM metrics WHERE session_id = ?"
    params: List[Any] = [session_id]
    
    if start_time:
        query += " AND timestamp >= ?"
        params.append(start_time)
    
    if end_time:
        query += " AND timestamp <= ?"
        params.append(end_time)
    
    query += " ORDER BY timestamp ASC"
```

**Issue:** While this specific implementation uses parameterized queries correctly, the pattern of string concatenation for SQL is dangerous. Other methods like `get_recent_sessions` accept a `limit` parameter that is directly interpolated:

```python
return await self._backend.fetchall(
    """SELECT * FROM sessions 
       ORDER BY updated_at DESC 
       LIMIT ?""",
    (limit,)  # This is safe
)
```

**Risk:** MEDIUM - Current implementation is safe, but the pattern is risky for future modifications.

**Fix:** Add input validation for `limit` parameter (ensure it's a positive integer within bounds).

---

### CRITICAL-003: Missing Authentication on Health Check Endpoint
**Location:** `src/api/dashboard.py:68-73`

```python
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "brain-guard-dashboard",
        "version": "1.0.0"
    }
```

**Issue:** The health endpoint is publicly accessible without authentication. While health checks typically don't require auth, this endpoint reveals service presence and version information.

**Risk:** Information disclosure; aids reconnaissance for attackers.

**Fix:** Either require auth or reduce information disclosure (remove version).

---

## 2. High Priority Issues

### HIGH-001: CORS Misconfiguration Allows All Origins
**Location:** `src/api/dashboard.py:52-58`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=self.cors_origins,  # Defaults to ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Issue:** The CORS configuration allows credentials with potentially broad origins. If `cors_origins` is misconfigured to include `*` or attacker-controlled domains, this creates a security risk.

**Risk:** Cross-origin attacks if origins are misconfigured.

**Fix:** 
1. Validate CORS origins against an allowlist
2. Reject wildcard origins when `allow_credentials=True`
3. Add validation in config loading

---

### HIGH-002: No Rate Limiting on API Endpoints
**Location:** `src/api/dashboard.py` (all endpoints)

**Issue:** No rate limiting is implemented on any dashboard API endpoints. This makes the service vulnerable to:
- Brute force attacks on the auth token
- Resource exhaustion via expensive queries
- Denial of service

**Risk:** DoS, brute force attacks.

**Fix:** Implement rate limiting using `slowapi` or similar:
```python
from slowapi import Limiter
limiter = Limiter(key_func=lambda: request.client.host)
```

---

### HIGH-003: Session ID Injection Without Validation
**Location:** `src/__init__.py:152-158`

```python
async def preprocess_message(
    self,
    session_id: str,
    user_message: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
```

**Issue:** `session_id` is passed directly to database queries without validation. While SQLite parameters prevent SQL injection, invalid session IDs could cause issues.

**Risk:** Potential injection in logging, file paths, or other contexts.

**Fix:** Validate session_id format (UUID or alphanumeric with fixed length).

---

### HIGH-004: API Key Exposure in Config Files
**Location:** `config/brain-guard.yml:19`

```yaml
embedding:
  api_key: ""  # Set via env var: OPENAI_API_KEY
```

**Issue:** While the comment suggests using env vars, the config structure allows API keys to be stored in YAML files which may be committed to version control.

**Risk:** Credential leakage via git history.

**Fix:** 
1. Remove `api_key` from config schema
2. Only read API keys from environment variables
3. Add pre-commit hooks to detect secrets

---

### HIGH-005: No HTTPS Enforcement
**Location:** `src/api/dashboard.py`

**Issue:** The dashboard server runs HTTP by default with no TLS/SSL configuration option.

**Risk:** Credentials and sensitive data transmitted in plaintext.

**Fix:** 
1. Add HTTPS/TLS configuration options
2. Document reverse proxy setup (nginx/traefik)
3. Add HSTS headers when HTTPS is enabled

---

## 3. Medium Priority Issues

### MEDIUM-001: Verbose Error Messages Leak Information
**Location:** `src/__init__.py:175-176`

```python
except Exception as e:
    logger.error(f"Error in preprocess_message: {e}")
    return {"conditioned_input": user_message, "metadata": {"error": str(e)}}
```

**Issue:** Error messages are returned to the caller, potentially leaking internal implementation details.

**Risk:** Information disclosure aiding attackers.

**Fix:** Return generic error messages to users; log detailed errors internally.

---

### MEDIUM-002: No Input Sanitization on User Messages
**Location:** `src/components/preprocessor.py:41-55`

```python
async def process(
    self,
    session_id: str,
    message: str,
    domain: str = "general"
) -> Dict[str, Any]:
```

**Issue:** User messages are processed without sanitization. While regex patterns are used, there's no protection against:
- Log injection (newline characters in logs)
- Embedding service poisoning
- Storage of malicious content

**Risk:** Log injection, potential downstream issues.

**Fix:** Sanitize input by removing/replacing control characters before processing.

---

### MEDIUM-003: Cache Key Collision Risk
**Location:** `src/utils/embedding_service.py:93-95`

```python
def _get_cache_key(self, text: str) -> str:
    """Generate cache key for text."""
    return hashlib.md5(text.encode()).hexdigest()
```

**Issue:** MD5 is used for cache keys. While not a security issue for caching, MD5 is cryptographically broken and should not be used for any security-sensitive purposes.

**Risk:** Low for caching, but bad practice.

**Fix:** Use SHA-256 for cache keys.

---

### MEDIUM-004: No Secrets Management for Database Credentials
**Location:** `src/utils/config.py:189-194`

```python
# BRAIN_GUARD_DB_URL
env_db = os.environ.get("BRAIN_GUARD_DB_URL")
if env_db:
    if "storage" not in config:
        config["storage"] = {}
    config["storage"]["connection_string"] = env_db
```

**Issue:** Database connection strings may contain passwords. No secure secrets management is implemented.

**Risk:** Credential exposure in environment variables.

**Fix:** 
1. Support separate DB_USER, DB_PASS, DB_HOST variables
2. Consider integration with secret managers (AWS Secrets Manager, etc.)

---

### MEDIUM-005: Missing Content Security Policy Headers
**Location:** `src/api/dashboard.py`

**Issue:** No CSP headers are set, increasing XSS risk if the dashboard serves HTML.

**Risk:** XSS attacks if HTML content is served.

**Fix:** Add CSP headers:
```python
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

---

## 4. Low Priority Recommendations

### LOW-001: Add Security Headers
**Location:** `src/api/dashboard.py`

Add the following security headers to all responses:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`

---

### LOW-002: Implement Request ID Logging
Add unique request IDs to all requests for audit trail and debugging.

---

### LOW-003: Add Database Connection Encryption
Ensure database connections use TLS when connecting to PostgreSQL over a network.

---

### LOW-004: Implement Audit Logging
Add structured audit logs for:
- Authentication attempts (success/failure)
- Configuration changes
- Intervention triggers
- Session access

---

### LOW-005: Add Dependency Scanning
**Location:** `requirements.txt`

Implement automated dependency scanning (e.g., `safety`, `snyk`, `dependabot`) to detect vulnerable packages.

---

## 5. Security Best Practices Not Followed

### 5.1 Input Validation
- **Missing:** Comprehensive input validation on all API parameters
- **Impact:** Potential injection attacks, DoS
- **Fix:** Use Pydantic models for all API inputs with strict validation

### 5.2 Principle of Least Privilege
- **Missing:** Database permissions are not restricted (uses full access)
- **Impact:** If compromised, attacker has full DB access
- **Fix:** Create separate DB users with minimal required permissions

### 5.3 Defense in Depth
- **Missing:** No WAF or reverse proxy configuration
- **Impact:** Direct exposure to attacks
- **Fix:** Document deployment behind nginx/traefik with security rules

### 5.4 Secure Defaults
- **Missing:** Dashboard binds to all interfaces by default in some configurations
- **Impact:** Unintended exposure
- **Fix:** Default to localhost-only binding

### 5.5 Secrets Rotation
- **Missing:** No mechanism for rotating auth tokens or API keys without restart
- **Impact:** Long-lived credentials increase exposure window
- **Fix:** Implement hot-reload for credentials

### 5.6 Security Testing
- **Missing:** No security-focused tests (no tests for auth bypass, injection, etc.)
- **Impact:** Vulnerabilities may go undetected
- **Fix:** Add security test cases to test suite

---

## Appendix A: File-by-File Risk Assessment

| File | Risk Level | Key Issues |
|------|------------|------------|
| `src/api/dashboard.py` | HIGH | Auth bypass, CORS, no rate limiting |
| `src/database/db_manager.py` | MEDIUM | Input validation gaps |
| `src/utils/config.py` | MEDIUM | Secrets handling |
| `src/utils/embedding_service.py` | LOW | MD5 usage |
| `src/components/preprocessor.py` | MEDIUM | Input sanitization |
| `src/__init__.py` | MEDIUM | Error handling, session validation |
| `config/brain-guard.yml` | MEDIUM | Potential credential storage |

---

## Appendix B: Recommended Security Checklist

Before deployment, ensure:

- [ ] Auth token logging removed
- [ ] Rate limiting implemented
- [ ] HTTPS/TLS configured
- [ ] Input validation added to all endpoints
- [ ] CORS origins restricted
- [ ] Security headers added
- [ ] Secrets management implemented
- [ ] Audit logging enabled
- [ ] Dependency scanning configured
- [ ] Security tests passing
- [ ] Database permissions restricted
- [ ] WAF/reverse proxy configured

---

## Conclusion

The Brain Guard plugin has a solid architectural foundation but requires security hardening before production deployment. The critical and high-priority issues should be addressed immediately, particularly around authentication, rate limiting, and input validation.

**Estimated Remediation Time:** 2-3 days for critical/high issues, 1 week for full hardening.
