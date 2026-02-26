'use client'

import { motion } from 'framer-motion'
import { AlertTriangle, Target, Layers } from 'lucide-react'
import type { AnomalyDetection } from '@/lib/types'

interface Props {
  anomaly: AnomalyDetection
}

export default function FaultPanel({ anomaly }: Props) {
  return (
    <section className="py-12 bg-background">
      <div className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="p-8 bg-destructive/10 border-2 border-destructive rounded-lg glow-red"
        >
          <div className="flex items-center gap-3 mb-6">
            <AlertTriangle className="w-8 h-8 text-destructive" />
            <h2 className="text-3xl font-bold text-destructive">Fault Isolation</h2>
          </div>
          
          <div className="grid md:grid-cols-3 gap-6">
            {/* Affected Channels */}
            <div className="p-6 bg-background rounded-lg">
              <div className="flex items-center gap-2 mb-4">
                <Target className="w-6 h-6 text-primary" />
                <h3 className="text-xl font-semibold">Affected Channels</h3>
              </div>
              <ul className="space-y-2">
                {anomaly.affectedChannels.map((channel, i) => (
                  <motion.li
                    key={channel}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className="flex items-center gap-2 p-2 bg-destructive/20 rounded"
                  >
                    <div className="w-2 h-2 bg-destructive rounded-full animate-pulse" />
                    <span className="font-mono">{channel}</span>
                  </motion.li>
                ))}
              </ul>
            </div>
            
            {/* Affected Subsystems */}
            <div className="p-6 bg-background rounded-lg">
              <div className="flex items-center gap-2 mb-4">
                <Layers className="w-6 h-6 text-warning" />
                <h3 className="text-xl font-semibold">Affected Subsystems</h3>
              </div>
              <ul className="space-y-2">
                {anomaly.affectedSubsystems.map((subsystem, i) => (
                  <motion.li
                    key={subsystem}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className="flex items-center gap-2 p-2 bg-warning/20 rounded"
                  >
                    <div className="w-2 h-2 bg-warning rounded-full" />
                    <span className="font-semibold">{subsystem}</span>
                  </motion.li>
                ))}
              </ul>
            </div>
            
            {/* Root Cause */}
            <div className="p-6 bg-background rounded-lg">
              <h3 className="text-xl font-semibold mb-4">Root Cause Analysis</h3>
              <div className="space-y-4">
                {anomaly.rootCause && (
                  <div className="p-4 bg-accent/20 rounded-lg">
                    <div className="text-sm text-foreground/60 mb-1">Primary Cause</div>
                    <div className="text-2xl font-bold text-accent font-mono">
                      {anomaly.rootCause}
                    </div>
                  </div>
                )}
                
                <div className="p-4 bg-secondary rounded-lg">
                  <div className="text-sm text-foreground/60 mb-1">Isolation Confidence</div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-background rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${anomaly.confidence * 100}%` }}
                        className="h-full bg-primary"
                      />
                    </div>
                    <span className="font-bold">{(anomaly.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
                
                <div className="p-4 bg-secondary rounded-lg">
                  <div className="text-sm text-foreground/60 mb-1">Severity Level</div>
                  <div className="text-2xl font-bold text-destructive">
                    {anomaly.severity > 0.7 ? 'CRITICAL' : 
                     anomaly.severity > 0.4 ? 'HIGH' : 'MEDIUM'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
