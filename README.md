# WG Proxy: доступ к upstream через bridge

Этот репозиторий описывает схему WireGuard из трёх ролей:

- **Клиент** — конечное устройство пользователя, которое подключается к VPN.
- **Bridge сервер** — промежуточный сервер: доступен клиенту и одновременно имеет доступ к upstream.
- **Upstream сервер** — сервер выхода в интернет; доступен bridge, но напрямую недоступен клиенту.

## Как работает схема

1. Клиент поднимает туннель до **bridge**.
2. Bridge принимает трафик клиента и отправляет его дальше в туннель до **upstream**.
3. Upstream выполняет NAT/маршрутизацию и выпускает трафик в интернет.

Идея: клиенту не нужен прямой доступ к upstream, весь путь строится через bridge.

## Шаблоны конфигураций

Используются следующие шаблоны WireGuard:

- `upstream/config/wg0.conf`
- `bridge/config/wg0.conf`
- `bridge/clients/example.conf`

Перед запуском нужно заменить плейсхолдеры (`[... ]`) на реальные значения: адреса, порт и ключи.

## Генерация ключей (с сохранением в файлы)

Сгенерируйте отдельные пары ключей для:

- upstream сервера,
- bridge сервера,
- клиента.

Рекомендуемая схема (приватный ключ сохраняется в файл, публичный — в отдельный файл):

```bash
wg genkey | tee upstream_private.key | wg pubkey > upstream_public.key
wg genkey | tee bridge_private.key   | wg pubkey > bridge_public.key
wg genkey | tee client_private.key   | wg pubkey > client_public.key
```

Так ключи не теряются: после команды остаются файлы `*_private.key` и `*_public.key`.

## Куда подставлять ключи

### `upstream/config/wg0.conf`

- `[UPSTREAM_PRIVATE_KEY]` ← содержимое `upstream_private.key`
- `[BRIDGE_SERVER_PUBLIC_KEY]` ← содержимое `bridge_public.key`

### `bridge/config/wg0.conf`

- `[BRIDGE_PRIVATE_KEY]` ← содержимое `bridge_private.key`
- `[PEER_PUBLIC_KEY]` ← содержимое `client_public.key`
- `[UPSTREAM_SERVER_PUBLIC_KEY]` ← содержимое `upstream_public.key`

### `bridge/clients/example.conf`

- `[CLIENT_PRIVATE_KEY]` ← содержимое `client_private.key`
- `[BRIDGE_PUBLIC_KEY]` ← содержимое `bridge_public.key`

## Минимальный порядок действий

1. Сгенерировать 3 пары ключей командами выше.
2. Заполнить шаблоны `wg0.conf` и `bridge/clients/example.conf` адресами, портом и ключами.
3. Запустить сервисы.

