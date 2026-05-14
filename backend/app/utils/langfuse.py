from __future__ import annotations

import logging
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from configs.settings import settings

logger = logging.getLogger(__name__)


def configure_langfuse_env() -> None:
    if settings.langfuse_public_key:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    if settings.langfuse_secret_key:
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    if settings.langfuse_base_url:
        os.environ.setdefault("LANGFUSE_BASE_URL", settings.langfuse_base_url)
    if settings.langfuse_tracing_environment:
        os.environ.setdefault("LANGFUSE_TRACING_ENVIRONMENT", settings.langfuse_tracing_environment)
    os.environ.setdefault("LANGFUSE_TRACING_ENABLED", str(settings.langfuse_tracing_enabled).lower())


def is_langfuse_enabled() -> bool:
    return bool(
        settings.langfuse_tracing_enabled
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    )


def _get_langfuse_client() -> Any | None:
    if not is_langfuse_enabled():
        return None

    configure_langfuse_env()
    try:
        from langfuse import get_client

        return get_client()
    except Exception as exc:
        logger.warning("Langfuse client is unavailable: %s", exc)
        return None


@contextmanager
def langfuse_observation(
    *,
    name: str,
    input_data: Any | None = None,
    metadata: dict[str, Any] | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    as_type: str = "span",
    model: str | None = None,
) -> Iterator[Any | None]:
    client = _get_langfuse_client()
    if client is None:
        yield None
        return

    try:
        from langfuse import propagate_attributes
    except Exception as exc:
        logger.warning("Langfuse propagation is unavailable: %s", exc)
        yield None
        return

    observation = None
    observation_cm = None
    propagation_cm = None
    exc_info = (None, None, None)
    try:
        kwargs: dict[str, Any] = {
            "as_type": as_type,
            "name": name,
            "input": input_data,
            "metadata": metadata,
        }
        if model:
            kwargs["model"] = model

        observation_cm = client.start_as_current_observation(**kwargs)
        observation = observation_cm.__enter__()
        propagation_cm = propagate_attributes(
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
            tags=tags,
        )
        propagation_cm.__enter__()
        yield observation
    except Exception:
        exc_info = sys.exc_info()
        raise
    finally:
        for manager in (propagation_cm, observation_cm):
            if manager is None:
                continue
            try:
                manager.__exit__(*exc_info)
            except Exception as exc:
                logger.warning("Langfuse observation close failed: %s", exc)


def update_langfuse_observation(observation: Any | None, **kwargs: Any) -> None:
    if observation is None:
        return
    try:
        observation.update(**kwargs)
    except Exception as exc:
        logger.warning("Langfuse observation update failed: %s", exc)


def flush_langfuse() -> None:
    client = _get_langfuse_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        logger.warning("Langfuse flush failed: %s", exc)
