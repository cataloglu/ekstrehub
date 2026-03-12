import json
import logging
from datetime import UTC, datetime


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
    )


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=True))
