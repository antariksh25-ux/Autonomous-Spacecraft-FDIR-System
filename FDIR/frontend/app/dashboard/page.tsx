'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Activity, AlertTriangle, CheckCircle2, Shield, User, Wrench } from 'lucide-react'
import {
  fdirApi,
  type FDIRConfig,
  type FDIRStatus,
  type FaultRecord,
  type InitMessage,
  type LogEntry,
  type SnapshotMessage,
  type SubsystemHealth,
} from '../../lib/api'

type TelemetryPoint = { t: number; value: number }

function severityBadge(sev: string | undefined): { text: string; cls: string } {
  switch (sev) {
    case 'green':
      return { text: 'GREEN', cls: 'text-accent border-accent' }
    case 'yellow':
      return { text: 'YELLOW', cls: 'text-warning border-warning' }
    case 'red':
      return { text: 'RED', cls: 'text-destructive border-destructive' }
    default:
      return { text: 'UNKNOWN', cls: 'text-foreground/70 border-foreground/20' }
  }
}

function autonomyBadge(level: string | undefined): { text: string; cls: string; icon: React.ReactNode } {
  const normalized = String(level || '').toLowerCase()
  if (normalized === 'full_autonomy') {
    return { text: 'FULL', cls: 'text-accent border-accent', icon: <Shield className="h-4 w-4" /> }
  }
  if (normalized === 'limited_autonomy') {
    return { text: 'LIMITED', cls: 'text-warning border-warning', icon: <Shield className="h-4 w-4" /> }
  }
  if (normalized === 'human_escalation') {
    return { text: 'HUMAN', cls: 'text-destructive border-destructive', icon: <User className="h-4 w-4" /> }
  }
  return { text: 'MONITOR', cls: 'text-foreground/70 border-foreground/20', icon: <Activity className="h-4 w-4" /> }
}

