import { useState, useEffect, useRef, useCallback } from 'react'
import Header from './components/Header'
import AttackFeed from './components/AttackFeed'
import ThreatMap from './components/ThreatMap'
import MLPanel from './components/MLPanel'
import BlockchainPanel from './components/BlockchainPanel'
import './App.css'

const ATTACK_TYPES = ['DDoS', 'DoS', 'Mirai', 'Spoofing', 'Recon', 'BruteForce', 'Web']
const ZONES = ['Downtown', 'Airport', 'Harbor', 'Industrial', 'Residential', 'University', 'Hospital']
const DEVICES_PER_ZONE = 15

function severityFromConfidence(c) {
  if (c >= 90) return 'Critical'
  if (c >= 75) return 'High'
  if (c >= 55) return 'Medium'
  return 'Low'
}

function generateMockEvent() {
  const zone = ZONES[Math.floor(Math.random() * ZONES.length)]
  const deviceIdx = Math.floor(Math.random() * DEVICES_PER_ZONE) + 1
  const prefix = zone.slice(0, 3).toUpperCase()
  const device_id = `${prefix}-${String(deviceIdx).padStart(3, '0')}`
  const attack_type = ATTACK_TYPES[Math.floor(Math.random() * ATTACK_TYPES.length)]
  const confidence = Math.round(Math.min(99.9, Math.max(20, 72 + (Math.random() - 0.5) * 60)) * 10) / 10
  const severity = severityFromConfidence(confidence)
  return {
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    device_id,
    zone,
    attack_type,
    confidence,
    severity,
    verified: true,
  }
}

let mockBlockCounter = 1
function generateMockBlock(events) {
  const batchNum = mockBlockCounter++
  const hash = Array.from({ length: 64 }, () => '0123456789abcdef'[Math.floor(Math.random() * 16)]).join('')
  const tampered = Math.random() < 0.05
  return {
    batch_num: batchNum,
    hash: tampered ? hash.slice(0, 8) + 'TAMPERED' + hash.slice(16) : hash,
    prev_hash: '0'.repeat(64),
    timestamp: new Date().toISOString(),
    event_count: events.length,
    status: tampered ? 'TAMPERED' : 'VERIFIED',
  }
}

export default function App() {
  const [events, setEvents] = useState([])
  const [blocks, setBlocks] = useState([])
  const [isPaused, setIsPaused] = useState(false)
  const [connected, setConnected] = useState(false)
  const pendingEventsRef = useRef([])
  const blockTimerRef = useRef(null)
  const wsRef = useRef(null)
  const intervalRef = useRef(null)

  const addEvent = useCallback((event) => {
    if (isPaused) return
    setEvents(prev => [event, ...prev].slice(0, 200))
    pendingEventsRef.current.push(event)
  }, [isPaused])

  const sealBlock = useCallback(() => {
    if (pendingEventsRef.current.length === 0) return
    const block = generateMockBlock(pendingEventsRef.current)
    pendingEventsRef.current = []
    setBlocks(prev => [...prev, block].slice(-20))
  }, [])

  useEffect(() => {
    // Try WebSocket first, fall back to mock
    let ws
    try {
      ws = new WebSocket('ws://localhost:8000/ws')
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        startMockInterval()
      }
      ws.onerror = () => {
        ws.close()
        startMockInterval()
      }
      ws.onmessage = (e) => {
        const payload = JSON.parse(e.data)
        if (payload.data) addEvent(payload.data)
        if (payload.block) setBlocks(prev => [...prev, payload.block].slice(-20))
      }
    } catch {
      startMockInterval()
    }

    function startMockInterval() {
      setConnected(false)
      intervalRef.current = setInterval(() => {
        addEvent(generateMockEvent())
      }, 1500 + Math.random() * 500)
    }

    blockTimerRef.current = setInterval(sealBlock, 10000)

    return () => {
      if (wsRef.current) wsRef.current.close()
      if (intervalRef.current) clearInterval(intervalRef.current)
      if (blockTimerRef.current) clearInterval(blockTimerRef.current)
    }
  }, [addEvent, sealBlock])

  // Stats derived from events
  const activeThreats = events.filter(e => e.severity === 'Critical' || e.severity === 'High').length
  const verifiedCount = blocks.filter(b => b.status === 'VERIFIED').length
  const blockchainPct = blocks.length > 0 ? Math.round((verifiedCount / blocks.length) * 100) : 100

  return (
    <div className="app-layout">
      <Header
        deviceCount={105}
        activeThreats={activeThreats}
        blockchainPct={blockchainPct}
        isPaused={isPaused}
        onTogglePause={() => setIsPaused(p => !p)}
        connected={connected}
      />
      <main className="dashboard-grid">
        <AttackFeed events={events} />
        <ThreatMap events={events} />
        <MLPanel events={events} />
        <BlockchainPanel blocks={blocks} />
      </main>
    </div>
  )
}
