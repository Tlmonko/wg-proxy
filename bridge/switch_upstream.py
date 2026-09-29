#!/usr/bin/env python3
"""Switch the bridge's upstream peer without restarting WireGuard or the bot."""

import argparse
import configparser
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
WG_CONFIG = ROOT / "config/wg_confs/wg0.conf"
OBF_CONFIG = ROOT / "wg-obfuscator.conf"
STATE_FILE = ROOT / ".obfuscation-state.json"
LOCAL_ENDPOINT = "127.0.0.1:51821"
SECTION_RE = re.compile(r"^\s*\[([^]]+)\]\s*$")
PROPERTY_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_-]*)\s*=\s*(.*?)\s*$")


class SwitchError(Exception):
    pass


def run(*args: str) -> str:
    try:
        result = subprocess.run(
            args, cwd=ROOT, check=True, text=True, capture_output=True
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise SwitchError(f"Команда {' '.join(args)} не удалась: {detail.strip()}") from exc
    return result.stdout.strip()


def docker_wg(*args: str) -> str:
    return run("docker", "compose", "exec", "-T", "wg", "wg", *args)


def sections(lines: list[str]) -> list[tuple[str, int, int, dict[str, tuple[int, str]]]]:
    found = []
    for index, line in enumerate(lines):
        match = SECTION_RE.match(line)
        if match:
            if found:
                found[-1][2] = index
            found.append([match.group(1).lower(), index, len(lines), {}])
        elif found:
            prop = PROPERTY_RE.match(line)
            if prop:
                key = prop.group(1).lower()
                if key in found[-1][3]:
                    raise SwitchError(f"Повторяется параметр {key} в {found[-1][0]}.")
                found[-1][3][key] = (index, prop.group(2).strip())
    return [(name, start, end, props) for name, start, end, props in found]


def upstream_peer(lines: list[str]) -> tuple[dict[str, tuple[int, str]], str]:
    peers = []
    for name, _, _, props in sections(lines):
        if name != "peer" or "allowedips" not in props:
            continue
        allowed = {part.strip() for part in props["allowedips"][1].split(",")}
        if "0.0.0.0/0" in allowed:
            peers.append(props)
    if len(peers) != 1 or "publickey" not in peers[0] or "endpoint" not in peers[0]:
        raise SwitchError("Нужен ровно один upstream peer с AllowedIPs = 0.0.0.0/0, PublicKey и Endpoint.")
    return peers[0], peers[0]["publickey"][1]


def interface(lines: list[str]) -> dict[str, tuple[int, str]]:
    matches = [props for name, _, _, props in sections(lines) if name == "interface"]
    if len(matches) != 1:
        raise SwitchError("Нужна одна секция [Interface] в wg0.conf.")
    return matches[0]


def replace_property(lines: list[str], props: dict, key: str, value: str | None,
                     insert_after: str | None = None) -> None:
    existing = props.get(key.lower())
    if existing:
        if value is None:
            del lines[existing[0]]
        else:
            lines[existing[0]] = f"{key} = {value}\n"
    elif value is not None:
        if not insert_after or insert_after.lower() not in props:
            raise SwitchError(f"Не удалось вставить {key}.")
        lines.insert(props[insert_after.lower()][0] + 1, f"{key} = {value}\n")


def set_peer(lines: list[str], endpoint: str, keepalive: str | None) -> None:
    props, _ = upstream_peer(lines)
    replace_property(lines, props, "Endpoint", endpoint)
    props, _ = upstream_peer(lines)
    replace_property(lines, props, "PersistentKeepalive", keepalive, "endpoint")


def set_fwmark(lines: list[str], mark: str | None) -> None:
    props = interface(lines)
    replace_property(lines, props, "FwMark", mark, "privatekey")


def atomic_write(path: Path, content: str, *, secret: bool = False) -> None:
    original = path.stat() if path.exists() else None
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600 if secret else stat.S_IMODE(original.st_mode) if original else 0o600)
            if original and os.geteuid() == 0:
                os.fchown(output.fileno(), original.st_uid, original.st_gid)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_state() -> dict | None:
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def active_mark() -> str:
    raw = docker_wg("show", "wg0", "fwmark")
    if raw == "off":
        raise SwitchError("У активного wg0 нет FwMark; переключение может создать петлю маршрутизации.")
    try:
        mark = int(raw, 0)
    except ValueError as exc:
        raise SwitchError(f"Неизвестный FwMark: {raw}") from exc
    if not 0 < mark <= 65535:
        raise SwitchError("wg-obfuscator поддерживает fwmark только в диапазоне 1..65535.")
    return str(mark)


def prepare_obfuscator(mark: str) -> None:
    if not OBF_CONFIG.is_file():
        raise SwitchError("Создайте bridge/wg-obfuscator.conf из .example и заполните ключ и IPv4 upstream.")
    text = OBF_CONFIG.read_text(encoding="utf-8")
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(text)
    if "main" not in parser:
        raise SwitchError("В wg-obfuscator.conf отсутствует секция [main].")
    cfg = parser["main"]
    key = cfg.get("key", "")
    host, separator, port = cfg.get("target", "").rpartition(":")
    try:
        ipaddress.IPv4Address(host)
    except ValueError as exc:
        raise SwitchError("Укажите публичный IPv4 upstream в target обфускатора.") from exc
    if not separator or port != "51821" or not key or "[" in key:
        raise SwitchError("Проверьте target и общий секрет в wg-obfuscator.conf.")
    if cfg.get("source-if") != "127.0.0.1" or cfg.get("source-lport") != "51821":
        raise SwitchError("Обфускатор bridge должен слушать 127.0.0.1:51821.")
    lines = text.splitlines(keepends=True)
    indexes = [i for i, line in enumerate(lines) if re.match(r"^\s*fwmark\s*=", line, re.I)]
    if len(indexes) != 1:
        raise SwitchError("В wg-obfuscator.conf должна быть ровно одна строка fwmark = ...")
    lines[indexes[0]] = f"fwmark = {mark}\n"
    updated = "".join(lines)
    if updated != text:
        atomic_write(OBF_CONFIG, updated, secret=True)


