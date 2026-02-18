import { useState, useCallback, useRef } from 'react'
import BarcodeScanner from './components/BarcodeScanner'
import ScanResult from './components/ScanResult'
import './App.css'

interface ScanEntry {
  id: number
  value: string
  format: string
  timestamp: Date
}

const MAX_HISTORY = 20

export default function App() {
  const [isScanning, setIsScanning] = useState(false)
  const [history, setHistory] = useState<ScanEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [lastScanValue, setLastScanValue] = useState<string | null>(null)
  const idCounter = useRef(0)
  const cooldownRef = useRef(false)

  const handleScan = useCallback((value: string, format: string) => {
    // 同じコードの連続スキャンを1秒間抑制
    if (cooldownRef.current || value === lastScanValue) return
    cooldownRef.current = true
    setTimeout(() => { cooldownRef.current = false }, 1000)

    setLastScanValue(value)
    setError(null)

    const entry: ScanEntry = {
      id: ++idCounter.current,
      value,
      format,
      timestamp: new Date(),
    }

    setHistory(prev => [entry, ...prev].slice(0, MAX_HISTORY))

    // 振動フィードバック (対応デバイスのみ)
    if (navigator.vibrate) {
      navigator.vibrate(50)
    }
  }, [lastScanValue])

  const handleError = useCallback((message: string) => {
    setError(message)
    setIsScanning(false)
  }, [])

  const toggleScanner = () => {
    setIsScanning(prev => !prev)
    setError(null)
    if (!isScanning) {
      setLastScanValue(null)
    }
  }

  const clearHistory = () => {
    setHistory([])
    setLastScanValue(null)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">CodeReader</h1>
        <p className="app-subtitle">バーコード・QRコードスキャナー</p>
      </header>

      <main className="app-main">
        <section className="scanner-section">
          {isScanning ? (
            <BarcodeScanner
              onScan={handleScan}
              onError={handleError}
              isActive={isScanning}
            />
          ) : (
            <div className="scanner-placeholder">
              <div className="placeholder-icon">
                <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <rect x="10" y="10" width="30" height="5" rx="2" fill="currentColor"/>
                  <rect x="10" y="10" width="5" height="30" rx="2" fill="currentColor"/>
                  <rect x="60" y="10" width="30" height="5" rx="2" fill="currentColor"/>
                  <rect x="85" y="10" width="5" height="30" rx="2" fill="currentColor"/>
                  <rect x="10" y="85" width="30" height="5" rx="2" fill="currentColor"/>
                  <rect x="10" y="60" width="5" height="30" rx="2" fill="currentColor"/>
                  <rect x="60" y="85" width="30" height="5" rx="2" fill="currentColor"/>
                  <rect x="85" y="60" width="5" height="30" rx="2" fill="currentColor"/>
                  <rect x="20" y="47" width="60" height="6" rx="3" fill="currentColor" opacity="0.5"/>
                </svg>
              </div>
              <p className="placeholder-text">カメラを起動してスキャン</p>
            </div>
          )}

          {error && (
            <div className="error-banner" role="alert">
              <strong>エラー:</strong> {error}
              {error.includes('permission') || error.includes('NotAllowed') ? (
                <p className="error-hint">カメラの使用許可を有効にしてください。</p>
              ) : null}
            </div>
          )}

          <button
            className={`scan-btn ${isScanning ? 'scan-btn--stop' : 'scan-btn--start'}`}
            onClick={toggleScanner}
          >
            {isScanning ? 'スキャン停止' : 'スキャン開始'}
          </button>
        </section>

        {history.length > 0 && (
          <section className="history-section">
            <div className="history-header">
              <h2 className="history-title">スキャン履歴</h2>
              <button className="clear-btn" onClick={clearHistory}>
                クリア
              </button>
            </div>
            <ul className="history-list">
              {history.map(entry => (
                <li key={entry.id}>
                  <ScanResult
                    value={entry.value}
                    format={entry.format}
                    timestamp={entry.timestamp}
                  />
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </div>
  )
}
