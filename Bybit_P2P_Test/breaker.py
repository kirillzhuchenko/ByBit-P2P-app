"""
Circuit Breaker Implementation for P2P Bot
==========================================

Save this as circuit_breaker.py in your project directory.
Then import and use in main.py

Author: Your P2P Bot
Date: 2026-01-18
"""

from datetime import datetime
from typing import Callable, Any, Optional
import asyncio
from notifier import send_telegram_message


class CircuitBreaker:
    """
    Circuit Breaker Pattern for API resilience.

    Prevents repeated calls to failing services by:
    1. Tracking consecutive failures
    2. Opening circuit after max failures
    3. Auto-testing recovery after timeout
    4. Closing circuit when service recovers

    Usage:
        breaker = CircuitBreaker(max_failures=5, timeout=60.0, name="Wise API")

        result = await breaker.call(some_async_function)
    """

    def __init__(
            self,
            max_failures: int = 5,
            timeout: float = 60.0,
            name: str = "unnamed",
            alert_callback: Optional[Callable] = None
    ):
        """
        Initialize circuit breaker.

        Args:
            max_failures: Number of consecutive failures before opening
            timeout: Seconds to wait before testing recovery
            name: Name for logging (e.g., "Wise Transfers")
            alert_callback: Optional function to call on state changes
                           Example: lambda msg: send_telegram_message(msg)
        """
        self.max_failures = max_failures
        self.timeout = timeout
        self.name = name
        self.alert_callback = alert_callback

        # State tracking
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_state_change = datetime.now()

        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0

        print(f"🔧 Circuit Breaker initialized: {self.name}")
        print(f"   Max failures: {self.max_failures} | Timeout: {self.timeout}s")

    def _should_attempt(self) -> bool:
        """
        Determine if we should attempt the call.

        Returns:
            True if call should be attempted, False otherwise
        """
        if self.state == "CLOSED":
            # Normal operation - always attempt
            return True

        if self.state == "OPEN":
            # Circuit is open - check if timeout passed
            if self.last_failure_time is None:
                return False

            elapsed = (datetime.now() - self.last_failure_time).total_seconds()

            if elapsed >= self.timeout:
                # Timeout passed - enter HALF_OPEN to test recovery
                self._transition_to_half_open()
                return True
            else:
                # Still in timeout period - reject
                return False

        if self.state == "HALF_OPEN":
            # Testing recovery - allow one attempt
            return True

        return False

    def _transition_to_half_open(self):
        """Transition from OPEN to HALF_OPEN state."""
        print(f"🟡 [{self.name}] Circuit breaker: OPEN → HALF_OPEN (testing recovery)")
        self.state = "HALF_OPEN"
        self.last_state_change = datetime.now()

    async def call(self, func: Callable) -> Any:
        """
        Execute function through circuit breaker.

        Args:
            func: Async function (or lambda) to execute
                  Example: lambda: api.get_balance()

        Returns:
            Result from func()

        Raises:
            Exception: If circuit is open OR if func() raises

        Example:
            async def get_balance():
                return await api.get_balance()

            balance = await breaker.call(get_balance)

            # Or with lambda:
            balance = await breaker.call(lambda: api.get_balance())
        """
        self.total_calls += 1

        # Check if circuit allows the call
        if not self._should_attempt():
            remaining = self.timeout - (datetime.now() - self.last_failure_time).total_seconds()
            error_msg = (
                f"Circuit breaker is OPEN for {self.name} "
                f"(retry in {remaining:.0f}s)"
            )
            raise CircuitBreakerOpenError(error_msg)

        # Attempt the call
        try:
            # If func is a lambda, call it to get the coroutine
            result = await func()

            # Success - handle state transition
            self._on_success()
            return result

        except Exception as e:
            # Failure - handle state transition
            self._on_failure(e)
            raise  # Re-raise the original exception

    def _on_success(self):
        """Handle successful call - may close circuit."""
        self.total_successes += 1

        if self.state == "HALF_OPEN":
            # Recovery test successful - close circuit
            print(f"✅ [{self.name}] Circuit breaker: HALF_OPEN → CLOSED (service recovered!)")
            send_telegram_message(f"✅ [{self.name}] Circuit breaker: HALF_OPEN → CLOSED (service recovered!)")

            if self.alert_callback:
                try:
                    self.alert_callback(
                        f"✅ SERVICE RECOVERED\n"
                        f"Circuit Breaker: {self.name}\n"
                        f"Status: CLOSED (operational)"
                    )
                    send_telegram_message(
                        f"✅ SERVICE RECOVERED\n"
                        f"Circuit Breaker: {self.name}\n"
                        f"Status: CLOSED (operational)"
                    )
                except:
                    pass  # Don't fail if alert fails

            self.state = "CLOSED"
            self.failures = 0
            self.last_state_change = datetime.now()

        elif self.state == "CLOSED":
            # Reset failure counter on success during normal operation
            if self.failures > 0:
                print(f"✅ [{self.name}] Failure counter reset (was {self.failures})")
                send_telegram_message(f"✅ [{self.name}] Failure counter reset (was {self.failures})")
                self.failures = 0

    def _on_failure(self, exception: Exception):
        """Handle failed call - may open circuit."""
        self.total_failures += 1
        self.failures += 1
        self.last_failure_time = datetime.now()

        error_preview = str(exception)[:50]

        if self.state == "HALF_OPEN":
            # Recovery test failed - reopen circuit
            print(f"❌ [{self.name}] Circuit breaker: HALF_OPEN → OPEN (service still down)")
            print(f"   Error: {error_preview}")
            send_telegram_message(f"❌ [{self.name}] Circuit breaker: HALF_OPEN → OPEN (service still down)")

            self.state = "OPEN"
            self.last_state_change = datetime.now()

        elif self.state == "CLOSED":
            # Check if we should open circuit
            if self.failures >= self.max_failures:
                print(f"🔴 [{self.name}] Circuit breaker: CLOSED → OPEN")
                print(f"   Reason: {self.failures} consecutive failures")
                print(f"   Last error: {error_preview}")
                send_telegram_message(f"🔴 [{self.name}] Circuit breaker: CLOSED → OPEN")
                send_telegram_message(f"   Reason: {self.failures} consecutive failures")
                send_telegram_message(f"   Last error: {error_preview}")

                if self.alert_callback:
                    try:
                        self.alert_callback(
                            f"🔴 CIRCUIT BREAKER OPENED\n"
                            f"Service: {self.name}\n"
                            f"Consecutive failures: {self.failures}\n"
                            f"Will retry in: {self.timeout}s\n"
                            f"Error: {error_preview}"
                        )
                        send_telegram_message(
                            f"🔴 CIRCUIT BREAKER OPENED\n"
                            f"Service: {self.name}\n"
                            f"Consecutive failures: {self.failures}\n"
                            f"Will retry in: {self.timeout}s\n"
                            f"Error: {error_preview}"
                        )
                    except:
                        pass

                self.state = "OPEN"
                self.last_state_change = datetime.now()
            else:
                print(f"⚠️ [{self.name}] Failure {self.failures}/{self.max_failures}: {error_preview}")
                send_telegram_message(f"⚠️ [{self.name}] Failure {self.failures}/{self.max_failures}: {error_preview}")

    def get_stats(self) -> dict:
        """
        Get current circuit breaker statistics.

        Returns:
            Dictionary with current state and statistics
        """
        time_in_state = (datetime.now() - self.last_state_change).total_seconds()

        return {
            "name": self.name,
            "state": self.state,
            "failures": self.failures,
            "max_failures": self.max_failures,
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "success_rate": (
                f"{(self.total_successes / self.total_calls * 100):.1f}%"
                if self.total_calls > 0 else "0.0%"
            ),
            "time_in_current_state_seconds": int(time_in_state),
            "time_in_current_state": self._format_duration(time_in_state),
        }

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds into human-readable duration."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def reset(self):
        """
        Manually reset circuit breaker to CLOSED state.
        Use this for manual recovery or testing.
        """
        print(f"🔄 [{self.name}] Manual reset - circuit breaker CLOSED")
        self.state = "CLOSED"
        self.failures = 0
        self.last_failure_time = None
        self.last_state_change = datetime.now()

    def __repr__(self):
        """String representation for debugging."""
        return (
            f"CircuitBreaker(name='{self.name}', state={self.state}, "
            f"failures={self.failures}/{self.max_failures})"
        )


