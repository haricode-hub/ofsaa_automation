'use client'

import { useEffect, useRef } from 'react'

export function BackgroundMatrix() {
  const matrixRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!matrixRef.current) return

    const matrix = matrixRef.current
    const cols = Math.floor(window.innerWidth / 40)
    const rows = Math.floor(window.innerHeight / 40)
    
    // Clear existing elements
    matrix.innerHTML = ''
    
    // Create minimal dot pattern
    for (let i = 0; i < cols * rows * 0.05; i++) {
      const dot = document.createElement('div')
      dot.className = 'absolute w-px h-px bg-white opacity-20 animate-pulse-slow'
      dot.style.left = Math.random() * 100 + '%'
      dot.style.top = Math.random() * 100 + '%'
      dot.style.animationDelay = Math.random() * 4 + 's'
      matrix.appendChild(dot)
    }

    // Add some larger accent dots
    for (let i = 0; i < 8; i++) {
      const accent = document.createElement('div')
      accent.className = 'absolute w-0.5 h-0.5 bg-white opacity-40 rounded-full animate-pulse-slow'
      accent.style.left = Math.random() * 100 + '%'
      accent.style.top = Math.random() * 100 + '%'
      accent.style.animationDelay = Math.random() * 6 + 's'
      accent.style.animationDuration = '8s'
      matrix.appendChild(accent)
    }

    const handleResize = () => {
      const newCols = Math.floor(window.innerWidth / 40)
      const newRows = Math.floor(window.innerHeight / 40)
      matrix.innerHTML = ''
      
      for (let i = 0; i < newCols * newRows * 0.05; i++) {
        const dot = document.createElement('div')
        dot.className = 'absolute w-px h-px bg-white opacity-20 animate-pulse-slow'
        dot.style.left = Math.random() * 100 + '%'
        dot.style.top = Math.random() * 100 + '%'
        dot.style.animationDelay = Math.random() * 4 + 's'
        matrix.appendChild(dot)
      }

      for (let i = 0; i < 8; i++) {
        const accent = document.createElement('div')
        accent.className = 'absolute w-0.5 h-0.5 bg-white opacity-40 rounded-full animate-pulse-slow'
        accent.style.left = Math.random() * 100 + '%'
        accent.style.top = Math.random() * 100 + '%'
        accent.style.animationDelay = Math.random() * 6 + 's'
        accent.style.animationDuration = '8s'
        matrix.appendChild(accent)
      }
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <div 
      ref={matrixRef}
      className="fixed top-0 left-0 w-full h-full pointer-events-none z-0"
    />
  )
}