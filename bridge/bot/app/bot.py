import asyncio
import logging
import os
import re
import subprocess

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message
from dotenv import load_dotenv

from .admins import AdminStore
from .config import Settings, load_settings
from .qr import make_qr_png
from .reload import ReloadError, reload_wireguard
from .storage import atomic_write_text
from .wg_config import WgConfigError, add_managed_client

CLIENT_NAME_RE = re.compile(r'^[a-zA-Z0-9_-]{1,15}$')


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)


def is_admin(user_id: int, store: AdminStore, initial_admin_ids: set[int]) -> bool:
    if user_id in initial_admin_ids:
        return True
    return user_id in store.load().active_admin_ids


def _run_wg(cmd: list[str], stdin: str | None = None) -> str:
    proc = subprocess.run(cmd, input=stdin, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or 'unknown error')
    return proc.stdout.strip()


def generate_client_materials() -> tuple[str, str, str]:
    private_key = _run_wg(['wg', 'genkey'])
    public_key = _run_wg(['wg', 'pubkey'], stdin=private_key + '\n')
    psk = _run_wg(['wg', 'genpsk'])
    return private_key, public_key, psk


def render_client_config(settings: Settings, private_key: str, psk: str, client_ip: str) -> str:
    return (
        '[Interface]\n'
        f'PrivateKey = {private_key}\n'
        f'Address = {client_ip}/32\n'
        f'DNS = {settings.wg_dns}\n\n'
        '[Peer]\n'
        f'PublicKey = {settings.wg_server_public_key}\n'
        f'PresharedKey = {psk}\n'
        f'Endpoint = {settings.wg_endpoint}\n'
        f'AllowedIPs = {settings.wg_allowed_ips}\n'
        'PersistentKeepalive = 25\n'
    )


def build_help() -> str:
    return (
        'Команды:\n'
        '/start - описание\n'
        '/help - эта справка\n'
        '/add_admin @username - добавить pending-admin\n'
        '/admins - список админов\n'
        '/add_user <client_name> - создать managed-клиента\n\n'
        'Бот управляет только managed-клиентами bridge-сервера.'
    )


async def main() -> None:
    load_dotenv()
    settings = load_settings()
    os.makedirs(settings.clients_dir, exist_ok=True)
    os.makedirs(settings.data_dir, exist_ok=True)

    admin_store = AdminStore(settings.admins_file)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    @dp.message(Command('start'))
    async def cmd_start(message: Message) -> None:
        user = message.from_user
        if user:
            activated = admin_store.activate_if_pending(user.id, user.username)
            if activated:
                await message.answer('Ваш аккаунт активирован как админ.')
        await message.answer('WireGuard bridge bot.\n' + build_help())

    @dp.message(Command('help'))
    async def cmd_help(message: Message) -> None:
        await message.answer(build_help())

    @dp.message(Command('add_admin'))
    async def cmd_add_admin(message: Message) -> None:
        user = message.from_user
        if not user or not is_admin(user.id, admin_store, settings.initial_admin_ids):
            await message.answer('Недостаточно прав.')
            return
        parts = (message.text or '').split(maxsplit=1)
        if len(parts) != 2 or not parts[1].startswith('@'):
            await message.answer('Использование: /add_admin @username')
            return
        username = parts[1][1:].strip()
        if not username:
            await message.answer('Некорректный username.')
            return
        admin_store.add_pending_admin(username)
        await message.answer(f'@{username} добавлен в pending-admins. Пользователь станет админом после /start.')

    @dp.message(Command('admins'))
    async def cmd_admins(message: Message) -> None:
        state = admin_store.load()
        initial = ', '.join(str(x) for x in sorted(settings.initial_admin_ids)) or '—'
        active = ', '.join(str(x) for x in sorted(state.active_admin_ids)) or '—'
        pending = ', '.join(f'@{x}' for x in sorted(state.pending_admin_usernames)) or '—'
        await message.answer(
            f'Initial admin IDs: {initial}\n'
            f'Active admins: {active}\n'
            f'Pending admins: {pending}'
        )

    @dp.message(Command('add_user'))
    async def cmd_add_user(message: Message) -> None:
        user = message.from_user
        if not user or not is_admin(user.id, admin_store, settings.initial_admin_ids):
            await message.answer('Недостаточно прав.')
            return

        parts = (message.text or '').split(maxsplit=1)
        if len(parts) != 2:
            await message.answer('Использование: /add_user <client_name>')
            return
        client_name = parts[1].strip()
        if not CLIENT_NAME_RE.fullmatch(client_name):
            await message.answer('Имя клиента: только a-zA-Z0-9_-, длина 1..15.')
            return

        await message.answer('Создаю пользователя...')

        try:
            private_key, public_key, psk = generate_client_materials()
            add_result = add_managed_client(
                config_path=settings.wg_config_file,
                client_name=client_name,
                client_public_key=public_key,
                client_psk=psk,
                server_ipv4=settings.wg_server_ipv4,
                server_cidr=settings.wg_server_cidr,
            )
        except (RuntimeError, WgConfigError) as exc:
            logger.exception('Failed to prepare user %s', client_name)
            await message.answer(f'Не удалось добавить пользователя: {exc}')
            return

        reload_ok = True
        try:
            reload_wireguard(settings.wg_config_file, settings.wg_interface)
        except ReloadError as exc:
            reload_ok = False
            logger.exception('WireGuard reload failed for client %s', client_name)
            await message.answer(f'Пользователь добавлен в файл, но reload WireGuard не удался: {exc}')

        client_config = render_client_config(settings, private_key, psk, add_result.client_ip)
        client_path = os.path.join(settings.clients_dir, f'wg_{client_name}.conf')
        atomic_write_text(client_path, client_config)

        qr_bytes = make_qr_png(client_config)
        conf_bytes = client_config.encode('utf-8')

        if reload_ok:
            await message.answer('Пользователь добавлен и WireGuard конфиг применен.')

        logger.info('Sending QR for %s to chat_id=%s', client_name, message.chat.id)
        try:
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=BufferedInputFile(qr_bytes, filename=f'{client_name}.png'),
                caption=f'{client_name}: QR',
            )
        except Exception as exc:
            logger.exception('Failed to send QR for %s', client_name)
            await message.answer(f'Не удалось отправить QR-код (ошибка: {exc}).')

        logger.info('Sending client config for %s to chat_id=%s', client_name, message.chat.id)
        try:
            await bot.send_document(
                chat_id=message.chat.id,
                document=BufferedInputFile(conf_bytes, filename=f'wg_{client_name}.conf'),
            )
        except Exception as exc:
            logger.exception('Failed to send client config for %s', client_name)
            await message.answer(f'Не удалось отправить конфигурационный файл (ошибка: {exc}).')

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
