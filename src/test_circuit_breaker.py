"""
Test script for the Circuit Breaker pattern implementation.

This script demonstrates:
1. Normal operation (circuit CLOSED)
2. Failures causing the circuit to OPEN
3. Fallback responses when circuit is OPEN
4. Recovery when the service comes back online
"""

import time

import httpx
from colorama import Fore, Style, init

# Initialize colorama for colored output
init(autoreset=True)

BOLD = Style.BRIGHT

BASE_URL = "http://localhost:8000"
STUDENT_ID = "BSCS22012"


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{Fore.CYAN}{'=' * 70}")
    print(f"{Fore.CYAN}{title}")
    print(f"{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}")


def print_success(message):
    """Print success message"""
    print(f"{Fore.GREEN}[OK] {message}{Style.RESET_ALL}")


def print_error(message):
    """Print error message"""
    print(f"{Fore.RED}[FAIL] {message}{Style.RESET_ALL}")


def print_info(message):
    """Print info message"""
    print(f"{Fore.YELLOW}[INFO] {message}{Style.RESET_ALL}")


def verify_student_id_header(response):
    """Verify that X-Student-ID header is present"""
    if "X-Student-ID" in response.headers:
        if response.headers["X-Student-ID"] == STUDENT_ID:
            return True
    return False


def test_health_check():
    """Test 1: Verify the server is running and returning the custom header"""
    print_section("TEST 1: Health Check & Custom Header Verification")

    try:
        response = httpx.get(f"{BASE_URL}/health")

        if response.status_code == 200:
            print_success("Server is running")
        else:
            print_error(f"Unexpected status code: {response.status_code}")
            return False

        if verify_student_id_header(response):
            print_success(
                f"X-Student-ID header is present: {response.headers['X-Student-ID']}"
            )
        else:
            print_error("X-Student-ID header is missing or incorrect")
            return False

        data = response.json()
        print_info(f"Circuit breaker state: {data['circuit_breaker']['state']}")
        return True

    except Exception as e:
        print_error(f"Failed to connect to server: {e}")
        print_info("Make sure to run: uvicorn main:app --reload")
        return False


def test_normal_operation():
    """Test 2: Normal operation with circuit CLOSED"""
    print_section("TEST 2: Normal Operation (Circuit CLOSED)")

    try:
        # Reset circuit breaker first
        response = httpx.post(f"{BASE_URL}/test-control/reset-circuit-breaker")
        print_info("Circuit breaker reset")

        # Make a successful request
        response = httpx.post(
            f"{BASE_URL}/generate-text", params={"prompt": "Hello, how are you?"}
        )

        if response.status_code == 200:
            print_success("Request succeeded with status 200")
        else:
            print_error(f"Unexpected status code: {response.status_code}")
            return False

        if verify_student_id_header(response):
            print_success(
                f"X-Student-ID header present: {response.headers['X-Student-ID']}"
            )
        else:
            print_error("X-Student-ID header missing")
            return False

        data = response.json()
        print_info(f"Response: {data['response'][:60]}...")
        print_info(f"Circuit state: {data['circuit_breaker_state']}")
        return True

    except Exception as e:
        print_error(f"Test failed: {e}")
        return False


def test_circuit_breaker_opens():
    """Test 3: Simulate failures and verify circuit opens"""
    print_section("TEST 3: Circuit Breaker Opens After Failures")

    try:
        # Reset circuit breaker first
        httpx.post(f"{BASE_URL}/test-control/reset-circuit-breaker")
        print_info("Circuit breaker reset")

        # Make the LLM fail
        print_info("Simulating LLM API failures (timeout after 2 seconds)...")
        httpx.post(f"{BASE_URL}/test-control/fail-llm", params={"duration": 2})

        # Make requests until circuit opens
        failures = 0
        for i in range(5):
            try:
                print_info(f"Attempt {i + 1}: Calling generate-text...")
                response = httpx.post(
                    f"{BASE_URL}/generate-text",
                    params={"prompt": "Test prompt"},
                    timeout=5.0,
                )

                if not verify_student_id_header(response):
                    print_error("X-Student-ID header missing in error response")
                    return False

                data = response.json()
                state = data.get("circuit_breaker_state", "unknown")
                print_info(f"  Status: {response.status_code}, Circuit: {state}")

                if response.status_code == 503:
                    failures += 1
                    if "Circuit breaker is OPEN" in data.get("reason", ""):
                        print_success("Circuit breaker is now OPEN!")
                        return True

                time.sleep(0.5)

            except httpx.TimeoutException:
                print_error(f"Attempt {i + 1}: Request timed out")
                failures += 1

        print_error("Circuit breaker did not open as expected")
        return False

    except Exception as e:
        print_error(f"Test failed: {e}")
        return False


