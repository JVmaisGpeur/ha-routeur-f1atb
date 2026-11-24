"""Diagnostics (secrets du routeur masqués)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import parsers as P
from .const import CONF_HOST

TO_REDACT = {CONF_HOST, "mac", "ip", "hostname", "known_ips"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    c = entry.runtime_data
    cfg = c.config
    return {
        "entry": async_redact_data({"data": dict(entry.data), "options": dict(entry.options)}, TO_REDACT),
        "firmware": {"api": cfg.firmware.api, "version": cfg.firmware.version, "tested": cfg.firmware.tested} if cfg else None,
        "read_only": c.read_only,
        "read_only_reason": c.read_only_reason,
        "router_config": P.redact(cfg.raw_redacted) if cfg else None,
        "actions": [
            {"index": a.index, "title": a.title, "mode": a.mode, "force_opening": a.force_opening,
             "slots": [s.as_dict() for s in a.slots]}
            for a in (cfg.actions if cfg else [])
        ],
        "state": {k: v for k, v in c.state.items()},
        "data": async_redact_data(dict(c.data or {}), TO_REDACT | {"system"}),
        "last_error": c.last_error,
    }
