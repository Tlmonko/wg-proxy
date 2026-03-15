import ipaddress
import os
import re
from dataclasses import dataclass

from .models import ManagedClient
from .storage import atomic_write_text, file_lock

BEGIN_MANAGED = '# BEGIN MANAGED CLIENTS'
END_MANAGED = '# END MANAGED CLIENTS'

CLIENT_BLOCK_RE = re.compile(
    r"# BEGIN CLIENT (?P<name>[A-Za-z0-9_-]+)\n"
    r"### Client (?P=name)\n"
    r"\[Peer\]\n"
    r"PublicKey = (?P<public_key>.+?)\n"
    r"PresharedKey = (?P<preshared_key>.+?)\n"
    r"AllowedIPs = (?P<allowed_ip>[0-9.]+/32)\n"
    r"# END CLIENT (?P=name)\n?",
    re.MULTILINE,
)


@dataclass(frozen=True)
class AddClientResult:
    client_ip: str
    config_written: bool


class WgConfigError(Exception):
    pass


def _read_text(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _split_managed_block(config_text: str) -> tuple[str, str, str]:
    if BEGIN_MANAGED not in config_text or END_MANAGED not in config_text:
        base = config_text.rstrip() + '\n\n' if config_text.strip() else ''
        managed = f'{BEGIN_MANAGED}\n{END_MANAGED}\n'
        return base, '', managed

    begin_idx = config_text.index(BEGIN_MANAGED)
    end_idx = config_text.index(END_MANAGED)
    if end_idx < begin_idx:
        raise WgConfigError('Managed block markers are in invalid order.')

    before = config_text[: begin_idx + len(BEGIN_MANAGED)] + '\n'
    managed_content = config_text[begin_idx + len(BEGIN_MANAGED) + 1 : end_idx]
    after = config_text[end_idx:]
    return before, managed_content.strip('\n'), after


def parse_managed_clients(config_text: str) -> list[ManagedClient]:
    _, managed, _ = _split_managed_block(config_text)
    clients: list[ManagedClient] = []
    for match in CLIENT_BLOCK_RE.finditer(managed + ('\n' if managed else '')):
        clients.append(
            ManagedClient(
                name=match.group('name'),
                public_key=match.group('public_key').strip(),
                preshared_key=match.group('preshared_key').strip(),
                allowed_ip=match.group('allowed_ip').strip(),
            )
        )
    return clients


def allocate_next_ip(server_ipv4: str, cidr: int, used_ips: set[str]) -> str:
    network = ipaddress.ip_network(f'{server_ipv4}/{cidr}', strict=False)
    server_ip = ipaddress.ip_address(server_ipv4)
    for host in network.hosts():
        if int(host.packed[-1]) < 2:
            continue
        if host == server_ip:
            continue
        host_str = str(host)
        if host_str in used_ips:
            continue
        return host_str
    raise WgConfigError('Свободных IPv4-адресов в managed-пуле не осталось.')


def _build_client_block(name: str, public_key: str, psk: str, ip: str) -> str:
    return (
        f'# BEGIN CLIENT {name}\n'
        f'### Client {name}\n'
        '[Peer]\n'
        f'PublicKey = {public_key}\n'
        f'PresharedKey = {psk}\n'
        f'AllowedIPs = {ip}/32\n'
        f'# END CLIENT {name}\n'
    )


def add_managed_client(
    config_path: str,
    client_name: str,
    client_public_key: str,
    client_psk: str,
    server_ipv4: str,
    server_cidr: int,
) -> AddClientResult:
    lock_path = f'{config_path}.lock'
    with file_lock(lock_path):
        if not os.path.exists(config_path):
            raise WgConfigError(f'Не найден конфиг WireGuard: {config_path}')

        config_text = _read_text(config_path)
        clients = parse_managed_clients(config_text)

        if any(c.name == client_name for c in clients):
            raise WgConfigError(f'Клиент {client_name} уже существует в managed-блоке.')

        used_ips = {c.allowed_ip.split('/')[0] for c in clients}
        used_ips.add(server_ipv4)
        client_ip = allocate_next_ip(server_ipv4, server_cidr, used_ips)

        before, managed, after = _split_managed_block(config_text)
        client_block = _build_client_block(client_name, client_public_key, client_psk, client_ip)
        new_managed = (managed + '\n\n' + client_block if managed else client_block).strip('\n') + '\n'
        new_config = before + new_managed + after
        atomic_write_text(config_path, new_config)
        return AddClientResult(client_ip=client_ip, config_written=True)
