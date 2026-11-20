import type { Peer, ChartSeries } from './types'

/*
 * Direct VictoriaMetrics client (Prometheus-compatible API).
 * Point `vmUrl` at your VM (or a reverse-proxied path like "/vm").
 * CORS: VM answers /api/v1/* with Access-Control-Allow-Origin: * by default.
 */

const C = 'allowed_ips!="0.0.0.0/0"'

/* Current name mapping: friendly_name when present, allowed_ips otherwise. */
const NAMING =
  '(0 * (' +
  `label_replace(wireguard_sent_bytes_total{${C},friendly_name!=""}, "peer", "$1", "friendly_name", "(.+)")` +
  ' or ' +
  `label_replace(wireguard_sent_bytes_total{${C},friendly_name=""}, "peer", "$1", "allowed_ips", "(.+)")` +
  '))'

/** Join a per-allowed_ips aggregate with the current peer-name mapping. */
function named(inner: string): string {
  return (
    `sum by (peer)(${inner} + on (allowed_ips) group_left (peer) ${NAMING})`
  )
}

interface VmSeries { metric: Record<string, string>; value: [number, string] }
interface VmResult { status: string; data?: { result: VmSeries[] }; error?: string }

async function getJson(base: string, path: string): Promise<VmResult> {
  const r = await fetch(base.replace(/\/$/, '') + path)
  if (!r.ok) throw new Error('VM HTTP ' + r.status)
  return r.json()
}

async function instant(base: string, expr: string): Promise<VmSeries[]> {
  const j = await getJson(base, '/api/v1/query?query=' + encodeURIComponent(expr))
  if (j.status !== 'success') throw new Error(j.error || 'VM query failed')
  return j.data?.result ?? []
}

export async function vmPeers(base: string, winSeconds: number): Promise<Peer[]> {
  const w = `[${winSeconds}s]`
  const [rx, tx, rxT, txT, hs, map] = await Promise.all([
    instant(base, named(`sum by (allowed_ips)(rate(wireguard_received_bytes_total{${C}}${w})) * 8 / 1e6`)),
    instant(base, named(`sum by (allowed_ips)(rate(wireguard_sent_bytes_total{${C}}${w})) * 8 / 1e6`)),
    instant(base, named(`sum by (allowed_ips)(increase(wireguard_received_bytes_total{${C}}${w})) / 1073741824`)),
    instant(base, named(`sum by (allowed_ips)(increase(wireguard_sent_bytes_total{${C}}${w})) / 1073741824`)),
    instant(base, named(`sum by (allowed_ips)(time() - wireguard_latest_handshake_seconds{${C}})`)),
    /* current series keep allowed_ips + friendly_name — fills the ip column */
    instant(base, `label_replace(wireguard_sent_bytes_total{${C},friendly_name!=""}, "peer", "$1", "friendly_name", "(.+)")`),
  ])
  const ips = new Map<string, string>()
  for (const s of map) {
    if (s.metric.peer && s.metric.allowed_ips) ips.set(s.metric.peer, s.metric.allowed_ips.replace('/32', ''))
  }
  const idx = new Map<string, Peer>()
  const put = (rows: VmSeries[], f: (p: Peer, v: number) => void) => {
    for (const s of rows) {
      const k = s.metric.peer
      if (!k) continue
      const p: Peer = idx.get(k) ?? { peer: k, ip: s.metric.allowed_ips ?? '', rxRate: 0, txRate: 0, rxTotal: 0, txTotal: 0, hsAge: NaN }
      f(p, parseFloat(s.value[1]))
      idx.set(k, p)
    }
  }
  put(rx, (p, v) => { p.rxRate = v })
  put(tx, (p, v) => { p.txRate = v })
  put(rxT, (p, v) => { p.rxTotal = v })
  put(txT, (p, v) => { p.txTotal = v })
  put(hs, (p, v) => { p.hsAge = v })
  for (const p of idx.values()) {
    if (!p.ip) p.ip = ips.get(p.peer) ?? ''
  }
  return [...idx.values()]
}

export async function vmUpstreamAge(base: string): Promise<number> {
  const rows = await instant(base, `time() - wireguard_latest_handshake_seconds{allowed_ips="0.0.0.0/0"}`)
  return rows.length ? parseFloat(rows[0].value[1]) : NaN
}

interface VmRangeSeries { metric: Record<string, string>; values: Array<[number, string]> }

export async function vmChart(base: string, winSeconds: number, step: number): Promise<ChartSeries> {
  const end = Math.floor(Date.now() / 1000)
  const start = end - winSeconds
  const q = (m: string) =>
    `sum(rate(wireguard_${m}_bytes_total{${C}}[${step * 2}s])) * 8 / 1e6`
  const fetchR = async (m: string) => {
    const r = await fetch(base.replace(/\/$/, '') +
      `/api/v1/query_range?query=${encodeURIComponent(q(m))}&start=${start}&end=${end}&step=${step}`)
    if (!r.ok) throw new Error('VM HTTP ' + r.status)
    const j = await r.json()
    if (j.status !== 'success') throw new Error(j.error || 'VM range query failed')
    return (j.data.result as VmRangeSeries[])[0]?.values ?? []
  }
  const [rx, tx] = await Promise.all([fetchR('received'), fetchR('sent')])
  return { ts: rx.map(v => v[0]), rx: rx.map(v => +parseFloat(v[1]).toFixed(3)), tx: tx.map(v => +parseFloat(v[1]).toFixed(3)) }
}

export async function vmPing(base: string): Promise<string> {
  const j = await getJson(base, '/api/v1/query?query=1')
  if (j.status !== 'success') throw new Error(j.error || 'VM unhealthy')
  return 'ok'
}
