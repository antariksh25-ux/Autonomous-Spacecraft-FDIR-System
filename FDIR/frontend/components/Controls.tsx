'use client'

import { motion } from 'framer-motion'
import { Play, Pause, Zap, TrendingDown, AlertCircle, RotateCcw } from 'lucide-react'

interface Props {
  isRunning: boolean
  onToggleRunning: () => void
  onInjectSpike: () => void
  onInjectDrift: () => void
  onInjectSubsystemFailure: () => void
  onReset: () => void
}

export default function Controls({
  isRunning,
  onToggleRunning,
  onInjectSpike,
  onInjectDrift,
  onInjectSubsystemFailure,
  onReset
}: Props) {
  return (
    <section className="py-12 bg-background sticky bottom-0 border-t-2 border-primary/30 backdrop-blur-sm bg-background/90">
      <div className="container mx-auto px-4">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          {/* System Control */}
          <div className="flex items-center gap-4">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={onToggleRunning}
              className={`p-4 rounded-lg font-semibold flex items-center gap-2 ${
                isRunning 
                  ? 'bg-warning text-warning-foreground glow-yellow' 
                  : 'bg-accent text-accent-foreground glow-green'
              }`}
            >
              {isRunning ? (
                <>
                  <Pause className="w-5 h-5" />
                  Pause
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  Resume
                </>
              )}
            </motion.button>
            
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={onReset}
              className="p-4 bg-secondary text-secondary-foreground rounded-lg font-semibold flex items-center gap-2 border border-primary/30"
            >
              <RotateCcw className="w-5 h-5" />
              Reset
            </motion.button>
          </div>
          
          {/* Anomaly Injection */}
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-semibold text-foreground/60 mr-2">Inject Anomaly:</span>
            
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={onInjectSpike}
              className="px-4 py-2 bg-destructive/20 border border-destructive text-destructive rounded-lg font-semibold flex items-center gap-2 text-sm"
            >
              <Zap className="w-4 h-4" />
              Spike
            </motion.button>
            
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={onInjectDrift}
              className="px-4 py-2 bg-warning/20 border border-warning text-warning rounded-lg font-semibold flex items-center gap-2 text-sm"
            >
              <TrendingDown className="w-4 h-4" />
              Drift
            </motion.button>
            
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={onInjectSubsystemFailure}
              className="px-4 py-2 bg-primary/20 border border-primary text-primary rounded-lg font-semibold flex items-center gap-2 text-sm"
            >
              <AlertCircle className="w-4 h-4" />
              Subsystem Failure
            </motion.button>
          </div>
        </div>
        
        {/* Terminal-style Log */}
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-4 p-4 bg-black/80 rounded-lg font-mono text-sm text-green-400 max-h-32 overflow-y-auto"
        >
          <div className="whitespace-pre-line">
            {`[FDIR] System initialized
[FDIR] Telemetry stream: ${isRunning ? 'ACTIVE' : 'PAUSED'}
[FDIR] Detection engine: READY
[FDIR] Recovery engine: STANDBY`}
          </div>
        </motion.div>
      </div>
    </section>
  )
}
