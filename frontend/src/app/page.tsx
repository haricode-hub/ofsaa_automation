'use client'

import { motion } from 'framer-motion'
import { BackgroundMatrix } from '@/components/BackgroundMatrix'
import { InstallationForm } from '@/components/InstallationForm'

export default function HomePage() {
  return (
    <div className="relative min-h-screen bg-bg-primary">
      <BackgroundMatrix />
      
      {/* Single column layout for better responsive behavior */}
      <div className="min-h-screen flex flex-col items-center justify-center p-4 lg:p-8 relative">
        
        {/* Installation Form Panel */}
        <motion.div 
          className="glass-panel rounded-2xl p-6 lg:p-12 w-full max-w-md lg:max-w-lg shadow-panel relative overflow-hidden mb-8"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        >
          {/* Subtle border glow */}
          <div className="absolute inset-0 opacity-10">
            <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-white to-transparent" />
            <div className="absolute bottom-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-white to-transparent" />
            <div className="absolute left-0 top-0 w-px h-full bg-gradient-to-b from-transparent via-white to-transparent" />
            <div className="absolute right-0 top-0 w-px h-full bg-gradient-to-b from-transparent via-white to-transparent" />
          </div>
          
          <div className="relative z-10">
            {/* Header */}
            <motion.div 
              className="text-center mb-8 lg:mb-10"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
            >
              <h1 className="text-5xl lg:text-6xl xl:text-7xl font-black text-text-primary mb-4 tracking-tighter leading-none">
                OFSAA
              </h1>
              <div className="w-20 h-px bg-white mx-auto mb-4" />
              <p className="text-xs lg:text-sm text-text-secondary font-light tracking-[0.25em] uppercase">
                Remote Installation Gateway
                <span className="inline-block w-1.5 h-1.5 bg-success rounded-full ml-3 animate-blink" />
              </p>
            </motion.div>

            {/* Installation Form */}
            <InstallationForm />

            {/* Footer */}
            <motion.div 
              className="flex items-center justify-center gap-2 mt-8 text-xs text-text-muted"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4, delay: 0.8 }}
            >
              <div className="flex items-center gap-1">
                <div className="w-1 h-1 bg-text-muted rounded-full animate-pulse" />
                <div className="w-1 h-1 bg-text-muted rounded-full animate-pulse" style={{ animationDelay: '0.3s' }} />
                <div className="w-1 h-1 bg-text-muted rounded-full animate-pulse" style={{ animationDelay: '0.6s' }} />
              </div>
              <span className="font-mono tracking-wider">SECURE CONNECTION</span>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}