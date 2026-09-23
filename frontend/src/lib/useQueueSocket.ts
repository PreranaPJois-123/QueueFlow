import { useEffect, useState } from 'react'
import { WS_BASE } from './api'
import type { QueueState } from '../types'

/**
 * Subscribes to a queue's real-time state over WebSocket.
 * Reconnects with backoff on drop, and always keeps `state` as the
 * latest snapshot the server broadcast (join, call-next, skip, serve,
 * pause/resume/close all push a fresh QueueState).
 */
export function useQueueSocket(queueId: string | null) {
  const [state, setState] = useState<QueueState | null>(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    setState(null)
    setConnected(false)
    if (!queueId) return
    let shouldRun = true
    let retryDelay = 1000
    let socket: WebSocket | null = null
    let retryTimeout: ReturnType<typeof setTimeout> | null = null

    function connect() {
      if (!shouldRun) return
      socket = new WebSocket(`${WS_BASE}/api/queues/${queueId}/ws`)

      socket.onopen = () => {
        if (!shouldRun) return
        setConnected(true)
        retryDelay = 1000
      }
      socket.onmessage = (event) => {
        if (!shouldRun) return
        try {
          const payload = JSON.parse(event.data)
          if (payload.event === 'queue_state') {
            setState(payload.data as QueueState)
          }
        } catch {
          // ignore malformed frames
        }
      }
      socket.onclose = () => {
        if (!shouldRun) return
        setConnected(false)
        if (shouldRun) {
          retryTimeout = setTimeout(connect, retryDelay)
          retryDelay = Math.min(retryDelay * 2, 15000)
        }
      }
      socket.onerror = () => {
        socket?.close()
      }
    }

    connect()

    return () => {
      shouldRun = false
      if (retryTimeout) clearTimeout(retryTimeout)
      socket?.close()
    }
  }, [queueId])

  return { state, connected }
}
