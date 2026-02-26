/**
 * FDIR API Client
 * Ingestion-first backend (FastAPI) via REST + WebSocket.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export type Severity = 'green' | 'yellow' | 'red'
export type SystemMode = 'run' | 'hold'

export interface ChannelConfig {
  name: string
  unit: string
  nominal_min: number
  nominal_max: number
  subsystem: string
  risk: string
}

export interface FDIRConfig {
  sample_rate_hz: number
  mission_phase: string
  channels: ChannelConfig[]
}

export interface FDIRStatus {
  mode: SystemMode
  mission_phase: string
  fault_count: number
  log_seq: number
  telemetry?: {
    last_rx_iso?: string | null
    total_samples?: number
  }
  sim?: {
    running: boolean
    fault: null | {
      name: string
      magnitude: number
      remaining_s: number
    }
  }
}

export interface LogEntry {
  seq: number
  timestamp_iso: string
  level: string
  stage: string
  message: string
  details: Record<string, any>
}

export interface SubsystemHealth {
  subsystem: string
  severity: Severity
  summary: string
  sensors: Array<{
    channel: string
    value: number
    nominal_min: number
    nominal_max: number
    within_nominal: boolean
    deviation: number
  }>
}

export interface FaultRecord {
  fault_id: string
  timestamp_iso: string
  subsystem: string
  component: string
  fault_type: string
  severity: Severity
  confidence: number
  ethical_level: string
  ethical_justification: string
  action_taken?: string | null
  action_rationale?: string | null
  escalated: boolean
}

export interface TelemetrySample {
  timestamp_iso: string
  values: Record<string, number>
}

export interface SnapshotMessage {
  type: 'snapshot'
  timestamp: string
  mode: SystemMode
  mission_phase: string
  telemetry: Record<string, number>
  health: SubsystemHealth[]
  active_fault: FaultRecord | null
  recovery_action: any | null
  fault_count: number
  log_seq: number
  logs: LogEntry[]
  telemetry_state?: {
    last_rx_iso?: string | null
    total_samples?: number
  }
}

export interface InitMessage {
  type: 'init'
  config: FDIRConfig
  status: FDIRStatus
  logs: LogEntry[]
  sim?: FDIRStatus['sim']
}

class FDIRApiClient {
  private baseUrl: string;
  private ws: WebSocket | null = null;
  private pingTimer: any = null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  async getConfig(): Promise<FDIRConfig> {
    const response = await fetch(`${this.baseUrl}/api/config`)
    if (!response.ok) throw new Error('Failed to get config')
    return response.json()
  }

  async getStatus(): Promise<FDIRStatus> {
    const response = await fetch(`${this.baseUrl}/api/status`)
    if (!response.ok) throw new Error('Failed to get status')
    return response.json()
  }

  async getFaults(limit: number = 50): Promise<{ faults: FaultRecord[] }> {
    const response = await fetch(`${this.baseUrl}/api/faults?limit=${limit}`)
    if (!response.ok) throw new Error('Failed to get faults')
    return response.json()
  }

  async resetSystem(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/control/reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    if (!response.ok) throw new Error('Failed to reset system')
    return response.json()
  }

  async sendOperatorMessage(message: string, channel: string = 'ops'): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/control/operator/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, channel }),
    })
    if (!response.ok) throw new Error('Failed to send operator message')
    return response.json()
  }

  async simStart(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/control/sim/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    if (!response.ok) throw new Error('Failed to start simulation')
    return response.json()
  }

  async simStop(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/control/sim/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    if (!response.ok) throw new Error('Failed to stop simulation')
    return response.json()
  }

  async injectFault(fault: string, magnitude: number = 1.0, duration_s: number = 12.0): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/control/inject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fault, magnitude, duration_s }),
    })
    if (!response.ok) throw new Error('Failed to inject fault')
    return response.json()
  }

  async clearInjection(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/control/inject/clear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    if (!response.ok) throw new Error('Failed to clear injection')
    return response.json()
  }

  async ingestTelemetry(sample: TelemetrySample): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/telemetry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sample),
    })
    if (!response.ok) throw new Error('Failed to ingest telemetry')
    return response.json()
  }

  async ingestBatch(samples: TelemetrySample[]): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/telemetry/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ samples }),
    })
    if (!response.ok) throw new Error('Failed to ingest telemetry batch')
    return response.json()
  }

  // ════════════════════════════════════════════════════════════
  // Real-time Streaming (WebSocket)
  // ════════════════════════════════════════════════════════════

  connect(
    onInit: (msg: InitMessage) => void,
    onSnapshot: (msg: SnapshotMessage) => void,
    onError?: (error: Event) => void,
    onClose?: (event: CloseEvent) => void
  ): void {
    const wsUrl = this.baseUrl.replace('http', 'ws')
    this.ws = new WebSocket(`${wsUrl}/ws`)

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data?.type === 'init') onInit(data)
        if (data?.type === 'snapshot') onSnapshot(data)
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }

    this.ws.onerror = (error) => {
      if (onError) onError(error)
    }

    this.ws.onclose = (event) => {
      if (this.pingTimer) {
        clearInterval(this.pingTimer)
        this.pingTimer = null
      }
      if (onClose) onClose(event)
    }

    this.ws.onopen = () => {
      // Starlette endpoint reads client text to keep the socket alive.
      this.pingTimer = setInterval(() => {
        try {
          this.ws?.send('ping')
        } catch {
          // ignore
        }
      }, 8000)
    }
  }

  disconnect(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}

// Export singleton instance
export const fdirApi = new FDIRApiClient();
