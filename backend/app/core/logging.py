"""
Structured logging setup. Per documnets/understanding/12_SECURITY_COMPLIANCE_DPDP.md §4, audit
logs and records must be retained >=3 years and be sufficient to review/audit model operation and
outputs -- so every log line here is structured (JSON-capable), not free-text, from day one.

This is application/operational logging (crashes, request timing, provider errors) -- it is
distinct from app.db.models.audit.TurnAuditLog, which is the per-turn clinical/safety audit trail
required by the same section. Do not log Protected Information (raw user text, clinical content)
at INFO level or above; see 12_SECURITY_COMPLIANCE_DPDP.md §3 on need-to-know access.
"""

import logging
import sys

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
