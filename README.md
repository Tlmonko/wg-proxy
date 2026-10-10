# WG Proxy: доступ к upstream через bridge

Репозиторий описывает схему WireGuard из трёх ролей:

- **Клиент** — устройство пользователя.
- **Bridge сервер** — принимает клиентов и отправляет трафик в upstream.
- **Upstream сервер** — точка выхода в интернет.

## Структура

- `upstream/` — docker-compose и серверный конфиг `config/wg_confs/wg0.conf` для upstream.
- `bridge/config/` — серверный конфиг bridge WireGuard (`wg_confs/wg0.conf`).
- `bridge/clients/` — клиентские `.conf`, создаваемые ботом.
- `bridge/config/wg_confs/` и `upstream/config/wg_confs/` — только серверные live tunnel configs WireGuard.
- `bridge/bot-data/` — JSON-хранилище админов Telegram-бота.
- `bridge/bot/` — минималистичный Telegram-бот управления managed-клиентами.
- `bridge/bot/requirements.txt` включает `Pillow` для стабильной генерации QR-кодов в PNG.

## Telegram-бот (bridge)

Бот работает отдельным контейнером `wg-bot` и использует **long polling**.

Ключевая особенность этой реализации:

1. бот изменяет `bridge/config/wg_confs/wg0.conf`;
2. затем делает live reload без рестарта контейнера:
   - `wg-quick strip <WG_CONFIG_FILE>`
   - `wg syncconf <WG_INTERFACE> /dev/stdin`

Новые пользователи начинают работать сразу, restart `wg` не нужен.

Важно: папка `wg_confs` предназначена только для tunnel-конфигов сервера (`wg0.conf`). Клиентские конфиги Telegram-бота сохраняются в `bridge/clients/` и не должны помещаться в `wg_confs`.

## Переменные окружения для бота (`bridge/.env`)

См. пример: `bridge/.env.example`.

Обязательные/поддерживаемые:

- `BOT_TOKEN`
- `ADMIN_IDS`
- `DATA_DIR=/data`
- `WG_CONFIG_FILE=/config/wg_confs/wg0.conf`
- `CLIENTS_DIR=/clients`
- `WG_INTERFACE=wg0`
- `WG_ENDPOINT=<bridge-public-ip-or-dns>:51820`
- `WG_SERVER_PUBLIC_KEY=<bridge-public-key>`
- `WG_SERVER_IPV4=10.10.10.1`
- `WG_SERVER_CIDR=24`
- `WG_ALLOWED_IPS=0.0.0.0/0`
- `WG_DNS=1.1.1.1,1.0.0.1`
- `TZ=Europe/Moscow`

## Команды бота

- `/start`
- `/help`
- `/add_admin @username`
- `/admins`
- `/add_user <client_name>`

`/add_user` делает:

1. генерацию ключей (`wg genkey`, `wg pubkey`, `wg genpsk`);
2. добавление peer в managed-блок `wg0.conf`;
3. live reload `wg syncconf`;
4. сохранение `/clients/wg_<client_name>.conf`;
5. отправку QR + `.conf` в Telegram.

Если reload не удался, бот явно сообщает об этом и пишет подробности в лог.

## Мониторинг WireGuard

Bridge Compose также запускает WireGuard exporter, Prometheus и Grafana. Exporter читает статистику `wg0` в сетевом namespace контейнера `wg`; Prometheus хранит историю до 90 дней в Docker volume, а Grafana автоматически загружает дашборд `WireGuard Bridge`.

Перед запуском задайте в `bridge/.env` непредсказуемый пароль `GRAFANA_ADMIN_PASSWORD`; переменная добавлена в `.env.example` пустой, поэтому Compose не запустит стек, пока пароль не задан. По умолчанию Grafana опубликована только на `127.0.0.1:3000`, exporter и Prometheus не публикуют порты на хост. Для открытия Grafana с локального компьютера используйте SSH-туннель:

```bash
ssh -L 3000:127.0.0.1:3000 <user>@<bridge-host>
```

После этого откройте `http://127.0.0.1:3000`. Чтобы изменить адрес или порт Grafana, задайте `MONITORING_BIND_ADDRESS` и `GRAFANA_PORT` в `bridge/.env`; перед публикацией на внешнем интерфейсе настройте firewall или reverse proxy.

Дашборд показывает текущую скорость по каждому managed-клиенту, объём трафика за выбранный период и давность handshake. Имена для exporter формирует бот в отдельном файле только с публичными ключами и именами — приватный ключ и preshared keys ему не монтируются. При добавлении клиента список обновляется автоматически.

На bridge счётчики показывают обмен трафиком каждого клиента с bridge. Upstream видит bridge как один peer, поэтому его счётчики не позволяют разбить трафик по конечным клиентам. Давность handshake отражает последний обмен WireGuard-пакетами и не гарантирует, что молчащий клиент отключён.

## Managed-блок в `wg0.conf`

Бот изменяет только managed-область:

- `# BEGIN MANAGED CLIENTS`
- `# END MANAGED CLIENTS`

Формат клиента:

```ini
# BEGIN CLIENT alice
### Client alice
[Peer]
PublicKey = <client_public_key>
PresharedKey = <client_psk>
AllowedIPs = 10.10.10.5/32
# END CLIENT alice
```

Остальные peer'ы (upstream/ручные) не трогаются.

## Как запустить

### 1) Подготовить конфиги и ключи

Заполните:

- `upstream/config/wg_confs/wg0.conf`
- `bridge/config/wg_confs/wg0.conf`

(замените плейсхолдеры на реальные значения).

Сгенерируйте и сохраните ключи в файлы, чтобы потом подставить их в шаблоны `wg0.conf`:

```bash
wg genkey | tee upstream_private.key | wg pubkey > upstream_public.key
wg genkey | tee bridge_private.key   | wg pubkey > bridge_public.key
```

При необходимости аналогично можно сгенерировать клиентскую пару:

```bash
wg genkey | tee client_private.key | wg pubkey > client_public.key
```

### 2) Поднять upstream (на upstream сервере)

```bash
cd upstream
docker compose up -d
```

### 3) Подготовить bridge env (на bridge сервере)

```bash
cd bridge
cp .env.example .env
# отредактируйте .env
```

### 4) Поднять bridge + бота (на bridge сервере)

`wg-bot` запускается из образа, который собирается CI-пайплайном этого репозитория: `ghcr.io/tlmonko/wg-proxy/wg-bot:latest`.

```bash
docker compose pull wg-bot
docker compose up -d
```

### 5) Добавить администратора бота

1. Один из `ADMIN_IDS` пишет `/add_admin @username`.
2. Пользователь `@username` пишет боту `/start`.
3. После этого он попадает в активные админы.

Проверка:

```text
/admins
```

### 6) Создать пользователя WireGuard

```text
/add_user alice
```

Бот отправит QR и файл `wg_alice.conf`.
