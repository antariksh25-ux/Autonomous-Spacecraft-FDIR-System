'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { Cpu } from 'lucide-react'

export default function Architecture() {
  const components = [
    { name: 'Telemetry Stream', color: 'primary' },
    { name: 'Preprocessing', color: 'accent' },
    { name: 'Detection', color: 'warning' },
    { name: 'Isolation', color: 'destructive' },
    { name: 'Recovery', color: 'accent' },
  ]
  
  return (
    <section id="architecture" className="py-20 bg-background">
      <div className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <div className="flex items-center gap-3 mb-12">
            <Cpu className="w-8 h-8 text-primary" />
            <h2 className="text-4xl font-bold">System Architecture</h2>
          </div>
          
          {/* Flow Diagram */}
          <div className="flex flex-wrap md:flex-nowrap items-center justify-center gap-4 mb-12">
            {components.map((component, i) => (
              <React.Fragment key={component.name}>
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  whileHover={{ scale: 1.05 }}
                  className={`p-6 bg-${component.color}/10 border-2 border-${component.color} rounded-lg min-w-[150px] text-center`}
                >
                  <div className={`text-lg font-bold text-${component.color}`}>
                    {component.name}
                  </div>
                </motion.div>
                
                {i < components.length - 1 && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.1 + 0.2 }}
                    className="text-primary text-3xl hidden md:block"
                  >
                    →
                  </motion.div>
                )}
              </React.Fragment>
            ))}
          </div>
          
          {/* Key Features */}
          <div className="grid md:grid-cols-3 gap-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.2 }}
              className="p-6 bg-secondary rounded-lg border border-primary/30"
            >
              <h3 className="text-xl font-bold mb-3 text-primary">Fault Detection</h3>
              <ul className="space-y-2 text-foreground/80">
                <li>✓ Multivariate anomaly detection</li>
                <li>✓ Statistical + ML models</li>
                <li>✓ Z-score, EWMA, Isolation Forest</li>
                <li>✓ Real-time processing</li>
              </ul>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.3 }}
              className="p-6 bg-secondary rounded-lg border border-accent/30"
            >
              <h3 className="text-xl font-bold mb-3 text-accent">Fault Isolation</h3>
              <ul className="space-y-2 text-foreground/80">
                <li>✓ Channel-level identification</li>
                <li>✓ Subsystem-level analysis</li>
                <li>✓ Root cause ranking</li>
                <li>✓ Dependency graph modeling</li>
              </ul>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.4 }}
              className="p-6 bg-secondary rounded-lg border border-warning/30"
            >
              <h3 className="text-xl font-bold mb-3 text-warning">Recovery</h3>
              <ul className="space-y-2 text-foreground/80">
                <li>✓ Rule-based actions</li>
                <li>✓ Automated decision engine</li>
                <li>✓ Safe mode trigger</li>
                <li>✓ Redundant system activation</li>
              </ul>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
