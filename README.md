# wg-proxy

Этот репозиторий поднимает цепочку из **3 сервисов**:

1. `vpn-bot-server` — контейнер с кодом `wg-vpn-tg-bot` + WireGuard сервер для клиентов.
2. `wg-egress-client` — контейнер WireGuard клиента к стороннему WG серверу.
3. `traefik` — reverse proxy + TLS termination + Let's Encrypt.

Схема трафика WG-клиентов:

`peer user -> vpn-bot-server (WG server) -> wg-egress-client -> внешний WG сервер`

## Почему теперь есть Dockerfile

Ранее сборка падала, потому что `docker-compose.yml` пытался собрать репозиторий бота напрямую, а в нём нет `Dockerfile`.

Теперь используется **локальный `Dockerfile`**:
- он клонирует `wg-vpn-tg-bot` по `BOT_REPO`/`BOT_REF`,
- ставит зависимости Python,
- содержит нужные сетевые утилиты (wireguard-tools/iptables/iproute2).

## Подготовка

1. Скопируйте env:

```bash
cp .env.example .env
```

2. Заполните `.env` минимум:
- `BOT_TOKEN`, `ADMIN_IDS`
- `TRAEFIK_BOT_HOST` (публичный домен, например `wg.example.com`)
- `WEBHOOK_HOST` (обязателен для этого бота, строго `https://<ваш_домен>`)
- `PROXY_BIND_IP` (обычно `172.31.0.10`, для проброса loopback webhook наружу)
- `LETSENCRYPT_EMAIL` (email для ACME/Let's Encrypt)
- `WG_SERVER_PRIVATE_KEY`
- `WG_CLIENT_CONFIG_PATH` (файл клиента внешнего WireGuard)
- `WG_CLIENT_GATEWAY_IP` (IP контейнера egress-клиента, обычно `172.30.0.2`)

3. Убедитесь, что DNS домена (`TRAEFIK_BOT_HOST`) указывает на этот сервер, и открыты порты `80/tcp` и `443/tcp`.

4. Подготовьте хранилище сертификатов Let's Encrypt:

```bash
mkdir -p letsencrypt
touch letsencrypt/acme.json
chmod 600 letsencrypt/acme.json
```

5. Положите конфиг внешнего WG клиента (контейнер 2), например:

`./config/wg-client/wg-egress.conf`

Этот файл будет смонтирован как:

`/etc/wireguard/${WG_CLIENT_INTERFACE}.conf`

`WG_CLIENT_EGRESS_IFACE` можно оставить пустым: интерфейс до `WG_CLIENT_GATEWAY_IP` определяется автоматически (это устраняет ошибку `Nexthop has invalid gateway` при изменении порядка docker-сетей).

Для `wg-egress-client` startup-скрипт автоматически создаёт runtime-конфиг (`/run/wireguard/*.conf`),
убирает `DNS=` и добавляет `Table = off`, чтобы избежать типичных ошибок контейнерной среды:
`could not detect a useable init system` и `sysctl ... src_valid_mark ... Read-only file system`.

## Запуск

```bash
docker compose up -d --build
```

## TLS / Webhook (Traefik + Let's Encrypt)

Traefik в `docker-compose.yml` настроен так:
- слушает `:80` и `:443`;
- делает редирект `HTTP -> HTTPS`;
- получает сертификат через Let's Encrypt (ACME HTTP challenge);
- роутит `Host(${TRAEFIK_BOT_HOST})` в `vpn-bot-server` по `websecure` и использует сеть `proxy` (`traefik.docker.network=proxy`).

Это соответствует требованию бота/Telegram: `WEBHOOK_HOST` должен быть HTTPS URL.

Дополнительно включён bridge внутри `vpn-bot-server`: если бот слушает только `127.0.0.1:8081`,
скрипт публикует этот порт на `PROXY_BIND_IP` (по умолчанию `172.31.0.10`) через `socat`,
чтобы Traefik стабильно доставлял webhook в контейнер.

> Если в логах бота видно `Running on http://127.0.0.1:8081`, задайте в `.env`
> `WEBHOOK_LISTEN_HOST=0.0.0.0` (а также при необходимости `WEBAPP_HOST`/`APP_HOST`),
> чтобы сервис был доступен Traefik из docker-сети.

## Важные замечания

- `vpn-bot-server` работает с `NET_ADMIN`/`SYS_MODULE` и `privileged: true` из-за WG и routing.
- `wg-egress-client` делает `MASQUERADE` исходящего трафика в внешний WG тоннель.
- В проде лучше зафиксировать `BOT_REF` на tag/commit, а не `main`.