class CircuitBreakerOpenError(Exception):
    """Custom exception raised when circuit breaker is open."""
    pass


# ============================================================================
# HELPER FUNCTION: Print Dashboard
# ============================================================================

def print_circuit_breaker_dashboard(breakers: list[CircuitBreaker]):
    """
    Print a visual dashboard of all circuit breakers.

    Args:
        breakers: List of CircuitBreaker instances to display

    Example:
        print_circuit_breaker_dashboard([
            wise_transfers_breaker,
            bybit_orders_breaker,
        ])
    """
    print("\n╔" + "=" * 78 + "╗")
    print("║" + " CIRCUIT BREAKER DASHBOARD ".center(78) + "║")
    print("╠" + "=" * 78 + "╣")

    state_icons = {
        "CLOSED": "🟢",
        "OPEN": "🔴",
        "HALF_OPEN": "🟡"
    }

    for breaker in breakers:
        stats = breaker.get_stats()
        icon = state_icons.get(stats["state"], "⚪")

        # Row 1: Name and state
        name_part = f"{icon} {stats['name']:<30}"
        state_part = f"State: {stats['state']:<10}"
        print(f"║ {name_part} │ {state_part} ║")

        # Row 2: Failures and success rate
        fail_part = f"Failures: {stats['failures']}/{stats['max_failures']:<15}"
        success_part = f"Success: {stats['success_rate']:<10}"
        print(f"║   {fail_part} │ {success_part} ║")

        # Row 3: Time in state
        time_part = f"Time in state: {stats['time_in_current_state']}"
        print(f"║   {time_part:<73} ║")

        # Separator
        print("╠" + "─" * 78 + "╣")

    print("╚" + "=" * 78 + "╝\n")


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """Example of how to use CircuitBreaker in your code."""

    # 1. Create circuit breaker with Telegram alerts
    def send_alert(message: str):
        print(f"📱 TELEGRAM ALERT: {message}")

    breaker = CircuitBreaker(
        max_failures=3,
        timeout=10.0,
        name="Example API",
        alert_callback=send_alert
    )

    # 2. Simulate flaky API
    call_count = 0

    async def flaky_api():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)

        # Fail first 3 calls, then succeed
        if call_count <= 3:
            raise Exception(f"API Error 502 (call {call_count})")

        return f"Success! (call {call_count})"

    # 3. Use circuit breaker
    print("Starting example...\n")

    for i in range(8):
        try:
            result = await breaker.call(flaky_api)
            print(f"Attempt {i + 1}: ✅ {result}")
        except CircuitBreakerOpenError as e:
            print(f"Attempt {i + 1}: 🔴 {e}")
        except Exception as e:
            print(f"Attempt {i + 1}: ❌ {e}")

        # Show stats
        stats = breaker.get_stats()
        print(f"  → State: {stats['state']} | Failures: {stats['failures']}/{stats['max_failures']}\n")

        await asyncio.sleep(1)

    # Wait for timeout
    print("Waiting for timeout (10s)...")
    await asyncio.sleep(11)

    # Try again - should recover
    try:
        result = await breaker.call(flaky_api)
        print(f"Recovery attempt: ✅ {result}")
    except Exception as e:
        print(f"Recovery attempt: ❌ {e}")

    # Final stats
    print("\nFinal Statistics:")
    print_circuit_breaker_dashboard([breaker])


if __name__ == "__main__":
    # Run example
    print("=" * 80)
    print("CIRCUIT BREAKER EXAMPLE")
    print("=" * 80 + "\n")
    asyncio.run(example_usage())