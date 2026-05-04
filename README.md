# BSCS22012 | Circuit Breaker Pattern Implementation

## Usage

### Server

```bash
uv run uvicorn main:app --reload
```

### Tests

```bash
uv run test_circuit_breaker.py
```

Covers:

1. Health check and X-Student-ID header presence
2. Normal operation (circuit closed)
3. Circuit opens after failures
4. Fallback response when circuit is open
5. Circuit recovery after timeout
