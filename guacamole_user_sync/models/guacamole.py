from dataclasses import dataclass


@dataclass
class GuacamoleUserDetails:
    """A Guacamole user with required attributes only."""

    entity_id: int
    full_name: str
    name: str
