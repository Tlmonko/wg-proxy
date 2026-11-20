import type { ChartSeries, RangeKey } from '../lib/types'
import { RANGES } from '../lib/types'

export function Throughput({ chart, range, onRange, error }: {
  chart: ChartSeries | null
  range: RangeKey
  onRange: (r: RangeKey) => void
  error: string
}) {
  const W = 600, H = 300, P = 44
  const n = chart ? chart.rx.length : 0
  const mx = chart && n ? Math.max(...chart.rx, ...chart.tx) * 1.15 || 1 : 1
  const X = (i: number) => P + (i * (W - P - 10)) / Math.max(1, n - 1)
  const Y = (v: number) => H - 24 - (v * (H - 44)) / mx
  const path = (a: number[]) => a.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join(' ')
  const area = (a: number[]) => a.length ? `${path(a)} L ${X(n - 1).toFixed(1)} ${H - 24} L ${P} ${H - 24} Z` : ''
  const label = (i: number, len: number) => {
    if (!chart || !n) return ''
    const sec = chart.ts[0] + (i * (chart.ts[n - 1] - chart.ts[0])) / Math.max(1, n - 1)
    const d = new Date(sec * 1000)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return len > 6 ? `${hh}:${mm}` : `${hh}:${mm}`
  }
  const lastRx = chart && n ? chart.rx[n - 1] : 0
  const lastTx = chart && n ? chart.tx[n - 1] : 0

  return (
    <section className="panel">
      <div className="phead">
        <h2>Throughput</h2>
        <span className="sub">bridge ↔ upstream</span>
        <div className="range" style={{ marginLeft: 'auto' }}>
          {(Object.keys(RANGES) as RangeKey[]).map(k => (
            <button key={k} className={range === k ? 'on' : ''} onClick={() => onRange(k)}>
              {RANGES[k].label}
            </button>
          ))}
        </div>
      </div>
      <div className="chartpad">
        <div className="legend">
          <span><i style={{ background: 'var(--pos)' }} />rx</span>
          <span><i style={{ background: 'var(--tx)' }} />tx</span>
          <span className="read num">
            now rx <span style={{ color: 'var(--pos)' }}>{lastRx.toFixed(2)}</span>
            {' · '}tx <span style={{ color: 'var(--tx)' }}>{lastTx.toFixed(2)}</span> Mb/s
          </span>
        </div>
        <div className="chartbox">
          {chart && n > 1 ? (
            <svg viewBox={`0 0 ${W} ${H}`} width="100%">
              {[0, 1, 2, 3, 4].map(g => {
                const v = (mx * g) / 4
                const y = Y(v)
                return (
                  <g key={g}>
                    <line x1={P} y1={y.toFixed(1)} x2={W - 10} y2={y.toFixed(1)} stroke="rgba(238,240,245,.06)" />
                    <text x={P - 8} y={(y + 4).toFixed(1)} textAnchor="end" fontSize="11" fill="var(--muted)">
                      {v.toFixed(1)}
                    </text>
                  </g>
                )
              })}
              {[0, 1, 2, 3].map(i => (
                <text key={i} x={X(Math.round((i * (n - 1)) / 3))} y={H - 4}
                  fontSize="11" fill="var(--muted)" textAnchor={i === 3 ? 'end' : 'middle'}>
                  {label(Math.round((i * (n - 1)) / 3), 2)}
                </text>
              ))}
              <path d={area(chart.rx)} fill="rgba(76,195,138,.12)" />
              <path d={area(chart.tx)} fill="rgba(123,150,255,.12)" />
              <path d={path(chart.rx)} fill="none" stroke="var(--pos)" strokeWidth="1.5" />
              <path d={path(chart.tx)} fill="none" stroke="var(--tx)" strokeWidth="1.5" />
              <circle cx={X(n - 1)} cy={Y(chart.rx[n - 1])} r="2.5" fill="var(--pos)" />
              <circle cx={X(n - 1)} cy={Y(chart.tx[n - 1])} r="2.5" fill="var(--tx)" />
            </svg>
          ) : (
            <div className="err">{error || 'no data'}</div>
          )}
        </div>
      </div>
    </section>
  )
}
