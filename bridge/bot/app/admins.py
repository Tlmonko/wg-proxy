from .models import AdminState
from .storage import atomic_write_json, file_lock, read_json


class AdminStore:
    def __init__(self, path: str):
        self.path = path
        self.lock_path = f'{path}.lock'

    def _read_unlocked(self) -> AdminState:
        raw = read_json(self.path, default={'active_admin_ids': [], 'pending_admin_usernames': []})
        return AdminState(
            active_admin_ids={int(x) for x in raw.get('active_admin_ids', [])},
            pending_admin_usernames={str(x).lower() for x in raw.get('pending_admin_usernames', [])},
        )

    def _write_unlocked(self, state: AdminState) -> None:
        payload = {
            'active_admin_ids': sorted(state.active_admin_ids),
            'pending_admin_usernames': sorted(state.pending_admin_usernames),
        }
        atomic_write_json(self.path, payload)

    def load(self) -> AdminState:
        with file_lock(self.lock_path):
            return self._read_unlocked()

    def add_pending_admin(self, username: str) -> None:
        username = username.lower()
        with file_lock(self.lock_path):
            state = self._read_unlocked()
            pending = set(state.pending_admin_usernames)
            pending.add(username)
            self._write_unlocked(AdminState(active_admin_ids=set(state.active_admin_ids), pending_admin_usernames=pending))

    def activate_if_pending(self, user_id: int, username: str | None) -> bool:
        if not username:
            return False
        uname = username.lower()
        with file_lock(self.lock_path):
            state = self._read_unlocked()
            if uname not in state.pending_admin_usernames:
                return False
            pending = set(state.pending_admin_usernames)
            pending.remove(uname)
            active = set(state.active_admin_ids)
            active.add(user_id)
            self._write_unlocked(AdminState(active_admin_ids=active, pending_admin_usernames=pending))
            return True
