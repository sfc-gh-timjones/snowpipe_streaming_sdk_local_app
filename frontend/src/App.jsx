import { useState, useEffect, useRef, useCallback } from 'react'

const MAX_RECORDS = 200
const CONF_WARN  = 0.7
const CONF_CRIT  = 0.6  // intrusion confidence threshold for red bar

function formatTime(iso) {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
    + '.' + String(d.getMilliseconds()).padStart(3, '0')
}

function ConfBar({ value }) {
  const pct = Math.round(value * 100)
  const cls = value < CONF_CRIT ? 'crit' : value < CONF_WARN ? 'low' : ''
  return (
    <div className="conf-bar">
      <div className="conf-track">
        <div className="conf-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="cell dim">{pct}%</span>
    </div>
  )
}

function RecordRow({ record }) {
  return (
    <div className="record-row">
      <span className="cell dim">{formatTime(record.ingested_at)}</span>
      <span className="cell">{record.camera_id}</span>
      <span className="cell dim" title={record.location}>{record.location}</span>
      <span className="cell dim">{record.zone}</span>
      <span className="cell">
        <span className={`badge ${record.event_type}`}>{record.event_type.replace(/_/g, ' ')}</span>
      </span>
      <ConfBar value={record.confidence} />
      <span className="cell dim" style={{ textAlign: 'right' }}>{record.object_count}</span>
      <span className="cell dim" style={{ textAlign: 'right' }}>{record.duration_ms}ms</span>
    </div>
  )
}

export default function App() {
  const [records, setRecords]       = useState([])
  const [isRunning, setIsRunning]   = useState(false)
  const [totalCount, setTotalCount] = useState(0)
  const [rateDisplay, setRateDisplay] = useState('0.0')

  const sourceRef    = useRef(null)

  const openStream = useCallback(() => {
    if (sourceRef.current) return
    const es = new EventSource('/stream')
    sourceRef.current = es

    es.onmessage = (e) => {
      try {
        const row = JSON.parse(e.data)
        setRecords(prev => [row, ...prev].slice(0, MAX_RECORDS))
      } catch (_) {}
    }

    // stats event carries the real Snowflake throughput from the backend
    es.addEventListener('stats', (e) => {
      try {
        const { rows_per_sec, total } = JSON.parse(e.data)
        setRateDisplay(rows_per_sec.toFixed(1))
        setTotalCount(total)
      } catch (_) {}
    })

    es.onerror = () => {
      // SSE reconnects automatically; nothing to do
    }
  }, [])

  const closeStream = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close()
      sourceRef.current = null
    }
  }, [])

  const handleToggle = async () => {
    if (!isRunning) {
      await fetch('/start', { method: 'POST' })
      openStream()
      setIsRunning(true)
    } else {
      await fetch('/stop', { method: 'POST' })
      closeStream()
      setIsRunning(false)
    }
  }

  // Check backend status on mount (in case of hot reload)
  useEffect(() => {
    fetch('/status')
      .then(r => r.json())
      .then(({ running }) => {
        if (running) {
          setIsRunning(true)
          openStream()
        }
      })
      .catch(() => {})
    return closeStream
  }, [openStream, closeStream])

  return (
    <>
      {/* Header */}
      <div className="header">
        <h1>
          {isRunning && <span className="pulse-dot" />}
          Security Camera Feed &nbsp;→&nbsp; <span>Snowpipe Streaming</span>
        </h1>
        <button
          className={`btn-generate ${isRunning ? 'running' : 'idle'}`}
          onClick={handleToggle}
        >
          {isRunning ? 'Stop Streaming' : 'Generate Streaming Records'}
        </button>
      </div>

      {/* Stats */}
      <div className="stats">
        <div className="stat-item">
          <span className="stat-label">Rows / sec</span>
          <span className="stat-value">{isRunning ? rateDisplay : '—'}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Total sent</span>
          <span className="stat-value">{totalCount.toLocaleString()}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Showing</span>
          <span className="stat-value">{records.length}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Status</span>
          <span className={`stat-value dim`} style={{ color: isRunning ? 'var(--green)' : 'var(--text-dim)' }}>
            {isRunning ? 'LIVE' : 'IDLE'}
          </span>
          {isRunning && (
            <span style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 2 }}>
              1,000/sec → Snowflake · ~20/sec shown in UI
            </span>
          )}
        </div>
        <div className="stat-item" style={{ marginLeft: 'auto' }}>
          <span className="stat-label">Snowflake query</span>
          <span className="stat-value dim" style={{ fontSize: 11 }}>
            SELECT COUNT(*) FROM STREAMING_DEMO.SECURITY.CAMERA_EVENTS;
          </span>
        </div>
      </div>

      {/* Column headers */}
      <div className="col-headers">
        <span>TIME</span>
        <span>CAMERA</span>
        <span>LOCATION</span>
        <span>ZONE</span>
        <span>EVENT TYPE</span>
        <span>CONFIDENCE</span>
        <span>OBJECTS</span>
        <span>DURATION</span>
      </div>

      {/* Feed */}
      <div className="feed">
        {records.length === 0 ? (
          <div className="empty-state">
            <span className="icon">📹</span>
            <p>Press <strong>Generate Streaming Records</strong> to start ingesting into Snowflake</p>
          </div>
        ) : (
          records.map(r => <RecordRow key={r.event_id} record={r} />)
        )}
      </div>
    </>
  )
}
