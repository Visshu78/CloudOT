import './BlockchainPanel.css'

function truncateHash(hash) {
  if (!hash) return '—'
  return hash.slice(0, 8) + '...' + hash.slice(-6)
}

function formatTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('en-US', { hour12: false })
}

export default function BlockchainPanel({ blocks }) {
  const displayBlocks = blocks.slice(-6)

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-header-dot" />
        BLOCKCHAIN INTEGRITY
        <span className="chain-count">{blocks.length} blocks sealed</span>
      </div>
      <div className="panel-body chain-body">
        {displayBlocks.length === 0 ? (
          <div className="chain-empty">Waiting for first block seal (~10s)...</div>
        ) : (
          <div className="chain-container">
            {displayBlocks.map((block, i) => (
              <div key={block.batch_num} className="chain-item-wrapper">
                <div className={`chain-block ${block.status === 'TAMPERED' ? 'block-tampered' : 'block-verified'} ${i === displayBlocks.length - 1 ? 'animate-slide-in' : ''}`}>
                  <div className="block-num">#{block.batch_num}</div>
                  <div className="block-hash">{truncateHash(block.hash)}</div>
                  <div className="block-meta">
                    <span>{block.event_count} events</span>
                    <span>{formatTime(block.timestamp)}</span>
                  </div>
                  <div className={`block-status ${block.status === 'VERIFIED' ? 'status-ok' : 'status-bad'}`}>
                    {block.status === 'VERIFIED' ? '✔ VERIFIED' : '✗ TAMPERED'}
                  </div>
                </div>
                {i < displayBlocks.length - 1 && (
                  <div className={`chain-link ${displayBlocks[i + 1]?.status === 'TAMPERED' ? 'link-broken' : ''}`}>
                    ——
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="chain-legend">
          <span className="legend-ok">✔ VERIFIED</span>
          <span className="legend-bad">✗ TAMPERED</span>
          <span className="legend-info">Blocks seal every ~10s</span>
        </div>
      </div>
    </div>
  )
}
