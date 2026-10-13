"""Quota providers."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass, field, replace

from .app_server import JsonRpcClient
from .limits import (
    UsageSnapshot,
    usage_snapshot_from_rate_limits,
)
from .local_usage import LocalTokenUsageReader


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CodexUsageProvider:
    """Fetch Codex subscription limits through the local Codex App Server."""

    codex_bin: str = "codex"
    timeout_sec: float = 15.0
    refresh_token: bool = False
    local_usage_reader: LocalTokenUsageReader | None = field(
        default_factory=LocalTokenUsageReader,
        compare=False,
        repr=False,
    )
    _usage_diagnostics: dict[str, object] = field(
        default_factory=dict,
        compare=False,
        repr=False,
    )

    async def fetch(self) -> UsageSnapshot:
        async with JsonRpcClient(self.codex_bin, self.timeout_sec) as client:
            await client.initialize()
            await client.request("account/read", {"refreshToken": self.refresh_token})
            rate_limits = await client.request("account/rateLimits/read")
        snapshot = usage_snapshot_from_rate_limits(rate_limits)
        if self.local_usage_reader is None:
            return snapshot
        try:
            now = dt.datetime.now().astimezone()
            daily = await asyncio.to_thread(self.local_usage_reader.read_daily_tokens, now)
        except Exception:
            # Local activity is optional; subscription quotas remain available.
            LOGGER.warning("Local token activity unavailable", exc_info=True)
            return snapshot
        if daily is None:
            return snapshot

        today_tokens = daily[now.date()]
        last_7d_tokens = sum(daily.values())
        self._log_local_usage_change(daily)
        return replace(snapshot, today_tokens=today_tokens, last_7d_tokens=last_7d_tokens)

    def _log_local_usage_change(self, daily: dict[dt.date, int]) -> None:
        signature = tuple(sorted(daily.items()))
        if self._usage_diagnostics.get("daily") == signature:
            return
        self._usage_diagnostics["daily"] = signature
        LOGGER.info(
            "Codex local token activity source=local_sessions first_date=%s "
            "last_date=%s today=%s last_7d=%s daily=%s",
            signature[0][0],
            signature[-1][0],
            signature[-1][1],
            sum(daily.values()),
            ",".join(f"{day}:{tokens}" for day, tokens in signature),
        )
