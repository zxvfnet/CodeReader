interface ScanResultProps {
  value: string
  format: string
  timestamp: Date
}

function isUrl(text: string): boolean {
  try {
    const url = new URL(text)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

export default function ScanResult({ value, format, timestamp }: ScanResultProps) {
  const url = isUrl(value)
  const timeStr = timestamp.toLocaleTimeString('ja-JP', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })

  return (
    <div className="scan-result">
      <div className="result-header">
        <span className="result-format">{format}</span>
        <span className="result-time">{timeStr}</span>
      </div>
      <div className="result-value">
        {url ? (
          <a href={value} target="_blank" rel="noopener noreferrer" className="result-link">
            {value}
          </a>
        ) : (
          <span>{value}</span>
        )}
      </div>
      <button
        className="copy-btn"
        onClick={() => navigator.clipboard.writeText(value)}
        aria-label="コピー"
      >
        コピー
      </button>
    </div>
  )
}
