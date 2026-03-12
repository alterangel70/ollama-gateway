"""
Seq structured logging adapter with automatic console fallback.
"""
import logging
import sys
from typing import Any, Optional

from ...domain.ports import ILogger


class SeqLogger(ILogger):
    """ILogger implementation that ships structured logs to a Seq server.

    Automatically falls back to console logging if the Seq endpoint is
    unreachable or fails to initialise.
    """
    
    def __init__(
        self,
        seq_url: str = "http://localhost:5340",
        api_key: Optional[str] = None,
        level: str = "INFO",
        app_name: str = "ollama-api",
        fallback_to_console: bool = True
    ):
        """
        Args:
            seq_url: Seq ingestion HTTP endpoint.
            api_key: API key for Seq authentication. Leave None if not required.
            level: Minimum log level (DEBUG, INFO, WARNING, ERROR).
            app_name: Application name attached to every log event.
            fallback_to_console: When True, routes logs to stdout if Seq is unavailable.
        """
        self.logger = logging.getLogger(app_name)
        self.logger.setLevel(getattr(logging, level.upper()))
        self.fallback_to_console = fallback_to_console
        
        # Attempt to configure the seqlog handler.
        try:
            import seqlog
            seqlog.log_to_seq(
                server_url=seq_url,
                api_key=api_key,
                level=getattr(logging, level.upper()),
                batch_size=10,
                auto_flush_timeout=2,
                override_root_logger=False
            )
            self.seq_available = True
            self._log_info("Seq logger initialised", seq_url=seq_url)

        except Exception as e:
            self.seq_available = False
            if fallback_to_console:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(getattr(logging, level.upper()))
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                console_handler.setFormatter(formatter)
                self.logger.addHandler(console_handler)
                self.logger.warning(
                    f"Seq unavailable, falling back to console: {str(e)}"
                )
    
    def _log_info(self, message: str, **context: Any) -> None:
        """Internal helper used during initialisation to avoid recursion."""
        if self.seq_available:
            self.logger.info(message, extra={k: v for k, v in context.items()})
        else:
            ctx = " | ".join(f"{k}={v}" for k, v in context.items())
            self.logger.info(f"{message} {ctx if ctx else ''}")

    def info(self, message: str, **context: Any) -> None:
        """Log an informational message with optional structured properties."""
        if self.seq_available:
            self.logger.info(message, extra={k: v for k, v in context.items()})
        else:
            ctx = " | ".join(f"{k}={v}" for k, v in context.items())
            self.logger.info(f"{message} {ctx if ctx else ''}")

    def error(self, message: str, error: Optional[Exception] = None, **context: Any) -> None:
        """Log an error message, optionally attaching exception info and properties."""
        if error:
            context["error_type"] = type(error).__name__
            context["error_message"] = str(error)

        if self.seq_available:
            self.logger.error(message, extra={k: v for k, v in context.items()}, exc_info=error is not None)
        else:
            ctx = " | ".join(f"{k}={v}" for k, v in context.items())
            self.logger.error(f"{message} {ctx if ctx else ''}", exc_info=error is not None)

    def warning(self, message: str, **context: Any) -> None:
        """Log a warning message with optional structured properties."""
        if self.seq_available:
            self.logger.warning(message, extra={k: v for k, v in context.items()})
        else:
            ctx = " | ".join(f"{k}={v}" for k, v in context.items())
            self.logger.warning(f"{message} {ctx if ctx else ''}")


class ConsoleLogger(ILogger):
    """Lightweight ILogger implementation that writes to stdout.

    Intended for local development or as a drop-in when Seq is not available.
    """
    
    def __init__(self, level: str = "INFO"):
        self.logger = logging.getLogger("console")
        self.logger.setLevel(getattr(logging, level.upper()))
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper()))
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def info(self, message: str, **context: Any) -> None:
        """Log info with context"""
        ctx = " | ".join(f"{k}={v}" for k, v in context.items())
        self.logger.info(f"{message} {ctx if ctx else ''}")
    
    def error(self, message: str, error: Optional[Exception] = None, **context: Any) -> None:
        """Log error with context"""
        ctx = " | ".join(f"{k}={v}" for k, v in context.items())
        self.logger.error(f"{message} {ctx if ctx else ''}", exc_info=error is not None)
    
    def warning(self, message: str, **context: Any) -> None:
        """Log warning with context"""
        ctx = " | ".join(f"{k}={v}" for k, v in context.items())
        self.logger.warning(f"{message} {ctx if ctx else ''}")
