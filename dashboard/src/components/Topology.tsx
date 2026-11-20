import { useMemo } from 'react'
import type { Peer } from '../lib/types'
import { fmtAgo, fmtGiB, fmtMb, freshness } from '../lib/types'

const W = 740, chipW = 176, chipH = 32, pitch = 40
const bx = 296, bw = 204, bh = 124
const ux = 520, uw = 204

function val(t: string): HTMLSpanElement {
  const s = document.createElement('span')
  s.className = 'v'
  s.textContent = t
  return s
}

export function Topology({ peers }: { peers: Peer[] }) {
  const top = useMemo(
    () => [...peers].sort((a, b) => b.txRate - a.txRate).slice(0, 16),
    [peers],
  )
  const H = 16 + top.length * pitch + 44
  const by = H / 2 - 62
  const online = peers.filter(p => p.hsAge < 180).length
  const totRx = peers.reduce((s, p) => s + p.rxRate, 0)
  const totTx = peers.reduce((s, p) => s + p.txRate, 0)
  const rest = peers.length - top.length
  const my = 8 + top.length * pitch + 6

  const tip = (e: React.MouseEvent<SVGGElement>, p: Peer) => {
    const el = document.getElementById('tip')!
    /* DOM methods, not innerHTML — peer names come from external VM labels */
    while (el.firstChild) el.removeChild(el.firstChild)
    const line = (bold: string, rest: string) => {
      const d = document.createElement('div')
      const b = document.createElement('b')
      b.textContent = bold
      d.appendChild(b)
      d.appendChild(document.createTextNode(rest))
      el.appendChild(d)
    }
    line(p.peer, p.ip ? ' · ' + p.ip : '')
    const l2 = document.createElement('div')
    l2.append('rx ', val(fmtGiB(p.rxTotal)), ' · tx ', val(fmtGiB(p.txTotal)))
    el.appendChild(l2)
    if (p.hsAge < 180) {
      const l3 = document.createElement('div')
      l3.append('rx ', val(fmtMb(p.rxRate)), ' · tx ', val(fmtMb(p.txRate) + ' Mb/s'))
      el.appendChild(l3)
    }
    line('handshake', ' ' + (Number.isNaN(p.hsAge) ? '—' : fmtAgo(p.hsAge)))
    el.style.display = 'block'
    el.style.left = Math.min(e.clientX + 14, window.innerWidth - 220) + 'px'
    el.style.top = e.clientY + 14 + 'px'
  }
  const hide = () => { document.getElementById('tip')!.style.display = 'none' }

  return (
    <section className="panel">
      <div className="phead">
        <h2>Topology</h2>
        <span className="sub">wg0 · 51820/udp+tcp</span>
        <span className="right num">tx Mb/s per peer</span>
      </div>
      <div className="topo">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="topology">
          {top.map((p, i) => {
            const y = 8 + i * pitch
            const cy = y + chipH / 2
            const tgt = by + 18 + Math.min(i, 5) * ((bh - 36) / 5)
            const cls = 'tlink' + (p.txRate > 1.2 ? ' big' : '') + (p.hsAge >= 180 ? ' off' : '')
            return (
              <path key={p.peer} className={cls}
                d={`M ${chipW + 8} ${cy} C ${bx - 64} ${cy}, ${bx - 64} ${tgt}, ${bx} ${tgt}`} />
            )
          })}
          <path className="trunk" d={`M ${bx + bw} ${by + bh - 32} L ${ux} ${by + bh - 32}`} />
          <path className="exit" d={`M ${ux + uw} ${by + bh - 32} L ${W - 44} ${by + bh - 32}`} />

          {top.map((p, i) => {
            const y = 8 + i * pitch
            const f = Number.isNaN(p.hsAge) ? 'bad' : freshness(p.hsAge)
            const col = f === 'ok' ? 'var(--pos)' : f === 'warn' ? 'var(--warn)' : 'var(--neg)'
            return (
              <g key={p.peer} className="chip"
                onMouseMove={e => tip(e, p)} onMouseLeave={hide}>
                <rect x="0" y={y} width={chipW} height={chipH} rx="8" />
                <circle cx="14" cy={y + chipH / 2} r="4" fill={col} />
                <text className="nm" x="28" y={y + 20}>{p.peer}</text>
                <text x={chipW - 12} y={y + 20} textAnchor="end">
                  {p.hsAge < 180 ? fmtMb(p.txRate) : '—'}
                </text>
              </g>
            )
          })}

          <g>
            <rect x="0" y={my} width={chipW} height={chipH} rx="8" fill="none"
              stroke="var(--line)" strokeDasharray="4 4" />
            <text x={chipW / 2} y={my + 20} textAnchor="middle" fontSize="12" fill="var(--muted)">
              +{rest} more — see table below
            </text>
          </g>

          <g className="node">
            <rect x={bx} y={by} width={bw} height={bh} rx="12" />
            <circle cx={bx + 20} cy={by + 24} r="4" fill="var(--pos)" />
            <text className="t" x={bx + 36} y={by + 28}>Bridge · berd</text>
            <text className="m" x={bx + 16} y={by + 52}>85.208.86.163:51820 · wg0</text>
            <text className="v" x={bx + 16} y={by + 72}>
              peers {online}/{peers.length} online · {peers.length - online} stale
            </text>
            <text className="v" x={bx + 16} y={by + 92}>
              <tspan fill="var(--pos)">rx {totRx.toFixed(1)}</tspan>
              {'  '}
              <tspan fill="var(--tx)">tx {totTx.toFixed(1)} Mb/s</tspan>
            </text>
            <text className="m" x={bx + 16} y={by + 112}>masquerade · telemt :8443</text>
          </g>

          <g className="node">
            <rect x={ux} y={by} width={uw} height={bh} rx="12" />
            <circle cx={ux + 20} cy={by + 24} r="4" fill="var(--pos)" />
            <text className="t" x={ux + 36} y={by + 28}>Upstream · knight</text>
            <text className="m" x={ux + 16} y={by + 52}>31.77.17.162:51820 · exit</text>
            <text className="v" x={ux + 16} y={by + 72}>177.3.218.244 · 13.143.173.251</text>
            <text className="v" x={ux + 16} y={by + 92}>
              <tspan fill="var(--pos)">rx {(totRx * 0.97).toFixed(1)}</tspan>
              {'  '}
              <tspan fill="var(--tx)">tx {(totTx * 0.97).toFixed(1)} Mb/s</tspan>
            </text>
            <text className="m" x={ux + 16} y={by + 112}>allowed ips 0.0.0.0/0</text>
          </g>

          <g>
            <circle cx={W - 24} cy={by + bh - 32} r="14" fill="none" stroke="var(--muted)" strokeOpacity=".6" />
            <ellipse cx={W - 24} cy={by + bh - 32} rx="12" ry="4.5" fill="none" stroke="var(--muted)" strokeOpacity=".5" />
            <text x={W - 24} y={by + bh + 4} textAnchor="middle" fontSize="11" fill="var(--muted)">internet</text>
          </g>
        </svg>
      </div>
      <div id="tip" />
    </section>
  )
}
