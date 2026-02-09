'use client'

import { motion } from 'framer-motion'
import { BackgroundMatrix } from '@/components/BackgroundMatrix'
import { InstallationForm } from '@/components/InstallationForm'

export default function HomePage() {
  return (
    <div className="relative min-h-screen bg-bg-primary">
      <BackgroundMatrix />
      
      {/* Single column layout for better responsive behavior */}
      <div className="min-h-screen flex flex-col items-center justify-start p-4 pt-6 lg:p-8 lg:pt-8 relative">
        
        {/* Installation Form Panel */}
        <motion.div 
          className="glass-panel rounded-2xl p-6 lg:p-10 w-full max-w-md sm:max-w-xl lg:max-w-3xl xl:max-w-5xl shadow-panel relative mb-8"
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
              className="text-center mb-6 lg:mb-8"
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
            <div className="max-h-none lg:max-h-[62vh] overflow-visible lg:overflow-y-auto lg:pr-2 scrollbar-thin scrollbar-track-gray-900 scrollbar-thumb-gray-700">
              <InstallationForm />
            </div>

            {/* Footer */}
            <motion.div 
              className="flex items-center justify-center gap-2 mt-6 text-xs text-text-muted"
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
