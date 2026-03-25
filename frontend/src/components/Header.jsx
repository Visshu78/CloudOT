import './Header.css'

export default function Header({ deviceCount, activeThreats, blockchainPct, isPaused, onTogglePause, connected }) {
  return (
    <header className="header">
      <div className="header-brand">
        <span className="header-logo">⬡</span>
        <span className="header-title">CITYSHIELD</span>
        <span className="header-subtitle">IoT Threat Intelligence</span>
      </div>

      <div className="header-stats">
        <Stat label="DEVICES" value={deviceCount} color="cyan" />
        <Stat label="ACTIVE THREATS" value={activeThreats} color="red" blink={activeThreats > 0} />
        <Stat label="CHAIN INTEGRITY" value={`${blockchainPct}%`} color={blockchainPct >= 90 ? 'green' : 'orange'} />
      </div>

      <div className="header-controls">
        <button className="pause-btn" onClick={onTogglePause}>
          {isPaused ? '▶ RESUME' : '⏸ PAUSE'}
        </button>
        <div className={`live-indicator ${isPaused ? 'paused' : ''}`}>
          <span className="live-dot" />
          {isPaused ? 'PAUSED' : connected ? 'LIVE' : 'MOCK'}
        </div>
      </div>
    </header>
  )
}

function Stat({ label, value, color, blink }) {
  return (
    <div className={`stat-item stat-${color} ${blink ? 'animate-pulse-red' : ''}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}
