import { useEffect, useState } from 'react'
import type { Mode } from '../lib/useStatus'
import { fmtAgo, RANGES, type RangeKey } from '../lib/types'

interface Props {
  mode: Mode
  error: string
  vmUrl: string
  range: RangeKey
  refresh: number
  online: number
  total: number
  since: number
  onRange: (r: RangeKey) => void
  onRefresh: (s: number) => void
  onSaveUrl: (url: string) => void
  onTest: (url: string) => Promise<void>
}

export function TopBar(p: Props) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(p.vmUrl)
  const [testMsg, setTestMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const [ago, setAgo] = useState(0)

  useEffect(() => {
    const iv = window.setInterval(() => setAgo(Math.round((Date.now() - p.since) / 1000)), 1000)
    return () => window.clearInterval(iv)
  }, [p.since])

  const apply = () => {
    p.onSaveUrl(draft.trim())
    setOpen(false)
    setTestMsg('')
  }

  const test = async () => {
    setBusy(true); setTestMsg('…')
    try { await p.onTest(draft.trim()); setTestMsg('ok — данные доступны') }
    catch (e) { setTestMsg('недоступно: ' + (e instanceof Error ? e.message : String(e))) }
    finally { setBusy(false) }
  }

  const srcClass = p.mode === 'live' ? 'live' : p.mode === 'demo' ? 'demo' : 'demo'
  const srcLabel = p.mode === 'live' ? 'vm · live' : p.mode === 'demo' ? 'demo data' : 'vm · error'

  return (
    <>
      <header className="topbar">
        <div className="brand"><b>wg-proxy</b><span>tunnel status</span></div>
        <div className="meta">
          <span>peers <b className="num">{p.online}/{p.total}</b></span>
          <span>updated <b className="num">{ago < 5 ? 'just now' : fmtAgo(ago)}</b> · {p.refresh} s</span>
          <button className={'srcbtn ' + srcClass} onClick={() => { setDraft(p.vmUrl); setOpen(!open) }}>
            {srcLabel}
          </button>
        </div>
      </header>

      {open && (
        <div className="srclayer" onClick={() => setOpen(false)}>
          <div className="srccard" onClick={e => e.stopPropagation()}>
            <h3>Data source</h3>
            <p>
              VictoriaMetrics base URL — the browser queries it directly
              (e.g. <span className="num">http://nas:8428</span> or an oauth-proxied path like{' '}
              <span className="num">/vm</span>). Leave empty for demo data.
            </p>
            <label>VM base URL</label>
            <input
              value={draft}
              placeholder="http://nas-host:8428"
              spellCheck={false}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && apply()}
            />
            <div className="row">
              <button className="btn" onClick={test} disabled={busy || !draft.trim()}>Test</button>
              <button className="btn primary" onClick={apply} disabled={busy}>Save</button>
            </div>
            {testMsg && (
              <div className={'status ' + (testMsg.startsWith('ok') ? 'ok' : 'err')}>{testMsg}</div>
            )}
            {p.mode === 'error' && <div className="status err">{p.error}</div>}
            <div style={{ marginTop: 12 }}>
              <label>Range</label>
              <div className="range">
                {(Object.keys(RANGES) as RangeKey[]).map(k => (
                  <button key={k} className={p.range === k ? 'on' : ''} onClick={() => p.onRange(k)}>
                    {RANGES[k].label}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ marginTop: 12 }}>
              <label>Refresh, seconds</label>
              <input
                type="number" min={10} max={3600} value={p.refresh} className="num"
                onChange={e => p.onRefresh(Math.max(10, Number(e.target.value) || 30))}
              />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
