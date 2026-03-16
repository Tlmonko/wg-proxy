import logging
import subprocess

logger = logging.getLogger(__name__)


class ReloadError(Exception):
    pass


def _run(cmd: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    logger.info("Running: %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
    )
    return proc


def _require_ok(proc: subprocess.CompletedProcess[str], action: str) -> None:
    if proc.returncode != 0:
        logger.error(
            "%s failed: stdout=%s stderr=%s",
            action,
            proc.stdout,
            proc.stderr,
        )
        raise ReloadError(
            f"{action} завершился с ошибкой: "
            f"{proc.stderr.strip() or proc.stdout.strip() or 'unknown error'}"
        )


def _get_fwmark(wg_interface: str) -> str | None:
    proc = _run(["wg", "show", wg_interface, "fwmark"])
    _require_ok(proc, f"wg show {wg_interface} fwmark")
    value = proc.stdout.strip()
    if not value or value == "off":
        return None
    return value


def _inject_fwmark(config_text: str, fwmark: str | None) -> str:
    if not fwmark:
        return config_text

    lines = config_text.splitlines()
    if not lines:
        raise ReloadError("wg-quick strip вернул пустой конфиг.")
    if lines[0].strip() != "[Interface]":
        raise ReloadError("strip-конфиг имеет неожиданный формат: нет [Interface] в начале.")

    # Если FwMark уже есть, не дублируем.
    for line in lines[1:]:
        if line.startswith("["):
            break
        if line.strip().startswith("FwMark"):
            return config_text

    lines.insert(1, f"FwMark = {fwmark}")
    return "\n".join(lines) + "\n"


def _restore_fwmark_if_needed(wg_interface: str, expected_fwmark: str | None) -> None:
    if not expected_fwmark:
        return

    current = _get_fwmark(wg_interface)
    if current == expected_fwmark:
        return

    logger.warning(
        "FwMark changed after syncconf: expected=%s current=%s. Restoring.",
        expected_fwmark,
        current,
    )
    proc = _run(["wg", "set", wg_interface, "fwmark", expected_fwmark])
    _require_ok(proc, f"wg set {wg_interface} fwmark {expected_fwmark}")

    current_after = _get_fwmark(wg_interface)
    if current_after != expected_fwmark:
        raise ReloadError(
            f"Не удалось восстановить FwMark: ожидался {expected_fwmark}, получен {current_after}"
        )


def reload_wireguard(wg_config_file: str, wg_interface: str) -> None:
    current_fwmark = _get_fwmark(wg_interface)
    if current_fwmark:
        logger.info("Preserving existing FwMark=%s during syncconf.", current_fwmark)
    else:
        logger.info("Interface %s has no active FwMark.", wg_interface)

    strip_proc = _run(["wg-quick", "strip", wg_config_file])
    _require_ok(strip_proc, "wg-quick strip")

    sync_input = _inject_fwmark(strip_proc.stdout, current_fwmark)

    sync_proc = _run(["wg", "syncconf", wg_interface, "/dev/stdin"], input_text=sync_input)
    _require_ok(sync_proc, "wg syncconf")

    _restore_fwmark_if_needed(wg_interface, current_fwmark)

    logger.info("WireGuard live reload completed successfully.")
