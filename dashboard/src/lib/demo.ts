import type { Peer, Snapshot } from './types'

/* Seeded demo data — neutral names, no real client identities. */
function mulberry32(a: number) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const RAW: Array<[string, string]> = [
  ['mbp-16', '10.10.10.5'], ['air-13', '10.10.10.6'], ['gk', '10.10.10.7'],
  ['daniel-phone', '10.10.10.8'], ['daniel-mac', '10.10.10.9'], ['mom-pad', '10.10.10.10'],
  ['dima-phone', '10.10.10.11'], ['dasha-phone', '10.10.10.12'], ['dima-book', '10.10.10.13'],
  ['home-router', '10.10.10.14'], ['pk1', '10.10.10.15'], ['pk2', '10.10.10.16'],
  ['mk1', '10.10.10.17'], ['asya-m', '10.10.10.18'], ['asya-p', '10.10.10.19'],
  ['gesha', '10.10.10.20'], ['vera-pc', '10.10.10.21'], ['polina', '10.10.10.22'],
  ['artem-phone', '10.10.10.23'], ['anna', '10.10.10.24'], ['tab-1', '10.10.10.25'],
  ['nina-phone', '10.10.10.26'], ['natasha-phone', '10.10.10.27'], ['senya', '10.10.10.28'],
  ['vera-home', '10.10.10.29'], ['daniel-home', '10.10.10.30'], ['pk3', '10.10.10.31'],
  ['timon', '10.10.10.32'], ['matvey', '10.10.10.33'], ['petus-pc', '10.10.10.34'],
  ['petus-phone', '10.10.10.35'], ['petus-tab', '10.10.10.36'], ['asya-phone', '10.10.10.37'],
  ['dima-home', '10.10.10.38'], ['asya-air', '10.10.10.39'], ['keenetic', '10.10.10.40'],
  ['gk2', '10.10.10.41'], ['natalia-phone', '10.10.10.42'], ['tv-xiaomi', '10.10.10.43'],
  ['ulia', '10.10.10.44'], ['pc-dmitrii', '10.10.10.45'], ['nikolai', '10.10.10.46'],
  ['flat-1', '10.10.10.47'], ['flat-2', '10.10.10.48'], ['mom2', '10.10.10.49'],
  ['vera-phone', '10.10.10.50'], ['avenir', '10.10.10.51'], ['desktop', '10.10.10.52'],
  ['book-m5', '10.10.10.53'], ['tema-desktop', '10.10.10.54'], ['polina-mac', '10.10.10.55'],
  ['lyuba', '10.10.10.56'], ['misha2', '10.10.10.57'], ['mini', '10.10.10.58'],
  ['gk-sil', '10.10.10.59'], ['gk-phone', '10.10.10.60'], ['s21', '10.10.10.61'],
  ['pk4', '10.10.10.62'], ['pk5', '10.10.10.63'], ['pk6', '10.10.10.64'],
  ['nk1', '10.10.10.65'], ['mk2', '10.10.10.66'], ['ma3', '10.10.10.67'],
  ['microb', '10.10.10.68'], ['leo', '10.10.10.69'], ['misha', '10.10.10.70'],
  ['sasha-c', '10.10.10.71'], ['misha-t', '10.10.10.72'], ['degior', '10.10.10.73'],
  ['andrey', '10.10.10.74'], ['katya', '10.10.10.75'], ['misha-k', '10.10.10.76'],
  ['kitsune', '10.10.10.77'], ['eugene', '10.10.10.78'], ['pk7', '10.10.10.79'],
  ['senya2', '10.10.10.80'], ['gosha-1', '10.10.10.81'], ['gosha-2', '10.10.10.82'],
  ['gosha-3', '10.10.10.83'], ['gosha-4', '10.10.10.84'], ['senya-mob', '10.10.10.85'],
  ['valya', '10.10.10.86'], ['andrey-s', '10.10.10.87'], ['mama-mob', '10.10.10.88'],
  ['anya', '10.10.10.89'], ['pk8', '10.10.10.90'], ['gosha-router', '10.10.10.91'],
  ['asya-tab', '10.10.10.92'], ['timur', '10.10.10.93'], ['aruuke', '10.10.10.94'],
  ['arina', '10.10.10.95'],
]

function peers(): Peer[] {
  return RAW.map(([name, ip], i) => {
    const r = mulberry32(48879 + i * 131)
    const heavy = r() < 0.12
    let tx = heavy ? +(0.5 + r() * 2.2).toFixed(2) : +(r() * 0.4).toFixed(2)
    let rxK = Math.round(tx * (180 + r() * 520))
    let rxG = +(0.4 + r() * 380).toFixed(1)
    let txG = +(0.15 + r() * 110).toFixed(1)
    const q = r()
    const hs = q < 0.6 ? Math.round(5 + r() * 55)
      : q < 0.85 ? Math.round(60 + r() * 119)
      : q < 0.94 ? Math.round(200 + r() * 7000)
      : Math.round(20000 + r() * 240000)
    const on = hs < 180
    if (!on) { tx = 0; rxK = 0; rxG = +(rxG * 0.2).toFixed(1); txG = +(txG * 0.2).toFixed(1) }
    return { peer: name, ip, rxRate: +(rxK / 1000).toFixed(3), txRate: tx, rxTotal: rxG, txTotal: txG, hsAge: hs }
  })
}

function walk(n: number, start: number, vol: number, rnd: () => number): number[] {
  const a: number[] = []
  let v = start
  for (let i = 0; i < n; i++) { v = Math.max(0.05, v + (rnd() - 0.48) * vol); a.push(+v.toFixed(3)) }
  return a
}

export function demoSnapshot(seconds: number, step: number): Snapshot {
  const rnd = mulberry32(20261121)
  const n = Math.max(10, Math.round(seconds / step))
  const now = Math.floor(Date.now() / 1000)
  const ts: number[] = []
  for (let i = n - 1; i >= 0; i--) ts.push(now - i * step)
  const p = peers()
  const totTx = p.reduce((s, x) => s + x.txRate, 0)
  const totRx = p.reduce((s, x) => s + x.rxRate, 0)
  return {
    peers: p,
    upstreamAge: 18 + Math.floor(rnd() * 30),
    chart: { ts, rx: walk(n, totRx, totRx * 0.4 + 0.3, rnd), tx: walk(n, totTx, totTx * 0.5 + 0.5, rnd) },
    at: Date.now(),
  }
}
