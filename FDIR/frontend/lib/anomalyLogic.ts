import type { TelemetryData, AnomalyDetection } from './types'
import { CHANNELS } from './telemetrySimulator'

export function detectAnomalies(
  history: TelemetryData[],
  current: TelemetryData
): AnomalyDetection {
  if (history.length < 10) {
    return {
      isAnomaly: false,
      timestamp: current.timestamp,
      severity: 0,
      affectedChannels: [],
      affectedSubsystems: [],
      confidence: 0
    }
  }
  
  const affectedChannels: string[] = []
  const channelScores: { [key: string]: number } = {}
  
  // Z-score anomaly detection per channel
  for (const [channel, value] of Object.entries(current.channels)) {
    const historicalValues = history.map(d => d.channels[channel]).filter(v => v !== undefined)
    
    if (historicalValues.length < 5) continue
    
    const mean = historicalValues.reduce((a, b) => a + b, 0) / historicalValues.length
    const variance = historicalValues.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / historicalValues.length
    const std = Math.sqrt(variance)
    
    const zscore = Math.abs((value - mean) / (std + 0.0001))
    
    if (zscore > 3.0) {
      affectedChannels.push(channel)
      channelScores[channel] = Math.min(zscore / 10, 1.0)
    }
  }
  
  if (affectedChannels.length === 0) {
    return {
      isAnomaly: false,
      timestamp: current.timestamp,
      severity: 0,
      affectedChannels: [],
      affectedSubsystems: [],
      confidence: 0
    }
  }
  
  // Identify affected subsystems
  const subsystemsSet = new Set<string>()
  for (const channel of affectedChannels) {
    if (channel in CHANNELS) {
      const config = CHANNELS[channel as keyof typeof CHANNELS]
      subsystemsSet.add(config.subsystem)
    }
  }
  const affectedSubsystems = Array.from(subsystemsSet)
  
  // Calculate overall severity
  const avgScore = Object.values(channelScores).reduce((a, b) => a + b, 0) / affectedChannels.length
  const severity = Math.min(avgScore, 1.0)
  
  // Determine root cause (channel with highest score)
  let rootCause = affectedChannels[0]
  let maxScore = channelScores[rootCause]
  for (const [channel, score] of Object.entries(channelScores)) {
    if (score > maxScore) {
      maxScore = score
      rootCause = channel
    }
  }
  
  // Calculate confidence based on how many channels affected vs subsystem size
  const confidence = Math.min(0.7 + (affectedChannels.length * 0.05), 0.95)
  
  return {
    isAnomaly: true,
    timestamp: current.timestamp,
    severity,
    affectedChannels,
    affectedSubsystems,
    rootCause,
    confidence
  }
}
