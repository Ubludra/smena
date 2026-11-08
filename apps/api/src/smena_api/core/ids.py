"""Public identifier generation.

All externally visible primary keys are UUIDv7 (RFC 9562):
- time-ordered  → B-tree index locality, no page thrash on insert;
- k-sortable    → creation order is recoverable without a separate column;
- unguessable   → unlike autoincrement integers, they leak no cardinality
  and cannot be enumerated by an attacker holding one identifier.

Implementation comes from the maintained ``uuid-utils`` library; we do not
hand-roll identifier or cryptographic primitives.
"""

import uuid

from uuid_utils import uuid7


def new_uuid7() -> uuid.UUID:
    """Return a new time-ordered UUIDv7 as a stdlib ``uuid.UUID``.

    ``uuid_utils`` returns its own UUID type; we normalize to the stdlib
    class so every consumer (SQLAlchemy, Pydantic, JSON serializers) sees
    exactly ``uuid.UUID``.
    """
    value = uuid7()
    # Preserve all bits: version/variant are embedded in the byte layout.
    return uuid.UUID(bytes=value.bytes)
