# wg-proxy

Этот репозиторий поднимает цепочку из **3 сервисов**:

1. `vpn-bot-server` — контейнер с кодом `wg-vpn-tg-bot` + WireGuard сервер для клиентов.
2. `wg-egress-client` — контейнер WireGuard клиента к стороннему WG серверу.
3. `traefik` — reverse proxy (для HTTP/webhook части бота, если используется).

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
- `WEBHOOK_HOST` (обязателен для этого бота, например `https://vpn.example.com`)
- при проблемах с доступностью webhook через Traefik: `WEBHOOK_LISTEN_HOST=0.0.0.0`
- `WG_SERVER_PRIVATE_KEY`
- `WG_CLIENT_CONFIG_PATH` (файл клиента внешнего WireGuard)
- `WG_CLIENT_GATEWAY_IP` (IP контейнера egress-клиента, обычно `172.30.0.2`)

3. Положите конфиг внешнего WG клиента (контейнер 2), например:

`./config/wg-client/wg-egress.conf`

Этот файл будет смонтирован как:

`/etc/wireguard/${WG_CLIENT_INTERFACE}.conf`

`WG_CLIENT_EGRESS_IFACE` можно оставить пустым: интерфейс до `WG_CLIENT_GATEWAY_IP` определяется автоматически (это устраняет ошибку `Nexthop has invalid gateway` при изменении порядка docker-сетей).

## Запуск

```bash
docker compose up -d --build
```

## Traefik

Traefik включён в compose и проксирует HTTP-сервис бота по host-правилу:

- `Host(${TRAEFIK_BOT_HOST})` для маршрутизации внутрь контейнера бота
- entrypoint `web` (порт `80`)

По умолчанию:
- HTTP: `:80`
- Dashboard Traefik: `:8080`

> Важно: `wg-vpn-tg-bot` в webhook-режиме требует `WEBHOOK_HOST` в формате `https://...`.
> Если Traefik у вас без TLS (как в этом примере), TLS должен терминироваться внешним прокси/балансером,
> а в `WEBHOOK_HOST` указывается внешний HTTPS-домен.
>
> Если в логах бота видно `Running on http://127.0.0.1:8081`, задайте в `.env`
> `WEBHOOK_LISTEN_HOST=0.0.0.0` (а также при необходимости `WEBAPP_HOST`/`APP_HOST`),
> чтобы сервис был доступен Traefik из docker-сети.

> Если ваш бот работает только через long polling и не поднимает HTTP endpoint/webhook,
> Traefik не мешает работе WG-схемы и может быть оставлен как инфраструктурный reverse proxy.

## Важные замечания

- `vpn-bot-server` работает с `NET_ADMIN`/`SYS_MODULE` и `privileged: true` из-за WG и routing.
- `wg-egress-client` делает `MASQUERADE` исходящего трафика в внешний WG тоннель.
- В проде лучше зафиксировать `BOT_REF` на tag/commit, а не `main`.
