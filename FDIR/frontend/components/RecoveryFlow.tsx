'use client'

import { motion } from 'framer-motion'
import { Shield, ArrowRight } from 'lucide-react'
import type { AnomalyDetection } from '@/lib/types'

interface Props {
  anomaly: AnomalyDetection
}

export default function RecoveryFlow({ anomaly }: Props) {
  // Generate recovery actions based on anomaly
  const getRecoveryActions = () => {
    const actions = []
    
    if (anomaly.severity > 0.9) {
      actions.push({
        type: 'safe_mode',
        description: 'CRITICAL: Enter safe mode - all non-essential systems shutdown',
        priority: 1,
        estimatedSuccess: 98
      })
    }
    
    for (const subsystem of anomaly.affectedSubsystems) {
      if (subsystem === 'Power' && anomaly.severity > 0.7) {
        actions.push({
          type: 'switch_redundant',
          description: 'Switch to redundant power supply',
          priority: 1,
          estimatedSuccess: 95
        })
      } else if (subsystem === 'Thermal') {
        actions.push({
          type: 'switch_redundant',
          description: 'Activate backup thermal control system',
          priority: 2,
          estimatedSuccess: 90
        })
      } else if (subsystem === 'Attitude') {
        actions.push({
          type: 'reset',
          description: 'Reinitialize attitude control system',
          priority: 2,
          estimatedSuccess: 88
        })
      } else if (subsystem === 'Communication') {
        actions.push({
          type: 'switch_redundant',
          description: 'Switch to backup transponder',
          priority: 1,
          estimatedSuccess: 92
        })
      }
    }
    
    // Always add ground alert
    actions.push({
      type: 'alert_ground',
      description: 'Alert ground control for manual intervention',
      priority: 5,
      estimatedSuccess: 100
    })
    
    return actions.sort((a, b) => a.priority - b.priority)
  }
  
  const actions = getRecoveryActions()
  
  const getActionColor = (type: string) => {
    switch (type) {
      case 'safe_mode': return 'destructive'
      case 'switch_redundant': return 'primary'
      case 'reset': return 'warning'
      default: return 'accent'
    }
  }
  
  const getActionIcon = (type: string) => {
    switch (type) {
      case 'safe_mode': return '🛡️'
      case 'switch_redundant': return '🔄'
      case 'reset': return '⚡'
      default: return '📡'
    }
  }
  
  return (
    <section className="py-12 bg-secondary/20">
      <div className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center gap-3 mb-8">
            <Shield className="w-8 h-8 text-accent" />
            <h2 className="text-3xl font-bold">Recovery Engine</h2>
          </div>
          
          <div className="p-8 bg-background border border-accent rounded-lg">
            <h3 className="text-xl font-semibold mb-6">Recommended Actions</h3>
            
            <div className="space-y-4">
              {actions.map((action, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.15 }}
                  className={`p-6 bg-${getActionColor(action.type)}/10 border border-${getActionColor(action.type)}/30 rounded-lg hover:border-${getActionColor(action.type)} transition-all cursor-pointer`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="text-2xl">{getActionIcon(action.type)}</span>
                        <div>
                          <span className="text-sm text-foreground/60">Priority {action.priority}</span>
                          <h4 className="text-lg font-semibold">{action.description}</h4>
                        </div>
                      </div>
                      
                      <div className="mt-4">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-sm text-foreground/60">Estimated Success Rate</span>
                          <span className="font-bold">{action.estimatedSuccess}%</span>
                        </div>
                        <div className="h-2 bg-background rounded-full overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${action.estimatedSuccess}%` }}
                            transition={{ delay: i * 0.15 + 0.3, duration: 0.5 }}
                            className={`h-full bg-${getActionColor(action.type)}`}
                          />
                        </div>
                      </div>
                    </div>
                    
                    <ArrowRight className={`w-6 h-6 text-${getActionColor(action.type)} ml-4`} />
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
