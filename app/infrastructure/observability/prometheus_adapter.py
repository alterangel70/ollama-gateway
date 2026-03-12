"""
Prometheus metrics adapter — implements IMetrics using prometheus_client.
"""
from typing import Dict, Optional
from prometheus_client import Counter, Histogram, Gauge

from ...domain.ports import IMetrics


# Module-level metric singletons.
# prometheus_client raises an error if a metric is registered twice,
# so metrics are initialised once and shared across all PrometheusMetrics instances.
_counters = None
_histograms = None
_gauges = None


def _initialize_metrics():
    """Register all Prometheus metrics. Safe to call multiple times (idempotent)."""
    global _counters, _histograms, _gauges

    if _counters is not None:
        return

    _counters = {
        "llm_requests_total": Counter(
            "llm_requests_total",
            "Total number of LLM requests",
            ["model", "status"]
        )
    }

    _histograms = {
        "llm_duration_seconds": Histogram(
            "llm_duration_seconds",
            "End-to-end LLM response time in seconds",
            ["model"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 90.0, 120.0, 180.0, 300.0, 600.0]
        ),
        "llm_tokens_total": Histogram(
            "llm_tokens_total",
            "Token count per LLM request, split by input/output",
            ["model", "type"],
            buckets=[10, 50, 100, 250, 500, 750, 1000, 1500, 2000, 3000, 4000, 6000, 8000]
        ),
        "llm_prompt_length": Histogram(
            "llm_prompt_length",
            "Prompt length in characters",
            ["model"],
            buckets=[100, 250, 500, 1000, 2000, 3000, 5000, 7500, 10000, 15000, 20000, 30000, 50000]
        )
    }

    _gauges = {
        "llm_active_requests": Gauge(
            "llm_active_requests",
            "Number of LLM requests currently being processed"
        ),
        "llm_last_request_timestamp": Gauge(
            "llm_last_request_timestamp",
            "Unix timestamp of the last successfully completed LLM request"
        )
    }


class PrometheusMetrics(IMetrics):
    """IMetrics implementation backed by prometheus_client."""

    def __init__(self):
        """Bind to the module-level metric singletons, initialising them on first use."""
        _initialize_metrics()
        self._counters = _counters
        self._histograms = _histograms
        self._gauges = _gauges

    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a named counter by value."""
        if name in self._counters:
            if labels:
                self._counters[name].labels(**labels).inc(value)
            else:
                self._counters[name].inc(value)

    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Observe a value in a named histogram."""
        if name in self._histograms:
            if labels:
                self._histograms[name].labels(**labels).observe(value)
            else:
                self._histograms[name].observe(value)

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a named gauge to an absolute value."""
        if name in self._gauges:
            if labels:
                self._gauges[name].labels(**labels).set(value)
            else:
                self._gauges[name].set(value)


class NoOpMetrics(IMetrics):
    """No-op IMetrics implementation. Use when metrics collection is disabled."""

    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        pass

    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        pass

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        pass
