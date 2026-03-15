import logging
import subprocess

logger = logging.getLogger(__name__)


class ReloadError(Exception):
    pass


def reload_wireguard(wg_config_file: str, wg_interface: str) -> None:
    strip_cmd = ['wg-quick', 'strip', wg_config_file]
    logger.info('Running: %s', ' '.join(strip_cmd))
    strip_proc = subprocess.run(strip_cmd, text=True, capture_output=True)
    if strip_proc.returncode != 0:
        logger.error('wg-quick strip failed: stdout=%s stderr=%s', strip_proc.stdout, strip_proc.stderr)
        raise ReloadError(f'wg-quick strip завершился с ошибкой: {strip_proc.stderr.strip() or strip_proc.stdout.strip()}')

    sync_cmd = ['wg', 'syncconf', wg_interface, '/dev/stdin']
    logger.info('Running: %s', ' '.join(sync_cmd))
    sync_proc = subprocess.run(sync_cmd, input=strip_proc.stdout, text=True, capture_output=True)
    if sync_proc.returncode != 0:
        logger.error('wg syncconf failed: stdout=%s stderr=%s', sync_proc.stdout, sync_proc.stderr)
        raise ReloadError(f'wg syncconf завершился с ошибкой: {sync_proc.stderr.strip() or sync_proc.stdout.strip()}')

    logger.info('WireGuard live reload completed successfully.')
