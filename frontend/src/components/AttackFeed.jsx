import { useRef, useEffect } from 'react'
import './AttackFeed.css'

const SEVERITY_CLASS = {
  Critical: 'badge-critical',
  High: 'badge-high',
  Medium: 'badge-medium',
  Low: 'badge-low',
}

function formatTime(iso) {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', { hour12: false })
}

export default function AttackFeed({ events }) {
  const tbodyRef = useRef(null)

  return (
    <div className="panel feed-panel">
      <div className="panel-header">
        <span className="panel-header-dot" />
        LIVE ATTACK FEED
        <span className="feed-count">{events.length} events</span>
      </div>
      <div className="panel-body feed-body">
        <table className="feed-table">
          <thead>
            <tr>
              <th>TIME</th>
              <th>DEVICE</th>
              <th>ZONE</th>
              <th>ATTACK</th>
              <th>CONF%</th>
              <th>SEVERITY</th>
              <th>✓</th>
            </tr>
          </thead>
          <tbody ref={tbodyRef}>
            {events.map((ev, i) => (
              <tr key={ev.id} className={`feed-row ${i === 0 ? 'animate-slide-in' : ''} ${ev.severity === 'Critical' ? 'row-critical' : ''}`}>
                <td className="td-time">{formatTime(ev.timestamp)}</td>
                <td className="td-device">{ev.device_id}</td>
                <td className="td-zone">{ev.zone}</td>
                <td className={`td-attack attack-${ev.attack_type.toLowerCase()}`}>{ev.attack_type}</td>
                <td className="td-conf">{ev.confidence}%</td>
                <td><span className={`badge ${SEVERITY_CLASS[ev.severity]}`}>{ev.severity}</span></td>
                <td className="td-verify">{ev.verified ? <span className="verified-check">✔</span> : '✗'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