def test_fallback_response():
    """Test 4: Verify fallback response when circuit is OPEN"""
    print_section("TEST 4: Fallback Response When Circuit is OPEN")

    try:
        # Get circuit breaker status
        response = httpx.get(f"{BASE_URL}/circuit-breaker-status")
        data = response.json()

        if data["state"] == "open":
            print_success("Circuit breaker is OPEN")
        else:
            print_info(f"Circuit state: {data['state']} (Expected: open)")

        # Make a request - should get immediate fallback without timeout
        print_info("Making request to closed circuit (should return immediately)...")
        start_time = time.time()

        response = httpx.post(
            f"{BASE_URL}/generate-text",
            params={"prompt": "This should get fallback"},
            timeout=2.0,
        )

        elapsed = time.time() - start_time
        print_info(f"Response time: {elapsed:.2f} seconds")

        if elapsed < 1.0:
            print_success("Fallback returned immediately (< 1 second)")
        else:
            print_error(f"Response took too long: {elapsed:.2f}s")
            return False

        if response.status_code == 503:
            print_success("Got 503 Service Unavailable status")
        else:
            print_error(f"Unexpected status: {response.status_code}")
            return False

        if verify_student_id_header(response):
            print_success(
                f"X-Student-ID header present: {response.headers['X-Student-ID']}"
            )
        else:
            print_error("X-Student-ID header missing")
            return False

        data = response.json()
        print_info(f"Message: {data.get('message', 'N/A')}")
        return True

    except httpx.TimeoutException:
        print_error("Request timed out (circuit breaker did not prevent the call)")
        return False
    except Exception as e:
        print_error(f"Test failed: {e}")
        return False


def test_circuit_recovery():
    """Test 5: Verify circuit recovers after timeout"""
    print_section("TEST 5: Circuit Breaker Recovery")

    try:
        # Wait for recovery timeout
        print_info("Waiting 6 seconds for circuit recovery timeout...")
        time.sleep(6)

        # Recover the LLM service
        print_info("Recovering the LLM service...")
        httpx.post(f"{BASE_URL}/test-control/recover-llm")

        # Check circuit state
        response = httpx.get(f"{BASE_URL}/circuit-breaker-status")
        data = response.json()
        print_info(f"Circuit state: {data['state']}")

        # Try to make a request
        print_info("Attempting request after recovery...")
        response = httpx.post(
            f"{BASE_URL}/generate-text", params={"prompt": "Are you back online?"}
        )

        if response.status_code == 200:
            print_success("Request succeeded! Circuit has recovered")
        else:
            print_error(f"Request failed with status {response.status_code}")
            return False

        if verify_student_id_header(response):
            print_success(
                f"X-Student-ID header present: {response.headers['X-Student-ID']}"
            )
        else:
            print_error("X-Student-ID header missing")
            return False

        data = response.json()
        print_info(f"Circuit state: {data['circuit_breaker_state']}")
        return True

    except Exception as e:
        print_error(f"Test failed: {e}")
        return False


def main():
    """Run all tests"""
    print(f"\n{BOLD}{Fore.CYAN}Circuit Breaker Pattern - Test Suite{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Student ID: {STUDENT_ID}{Style.RESET_ALL}")
    print(
        f"{Fore.CYAN}This script validates the Circuit Breaker implementation{Style.RESET_ALL}"
    )

    results = {
        "Health Check": test_health_check(),
        "Normal Operation": test_normal_operation(),
        "Circuit Opens": test_circuit_breaker_opens(),
        "Fallback Response": test_fallback_response(),
        "Circuit Recovery": test_circuit_recovery(),
    }

    # Print summary
    print_section("TEST SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = (
            f"{Fore.GREEN}PASS{Style.RESET_ALL}"
            if result
            else f"{Fore.RED}FAIL{Style.RESET_ALL}"
        )
        print(f"  {test_name}: {status}")

    print(f"\n{BOLD}Total: {passed}/{total} tests passed{Style.RESET_ALL}\n")

    if passed == total:
        print(
            f"{Fore.GREEN}[OK] All tests passed! Circuit Breaker is working correctly.{Style.RESET_ALL}\n"
        )
    else:
        print(
            f"{Fore.RED}[FAIL] Some tests failed. Please check the implementation.{Style.RESET_ALL}\n"
        )


if __name__ == "__main__":
    main()
