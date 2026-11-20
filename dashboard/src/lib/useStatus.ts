import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Snapshot, RangeKey } from './types'
import { RANGES } from './types'
import { demoSnapshot } from './demo'
import { vmPeers, vmUpstreamAge, vmChart, vmPing } from './vm'

export type Mode = 'demo' | 'live' | 'error'

export interface Config {
  vmUrl: string
  range: RangeKey
  refresh: number // seconds
}

const LS_KEY = 'wg-status-config-v1'

function loadConfig(): Config {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (raw) return { vmUrl: '', range: '30m', refresh: 30, ...JSON.parse(raw) }
  } catch { /* ignore */ }
  const env = (import.meta.env.VITE_VM_URL as string | undefined) ?? ''
  return { vmUrl: env, range: '30m', refresh: 30 }
}

export function useStatus() {
  const [config, setConfigState] = useState<Config>(loadConfig)
  const [snap, setSnap] = useState<Snapshot | null>(null)
  const [mode, setMode] = useState<Mode>(loadConfig().vmUrl ? 'live' : 'demo')
  const [error, setError] = useState('')
  const [since, setSince] = useState(Date.now())
  const timer = useRef<number | null>(null)

  const setConfig = useCallback((patch: Partial<Config>) => {
    setConfigState(prev => {
      const next = { ...prev, ...patch }
      try { localStorage.setItem(LS_KEY, JSON.stringify(next)) } catch { /* ignore */ }
      return next
    })
  }, [])

  const load = useCallback(async (cfg: Config) => {
    const { seconds, step } = RANGES[cfg.range]
    if (!cfg.vmUrl) {
      setSnap(demoSnapshot(seconds, step))
      setMode('demo')
      setError('')
      setSince(Date.now())
      return
    }
    try {
      const [peers, upstreamAge, chart] = await Promise.all([
        vmPeers(cfg.vmUrl, seconds),
        vmUpstreamAge(cfg.vmUrl),
        vmChart(cfg.vmUrl, seconds, step),
      ])
      setSnap({ peers, upstreamAge, chart, at: Date.now() })
      setMode('live')
      setError('')
      setSince(Date.now())
    } catch (e) {
      setMode('error')
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => { load(config) }, [config, load])

  useEffect(() => {
    if (timer.current) window.clearInterval(timer.current)
    timer.current = window.setInterval(() => load(config), Math.max(10, config.refresh) * 1000)
    return () => { if (timer.current) window.clearInterval(timer.current) }
  }, [config, load])

  const test = useCallback(async (url: string) => {
    await vmPing(url)
  }, [])

  const online = useMemo(
    () => (snap ? snap.peers.filter(p => p.hsAge < 180).length : 0),
    [snap],
  )

  return { snap, mode, error, config, setConfig, online, since, test }
}
