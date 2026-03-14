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

3. Укажите, какой конфиг внешнего WG монтировать в контейнер 2:

- В `.env` задайте `WG_CLIENT_CONFIG_PATH` (по умолчанию `./config/wg-client/wg-egress.conf`).
- Внутрь контейнера файл попадёт как `/etc/wireguard/${WG_CLIENT_INTERFACE}.conf`.

Пример:

```env
WG_CLIENT_INTERFACE=wg-egress
WG_CLIENT_CONFIG_PATH=./config/wg-client/wg-egress.conf
```

То есть конфиг подключения к стороннему WG-серверу нужно хранить на хосте по пути из `WG_CLIENT_CONFIG_PATH`.

## Запуск

```bash
docker compose up -d --build
```

## Важные замечания

- Контейнер `vpn-bot-server` запускается в привилегированном режиме, так как WireGuard и маршрутизация требуют `NET_ADMIN`/`SYS_MODULE`.
- Контейнер `wg-egress-client` выполняет NAT (`MASQUERADE`) в сторону внешнего WG туннеля.
- Для продакшена рекомендуется заменить `build` на фиксированный image tag вашего бота.
