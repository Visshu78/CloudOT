import { useState, useEffect } from 'react'
import './DataNodePanel.css'

export default function DataNodePanel() {
  const [activeTab, setActiveTab] = useState('spark') // 'spark' or 'hdfs'
  
  // HDFS State
  const [hdfsStatus, setHdfsStatus] = useState(null)
  const [recentBlocks, setRecentBlocks] = useState([])
  const [isSimulatingHdfs, setIsSimulatingHdfs] = useState(false)

  // Spark State
  const [sparkStatus, setSparkStatus] = useState(null)
  const [recentBatches, setRecentBatches] = useState([])
  const [isTriggeringSpark, setIsTriggeringSpark] = useState(false)

  const fetchData = () => {
    // 1. Fetch HDFS
    fetch('http://localhost:8000/api/hdfs/status')
      .then(r => r.json())
      .then(data => setHdfsStatus(data))
      .catch(() => {})

    fetch('http://localhost:8000/api/hdfs/blocks?limit=10')
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data)) setRecentBlocks(data)
      })
      .catch(() => {})

    // 2. Fetch Spark
    fetch('http://localhost:8000/api/spark/status')
      .then(r => r.json())
      .then(data => setSparkStatus(data))
      .catch(() => {})

    fetch('http://localhost:8000/api/spark/batches?limit=10')
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data)) setRecentBatches(data)
      })
      .catch(() => {})
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 2500)
    return () => clearInterval(interval)
  }, [])

  const handleSimulateBlocks = async () => {
    setIsSimulatingHdfs(true)
    try {
      await fetch('http://localhost:8000/api/hdfs/simulate?count=5', { method: 'POST' })
      fetchData()
    } catch (e) {
      console.error(e)
    } finally {
      setIsSimulatingHdfs(false)
    }
  }

  const handleTriggerSparkBatch = async () => {
    setIsTriggeringSpark(true)
    try {
      await fetch('http://localhost:8000/api/spark/trigger', { method: 'POST' })
      fetchData()
    } catch (e) {
      console.error(e)
    } finally {
      setIsTriggeringSpark(false)
    }
  }

  const formatKB = (bytes) => {
    if (!bytes) return '0.0 KB'
    return (bytes / 1024).toFixed(1) + ' KB'
  }

  return (
    <div className="datanode-panel">
      {/* Top Header & Tab Controls */}
      <div className="panel-header">
        <div className="title-group">
          <div className="pipeline-tabs">
            <button 
              className={`pipeline-tab-btn ${activeTab === 'spark' ? 'active-spark' : ''}`}
              onClick={() => setActiveTab('spark')}
            >
              <span className="panel-icon">⚡</span>
              <span>APACHE SPARK STREAMING</span>
              <span className="live-pill">MICRO-BATCH</span>
            </button>
            <button 
              className={`pipeline-tab-btn ${activeTab === 'hdfs' ? 'active-hdfs' : ''}`}
              onClick={() => setActiveTab('hdfs')}
            >
              <span className="panel-icon">💾</span>
              <span>HDFS DATANODE</span>
              <span className="live-pill">REP=1</span>
            </button>
          </div>
        </div>

        {activeTab === 'spark' ? (
          <button 
            className="simulate-btn spark-btn" 
            onClick={handleTriggerSparkBatch}
            disabled={isTriggeringSpark}
          >
            {isTriggeringSpark ? 'PROCESSING...' : '⚡ TRIGGER SPARK MICRO-BATCH'}
          </button>
        ) : (
          <button 
            className="simulate-btn" 
            onClick={handleSimulateBlocks}
            disabled={isSimulatingHdfs}
          >
            {isSimulatingHdfs ? 'SIMULATING...' : '💾 SIMULATE DATANODE BLOCKS'}
          </button>
        )}
      </div>

      {/* --- TAB 1: APACHE SPARK MICRO-BATCH STREAMING --- */}
      {activeTab === 'spark' && (
        <>
          <div className="datanode-metrics">
            <div className="metric-box">
              <span className="metric-val text-amber">{sparkStatus?.processed_microbatches || 0}</span>
              <span className="metric-lbl">TOTAL MICRO-BATCHES</span>
            </div>
            <div className="metric-box">
              <span className="metric-val text-cyan">{sparkStatus?.total_events_processed || 0}</span>
              <span className="metric-lbl">EVENTS PROCESSED</span>
            </div>
            <div className="metric-box">
              <span className="metric-val text-lime">
                {sparkStatus?.pending_buffer_events || 0} / {sparkStatus?.batch_size_threshold || 15}
              </span>
              <span className="metric-lbl">CURRENT BATCH BUFFER</span>
            </div>
            <div className="metric-box">
              <span className="metric-val status-tag">
                {sparkStatus?.spark_active ? 'ACTIVE (Micro-Batch)' : 'READY'}
              </span>
              <span className="metric-lbl">SPARK ENGINE</span>
            </div>
          </div>

          <div className="blocks-list-container">
            <div className="spark-table-header">
              <span>BATCH ID</span>
              <span>WINDOW</span>
              <span>EVENTS</span>
              <span>TOP THREAT</span>
              <span>TARGET ZONE</span>
              <span>AVG CONF</span>
              <span>LATENCY</span>
              <span>STATUS</span>
            </div>
            <div className="blocks-list">
              {recentBatches.length === 0 ? (
                <div className="no-blocks">
                  Ingesting live IoT stream into Spark micro-batches... Wait 3-5 seconds.
                </div>
              ) : (
                recentBatches.map((b, i) => (
                  <div className="block-row spark-row" key={`${b.batch_id}-${i}`}>
                    <span className="blk-id" title={b.batch_id}>{b.batch_id}</span>
                    <span className="spark-window">{b.window_duration || '5s-Window'}</span>
                    <span className="blk-events">{b.event_count} Events</span>
                    <span className={`spark-atk-badge atk-${(b.top_attack || 'DDoS').toLowerCase().replace(/[^a-z]/g, '')}`}>
                      {b.top_attack}
                    </span>
                    <span className="blk-zone">zone={b.top_zone}</span>
                    <span className="spark-conf">{b.avg_confidence}%</span>
                    <span className="spark-latency">{b.latency_ms} ms</span>
                    <span className="blk-status spark-status">✔ PROCESSED</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}

      {/* --- TAB 2: HDFS DATANODE STORAGE --- */}
      {activeTab === 'hdfs' && (
        <>
          <div className="datanode-metrics">
            <div className="metric-box">
              <span className="metric-val">{hdfsStatus?.datanode_total_blocks_stored || 0}</span>
              <span className="metric-lbl">TOTAL BLOCKS</span>
            </div>
            <div className="metric-box">
              <span className="metric-val">{formatKB(hdfsStatus?.datanode_total_bytes_stored)}</span>
              <span className="metric-lbl">TOTAL DATA SIZE</span>
            </div>
            <div className="metric-box">
              <span className="metric-val status-tag">{hdfsStatus?.status || 'ONLINE'}</span>
              <span className="metric-lbl">STORAGE ENGINE</span>
            </div>
            <div className="metric-box">
              <span className="metric-val rep-val">1 Node</span>
              <span className="metric-lbl">REPLICATION FACTOR</span>
            </div>
          </div>

          <div className="blocks-list-container">
            <div className="blocks-list-header">
              <span>BLOCK ID</span>
              <span>ZONE PARTITION</span>
              <span>EVENTS</span>
              <span>SIZE</span>
              <span>STATUS</span>
            </div>
            <div className="blocks-list">
              {recentBlocks.length === 0 ? (
                <div className="no-blocks">No DataNode storage blocks generated yet.</div>
              ) : (
                recentBlocks.map((blk, i) => (
                  <div className="block-row" key={`${blk.block_id}-${i}`}>
                    <span className="blk-id" title={blk.filename}>{blk.block_id}</span>
                    <span className="blk-zone">zone={blk.zone}</span>
                    <span className="blk-events">{blk.event_count} Recs</span>
                    <span className="blk-size">{blk.size_bytes} B</span>
                    <span className="blk-status">✔ STORED</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
