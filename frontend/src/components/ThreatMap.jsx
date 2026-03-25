import { useState, useMemo } from 'react'
import './ThreatMap.css'

const ZONE_LAYOUT = [
  { name: 'Downtown',    x: 10,  y: 10,  w: 120, h: 80 },
  { name: 'Airport',     x: 150, y: 10,  w: 140, h: 80 },
  { name: 'Harbor',      x: 310, y: 10,  w: 110, h: 80 },
  { name: 'Industrial',  x: 10,  y: 110, w: 130, h: 80 },
  { name: 'Residential', x: 160, y: 110, w: 120, h: 80 },
  { name: 'University',  x: 300, y: 110, w: 120, h: 80 },
  { name: 'Hospital',    x: 85,  y: 210, w: 260, h: 70 },
]

const SEVERITY_COLOR = {
  Critical: '#ff2d55',
  High: '#ff6b35',
  Medium: '#ffd60a',
  Low: '#00f5ff',
  None: '#1a2540',
}

function getZoneSeverity(zoneName, events) {
  const zoneEvents = events.filter(e => e.zone === zoneName).slice(0, 20)
  if (zoneEvents.length === 0) return 'None'
  const counts = { Critical: 0, High: 0, Medium: 0, Low: 0 }
  zoneEvents.forEach(e => counts[e.severity]++)
  if (counts.Critical > 0) return 'Critical'
  if (counts.High > 0) return 'High'
  if (counts.Medium > 0) return 'Medium'
  return 'Low'
}

export default function ThreatMap({ events }) {
  const [selectedZone, setSelectedZone] = useState(null)

  const zoneSeverities = useMemo(() => {
    const map = {}
    ZONE_LAYOUT.forEach(z => { map[z.name] = getZoneSeverity(z.name, events) })
    return map
  }, [events])

  const selectedEvents = useMemo(() => {
    if (!selectedZone) return []
    return events.filter(e => e.zone === selectedZone).slice(0, 5)
  }, [selectedZone, events])

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-header-dot" />
        THREAT MAP — 7 CITY ZONES
      </div>
      <div className="panel-body map-body">
        <svg viewBox="0 0 440 300" className="city-map">
          {ZONE_LAYOUT.map(zone => {
            const severity = zoneSeverities[zone.name]
            const color = SEVERITY_COLOR[severity]
            const isCritical = severity === 'Critical'
            return (
              <g key={zone.name} onClick={() => setSelectedZone(zone.name === selectedZone ? null : zone.name)}
                style={{ cursor: 'pointer' }}>
                <rect
                  x={zone.x} y={zone.y} width={zone.w} height={zone.h}
                  rx="4"
                  fill={`${color}18`}
                  stroke={color}
                  strokeWidth={selectedZone === zone.name ? 2 : 1}
                  className={isCritical ? 'zone-critical' : ''}
                />
                <text
                  x={zone.x + zone.w / 2}
                  y={zone.y + zone.h / 2 - 6}
                  textAnchor="middle"
                  fill={color}
                  fontSize="10"
                  fontFamily="'Orbitron', monospace"
                  fontWeight="700"
                  letterSpacing="1"
                >
                  {zone.name.toUpperCase()}
                </text>
                <text
                  x={zone.x + zone.w / 2}
                  y={zone.y + zone.h / 2 + 12}
                  textAnchor="middle"
                  fill={`${color}aa`}
                  fontSize="8"
                  fontFamily="'IBM Plex Mono', monospace"
                >
                  {severity}
                </text>
                {isCritical && (
                  <circle
                    cx={zone.x + zone.w - 10}
                    cy={zone.y + 10}
                    r="4"
                    fill={color}
                    className="pulse-dot"
                  />
                )}
              </g>
            )
          })}
        </svg>

        {selectedZone && (
          <div className="zone-detail">
            <div className="zone-detail-title">↳ {selectedZone} — Recent Events</div>
            {selectedEvents.length === 0
              ? <div className="zone-no-events">No events recorded</div>
              : selectedEvents.map(ev => (
                <div key={ev.id} className="zone-event-row">
                  <span className="ze-type">{ev.attack_type}</span>
                  <span className={`badge badge-${ev.severity.toLowerCase()}`}>{ev.severity}</span>
                  <span className="ze-conf">{ev.confidence}%</span>
                  <span className="ze-device">{ev.device_id}</span>
                </div>
              ))
            }
          </div>
        )}
      </div>
    </div>
  )
}
