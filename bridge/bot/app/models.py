from dataclasses import dataclass


@dataclass(frozen=True)
class ManagedClient:
    name: str
    public_key: str
    preshared_key: str
    allowed_ip: str


@dataclass(frozen=True)
class AdminState:
    active_admin_ids: set[int]
    pending_admin_usernames: set[str]
