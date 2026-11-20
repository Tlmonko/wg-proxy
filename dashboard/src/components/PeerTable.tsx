import { useMemo, useState } from 'react'
import type { Peer } from '../lib/types'
import { fmtAgo, fmtGiB, fmtMb, freshness } from '../lib/types'

type SortKey = 'tx' | 'rx' | 'total' | 'hs' | 'name'

export function PeerTable({ peers }: { peers: Peer[] }) {
  const [sort, setSort] = useState<SortKey>('tx')

  const rows = useMemo(() => {
    const r = [...peers]
    switch (sort) {
      case 'tx': r.sort((a, b) => b.txRate - a.txRate); break
      case 'rx': r.sort((a, b) => b.rxRate - a.rxRate); break
      case 'total': r.sort((a, b) => (b.rxTotal + b.txTotal) - (a.rxTotal + a.txTotal)); break
      case 'hs': r.sort((a, b) => a.hsAge - b.hsAge); break
      case 'name': r.sort((a, b) => a.peer.localeCompare(b.peer)); break
    }
    return r
  }, [peers, sort])

  const th = (key: SortKey, label: string, right = true) => (
    <th className={right ? 'r' : ''} onClick={() => setSort(key)}>
      {label}{sort === key ? ' ▾' : ''}
    </th>
  )

  return (
    <section className="panel full">
      <div className="phead">
        <h2>Peers</h2>
        <span className="sub">{peers.length} managed</span>
        <span className="right num">window totals · current rates</span>
      </div>
      <table>
        <thead>
          <tr>
            {th('name', 'Peer', false)}
            <th>Tunnel ip</th>
            {th('total', 'Received')}
            {th('total', 'Sent')}
            {th('rx', 'rx Mb/s')}
            {th('tx', 'tx Mb/s')}
            {th('hs', 'Handshake')}
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(p => {
            const f = Number.isNaN(p.hsAge) ? 'bad' : freshness(p.hsAge)
            const on = p.hsAge < 180
            const dotCls = f === 'ok' ? '' : f === 'warn' ? 'warn' : 'neg'
            return (
              <tr key={p.peer}>
                <td>
                  <span className="peer">
                    <span className={'dot ' + dotCls} />
                    {p.peer}
                  </span>
                </td>
                <td>{p.ip || '—'}</td>
                <td className="r">{fmtGiB(p.rxTotal)}</td>
                <td className="r">{fmtGiB(p.txTotal)}</td>
                <td className="r down">{on ? fmtMb(p.rxRate) : '0.00'}</td>
                <td className="r up">{on ? fmtMb(p.txRate) : '0.00'}</td>
                <td className={'r' + (on ? '' : ' stale')}>
                  {Number.isNaN(p.hsAge) ? '—' : fmtAgo(p.hsAge)}
                </td>
                <td className={on ? (f === 'warn' ? 'mut' : 'pos') : 'stale'}>
                  {on ? (f === 'warn' ? 'slow' : 'online') : 'stale'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
