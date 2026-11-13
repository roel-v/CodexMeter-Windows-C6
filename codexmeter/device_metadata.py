"""Optional device metadata shared by identity parsing and the device registry.

Absence means legacy/unknown, never an inferred hardware capability.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

MAX_IDENTITY_BYTES = 512
SUPPORTED_PROTOCOL = 1
_TOKEN = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")


@dataclass(frozen=True)
class DeviceMetadata:
    model: str | None = None
    firmware: str | None = None
    protocol: int | None = None
    width: int | None = None
    height: int | None = None
    capabilities: tuple[str, ...] | None = None

    @property
    def compatible(self) -> bool:
        return self.protocol is None or self.protocol == SUPPORTED_PROTOCOL

    @property
    def compatibility(self) -> str:
        if self.protocol is None:
            return "legacy"
        return "compatible" if self.compatible else "incompatible"

    def supports(self, capability: str) -> bool | None:
        """None preserves legacy handling; an explicit empty list supports nothing."""
        if self.capabilities is None:
            return None
        return capability in self.capabilities

    def to_json(self) -> dict[str, Any]:
        values = {key: getattr(self, key) for key in
                  ("model", "firmware", "protocol", "width", "height")}
        if self.capabilities is not None:
            values["capabilities"] = list(self.capabilities)
        return {key: value for key, value in values.items() if value is not None}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DeviceMetadata":
        # Malformed declared metadata is not silently downgraded to legacy.
        values: dict[str, Any] = {}
        for key in ("model", "firmware"):
            if key not in data:
                continue
            value = data[key]
            if not isinstance(value, str) or not value or len(value) > 48 or not value.isascii():
                raise ValueError(f"invalid device {key}")
            if any(ord(char) < 32 or ord(char) == 127 for char in value):
                raise ValueError(f"invalid device {key}")
            values[key] = value
        for key in ("protocol", "width", "height"):
            if key not in data:
                continue
            value = data[key]
            maximum = 65535 if key == "protocol" else 4096
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"invalid device {key}")
            values[key] = value
        if ("width" in values) != ("height" in values):
            raise ValueError("device dimensions require both width and height")
        if "capabilities" in data:
            caps = data["capabilities"]
            if not isinstance(caps, list) or len(caps) > 16:
                raise ValueError("invalid device capabilities")
            if any(not isinstance(cap, str) or not _TOKEN.fullmatch(cap) for cap in caps):
                raise ValueError("invalid device capability")
            values["capabilities"] = tuple(sorted(set(caps)))
        return cls(**values)
