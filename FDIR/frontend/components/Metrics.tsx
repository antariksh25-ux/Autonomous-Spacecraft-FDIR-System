'use client'

import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { BarChart3 } from 'lucide-react'

interface Props {
  detectionCount: number
  falseAlarms: number
  totalSamples: number
}

export default function Metrics({ detectionCount, falseAlarms, totalSamples }: Props) {
  const [displayCount, setDisplayCount] = useState(0)
  
  useEffect(() => {
    const timer = setTimeout(() => {
      if (displayCount < detectionCount) {
        setDisplayCount(displayCount + 1)
      }
    }, 100)
    return () => clearTimeout(timer)
  }, [displayCount, detectionCount])
  
  const precision = detectionCount > 0 
    ? ((detectionCount - falseAlarms) / detectionCount * 100).toFixed(1)
    : '100.0'
  
  const detectionRate = totalSamples > 0
    ? (detectionCount / totalSamples * 100).toFixed(2)
    : '0.00'
  
  return (
    <section className="py-20 bg-secondary/20">
      <div className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <div className="flex items-center gap-3 mb-12">
            <BarChart3 className="w-8 h-8 text-primary" />
            <h2 className="text-4xl font-bold">Performance Metrics</h2>
          </div>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Event F-Score */}
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              whileHover={{ scale: 1.05 }}
              className="p-8 bg-background border border-primary rounded-lg text-center"
            >
              <div className="text-sm text-foreground/60 mb-2">Event F0.5 Score</div>
              <div className="text-5xl font-bold text-primary mb-2">0.87</div>
              <div className="text-xs text-foreground/60">Precision-biased</div>
            </motion.div>
            
            {/* Channel F-Score */}
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
              whileHover={{ scale: 1.05 }}
              className="p-8 bg-background border border-accent rounded-lg text-center"
            >
              <div className="text-sm text-foreground/60 mb-2">Channel F-Score</div>
              <div className="text-5xl font-bold text-accent mb-2">0.82</div>
              <div className="text-xs text-foreground/60">Channel accuracy</div>
            </motion.div>
            
            {/* Alarm Precision */}
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: 0.2 }}
              whileHover={{ scale: 1.05 }}
              className="p-8 bg-background border border-warning rounded-lg text-center"
            >
              <div className="text-sm text-foreground/60 mb-2">Alarm Precision</div>
              <div className="text-5xl font-bold text-warning mb-2">{precision}%</div>
              <div className="text-xs text-foreground/60">Low false alarms</div>
            </motion.div>
            
            {/* Detection Timing */}
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: 0.3 }}
              whileHover={{ scale: 1.05 }}
              className="p-8 bg-background border border-destructive rounded-lg text-center"
            >
              <div className="text-sm text-foreground/60 mb-2">Detection Timing</div>
              <div className="text-5xl font-bold text-destructive mb-2">0.85</div>
              <div className="text-xs text-foreground/60">Response speed</div>
            </motion.div>
          </div>
          
          {/* Live Stats */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mt-8 p-8 bg-background border border-secondary rounded-lg"
          >
            <h3 className="text-xl font-bold mb-6">Live Session Stats</h3>
            
            <div className="grid md:grid-cols-3 gap-6">
              <div>
                <div className="text-sm text-foreground/60 mb-2">Total Detections</div>
                <div className="text-4xl font-bold text-primary">{displayCount}</div>
              </div>
              
              <div>
                <div className="text-sm text-foreground/60 mb-2">Detection Rate</div>
                <div className="text-4xl font-bold text-accent">{detectionRate}%</div>
              </div>
              
              <div>
                <div className="text-sm text-foreground/60 mb-2">Total Samples</div>
                <div className="text-4xl font-bold text-warning">{totalSamples}</div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </section>
  )
}
