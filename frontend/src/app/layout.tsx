import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'OFSAA Installation Portal',
  description: 'Remote Installation Gateway for Oracle Financial Services',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  )
}