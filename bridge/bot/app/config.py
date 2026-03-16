from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    bot_token: str
    initial_admin_ids: set[int]
    data_dir: str
    admins_file: str
    wg_config_file: str
    clients_dir: str
    wg_interface: str
    wg_endpoint: str
    wg_server_public_key: str
    wg_server_ipv4: str
    wg_server_cidr: int
    wg_allowed_ips: str
    wg_dns: str



def _parse_admin_ids(raw: str) -> set[int]:
    result: set[int] = set()
    for chunk in raw.split(','):
        chunk = chunk.strip()
        if not chunk:
            continue
        result.add(int(chunk))
    return result


def load_settings() -> Settings:
    bot_token = os.environ['BOT_TOKEN']
    return Settings(
        bot_token=bot_token,
        initial_admin_ids=_parse_admin_ids(os.getenv('ADMIN_IDS', '')),
        data_dir=os.getenv('DATA_DIR', '/data'),
        admins_file=os.path.join(os.getenv('DATA_DIR', '/data'), 'admins.json'),
        wg_config_file=os.getenv('WG_CONFIG_FILE', '/config/wg_confs/wg0.conf'),
        clients_dir=os.getenv('CLIENTS_DIR', '/clients'),
        wg_interface=os.getenv('WG_INTERFACE', 'wg0'),
        wg_endpoint=os.environ['WG_ENDPOINT'],
        wg_server_public_key=os.environ['WG_SERVER_PUBLIC_KEY'],
        wg_server_ipv4=os.getenv('WG_SERVER_IPV4', '10.10.10.1'),
        wg_server_cidr=int(os.getenv('WG_SERVER_CIDR', '24')),
        wg_allowed_ips=os.getenv('WG_ALLOWED_IPS', '0.0.0.0/0'),
        wg_dns=os.getenv('WG_DNS', '1.1.1.1,1.0.0.1'),
    )
