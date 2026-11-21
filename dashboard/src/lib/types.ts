export type Freshness = 'ok' | 'warn' | 'bad'

export interface Peer {
  peer: string
  ip: string
  rxRate: number   // Mb/s
  txRate: number   // Mb/s
  rxTotal: number  // GiB over window
  txTotal: number  // GiB over window
  hsAge: number    // seconds since handshake
}

export interface ChartSeries {
  ts: number[]      // unix seconds
  rx: number[]      // Mb/s
  tx: number[]
}

export interface Snapshot {
  peers: Peer[]
  upstreamAge: number
  chart: ChartSeries
  at: number
}

export type RangeKey = '30m' | '3h' | '24h'
export const RANGES: Record<RangeKey, { label: string; seconds: number; step: number }> = {
  '30m': { label: '30 m', seconds: 30 * 60, step: 30 },
  '3h': { label: '3 h', seconds: 3 * 3600, step: 120 },
  '24h': { label: '24 h', seconds: 24 * 3600, step: 900 },
}

export function freshness(age: number): Freshness {
  if (age < 60) return 'ok'
  if (age < 180) return 'warn'
  return 'bad'
}

export function fmtGiB(g: number): string {
  return g >= 100 ? g.toFixed(0) + ' GiB' : g.toFixed(1) + ' GiB'
}

export function fmtAgo(s: number): string {
  if (s < 60) return Math.round(s) + ' s'
  if (s < 3600) return Math.round(s / 60) + ' min'
  if (s < 86400) return (s / 3600).toFixed(1) + ' h'
  return Math.round(s / 86400) + ' d'
}

export function fmtMb(v: number): string {
  return v.toFixed(2)
}