def show_status() -> None:
    lines = WG_CONFIG.read_text(encoding="utf-8").splitlines(keepends=True)
    props, _ = upstream_peer(lines)
    endpoint = props["endpoint"][1]
    state = read_state()
    mode = "обфускация" if endpoint == LOCAL_ENDPOINT else "прямое соединение"
    print(f"Режим в wg0.conf: {mode}; Endpoint = {endpoint}")
    if state:
        print(f"Сохранён адрес отката: {state['direct_endpoint']}")


def enable() -> None:
    original = WG_CONFIG.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    props, public_key = upstream_peer(lines)
    current_endpoint = props["endpoint"][1]
    state = read_state()
    if current_endpoint == LOCAL_ENDPOINT and not state:
        raise SwitchError("Уже задан локальный Endpoint, но адрес отката не сохранён.")
    if state and current_endpoint not in (LOCAL_ENDPOINT, state["direct_endpoint"]):
        raise SwitchError("Endpoint изменён после сохранения адреса отката; разберите состояние вручную.")
    mark = active_mark()
    current_fwmark = interface(lines).get("fwmark")
    if current_fwmark and int(current_fwmark[1], 0) != int(mark):
        raise SwitchError("FwMark в wg0.conf отличается от активного mark; нужен разбор вручную.")
    if public_key not in docker_wg("show", "wg0", "peers").splitlines():
        raise SwitchError("Upstream peer отсутствует в активном wg0.")
    prepare_obfuscator(mark)
    run("docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.obfuscation.yml",
        "up", "-d", "--no-deps", "--force-recreate", "wg-obfuscator")
    if run("docker", "inspect", "--format", "{{.State.Running}}", "wg-obfuscator") != "true":
        raise SwitchError("Контейнер wg-obfuscator не запущен; проверьте его логи. WG не переключён.")

    if not state:
        state = {
            "direct_endpoint": current_endpoint,
            "original_keepalive": props.get("persistentkeepalive", (None, None))[1],
            "fwmark_added": current_fwmark is None,
            "active_fwmark": mark,
        }
        atomic_write(STATE_FILE, json.dumps(state, indent=2) + "\n", secret=True)
    set_peer(lines, LOCAL_ENDPOINT, "25")
    if state["fwmark_added"]:
        set_fwmark(lines, mark)
    atomic_write(WG_CONFIG, "".join(lines))
    try:
        docker_wg("set", "wg0", "peer", public_key, "endpoint", LOCAL_ENDPOINT,
                  "persistent-keepalive", "25")
    except SwitchError:
        atomic_write(WG_CONFIG, original)
        try:
            docker_wg("set", "wg0", "peer", public_key, "endpoint", state["direct_endpoint"],
                      "persistent-keepalive", state["original_keepalive"] or "0")
        except SwitchError:
            pass
        raise
    print("Bridge переключён на обфускацию без перезапуска WireGuard.")
    print("Проверьте handshake: docker compose exec wg wg show wg0")
    print("Откат: python3 switch_upstream.py direct")


def disable() -> None:
    state = read_state()
    if not state:
        raise SwitchError("Адрес отката не найден. Прямой Endpoint нельзя восстановить автоматически.")
    original = WG_CONFIG.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    props, public_key = upstream_peer(lines)
    if props["endpoint"][1] not in (LOCAL_ENDPOINT, state["direct_endpoint"]):
        raise SwitchError("Endpoint изменён вручную после включения обфускации.")
    set_peer(lines, state["direct_endpoint"], state["original_keepalive"])
    if state["fwmark_added"]:
        current_fwmark = interface(lines).get("fwmark")
        if current_fwmark and int(current_fwmark[1], 0) != int(state["active_fwmark"]):
            raise SwitchError("FwMark изменён вручную после включения обфускации.")
        set_fwmark(lines, None)
    atomic_write(WG_CONFIG, "".join(lines))
    try:
        docker_wg("set", "wg0", "peer", public_key, "endpoint", state["direct_endpoint"],
                  "persistent-keepalive", state["original_keepalive"] or "0")
    except SwitchError:
        print("Файл уже возвращён к прямому Endpoint; повторите команду после восстановления Docker.",
              file=sys.stderr)
        raise
    STATE_FILE.unlink()
    print(f"Bridge возвращён на прямой Endpoint {state['direct_endpoint']} без перезапуска WireGuard.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("obfuscated", "direct", "status"))
    mode = parser.parse_args().mode
    try:
        lock_path = Path(f"{WG_CONFIG}.lock")
        with lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if mode == "obfuscated":
                enable()
            elif mode == "direct":
                disable()
            else:
                show_status()
    except (OSError, ValueError, json.JSONDecodeError, SwitchError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
