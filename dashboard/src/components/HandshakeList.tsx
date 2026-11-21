import { useMemo } from 'react'
import type { Peer } from '../lib/types'
import { fmtAgo, freshness } from '../lib/types'

export function HandshakeList({ peers }: { peers: Peer[] }) {
  const sorted = useMemo(
    () => [...peers].filter(p => !Number.isNaN(p.hsAge)).sort((a, b) => a.hsAge - b.hsAge),
    [peers],
  )
  return (
    <section className="panel">
      <div className="phead">
        <h2>Handshake</h2>
        <span className="right num">latest_handshake_seconds</span>
      </div>
      <div className="hslist">
        {sorted.map(p => {
          const f = freshness(p.hsAge)
          const cls = f === 'ok' ? '' : f === 'warn' ? 'warn' : 'neg'
          return (
            <div className="hrow" key={p.peer}>
              <span className={'dot ' + (f === 'ok' ? '' : cls)} />
              <span className="nm">{p.peer}</span>
              <span className="age">{fmtAgo(p.hsAge)}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}
