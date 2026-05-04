# BSCS22012 | Circuit Breaker Pattern Implementation

## Setup

```bash
git clone https://github.com/masroof-maindak/PDC-Sp26-BSCS22012-Asim.git pdc-asg02
cd pdc-asg02
```

Additionally, you will also need `uv` for project management. Install it via
your system's package manager.

## Usage

### Server

```bash
uv run uvicorn src.main:app --reload
# Alternatively: `make`
```

### Tests

```bash
uv run src/test_circuit_breaker.py
# Alternatively: `make test`
```

Covers:

1. Health check and X-Student-ID header presence
2. Normal operation (circuit closed)
3. Circuit opens after failures
4. Fallback response when circuit is open
5. Circuit recovery after timeout
