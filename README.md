# wg-proxy

`docker-compose.yml` поднимает двухконтейнерную схему:

1. `vpn-bot-server` — контейнер с ботом `wg-vpn-tg-bot` и WireGuard сервером для пользователей.
2. `wg-egress-client` — отдельный контейнер WireGuard клиента, подключенного к стороннему WG.

Трафик клиентов, которых создает бот:

`user peer -> vpn-bot-server (WG server) -> wg-egress-client -> внешний WG сервер`

## Подготовка

1. Скопируйте переменные окружения:

```bash
cp .env.example .env
```

2. Заполните `.env`:
- `BOT_TOKEN`, `ADMIN_ID`
- `WG_SERVER_PRIVATE_KEY`
- при необходимости поменяйте подсети и порты

3. Положите конфиг клиента внешнего WG в:

`./config/wg-client/wg-egress.conf`

(имя интерфейса по умолчанию: `wg-egress`, можно изменить через `WG_CLIENT_INTERFACE`).

## Запуск

```bash
docker compose up -d --build
```

## Важные замечания

- Контейнер `vpn-bot-server` запускается в привилегированном режиме, так как WireGuard и маршрутизация требуют `NET_ADMIN`/`SYS_MODULE`.
- Контейнер `wg-egress-client` выполняет NAT (`MASQUERADE`) в сторону внешнего WG туннеля.
- Для продакшена рекомендуется заменить `build` на фиксированный image tag вашего бота.
