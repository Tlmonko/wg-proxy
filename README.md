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
- `bridge/clients/example.conf` — пример конфига клиента.

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

## Порядок действий

1. Сгенерировать 3 пары ключей командами выше.
2. Заполнить шаблоны `upstream/config/wg0.conf`, `bridge/config/wg0.conf` и `bridge/clients/example.conf` адресами, портом и ключами.
3. Запустить upstream:
   ```bash
   cd upstream && docker compose up -d
   ```
4. Запустить bridge:
   ```bash
   cd bridge && docker compose up -d
   ```
5. Подключить клиент, используя заполненный клиентский конфиг `bridge/clients/example.conf` (или его копию для конкретного клиента).

