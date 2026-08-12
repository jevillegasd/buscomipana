import enum

from sqlalchemy import JSON, Enum
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on Postgres (prod), generic JSON everywhere else (SQLite in unit tests).
PortableJSON = JSON().with_variant(JSONB(), "postgresql")


def str_enum(enum_cls: type[enum.Enum], length: int) -> Enum:
    """Enum(..., native_enum=False) stores the Python member *name* by default
    (e.g. BloodType.o_pos -> "o_pos"), not its .value ("O+") -- which silently
    mismatches every CHECK constraint in the initial migration, all of which
    list the .value strings. values_callable makes it store/compare .value
    instead, so DB rows actually match what the CHECK constraints (and every
    other consumer of the raw column) expect."""
    return Enum(enum_cls, native_enum=False, length=length, values_callable=lambda x: [e.value for e in x])
