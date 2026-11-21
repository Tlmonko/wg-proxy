# wg-proxy · dashboard

Статус-страница WireGuard-туннеля (клиенты → bridge → upstream): топология,
throughput, свежесть handshake, таблица пиров. Чистый фронтенд без бека —
браузер читает данные напрямую из VictoriaMetrics.

Стек: React 18 + Vite + TypeScript.

## Data source

По умолчанию — **demo-режим** (мок-данные). Кнопка в правом верхнем углу
(`demo data` / `vm · live`) открывает настройки:

- **VM base URL** — например `http://nas:8428`, или `/vm`, если VM проксируется
  тем же nginx (см. закомментированный блок в `nginx.conf`); кнопка **Test**
  проверяет доступность.
- **Range** — окно (30 m / 3 h / 24 h), влияет на графики и totals.
- **Refresh** — период опроса (по умолчанию 30 s, как scrape VM).

Настройки хранятся в `localStorage`. Дефолт можно зашить на этапе сборки:
`VITE_VM_URL=/vm npm run build`.

CORS: VictoriaMetrics отдаёт `Access-Control-Allow-Origin: *` на `/api/v1/*`,
поэтому прямой URL работает; вариант с `/vm` через nginx вообще избавляет от
CORS.

## Имена пиров

Имена приходят из лейбла `friendly_name`, который wg-bot (bridge) генерирует в
`monitoring/peer-names/wg0.conf`; пиры без имени подписываются своим
allowed-ip. Запросы устойчивы к исторической смене лейбла: трафик мержится по
`allowed_ips`, имя подтягивается из текущего маппинга (см. `src/lib/vm.ts`).

## Разработка

```sh
npm install
npm run dev        # http://localhost:5173

# с прокси на VM (опционально), затем указать источник "/vm" в настройках:
VM_PROXY_TARGET=http://<vm-host>:8428 npm run dev
```

## Сборка и деплой

```sh
npm run build      # статика в dist/
npm run preview    # локальный просмотр билда
```

Docker (nginx + статика, SPA fallback, опциональный блок `/vm`):

```sh
docker build -t wg-dashboard .
docker run -d -p 8080:80 --name wg-dashboard wg-dashboard
```

Или просто отдавать содержимое `dist/` любым статик-сервером.
OAuth-прокси (oauth2-proxy, authentik, …) накручивается сверху — фронт не
требует авторизации и не хранит секретов.