function toPolyline(points: TelemetryPoint[], width: number, height: number): string {
  if (points.length < 2) return ''

  const xs = points.map((p) => p.t)
  const ys = points.map((p) => p.value)

  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)

  const dx = Math.max(1e-6, maxX - minX)
  const dy = Math.max(1e-6, maxY - minY)

  return points
    .map((p) => {
      const x = ((p.t - minX) / dx) * width
      const y = height - ((p.value - minY) / dy) * height
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

const MAX_POINTS = 240

export default function DashboardPage() {
  const [config, setConfig] = useState<FDIRConfig | null>(null)
  const [status, setStatus] = useState<FDIRStatus | null>(null)
  const [snapshot, setSnapshot] = useState<SnapshotMessage | null>(null)
  const [faults, setFaults] = useState<FaultRecord[]>([])
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [series, setSeries] = useState<Record<string, TelemetryPoint[]>>({})
  const [selectedChannel, setSelectedChannel] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [opsMsg, setOpsMsg] = useState<string>('')
  const [opsSending, setOpsSending] = useState<boolean>(false)
  const lastTickRef = useRef<number>(Date.now())

  const channelMap = useMemo(() => {
    const m = new Map<string, FDIRConfig['channels'][number]>()
    for (const ch of config?.channels ?? []) m.set(ch.name, ch)
    return m
  }, [config])

  const healthBySubsystem: Record<string, SubsystemHealth | undefined> = useMemo(() => {
    const by: Record<string, SubsystemHealth | undefined> = {}
    for (const h of snapshot?.health ?? []) by[h.subsystem] = h
    return by
  }, [snapshot])

  const selectedSeries = series[selectedChannel] ?? []
  const nominal = channelMap.get(selectedChannel)
  const poly = useMemo(() => toPolyline(selectedSeries, 520, 180), [selectedSeries])

  const analytics = useMemo(() => {
    const pts = selectedSeries
    if (!pts.length) {
      return {
        last: null as number | null,
        min: null as number | null,
        max: null as number | null,
        avg: null as number | null,
        slope: null as number | null,
      }
    }

    const values = pts.map((p: TelemetryPoint) => p.value)
    const last = values[values.length - 1]
    const min = Math.min(...values)
    const max = Math.max(...values)
    const avg = values.reduce((a: number, b: number) => a + b, 0) / Math.max(1, values.length)

    const k = Math.min(20, pts.length - 1)
    const slope = k > 0 ? (pts[pts.length - 1].value - pts[pts.length - 1 - k].value) / k : 0

    return { last, min, max, avg, slope }
  }, [selectedSeries])

  const problemsAndSolutions = useMemo(() => {
    const active = snapshot?.active_fault
    if (!active) {
      return {
        problems: [] as Array<{ title: string; detail: string }>,
        solutions: [] as Array<{ title: string; detail: string }>,
      }
    }

    const problems = [
      {
        title: `${active.subsystem.toUpperCase()} / ${active.fault_type}`,
        detail: `Severity ${active.severity.toUpperCase()} • Confidence ${(active.confidence * 100).toFixed(0)}% • Component ${active.component}`,
      },
    ]

    const solutions: Array<{ title: string; detail: string }> = []
    if (active.action_taken) {
      solutions.push({
        title: `Recommended/Executed Action: ${active.action_taken}`,
        detail: active.action_rationale || '—',
      })
    } else if (active.escalated || status?.mode === 'hold') {
      solutions.push({
        title: 'Human operator action required',
        detail: 'Review telemetry + ethics justification, then reset the system to resume recovery.',
      })
    } else {
      solutions.push({ title: 'Monitoring', detail: 'No recovery action executed for this fault.' })
    }
    solutions.push({
      title: `Ethical level: ${String(active.ethical_level).toUpperCase()}`,
      detail: active.ethical_justification,
    })

    return { problems, solutions }
  }, [snapshot, status?.mode])

  const refreshFaults = async () => {
    try {
      const res = await fdirApi.getFaults(50)
      setFaults(res.faults ?? [])
    } catch {
      // ignore
    }
  }

  const refreshStatus = async () => {
    try {
      const st = await fdirApi.getStatus()
      setStatus(st)
    } catch {
      // ignore; WS is primary
    }
  }

  useEffect(() => {
    let cancelled = false

    const onInit = (msg: InitMessage) => {
      if (cancelled) return
      setConfig(msg.config)
      setStatus(msg.status)
      setLogs(msg.logs ?? [])
      setSelectedChannel((cur) => cur || msg.config?.channels?.[0]?.name || '')
    }

    const onSnapshot = (msg: SnapshotMessage) => {
      if (cancelled) return
      setSnapshot(msg)

      setStatus((prev) => {
        const next: FDIRStatus = {
          mode: msg.mode,
          mission_phase: msg.mission_phase,
          fault_count: msg.fault_count,
          log_seq: msg.log_seq,
          telemetry: msg.telemetry_state,
          sim: prev?.sim,
        }
        return next
      })

      setLogs(msg.logs ?? [])

      const t = Date.now()
      if (t !== lastTickRef.current) lastTickRef.current = t
      setSeries((prev) => {
        const next: Record<string, TelemetryPoint[]> = { ...prev }
        for (const [ch, v] of Object.entries(msg.telemetry ?? {})) {
          const arr = (next[ch] ?? []).slice()
          arr.push({ t: lastTickRef.current, value: Number(v) })
          if (arr.length > MAX_POINTS) arr.splice(0, arr.length - MAX_POINTS)
          next[ch] = arr
        }
        return next
      })
    }

    const onClose = () => {
      if (cancelled) return
      setError('WebSocket disconnected from backend')
    }

    try {
      fdirApi.connect(onInit, onSnapshot, undefined, onClose)
      setError(null)
    } catch {
      setError('Failed to connect to backend WebSocket')
    }

    refreshStatus()
    refreshFaults()
    const poll = setInterval(() => {
      refreshStatus()
      refreshFaults()
    }, 6000)

    return () => {
      cancelled = true
      clearInterval(poll)
      fdirApi.disconnect()
    }
  }, [])

  const reset = async () => {
    try {
      await fdirApi.resetSystem()
      setError(null)
      setFaults([])
      setLogs([])
      setSeries({})
    } catch (e: any) {
      setError(e?.message || 'Failed to reset')
    }
  }

  const toggleSimulation = async () => {
    try {
      const running = status?.sim?.running ?? true
      if (running) await fdirApi.simStop()
      else await fdirApi.simStart()
      await refreshStatus()
      setError(null)
    } catch (e: any) {
      setError(e?.message || 'Failed to toggle simulation')
    }
  }

  const inject = async (fault: string) => {
    try {
      await fdirApi.injectFault(fault, 1.0, 15.0)
      await refreshStatus()
      setError(null)
    } catch (e: any) {
      setError(e?.message || 'Failed to inject fault')
    }
  }

  const clearInjection = async () => {
    try {
      await fdirApi.clearInjection()
      await refreshStatus()
      setError(null)
    } catch (e: any) {
      setError(e?.message || 'Failed to clear injection')
    }
  }

  const sendOpsMessage = async () => {
    const msg = opsMsg.trim()
    if (!msg) return
    try {
      setOpsSending(true)
      await fdirApi.sendOperatorMessage(msg, 'ops')
      setOpsMsg('')
      setError(null)
    } catch (e: any) {
      setError(e?.message || 'Failed to send operator message')
    } finally {
      setOpsSending(false)
    }
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background text-foreground p-6">
        <div className="max-w-2xl mx-auto mt-16 border border-destructive rounded-lg p-6 bg-secondary">
          <div className="flex items-center gap-3 mb-2">
            <AlertTriangle className="h-6 w-6 text-destructive" />
            <h1 className="text-xl font-semibold">Backend Connection Problem</h1>
          </div>
          <p className="text-foreground/80 mb-4">{error}</p>
          <div className="flex gap-3">
            <button onClick={() => window.location.reload()} className="px-4 py-2 rounded bg-primary text-primary-foreground">
              Retry
            </button>
            <button onClick={reset} className="px-4 py-2 rounded border border-foreground/20">
              Reset Backend State
            </button>
          </div>
          <p className="text-xs text-foreground/60 mt-4">
            Ensure the backend is running via <span className="font-mono">FDIR\start-backend.ps1</span>.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen overflow-hidden bg-background text-foreground p-4 max-[800px]:p-2 [@media(max-height:820px)]:p-2 flex flex-col min-h-0">
      {/* Header */}
      <div className="mb-3 flex items-start justify-between gap-3 shrink-0">
        <div>
          <h1 className="text-2xl [@media(max-height:820px)]:text-xl font-semibold flex items-center gap-2">
            <Activity className="h-7 w-7 [@media(max-height:820px)]:h-6 [@media(max-height:820px)]:w-6 text-primary" />
            Spacecraft FDIR Dashboard
          </h1>
          <p className="text-foreground/70 max-[800px]:hidden">Simulation-first • Deterministic • Ethical autonomy gating</p>
        </div>
        <div className="text-right text-sm [@media(max-height:820px)]:text-xs text-foreground/70">
          <div className="flex items-center justify-end gap-2">
            {status?.mode === 'hold' ? <User className="h-4 w-4 text-destructive" /> : <CheckCircle2 className="h-4 w-4 text-accent" />}
            <span className="font-mono uppercase">MODE: {status?.mode ?? '...'}</span>
          </div>
          <div className="font-mono uppercase">PHASE: {status?.mission_phase ?? '...'}</div>
          <div className="font-mono uppercase text-xs text-foreground/60 mt-1">
            RX: {status?.telemetry?.last_rx_iso ? new Date(status.telemetry.last_rx_iso).toLocaleTimeString() : '—'} • SAMPLES:{' '}
            {status?.telemetry?.total_samples ?? 0}
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-hidden grid grid-rows-[auto_minmax(0,1fr)_minmax(0,1fr)] gap-3 max-[800px]:gap-2 [@media(max-height:820px)]:gap-2">
        {/* Subsystem status */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {['power', 'thermal', 'communication', 'attitude'].map((name) => {
            const h = healthBySubsystem[name]
            const badge = severityBadge(h?.severity)
            return (
              <div key={name} className="rounded-lg border border-foreground/10 bg-secondary p-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm uppercase tracking-wide text-foreground/70">{name}</div>
                  <span className={`text-xs px-2 py-1 rounded border ${badge.cls}`}>{badge.text}</span>
                </div>
                <div className="mt-2 text-sm [@media(max-height:820px)]:text-xs text-foreground/80">{h?.summary ?? 'Awaiting telemetry...'}</div>
                <div className="mt-3 text-xs text-foreground/60 font-mono [@media(max-height:820px)]:hidden">Sensors: {h?.sensors?.length ?? 0}</div>
              </div>
            )
          })}
        </div>

        {/* Row 2: Operator console + analytics + problems/solutions */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 max-[800px]:gap-2 overflow-hidden min-h-0">
          <div className="rounded-lg border border-foreground/10 bg-secondary p-3 max-[800px]:p-2 [@media(max-height:820px)]:p-2 overflow-hidden flex flex-col min-h-0">
            <h2 className="font-semibold mb-3 flex items-center gap-2">
              <User className="h-5 w-5 text-primary" />
              Operator Console
            </h2>

            <div className="grid grid-cols-2 gap-2">
              <button onClick={toggleSimulation} className="px-3 py-2 [@media(max-height:820px)]:py-1.5 rounded border border-foreground/20 hover:border-foreground/30 text-sm [@media(max-height:820px)]:text-xs">
                {status?.sim?.running ?? true ? 'Pause Sim' : 'Resume Sim'}
              </button>
              <button onClick={reset} className="px-3 py-2 [@media(max-height:820px)]:py-1.5 rounded border border-foreground/20 hover:border-foreground/30 text-sm [@media(max-height:820px)]:text-xs">
                Reset
              </button>
              <button
                onClick={clearInjection}
                disabled={!status?.sim?.fault}
                className="px-3 py-2 [@media(max-height:820px)]:py-1.5 rounded border border-foreground/20 hover:border-foreground/30 text-sm [@media(max-height:820px)]:text-xs disabled:opacity-50"
              >
                Clear Fault
              </button>
              <button onClick={() => inject('battery_drain')} className="px-3 py-2 [@media(max-height:820px)]:py-1.5 rounded border border-foreground/20 hover:border-foreground/30 text-sm [@media(max-height:820px)]:text-xs">
                Battery Drain
              </button>
            </div>

            <div className="mt-3 text-xs text-foreground/60">
              Inject (15s):
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  onClick={() => inject('power_regulator_failure')}
                  className="px-2 py-1 rounded border border-foreground/20 hover:border-foreground/30 text-xs"
                >
                  Power
                </button>
                <button
                  onClick={() => inject('thermal_runaway')}
                  className="px-2 py-1 rounded border border-foreground/20 hover:border-foreground/30 text-xs"
                >
                  Thermal
                </button>
                <button
                  onClick={() => inject('overcurrent')}
                  className="px-2 py-1 rounded border border-foreground/20 hover:border-foreground/30 text-xs"
                >
                  Overcurrent
                </button>
              </div>
            </div>

            <div className="mt-3 rounded border border-foreground/10 bg-background p-3 max-[800px]:p-2 [@media(max-height:820px)]:p-2 flex-1 min-h-0 overflow-hidden flex flex-col">
              <div className="text-xs uppercase text-foreground/60">Operator message (recorded to log)</div>
              <textarea
                value={opsMsg}
                onChange={(e) => setOpsMsg(e.target.value)}
                placeholder="Example: Request spacecraft to switch to safe-mode comm, confirm bus voltage telemetry..."
                className="mt-2 w-full flex-1 resize-none bg-background border border-foreground/10 rounded p-2 text-sm [@media(max-height:820px)]:text-xs"
              />
              <div className="mt-2 flex items-center justify-between gap-2">
                <div className="text-xs text-foreground/60 font-mono">Sim: {status?.sim?.running ?? true ? 'RUNNING' : 'PAUSED'}</div>
                <button
                  onClick={sendOpsMessage}
                  disabled={opsSending || !opsMsg.trim()}
                  className="px-3 py-2 [@media(max-height:820px)]:py-1.5 rounded border border-foreground/20 hover:border-foreground/30 text-sm [@media(max-height:820px)]:text-xs disabled:opacity-50"
                >
                  {opsSending ? 'Sending...' : 'Send'}
                </button>
              </div>
            </div>

            {status?.mode === 'hold' && (
              <div className="mt-3 rounded border border-destructive p-3 text-sm">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-destructive" />
                  <span className="font-semibold">HOLD: Human decision required</span>
                </div>
                <div className="text-foreground/70 mt-1">Recovery is suppressed until a reset is performed.</div>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-foreground/10 bg-secondary p-3 max-[800px]:p-2 [@media(max-height:820px)]:p-2 overflow-hidden flex flex-col min-h-0">
            <h2 className="font-semibold mb-3">Data Analytics</h2>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded border border-foreground/10 bg-background p-3">
                <div className="text-xs uppercase text-foreground/60">Selected channel</div>
                <div className="mt-1 font-mono">{selectedChannel || '—'}</div>
                <div className="mt-1 text-xs text-foreground/60">
                  Nominal: {nominal ? `${nominal.nominal_min}..${nominal.nominal_max} ${nominal.unit}` : '—'}
                </div>
              </div>
              <div className="rounded border border-foreground/10 bg-background p-3">
                <div className="text-xs uppercase text-foreground/60">Latest value</div>
                <div className="mt-1 font-mono text-lg">{analytics.last == null ? '—' : analytics.last.toFixed(3)}</div>
                <div className="mt-1 text-xs text-foreground/60">Slope: {analytics.slope == null ? '—' : analytics.slope.toFixed(4)} /sample</div>
              </div>
              <div className="rounded border border-foreground/10 bg-background p-3">
                <div className="text-xs uppercase text-foreground/60">Min / Max (window)</div>
                <div className="mt-1 font-mono">
                  {analytics.min == null ? '—' : analytics.min.toFixed(3)} / {analytics.max == null ? '—' : analytics.max.toFixed(3)}
                </div>
              </div>
              <div className="rounded border border-foreground/10 bg-background p-3">
                <div className="text-xs uppercase text-foreground/60">Avg (window)</div>
                <div className="mt-1 font-mono">{analytics.avg == null ? '—' : analytics.avg.toFixed(3)}</div>
              </div>
            </div>

            <div className="mt-3 flex-1 min-h-0 overflow-hidden rounded border border-foreground/10 bg-background p-2">
              <div className="flex items-center justify-between gap-3 mb-2">
                <div className="text-xs uppercase text-foreground/60">Telemetry</div>
                <select
                  value={selectedChannel}
                  onChange={(e) => setSelectedChannel(e.target.value)}
                  className="bg-background border border-foreground/20 rounded px-2 py-1 text-xs"
                >
                  {(config?.channels ?? []).map((ch) => (
                    <option key={ch.name} value={ch.name}>
                      {ch.name}
                    </option>
                  ))}
                </select>
              </div>
              {selectedSeries.length >= 2 ? (
                <svg viewBox="0 0 520 180" className="w-full h-[150px] [@media(max-height:820px)]:h-[120px] text-primary">
                  <polyline fill="none" stroke="currentColor" strokeWidth="2" points={poly} />
                </svg>
              ) : (
                <div className="h-[150px] [@media(max-height:820px)]:h-[120px] flex items-center justify-center text-foreground/60 text-sm">Waiting for telemetry...</div>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-foreground/10 bg-secondary p-3 max-[800px]:p-2 [@media(max-height:820px)]:p-2 overflow-hidden flex flex-col min-h-0">
            <h2 className="font-semibold mb-3">Problems & Solutions</h2>
            <div className="rounded border border-foreground/10 bg-background p-3">
              <div className="text-xs uppercase text-foreground/60">Problems</div>
              {problemsAndSolutions.problems.length ? (
                <div className="mt-2 space-y-2">
                  {problemsAndSolutions.problems.map((p, i) => (
                    <div key={i} className="text-sm">
                      <div className="font-mono">{p.title}</div>
                      <div className="text-foreground/70 text-xs">{p.detail}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-2 text-sm text-foreground/70">No active problems. System monitoring.</div>
              )}
            </div>
            <div className="mt-3 rounded border border-foreground/10 bg-background p-3 flex-1 min-h-0 overflow-auto">
              <div className="text-xs uppercase text-foreground/60">Solutions</div>
              <div className="mt-2 space-y-2">
                {(problemsAndSolutions.solutions.length
                  ? problemsAndSolutions.solutions
                  : [{ title: 'Nominal', detail: 'No action required.' }]
                ).map((s, i) => (
                  <div key={i} className="text-sm">
                    <div className="font-mono">{s.title}</div>
                    <div className="text-foreground/70 text-xs">{s.detail}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Row 3: Fault history + logs */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 max-[800px]:gap-2 overflow-hidden min-h-0">
          <div className="rounded-lg border border-foreground/10 bg-secondary p-3 max-[800px]:p-2 [@media(max-height:820px)]:p-2 overflow-hidden flex flex-col min-h-0">
            <h2 className="font-semibold mb-3">Recent Faults</h2>
            <div className="flex-1 min-h-0 overflow-auto">
              {faults.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm [@media(max-height:820px)]:text-xs">
                    <thead>
                      <tr className="text-foreground/70 border-b border-foreground/10">
                        <th className="text-left py-2">Time</th>
                        <th className="text-left py-2">Subsystem</th>
                        <th className="text-left py-2">Conf</th>
                        <th className="text-left py-2">Ethics</th>
                        <th className="text-left py-2">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {faults.slice(0, 20).map((f) => {
                        const ab = autonomyBadge(f.ethical_level)
                        return (
                          <tr key={f.fault_id} className="border-b border-foreground/5">
                            <td className="py-2 font-mono text-xs">{new Date(f.timestamp_iso).toLocaleTimeString()}</td>
                            <td className="py-2">{f.subsystem}</td>
                            <td className="py-2 font-mono">{(f.confidence * 100).toFixed(0)}%</td>
                            <td className="py-2">
                              <span className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs ${ab.cls}`}>
                                {ab.icon}
                                {ab.text}
                              </span>
                            </td>
                            <td className="py-2 font-mono text-xs">{f.action_taken ?? '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-sm text-foreground/70">No faults recorded yet.</div>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-foreground/10 bg-secondary p-3 max-[800px]:p-2 [@media(max-height:820px)]:p-2 overflow-hidden flex flex-col min-h-0">
            <h2 className="font-semibold mb-3">Live Log</h2>
            <div className="rounded border border-foreground/10 bg-background flex-1 min-h-0 overflow-auto p-2">
              {logs.length ? (
                <div className="space-y-1">
                  {logs.slice(-200).map((l) => (
                    <div key={l.seq} className="text-xs [@media(max-height:820px)]:text-[11px] font-mono text-foreground/80">
                      <span className="text-foreground/50">{new Date(l.timestamp_iso).toLocaleTimeString()}</span>{' '}
                      <span className="text-foreground/60">[{l.stage}]</span>{' '}
                      <span className="text-foreground/60">{l.level}</span>{' '}
                      <span>{l.message}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-foreground/60 text-sm">Waiting for logs...</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
