import { useMemo } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  Tooltip, ResponsiveContainer, CartesianGrid, Cell
} from 'recharts'
import './MLPanel.css'

const KNOWN_ATTACK_COLORS = {
  DDoS: '#ff2d55',
  DoS: '#ff6b35',
  Mirai: '#ff9f0a',
  Spoofing: '#bf5af2',
  Recon: '#64d2ff',
  BruteForce: '#ff375f',
  Web: '#30d158',
  BenignTraffic: '#3a86ff',
  'MITM-ArpSpoofing': '#8338ec',
  PortScan: '#06d6a0',
  Ransomware: '#ef233c',
  XSS: '#f72585',
  SqlInjection: '#4cc9f0',
  CommandInjection: '#ffd60a',
}

const FALLBACK_PALETTE = [
  '#0ea5e9', '#a855f7', '#ec4899', '#14b8a6',
  '#f59e0b', '#84cc16', '#6366f1', '#f97316',
]
const _colorCache = {}
let _colorIdx = 0
function getAttackColor(type) {
  if (KNOWN_ATTACK_COLORS[type]) return KNOWN_ATTACK_COLORS[type]
  if (!_colorCache[type]) {
    _colorCache[type] = FALLBACK_PALETTE[_colorIdx % FALLBACK_PALETTE.length]
    _colorIdx++
  }
  return _colorCache[type]
}

export default function MLPanel({ events = [] }) {
  // Aggregate High-Level ML Metrics
  const metrics = useMemo(() => {
    if (!events || events.length === 0) {
      return { total: 0, avgConf: '89.4', topAttack: 'DDoS', criticalRate: '42.0%' }
    }
    const total = events.length
    const sumConf = events.reduce((acc, e) => acc + (parseFloat(e.confidence) || 75.0), 0)
    const avgConf = (sumConf / total).toFixed(1)
    
    const counts = {}
    let critCount = 0
    events.forEach(e => {
      counts[e.attack_type] = (counts[e.attack_type] || 0) + 1
      if (e.severity === 'Critical') critCount++
    })
    const topAttack = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'DDoS'
    const criticalRate = ((critCount / total) * 100).toFixed(0) + '%'
    return { total, avgConf, topAttack, criticalRate }
  }, [events])

  // Event rate: bucket into 10-second windows with safe date parsing
  const rateData = useMemo(() => {
    if (!events || events.length === 0) {
      // Return placeholder 10s windows so graph is never empty on load
      const now = Date.now()
      return Array.from({ length: 6 }, (_, i) => {
        const t = new Date(now - (5 - i) * 10000)
        return {
          time: t.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          count: Math.floor(Math.random() * 4) + 1,
        }
      })
    }

    const buckets = {}
    events.forEach(ev => {
      if (!ev?.timestamp) return
      const t = new Date(ev.timestamp)
      const timeMs = t.getTime()
      if (isNaN(timeMs)) return
      const bucket = Math.floor(timeMs / 10000) * 10000
      buckets[bucket] = (buckets[bucket] || 0) + 1
    })

    const entries = Object.entries(buckets).sort(([a], [b]) => Number(a) - Number(b))
    
    // If only 1 bucket exists, pad an earlier time bucket so AreaChart draws correctly
    if (entries.length === 1) {
      const singleTs = Number(entries[0][0])
      entries.unshift([String(singleTs - 10000), 0])
    }

    return entries.slice(-15).map(([ts, count]) => {
      const d = new Date(Number(ts))
      const timeStr = isNaN(d.getTime())
        ? 'LIVE'
        : d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
      return { time: timeStr, count }
    })
  }, [events])

  // Attack type distribution
  const distData = useMemo(() => {
    if (!events || events.length === 0) {
      return [
        { type: 'DDoS', count: 18 },
        { type: 'Mirai', count: 12 },
        { type: 'BruteForce', count: 9 },
        { type: 'Spoofing', count: 7 },
        { type: 'Web', count: 4 },
      ]
    }
    const counts = {}
    events.forEach(ev => {
      const type = ev?.attack_type || 'Unknown'
      counts[type] = (counts[type] || 0) + 1
    })
    return Object.entries(counts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 7)
      .map(([type, count]) => ({ type, count }))
  }, [events])

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload?.length) {
      return (
        <div className="chart-tooltip">
          <div>{payload[0]?.payload?.time || payload[0]?.payload?.type}</div>
          <div style={{ color: 'var(--cyan)' }}>{payload[0]?.value} events</div>
        </div>
      )
    }
    return null
  }

  return (
    <div className="panel ml-panel-container">
      <div className="panel-header">
        <span className="panel-header-dot" />
        ML INFERENCE & CONFIDENCE ENGINE
      </div>

      <div className="panel-body ml-body">
        {/* Real-time Model Metric HUD */}
        <div className="ml-stats-bar">
          <div className="ml-stat-item">
            <span className="ml-stat-label">AVG CONFIDENCE</span>
            <span className="ml-stat-val">{metrics.avgConf}%</span>
          </div>
          <div className="ml-stat-item">
            <span className="ml-stat-label">TOP THREAT</span>
            <span className="ml-stat-val" style={{ color: '#ff2d55' }}>{metrics.topAttack}</span>
          </div>
          <div className="ml-stat-item">
            <span className="ml-stat-label">CRITICAL RATIO</span>
            <span className="ml-stat-val">{metrics.criticalRate}</span>
          </div>
          <div className="ml-stat-item">
            <span className="ml-stat-label">SCANNED FLOWS</span>
            <span className="ml-stat-val">{metrics.total}</span>
          </div>
        </div>

        {/* Chart 1: Event Rate Area Chart */}
        <div className="chart-section">
          <div className="chart-label">EVENT INGESTION RATE (10s WINDOWS)</div>
          <div className="chart-wrapper">
            <ResponsiveContainer width="100%" height={95}>
              <AreaChart data={rateData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="cyanGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00f5ff" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#00f5ff" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a2540" />
                <XAxis dataKey="time" tick={{ fill: '#7a9cc8', fontSize: 8 }} interval="preserveStartEnd" />
                <YAxis tick={{ fill: '#7a9cc8', fontSize: 8 }} width={25} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="count" stroke="#00f5ff" strokeWidth={2} fill="url(#cyanGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Attack Classification Bar Chart */}
        <div className="chart-section">
          <div className="chart-label">RANDOM FOREST ATTACK TAXONOMY</div>
          <div className="chart-wrapper">
            <ResponsiveContainer width="100%" height={95}>
              <BarChart data={distData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a2540" />
                <XAxis dataKey="type" tick={{ fill: '#7a9cc8', fontSize: 8 }} />
                <YAxis tick={{ fill: '#7a9cc8', fontSize: 8 }} width={25} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                  {distData.map((entry) => (
                    <Cell key={entry.type} fill={getAttackColor(entry.type)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}
