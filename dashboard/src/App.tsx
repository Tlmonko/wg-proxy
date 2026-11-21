import { useStatus } from './lib/useStatus'
import { TopBar } from './components/TopBar'
import { Topology } from './components/Topology'
import { Throughput } from './components/Throughput'
import { HandshakeList } from './components/HandshakeList'
import { PeerTable } from './components/PeerTable'
import { fmtAgo } from './lib/types'

export default function App() {
  const { snap, mode, error, config, setConfig, online, since, test } = useStatus()
  const peers = snap?.peers ?? []

  return (
    <>
      <TopBar
        mode={mode} error={error} vmUrl={config.vmUrl}
        range={config.range} refresh={config.refresh}
        online={online} total={peers.length} since={since}
        onRange={r => setConfig({ range: r })}
        onRefresh={s => setConfig({ refresh: s })}
        onSaveUrl={u => setConfig({ vmUrl: u })}
        onTest={test}
      />

      {mode === 'error' && (
        <div style={{ maxWidth: 1440, margin: '16px auto 0', padding: '0 24px' }}>
          <div className="panel" style={{ padding: '12px 16px', fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--neg)' }}>
            vm error: {error} — check the URL in the data-source menu (top right)
          </div>
        </div>
      )}

      <div className="wrap">
        <Topology peers={peers} />
        <div className="col">
          <Throughput
            chart={snap?.chart ?? null}
            range={config.range}
            onRange={r => setConfig({ range: r })}
            error={mode === 'error' ? error : ''}
          />
          <HandshakeList peers={peers} />
        </div>
        <PeerTable peers={peers} />
      </div>

      <footer>
        <span>
          {mode === 'live'
            ? 'source · VictoriaMetrics — wireguard exporter'
            : 'demo data — set a VM URL for live stats'}
        </span>
        {snap && !Number.isNaN(snap.upstreamAge) && (
          <span>upstream handshake {fmtAgo(snap.upstreamAge)} ago</span>
        )}
        <span>wg-proxy · status-web</span>
      </footer>
    </>
  )
}
