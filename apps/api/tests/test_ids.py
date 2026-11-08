"""UUIDv7 identifier guarantees."""

import time
import uuid

from smena_api.core.ids import new_uuid7


def test_uuid7_version_and_variant() -> None:
    value = new_uuid7()
    assert isinstance(value, uuid.UUID)
    assert value.version == 7
    assert value.variant == uuid.RFC_4122


def test_uuid7_unique_across_many_calls() -> None:
    values = {new_uuid7() for _ in range(10_000)}
    assert len(values) == 10_000


def test_uuid7_is_time_ordered() -> None:
    first = new_uuid7()
    time.sleep(0.005)
    second = new_uuid7()
    assert first.bytes < second.bytes
