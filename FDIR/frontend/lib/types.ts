export interface TelemetryData {
  timestamp: number
  channels: {
    [key: string]: number
  }
}

export interface AnomalyDetection {
  isAnomaly: boolean
  timestamp: number
  severity: number
  affectedChannels: string[]
  affectedSubsystems: string[]
  rootCause?: string
  confidence: number
}

export interface RecoveryAction {
  id: string
  type: 'safe_mode' | 'switch_redundant' | 'reset' | 'alert_ground'
  description: string
  priority: number
  estimatedSuccess: number
}
