"""Report unexpected exceptions in the config, options and room flows (0.26.4.3).

Home Assistant only shows "Unknown error occurred" when a flow step raises. The
wrapper below keeps that behaviour (the exception is re-raised unchanged) but first
stores a privacy-safe signature in the local diagnostics and - only with the
user's diagnostics consent and reporting not switched off - reports it to the Hub.
"""
from __future__ import annotations

import functools
import logging
import sys
from typing import Any

from .flow_error_signature import flow_error_message, flow_error_signature

_LOGGER = logging.getLogger(__name__)
# Exceptions Home Assistant raises on purpose to control a flow; never bugs.
_FLOW_CONTROL = {"AbortFlow", "UnknownFlow", "UnknownStep", "InvalidData", "UnknownHandler", "FlowError"}


def _entry_of(flow: Any) -> Any:
    for getter in ("_get_entry",):
        fn = getattr(flow, getter, None)
        if callable(fn):
            try:
                return fn()
            except Exception:  # not available in this flow type
                pass
    try:
        return getattr(flow, "config_entry", None)
    except Exception:
        return None


async def _async_report(flow: Any, signature: dict[str, Any]) -> None:
    entry = _entry_of(flow)
    coordinator = getattr(entry, "runtime_data", None) if entry is not None else None
    recorder = getattr(coordinator, "diagnostics", None)
    if recorder is not None and hasattr(recorder, "async_record_flow_error"):
        await recorder.async_record_flow_error(signature)
    telemetry = getattr(coordinator, "telemetry", None)
    if telemetry is None or entry is None:
        return
    from .diagnostic_transport import effective_reporting_mode, normalise_consent
    options = dict(getattr(entry, "options", {}) or {})
    if normalise_consent(options.get("diagnostics_consent")) != "granted" or effective_reporting_mode(options) == "off":
        return
    await telemetry.async_report_client_error(
        code=signature["code"], component="config_flow",
        operation=f"{signature['flow']}.{signature['step']}", message=flow_error_message(signature),
    )


def _wrap(flow_name: str, step_name: str, fn: Any) -> Any:
    @functools.wraps(fn)
    async def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(self, *args, **kwargs)
        except Exception as err:
            if type(err).__name__ in _FLOW_CONTROL:
                raise  # Home Assistant uses these for normal flow control (abort etc.)
            signature = flow_error_signature(err, sys.exc_info()[2], flow=flow_name, step=step_name)
            _LOGGER.error("FreshAirIQ %s (%s)", signature["code"], flow_error_message(signature))
            hass = getattr(self, "hass", None)
            if hass is not None:
                async def _report() -> None:
                    try:
                        await _async_report(self, signature)
                    except Exception:  # reporting must never hide the original error
                        _LOGGER.debug("FreshAirIQ flow error report failed", exc_info=True)
                hass.async_create_task(_report())
            raise
    wrapper.__faiq_flow_guard__ = True
    return wrapper


def guard_flow_steps(cls: type, flow_name: str) -> type:
    """Wrap every ``async_step_*`` defined on ``cls`` (idempotent)."""
    for name, value in list(vars(cls).items()):
        if name.startswith("async_step_") and callable(value) and not getattr(value, "__faiq_flow_guard__", False):
            setattr(cls, name, _wrap(flow_name, name.removeprefix("async_step_"), value))
    return cls
