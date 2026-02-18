import { useEffect, useRef, useCallback } from 'react'
import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode'

const SCANNER_ELEMENT_ID = 'barcode-scanner-element'

const SUPPORTED_FORMATS = [
  Html5QrcodeSupportedFormats.QR_CODE,
  Html5QrcodeSupportedFormats.EAN_13,
  Html5QrcodeSupportedFormats.EAN_8,
  Html5QrcodeSupportedFormats.CODE_128,
  Html5QrcodeSupportedFormats.CODE_39,
  Html5QrcodeSupportedFormats.CODE_93,
  Html5QrcodeSupportedFormats.UPC_A,
  Html5QrcodeSupportedFormats.UPC_E,
  Html5QrcodeSupportedFormats.ITF,
  Html5QrcodeSupportedFormats.DATA_MATRIX,
  Html5QrcodeSupportedFormats.PDF_417,
  Html5QrcodeSupportedFormats.AZTEC,
]

interface BarcodeScannerProps {
  onScan: (value: string, format: string) => void
  onError?: (error: string) => void
  isActive: boolean
}

export default function BarcodeScanner({ onScan, onError, isActive }: BarcodeScannerProps) {
  const scannerRef = useRef<Html5Qrcode | null>(null)
  const isRunningRef = useRef(false)

  const startScanner = useCallback(async () => {
    if (isRunningRef.current || !scannerRef.current) return

    try {
      await scannerRef.current.start(
        { facingMode: 'environment' },
        {
          fps: 10,
          qrbox: { width: 250, height: 250 },
          aspectRatio: 1.0,
        },
        (decodedText, decodedResult) => {
          const format = decodedResult.result.format?.formatName ?? 'UNKNOWN'
          onScan(decodedText, format)
        },
        undefined,
      )
      isRunningRef.current = true
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      onError?.(message)
    }
  }, [onScan, onError])

  const stopScanner = useCallback(async () => {
    if (!isRunningRef.current || !scannerRef.current) return
    try {
      await scannerRef.current.stop()
      isRunningRef.current = false
    } catch {
      // ignore stop errors
    }
  }, [])

  useEffect(() => {
    const scanner = new Html5Qrcode(SCANNER_ELEMENT_ID, {
      formatsToSupport: SUPPORTED_FORMATS,
      verbose: false,
    })
    scannerRef.current = scanner

    return () => {
      stopScanner().then(() => {
        try { scanner.clear() } catch { /* ignore */ }
      })
    }
  }, [stopScanner])

  useEffect(() => {
    if (isActive) {
      startScanner()
    } else {
      stopScanner()
    }
  }, [isActive, startScanner, stopScanner])

  return (
    <div className="scanner-wrapper">
      <div id={SCANNER_ELEMENT_ID} className="scanner-element" />
      <div className="scanner-overlay">
        <div className="scanner-frame">
          <span className="corner top-left" />
          <span className="corner top-right" />
          <span className="corner bottom-left" />
          <span className="corner bottom-right" />
          <div className="scan-line" />
        </div>
      </div>
    </div>
  )
}
