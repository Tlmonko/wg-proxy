# WG Proxy: доступ к upstream через bridge

Репозиторий описывает схему WireGuard из трёх ролей:

- **Клиент** — устройство пользователя.
- **Bridge сервер** — принимает клиентов и отправляет трафик в upstream.
- **Upstream сервер** — точка выхода в интернет.

Для канала bridge ↔ upstream можно включить [wg-obfuscator](https://github.com/ClusterM/wg-obfuscator) на обеих сторонах. Обычный запуск `docker compose up -d` сохраняет прямое соединение. Клиенты по-прежнему подключаются к bridge обычным WireGuard.

```text
клиент --WG/UDP 51820--> bridge WG --локальный UDP--> bridge obfuscator
    --обфусцированный STUN/UDP 51821--> upstream obfuscator
    --локальный UDP--> upstream WG 51820
```

## Структура

- `upstream/` — docker-compose и серверный конфиг `config/wg_confs/wg0.conf` для upstream.
- `bridge/config/` — серверный конфиг bridge WireGuard (`wg_confs/wg0.conf`).
- `bridge/clients/` — клиентские `.conf`, создаваемые ботом.
- `bridge/config/wg_confs/` и `upstream/config/wg_confs/` — только серверные live tunnel configs WireGuard.
- `bridge/bot-data/` — JSON-хранилище админов Telegram-бота.
- `bridge/bot/` — минималистичный Telegram-бот управления managed-клиентами.
- `bridge/bot/requirements.txt` включает `Pillow` для стабильной генерации QR-кодов в PNG.
- `bridge/wg-obfuscator.conf.example` и `upstream/wg-obfuscator.conf.example` — шаблоны обфускаторов. Рабочие `.conf` хранят общий секрет и исключены из Git.
- `*/docker-compose.obfuscation.yml` — дополнительные Compose-файлы для включения обфускаторов.
- `bridge/switch_upstream.py` — переключение активного upstream peer и откат одной командой на bridge.

## Обфускация bridge ↔ upstream

Обфускаторы используют образ `clustermeerkat/wg-obfuscator:1.6`. На upstream дополнительный контейнер слушает UDP `51821` и пересылает пакеты на существующий WG-контейнер `wg:51820` в той же Docker-сети. На bridge обфускатор делит сетевое пространство с `wg` и слушает только `127.0.0.1:51821`. Базовые Compose-файлы, публичный WG-порт upstream `51820` и клиентский порт bridge `51820` при подготовке не меняются.

### Переход с работающей связки

1. На обоих серверах скопируйте соответствующий `wg-obfuscator.conf.example` в `wg-obfuscator.conf`. Сгенерируйте общий секрет, например `openssl rand -hex 32`, впишите **одно и то же значение** вместо `[SAME_RANDOM_SECRET_ON_BOTH_SERVERS]` и установите `chmod 600 wg-obfuscator.conf`. На bridge также замените `[UPSTREAM_PUBLIC_IPV4]` на внешний IPv4 upstream. Поле `fwmark` на bridge заполнит переключатель из работающего `wg0`.
2. На upstream откройте UDP `51821` в сетевом экране и запустите только новый контейнер, не пересоздавая WG:

   ```bash
   cd upstream
   docker compose -f docker-compose.yml -f docker-compose.obfuscation.yml up -d --no-deps wg-obfuscator
   docker compose -f docker-compose.yml -f docker-compose.obfuscation.yml logs wg-obfuscator
   ```

3. На bridge запустите переключатель. Ему нужны Python 3 и Docker Compose на хосте. Он сохранит прямой `Endpoint` в `bridge/.obfuscation-state.json`, сверит активный `FwMark`, запустит локальный обфускатор, изменит `wg0.conf` под блокировкой, общей с Telegram-ботом, и применит `wg set` без перезапуска интерфейса. В `wg0.conf` он меняет только `Endpoint` и `PersistentKeepalive` upstream peer, а также `FwMark` интерфейса; ручные peer и весь managed-блок клиентов сохраняются:

   ```bash
   cd bridge
   python3 switch_upstream.py obfuscated
   ```

4. Проверьте `docker compose exec wg wg show wg0` на обоих серверах, появление handshake после трафика и логи обфускаторов. Статус сохранённого режима на bridge: `python3 switch_upstream.py status`.

### Откат

Пока upstream по-прежнему принимает прямой UDP `51820`, достаточно **одной команды на bridge**:

```bash
cd bridge
python3 switch_upstream.py direct
```

Команда восстановит сохранённый `Endpoint` в файле и активном peer через `wg set`; WG и бот не перезапускаются. Контейнеры обфускатора могут остаться запущенными для повторной попытки. Файл `.obfuscation-state.json` нужен для отката: сохраните его вместе с локальными настройками bridge, не удаляйте вручную в режиме обфускации.

Переключение не требует рестарта WG, поэтому клиентские соединения и бот остаются запущенными. **Нулевой перерыв не гарантирован**: до следующего handshake/переподключения канала возможна краткая пауза. При долгой паузе выполните откат. В период проверки прямой порт upstream остаётся доступен; это сознательный резервный путь. Если позже закрыть UDP `51820` upstream ради строгого запрета прямого соединения, откат одной командой перестанет работать, пока этот порт не будет открыт снова. Если есть потери пакетов, уменьшите WG `MTU`: STUN-маскировка добавляет байты. Обфускация не заменяет шифрование WireGuard.

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

Для первого запуска обфускатор не требуется. Его можно подготовить позже по разделу выше.

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
