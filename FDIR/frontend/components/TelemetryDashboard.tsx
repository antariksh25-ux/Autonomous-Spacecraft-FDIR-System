'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { TelemetryData, AnomalyDetection } from '@/lib/types'
import { Activity } from 'lucide-react'

interface Props {
  data: TelemetryData
  history: TelemetryData[]
  anomaly: AnomalyDetection | null
}

export default function TelemetryDashboard({ data, history, anomaly }: Props) {
  // Prepare chart data
  const chartData = history.slice(-30).map((d, i) => ({
    time: i,
    temp_1: d.channels.temp_1,
    temp_2: d.channels.temp_2,
    voltage_1: d.channels.voltage_1,
    current_1: d.channels.current_1,
    gyro_x: d.channels.gyro_x * 10 + 50, // Scale for visibility
    signal_strength: d.channels.signal_strength + 100, // Shift for visibility
  }))

  const getChannelStatus = (channel: string, value: number) => {
    if (anomaly?.affectedChannels.includes(channel)) {
      return 'text-destructive glow-red'
    }
    return 'text-accent glow-green'
  }

  return (
    <section id="telemetry" className="py-20 bg-secondary/20">
      <div className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <div className="flex items-center gap-3 mb-8">
            <Activity className="w-8 h-8 text-primary" />
            <h2 className="text-4xl font-bold">Live Telemetry Dashboard</h2>
          </div>
          
          {anomaly && (
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="mb-6 p-4 bg-destructive/20 border border-destructive rounded-lg"
            >
              <p className="text-destructive font-bold text-lg">
                ⚠️ ANOMALY DETECTED - Severity: {(anomaly.severity * 100).toFixed(0)}%
              </p>
            </motion.div>
          )}
          
          {/* Channel Values Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
            {Object.entries(data.channels).map(([channel, value]) => (
              <motion.div
                key={channel}
                whileHover={{ scale: 1.05 }}
                className={`p-4 bg-background border rounded-lg ${getChannelStatus(channel, value)}`}
              >
                <div className="text-sm text-foreground/60 mb-1">{channel}</div>
                <div className="text-2xl font-bold font-mono">
                  {value.toFixed(2)}
                </div>
              </motion.div>
            ))}
          </div>
          
          {/* Charts */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Thermal Chart */}
            <div className="p-6 bg-background border border-secondary rounded-lg">
              <h3 className="text-xl font-semibold mb-4">Thermal Subsystem</h3>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="time" stroke="#9CA3AF" />
                  <YAxis stroke="#9CA3AF" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="temp_1" stroke="#EF4444" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="temp_2" stroke="#F59E0B" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            
            {/* Power Chart */}
            <div className="p-6 bg-background border border-secondary rounded-lg">
              <h3 className="text-xl font-semibold mb-4">Power Subsystem</h3>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="time" stroke="#9CA3AF" />
                  <YAxis stroke="#9CA3AF" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="voltage_1" stroke="#3B82F6" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="current_1" stroke="#10B981" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
