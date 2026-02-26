'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { Activity, AlertTriangle, CheckCircle2, Shield, User, Wrench } from 'lucide-react'
import {
  fdirApi,
  type FDIRConfig,
  type FDIRStatus,
  type FaultRecord,
  type LogEntry,
  type SnapshotMessage,
  type SubsystemHealth,
} from '../../lib/api'

type TelemetryPoint = { t: number; value: number }

function severityBadge(sev: string): { text: string; cls: string } {
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

function autonomyBadge(level: string): { text: string; cls: string; icon: React.ReactNode } {
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

export default function FDIRDashboard() {
  const [config, setConfig] = useState<FDIRConfig | null>(null)
  const [status, setStatus] = useState<FDIRStatus | null>(null)
  const [snapshot, setSnapshot] = useState<SnapshotMessage | null>(null)
  const [faults, setFaults] = useState<FaultRecord[]>([])
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [selectedChannel, setSelectedChannel] = useState<string>('')
  const [series, setSeries] = useState<Record<string, TelemetryPoint[]>>({})

  const channelMap = useMemo(() => {
    const map = new Map<string, any>()
    for (const ch of config?.channels ?? []) map.set(ch.name, ch)
    return map
  }, [config])

  const healthBySubsystem = useMemo(() => {
    const out: Record<string, SubsystemHealth> = {}
    for (const h of snapshot?.health ?? []) out[h.subsystem] = h
    return out
  }, [snapshot])

  useEffect(() => {
    let cancelled = false
    let tCounter = 0

    const refreshFaults = async () => {
      try {
        const resp = await fdirApi.getFaults(20)
        if (!cancelled) setFaults(resp.faults || [])
      } catch {
        // ignore - WS provides the primary signal
      }
    }

    fdirApi.connect(
      (init) => {
        if (cancelled) return
        setConfig(init.config)
        setStatus(init.status)
        setLogs(init.logs || [])
        setError(null)

        const firstChannel = init.config?.channels?.[0]?.name
        if (firstChannel) {
          setSelectedChannel((prev) => (prev && init.config.channels.some((c) => c.name === prev) ? prev : firstChannel))
        }
        refreshFaults()
      },
      (msg) => {
        if (cancelled) return
        setSnapshot(msg)
        setStatus((prev) =>
          prev
            ? {
                ...prev,
                mode: msg.mode,
                mission_phase: msg.mission_phase,
                fault_count: msg.fault_count,
                log_seq: msg.log_seq,
                telemetry: msg.telemetry_state ?? prev.telemetry,
              }
            : null
        )

        setSeries((prev) => {
          const next: Record<string, TelemetryPoint[]> = { ...prev }
          tCounter += 1
          for (const [k, v] of Object.entries(msg.telemetry || {})) {
            const arr = next[k] ? [...next[k]] : []
            arr.push({ t: tCounter, value: v })
            next[k] = arr.slice(-180)
          }
          return next
        })

        if (msg.logs?.length) {
          setLogs((prev) => [...prev, ...msg.logs].slice(-400))
        }

        if (msg.active_fault) {
          refreshFaults()
        }
      },
      (e) => {
        if (cancelled) return
        setError('WebSocket error connecting to backend')
        console.error(e)
      },
      () => {
        if (cancelled) return
        setError('WebSocket disconnected from backend')
      }
    )

    const poll = setInterval(refreshFaults, 6000)
    return () => {
      cancelled = true
      clearInterval(poll)
      fdirApi.disconnect()
    }
  }, [])

  const selectedSeries = series[selectedChannel] ?? []
  const nominal = channelMap.get(selectedChannel)
  const poly = useMemo(() => toPolyline(selectedSeries, 520, 180), [selectedSeries])

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

  const refreshStatus = async () => {
    try {
      const st = await fdirApi.getStatus()
      setStatus(st)
    } catch {
      // ignore; WS is primary
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
    <div className="min-h-screen bg-background text-foreground p-6">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold flex items-center gap-3">
            <Activity className="h-8 w-8 text-primary" />
            Spacecraft FDIR Dashboard
          </h1>
          <p className="text-foreground/70">Simulation-first • Deterministic • Ethical autonomy gating</p>
        </div>
        <div className="text-right text-sm text-foreground/70">
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

      {/* Subsystem status */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {['power', 'thermal', 'communication', 'attitude'].map((name) => {
          const h = healthBySubsystem[name]
          const badge = severityBadge(h?.severity)
          return (
            <div key={name} className="rounded-lg border border-foreground/10 bg-secondary p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm uppercase tracking-wide text-foreground/70">{name}</div>
                <span className={`text-xs px-2 py-1 rounded border ${badge.cls}`}>{badge.text}</span>
              </div>
              <div className="mt-2 text-sm text-foreground/80">{h?.summary ?? 'Awaiting telemetry...'}</div>
              <div className="mt-3 text-xs text-foreground/60 font-mono">Sensors: {h?.sensors?.length ?? 0}</div>
            </div>
          )
        })}
      </div>

      {/* Controls */}
      <div className="rounded-lg border border-foreground/10 bg-secondary p-4 mb-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h2 className="font-semibold flex items-center gap-2">
            <Wrench className="h-5 w-5 text-primary" />
            Simulation & Fault Injection
          </h2>
          <div className="flex items-center gap-2">
            <button onClick={toggleSimulation} className="px-3 py-2 rounded border border-foreground/20 hover:border-foreground/30 text-sm">
              {status?.sim?.running ?? true ? 'Stop Simulation' : 'Start Simulation'}
            </button>
            <button onClick={reset} className="px-3 py-2 rounded border border-foreground/20 hover:border-foreground/30 text-sm">
              Reset System
            </button>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded border border-foreground/10 bg-background p-3">
            <div className="text-xs uppercase text-foreground/60">Simulator</div>
            <div className="mt-2 text-sm text-foreground/80">
              Status:{' '}
              <span className="font-mono">{status?.sim?.running ?? true ? 'RUNNING' : 'PAUSED'}</span>
            </div>
            <div className="mt-1 text-xs text-foreground/60">
              Injected:{' '}
              {status?.sim?.fault ? (
                <span className="font-mono">
                  {status.sim.fault.name} ({status.sim.fault.remaining_s.toFixed(1)}s)
                </span>
              ) : (
                <span className="font-mono">None</span>
              )}
            </div>
            <button
              onClick={clearInjection}
              disabled={!status?.sim?.fault}
              className="mt-3 px-3 py-2 rounded border border-foreground/20 hover:border-foreground/30 text-sm disabled:opacity-50"
            >
              Clear Injected Fault
            </button>
          </div>
          <div className="rounded border border-foreground/10 bg-background p-3">
            <div className="text-xs uppercase text-foreground/60">Inject fault (15s)</div>
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                onClick={() => inject('power_regulator_failure')}
                className="px-3 py-2 rounded border border-foreground/20 hover:border-foreground/30 text-sm"
              >
                Power Regulator
              </button>
              <button onClick={() => inject('thermal_runaway')} className="px-3 py-2 rounded border border-foreground/20 hover:border-foreground/30 text-sm">
                Thermal Runaway
              </button>
              <button
                onClick={() => inject('communication_dropout')}
                className="px-3 py-2 rounded border border-foreground/20 hover:border-foreground/30 text-sm"
              >
                Comm Dropout
              </button>
              <button onClick={() => inject('attitude_drift')} className="px-3 py-2 rounded border border-foreground/20 hover:border-foreground/30 text-sm">
                Attitude Drift
              </button>
            </div>
          </div>
        </div>
        {status?.mode === 'hold' && (
          <div className="mt-4 rounded border border-destructive p-3 text-sm">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-destructive" />
              <span className="font-semibold">Awaiting Human Decision (HOLD)</span>
            </div>
            <div className="text-foreground/70 mt-1">Recovery is suppressed until a reset is performed.</div>
          </div>
        )}
      </div>

      {/* Telemetry + decision */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="rounded-lg border border-foreground/10 bg-secondary p-4">
          <div className="flex items-center justify-between gap-3 mb-2">
            <h2 className="font-semibold">Telemetry</h2>
            <select
              value={selectedChannel}
              onChange={(e) => setSelectedChannel(e.target.value)}
              className="bg-background border border-foreground/20 rounded px-2 py-1 text-sm"
            >
              {(config?.channels ?? []).map((ch) => (
                <option key={ch.name} value={ch.name}>
                  {ch.name}
                </option>
              ))}
            </select>
          </div>
          <div className="text-xs text-foreground/70 font-mono mb-3">
            {nominal
              ? `Nominal: ${nominal.nominal_min}..${nominal.nominal_max} ${nominal.unit} • Subsystem: ${nominal.subsystem}`
              : 'Loading channel config...'}
          </div>
          <div className="rounded border border-foreground/10 bg-background p-2">
            {selectedSeries.length >= 2 ? (
              <svg viewBox="0 0 520 180" className="w-full h-[200px] text-primary">
                <polyline fill="none" stroke="currentColor" strokeWidth="2" points={poly} />
              </svg>
            ) : (
              <div className="h-[200px] flex items-center justify-center text-foreground/60">Waiting for telemetry...</div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-foreground/10 bg-secondary p-4">
          <h2 className="font-semibold mb-3 flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            Ethical Autonomy Decision
          </h2>

          {snapshot?.active_fault ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded border border-foreground/10 bg-background p-3">
                  <div className="text-xs uppercase text-foreground/60">Active fault</div>
                  <div className="mt-1 font-mono text-sm">{snapshot.active_fault.fault_id}</div>
                  <div className="mt-1 text-sm">
                    {snapshot.active_fault.subsystem} • {snapshot.active_fault.component}
                  </div>
                  <div className="mt-1 text-sm text-foreground/70">{snapshot.active_fault.fault_type}</div>
                </div>
                <div className="rounded border border-foreground/10 bg-background p-3">
                  <div className="text-xs uppercase text-foreground/60">Confidence</div>
                  <div className="mt-1 font-mono text-2xl">{(snapshot.active_fault.confidence * 100).toFixed(1)}%</div>
                  <div className="mt-2 flex items-center gap-2">
                    {(() => {
                      const b = autonomyBadge(snapshot.active_fault.ethical_level)
                      return (
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs ${b.cls}`}>
                          {b.icon}
                          {b.text}
                        </span>
                      )
                    })()}
                    <span className={`px-2 py-1 rounded border text-xs ${severityBadge(snapshot.active_fault.severity).cls}`}>
                      {severityBadge(snapshot.active_fault.severity).text}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-4 rounded border border-foreground/10 bg-background p-3">
                <div className="text-xs uppercase text-foreground/60">Justification</div>
                <div className="mt-1 text-sm text-foreground/80">{snapshot.active_fault.ethical_justification}</div>
              </div>

              <div className="mt-4 rounded border border-foreground/10 bg-background p-3">
                <div className="flex items-center gap-2">
                  <Wrench className="h-4 w-4 text-primary" />
                  <div className="text-xs uppercase text-foreground/60">Recovery</div>
                </div>
                <div className="mt-2 text-sm">
                  {snapshot.active_fault.action_taken ? (
                    <span className="font-mono">ACTION: {snapshot.active_fault.action_taken}</span>
                  ) : (
                    <span className="text-foreground/70">No recovery action executed.</span>
                  )}
                </div>
                {snapshot.active_fault.action_rationale && (
                  <div className="mt-1 text-sm text-foreground/70">{snapshot.active_fault.action_rationale}</div>
                )}
              </div>
            </>
          ) : (
            <div className="rounded border border-foreground/10 bg-background p-4 text-foreground/70">
              No active confirmed faults. The system is monitoring telemetry.
            </div>
          )}
        </div>
      </div>

      {/* Fault history + logs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-lg border border-foreground/10 bg-secondary p-4">
          <h2 className="font-semibold mb-3">Recent Faults</h2>
          {faults.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
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
                  {faults.slice(0, 12).map((f) => {
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

        <div className="rounded-lg border border-foreground/10 bg-secondary p-4">
          <h2 className="font-semibold mb-3">Live Log</h2>
          <div className="rounded border border-foreground/10 bg-background h-[360px] overflow-auto p-2">
            {logs.length ? (
              <div className="space-y-1">
                {logs.slice(-120).map((l) => (
                  <div key={l.seq} className="text-xs font-mono text-foreground/80">
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
  )
}
