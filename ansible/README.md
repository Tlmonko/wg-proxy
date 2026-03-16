# Ansible deployment for wg-proxy

Эта директория добавляет **дополнительный** способ деплоя (ручной сценарий из корневого `README.md` остается рабочим).

## Структура

- `inventory/production.yml` — пример inventory с группами `upstream` и `bridge`.
- `group_vars/all.yml` — общие и bot-переменные.
- `group_vars/upstream.yml` — переменные upstream.
- `group_vars/bridge.yml` — переменные bridge.
- `playbooks/site.yml` — основной playbook с тегами `docker`, `upstream`, `bridge`.
- `roles/docker` — установка Docker Engine + Docker Compose plugin.
- `roles/wg_upstream` — раскатка upstream compose + `wg0.conf`.
- `roles/wg_bridge` — раскатка bridge compose + `wg0.conf` + `.env` + bot-код.
- `templates/` — Jinja2-шаблоны конфигов.

## Какие переменные заполнить

### Общие (`group_vars/all.yml`)

Обязательно:
- `wg_project_root`
- `wg_timezone`
- `wg_listen_port`
- `upstream_public_key`
- `bridge_public_key`
- `upstream_endpoint_host`
- `bot_token`
- `bot_admin_ids`

Опционально:
- `bot_wg_allowed_ips`
- `bot_wg_dns`
- `bot_data_dir`
- `bot_wg_interface`

Автоматически вычисляются:
- `bot_wg_endpoint = {{ bridge_public_ip_or_dns }}:{{ wg_listen_port }}`
- `bot_wg_server_public_key = {{ bridge_public_key }}`
- `bot_wg_server_ipv4 = {{ bridge_wg_address.split('/')[0] }}`
- `bot_wg_server_cidr = {{ bridge_wg_address.split('/')[1] }}`

### Upstream (`group_vars/upstream.yml`)

- `upstream_public_ip`
- `upstream_wg_address`
- `upstream_private_key`

### Bridge (`group_vars/bridge.yml`)

- `bridge_public_ip_or_dns`
- `bridge_wg_address`
- `bridge_private_key`
- `bridge_manual_peers` (опциональный список ручных peer'ов)

Формат `bridge_manual_peers`:

```yaml
bridge_manual_peers:
  - comment: office-router
    public_key: BASE64_PUBLIC_KEY
    allowed_ips: 10.10.10.4/32
    preshared_key: OPTIONAL_BASE64_PSK
```

Эти peer'ы рендерятся до managed-блока, который бот продолжает менять сам:
- `# BEGIN MANAGED CLIENTS`
- `# END MANAGED CLIENTS`

## Пример inventory

```yaml
all:
  children:
    upstream:
      hosts:
        upstream-1:
          ansible_host: 203.0.113.10
          ansible_user: root
    bridge:
      hosts:
        bridge-1:
          ansible_host: 198.51.100.20
          ansible_user: root
```

## Пример `group_vars/all.yml`

```yaml
wg_project_root: /opt/wg-proxy
wg_timezone: Europe/Moscow
wg_listen_port: 51820

upstream_public_key: "<upstream-public-key>"
bridge_public_key: "<bridge-public-key>"
upstream_endpoint_host: "203.0.113.10"

bot_token: "123456:telegram-bot-token"
bot_admin_ids:
  - 123456789

bot_wg_allowed_ips: 0.0.0.0/0
bot_wg_dns: 1.1.1.1,1.0.0.1
```

## Ключи WireGuard (генерируются заранее)

В первой версии автоматизация **не генерирует ключи** автоматически.
Сгенерируйте ключи локально заранее и подставьте в переменные:

```bash
wg genkey | tee upstream_private.key | wg pubkey > upstream_public.key
wg genkey | tee bridge_private.key   | wg pubkey > bridge_public.key
```

## Запуск

Из корня репозитория:

### Полный деплой (docker + upstream + bridge)

```bash
ansible-playbook -i ansible/inventory/production.yml ansible/playbooks/site.yml
```

### Только upstream

```bash
ansible-playbook -i ansible/inventory/production.yml ansible/playbooks/site.yml --tags upstream
```

### Только bridge

```bash
ansible-playbook -i ansible/inventory/production.yml ansible/playbooks/site.yml --tags bridge
```

### Только установка Docker

```bash
ansible-playbook -i ansible/inventory/production.yml ansible/playbooks/site.yml --tags docker
```

### Обновить только bridge bot

Используйте `--tags bridge` (роль скопирует `bridge/bot/` и выполнит `docker compose up -d --build`):

```bash
ansible-playbook -i ansible/inventory/production.yml ansible/playbooks/site.yml --tags bridge --limit bridge
```
