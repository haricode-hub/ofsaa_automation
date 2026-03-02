/**
 * Get the backend API URL from environment variables
 * Falls back to localhost if not defined (for development)
 */
export const getApiUrl = (): string => {
  if (typeof window !== 'undefined') {
    // Client-side
    return (
      process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    )
  }
  // Server-side (shouldn't be called there, but just in case)
  return 'http://localhost:8000'
}

/**
 * Get the WebSocket URL from the API URL
 * Converts http/https to ws/wss
 */
export const getWebSocketUrl = (): string => {
  const apiUrl = getApiUrl()
  return apiUrl.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:')
}

export const API_BASE_URL = getApiUrl()

