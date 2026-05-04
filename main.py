from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
import time
from enum import Enum
from datetime import datetime, timedelta

# Circuit Breaker Configuration
STUDENT_ID = "BSCS22012"

class CircuitBreakerState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Stop making requests
    HALF_OPEN = "half_open"  # Testing if service is back


class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_timeout=5):
        """
        Initialize Circuit Breaker
        - failure_threshold: Number of failures before opening circuit
        - recovery_timeout: Seconds before trying to recover
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time = None
        self.last_check_time = None

    def record_success(self):
        """Record a successful request"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time = None

    def record_failure(self):
        """Record a failed request"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN

    def can_attempt_request(self):
        """Check if we should attempt to make a request"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time and \
               (datetime.now() - self.last_failure_time).total_seconds() > self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False

    def get_status(self):
        """Return circuit breaker status"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


# Global Circuit Breaker instance
circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5)

# Create FastAPI app
app = FastAPI(title="StudySync LLM Service with Circuit Breaker")


# Custom Middleware to add X-Student-ID header
class StudentIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Student-ID"] = STUDENT_ID
        return response


# Add the middleware
app.add_middleware(StudentIDMiddleware)


# Mock LLM Service with global state for testing
class MockLLMService:
    def __init__(self):
        self.is_failing = False
        self.delay = 0

    def set_failing(self, failing: bool, delay: int = 60):
        """Set if the LLM service should fail"""
        self.is_failing = failing
        self.delay = delay

    async def generate_text(self, prompt: str) -> str:
        """Simulate calling an external LLM API"""
        if self.is_failing:
            # Simulate timeout by sleeping
            time.sleep(self.delay)
            raise TimeoutError(f"LLM API timed out after {self.delay} seconds")
        
        # Simulate successful response with slight delay
        time.sleep(0.1)
        return f"LLM Response to '{prompt}': This is a generated response from the AI assistant."


mock_llm = MockLLMService()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "circuit_breaker": circuit_breaker.get_status()
    }


@app.post("/generate-text")
async def generate_text(prompt: str):
    """
    Generate text using the LLM API with Circuit Breaker protection.
    
    If the circuit is OPEN (LLM is failing), immediately return a fallback response
    without attempting to call the failing service.
    """
    
    # Check if circuit breaker allows request
    if not circuit_breaker.can_attempt_request():
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "message": "The AI assistant is currently unavailable. Please try again later.",
                "circuit_breaker_state": circuit_breaker.state.value,
                "reason": "Circuit breaker is OPEN - LLM service is not responding"
            }
        )
    
    try:
        # Attempt to call the LLM
        response = await mock_llm.generate_text(prompt)
        circuit_breaker.record_success()
        
        return {
            "status": "success",
            "prompt": prompt,
            "response": response,
            "circuit_breaker_state": circuit_breaker.state.value
        }
    
    except TimeoutError as e:
        circuit_breaker.record_failure()
        
        # If circuit is now open, return fallback immediately
        if circuit_breaker.state == CircuitBreakerState.OPEN:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "message": "The AI assistant is currently busy. Please try again in a few minutes.",
                    "circuit_breaker_state": circuit_breaker.state.value,
                    "reason": "Circuit breaker is OPEN - too many failures detected"
                }
            )
        
        # Still CLOSED or HALF_OPEN, return error but keep trying
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": str(e),
                "circuit_breaker_state": circuit_breaker.state.value,
                "failure_count": circuit_breaker.failure_count
            }
        )
    
    except Exception as e:
        circuit_breaker.record_failure()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
                "circuit_breaker_state": circuit_breaker.state.value
            }
        )


@app.get("/circuit-breaker-status")
async def get_circuit_breaker_status():
    """Get current circuit breaker status"""
    return circuit_breaker.get_status()


@app.post("/test-control/fail-llm")
async def fail_llm(duration: int = 60):
    """
    Test endpoint to simulate LLM failure.
    
    This is ONLY for testing purposes.
    """
    mock_llm.set_failing(True, duration)
    return {
        "message": "LLM service is now failing",
        "will_timeout_after": duration,
        "circuit_breaker_state": circuit_breaker.state.value
    }


@app.post("/test-control/recover-llm")
async def recover_llm():
    """
    Test endpoint to recover the LLM service.
    
    This is ONLY for testing purposes.
    """
    mock_llm.set_failing(False)
    circuit_breaker.record_success()
    return {
        "message": "LLM service is recovered",
        "circuit_breaker_state": circuit_breaker.state.value
    }


@app.post("/test-control/reset-circuit-breaker")
async def reset_circuit_breaker():
    """
    Test endpoint to reset the circuit breaker.
    
    This is ONLY for testing purposes.
    """
    global circuit_breaker
    circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5)
    return {
        "message": "Circuit breaker reset",
        "circuit_breaker_state": circuit_breaker.get_status()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
