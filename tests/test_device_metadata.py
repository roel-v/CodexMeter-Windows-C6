import json
import pytest

from codexmeter.device_metadata import DeviceMetadata, MAX_IDENTITY_BYTES


@pytest.mark.parametrize("model,size,caps", [
    ("waveshare_c6_amoled_216", 480, ["brightness", "rotation", "auto_rotation", "themes"]),
    ("spotpear_ball_v2", 240, ["brightness", "rotation", "touch", "screen"]),
])
def test_metadata_roundtrip_and_identity_budget(model, size, caps):
    fields = dict(model=model, firmware="3.12.3.0", protocol=1,
                  width=size, height=size, capabilities=caps)
    parsed = DeviceMetadata.from_json(fields)
    assert DeviceMetadata.from_json(parsed.to_json()) == parsed
    assert parsed.compatible
    identity = dict(device_id="codexmeter-6867f4697090", short_id="6867F4",
                    name="CodexMeter-6867F4", **fields)
    assert len(json.dumps(identity).encode()) <= MAX_IDENTITY_BYTES


def test_legacy_and_declared_empty_are_distinct():
    legacy = DeviceMetadata.from_json({})
    assert legacy.compatibility == "legacy"
    assert legacy.supports("auto_rotation") is None
    assert legacy.to_json() == {}
    explicit = DeviceMetadata.from_json({"capabilities": []})
    assert explicit.supports("auto_rotation") is False


def test_unknown_fields_and_future_capabilities_are_tolerated():
    parsed = DeviceMetadata.from_json({"future": {}, "capabilities": ["future_sensor"]})
    assert parsed.supports("future_sensor")
    assert not parsed.supports("auto_rotation")


def test_unknown_protocol_is_not_legacy():
    parsed = DeviceMetadata.from_json({"protocol": 2})
    assert not parsed.compatible
    assert parsed.compatibility == "incompatible"


@pytest.mark.parametrize("fields", [
    {"protocol": True}, {"protocol": "1"}, {"protocol": 0}, {"protocol": None},
    {"width": 240}, {"width": 0, "height": 240}, {"capabilities": "touch"},
    {"capabilities": [None]}, {"capabilities": ["x"] * 17},
    {"model": "bad\nmodel"}, {"firmware": "x" * 49},
])
def test_malformed_metadata_fails_closed(fields):
    with pytest.raises(ValueError):
        DeviceMetadata.from_json(fields)
