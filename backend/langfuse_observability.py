"""Optional Langfuse tracing for the analytics and ML workflow.

No transaction rows, customer identifiers, or credentials are sent to
Langfuse. Traces contain only query intent, selected dimensions, aggregate
counts, and model metrics. The application remains fully functional when
Langfuse is not configured or its SDK is unavailable.
"""

import logging
import os
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional

logger = logging.getLogger("control-tower.langfuse")


class LangfuseObserver:
    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._initialized = False

    def _get_client(self) -> Optional[Any]:
        if self._initialized:
            return self._client

        self._initialized = True
        if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
            logger.info("Langfuse tracing disabled: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are not both set.")
            return None

        try:
            from langfuse import get_client

            self._client = get_client()
            logger.info("Langfuse tracing enabled.")
        except Exception as exc:
            # Observability must never take down the live control tower.
            logger.warning("Langfuse tracing disabled: unable to initialize client: %s", exc)
        return self._client

    @contextmanager
    def span(self, name: str, trace_input: Dict[str, Any]) -> Iterator[Callable[[Dict[str, Any]], None]]:
        """Create a best-effort Langfuse span and yield an output recorder."""
        client = self._get_client()
        if client is None:
            yield lambda _output: None
            return

        try:
            observation_context = client.start_as_current_observation(
                as_type="span", name=name, input=trace_input,
            )
        except Exception as exc:
            logger.warning("Langfuse trace '%s' could not be started: %s", name, exc)
            yield lambda _output: None
            return

        application_error = False
        try:
            with observation_context as observation:
                try:
                    yield lambda output: observation.update(output=output)
                except Exception:
                    application_error = True
                    raise
        except Exception as exc:
            # Do not hide the query/model error that the span encloses. Errors
            # emitted solely by the observability SDK are non-fatal.
            if application_error:
                raise
            logger.warning("Langfuse trace '%s' could not be recorded: %s", name, exc)


langfuse_observer = LangfuseObserver()
