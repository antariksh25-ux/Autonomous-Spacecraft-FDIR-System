import type { TelemetryData } from './types'

// Channel definitions with subsystems
const CHANNELS = {
  // Power
  voltage_1: { subsystem: 'Power', nominal: 28.0, std: 0.5 },
  voltage_2: { subsystem: 'Power', nominal: 28.0, std: 0.5 },
  current_1: { subsystem: 'Power', nominal: 5.0, std: 0.3 },
  current_2: { subsystem: 'Power', nominal: 5.0, std: 0.3 },
  
  // Thermal
  temp_1: { subsystem: 'Thermal', nominal: 22.0, std: 1.0 },
  temp_2: { subsystem: 'Thermal', nominal: 20.0, std: 1.2 },
  temp_3: { subsystem: 'Thermal', nominal: 25.0, std: 0.8 },
  temp_4: { subsystem: 'Thermal', nominal: 23.0, std: 0.9 },
  
  // Attitude
  gyro_x: { subsystem: 'Attitude', nominal: 0.0, std: 0.02 },
  gyro_y: { subsystem: 'Attitude', nominal: 0.0, std: 0.02 },
  gyro_z: { subsystem: 'Attitude', nominal: 0.0, std: 0.02 },
  acc_x: { subsystem: 'Attitude', nominal: 0.0, std: 0.01 },
  acc_y: { subsystem: 'Attitude', nominal: 0.0, std: 0.01 },
  acc_z: { subsystem: 'Attitude', nominal: 9.81, std: 0.05 },
  
  // Communication
  signal_strength: { subsystem: 'Communication', nominal: -80.0, std: 2.0 },
  packet_loss: { subsystem: 'Communication', nominal: 0.01, std: 0.005 },
  latency: { subsystem: 'Communication', nominal: 150.0, std: 10.0 },
}

let time = 0

export function generateTelemetry(): TelemetryData {
  time += 1
  const channels: { [key: string]: number } = {}
  
  for (const [name, config] of Object.entries(CHANNELS)) {
    // Add some variation
    let value = config.nominal
    
    // Sinusoidal variation for some channels
    if (name.includes('temp') || name.includes('current')) {
      value += Math.sin(time * 0.05) * config.std * 2
    }
    
    // Add noise
    value += (Math.random() - 0.5) * config.std * 2
    
    channels[name] = value
  }
  
  return {
    timestamp: Date.now(),
    channels
  }
}

export function injectSpike(data: TelemetryData, channels: string[]): TelemetryData {
  const modified = { ...data, channels: { ...data.channels } }
  
  for (const channel of channels) {
    if (channel in CHANNELS) {
      const config = CHANNELS[channel as keyof typeof CHANNELS]
      modified.channels[channel] = config.nominal + config.std * 10
    }
  }
  
  return modified
}

export function injectDrift(data: TelemetryData, channels: string[], driftAmount: number): TelemetryData {
  const modified = { ...data, channels: { ...data.channels } }
  
  for (const channel of channels) {
    if (channel in CHANNELS) {
      const config = CHANNELS[channel as keyof typeof CHANNELS]
      modified.channels[channel] += config.std * 5 * driftAmount
    }
  }
  
  return modified
}

export function injectSubsystemFailure(data: TelemetryData, subsystem: string): TelemetryData {
  const modified = { ...data, channels: { ...data.channels } }
  
  for (const [channel, config] of Object.entries(CHANNELS)) {
    if (config.subsystem === subsystem) {
      modified.channels[channel] = 0
    }
  }
  
  return modified
}

export { CHANNELS }
