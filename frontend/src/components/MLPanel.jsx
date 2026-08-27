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

export default function MLPanel({ events }) {
  // Event rate: bucket into 10-second windows
  const rateData = useMemo(() => {
    if (events.length === 0) return []
    const buckets = {}
    events.forEach(ev => {
      const t = new Date(ev.timestamp)
      const bucket = Math.floor(t.getTime() / 10000) * 10000
      buckets[bucket] = (buckets[bucket] || 0) + 1
    })
    return Object.entries(buckets)
      .sort(([a], [b]) => Number(a) - Number(b))
      .slice(-20)
      .map(([ts, count]) => ({
        time: new Date(Number(ts)).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        count,
      }))
  }, [events])

  // Attack type distribution — dynamic, works with any label from the ML model
  const distData = useMemo(() => {
    const counts = {}
    events.forEach(ev => { counts[ev.attack_type] = (counts[ev.attack_type] || 0) + 1 })
    return Object.entries(counts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 10)  // show top 10 types max
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
    <div className="panel">
      <div className="panel-header">
        <span className="panel-header-dot" />
        ML CONFIDENCE PANEL
      </div>
      <div className="panel-body ml-body">
        <div className="chart-section">
          <div className="chart-label">EVENT RATE (10s WINDOWS)</div>
          <ResponsiveContainer width="100%" height={100}>
            <AreaChart data={rateData}>
              <defs>
                <linearGradient id="cyanGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00f5ff" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#00f5ff" stopOpacity={0} />
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

        <div className="chart-section">
          <div className="chart-label">ATTACK TYPE DISTRIBUTION</div>
          <ResponsiveContainer width="100%" height={100}>
            <BarChart data={distData}>
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
  )
}
