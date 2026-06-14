import { ReactNode, useEffect, useRef, useState } from 'react'

interface Props {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  snapPoints?: number[]  // heights as vh percentages
}

export function BottomSheet({ open, onClose, title, children, snapPoints = [65] }: Props) {
  const [snap, setSnap] = useState(snapPoints[0])
  const dragStart = useRef<{ y: number; snap: number } | null>(null)

  // Reset snap when opened
  useEffect(() => { if (open) setSnap(snapPoints[0]) }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const onDragStart = (clientY: number) => {
    dragStart.current = { y: clientY, snap }
  }
  const onDragMove = (clientY: number) => {
    if (!dragStart.current) return
    const delta = dragStart.current.y - clientY
    const newSnap = Math.max(20, Math.min(92, dragStart.current.snap + (delta / window.innerHeight) * 100))
    setSnap(newSnap)
  }
  const onDragEnd = (clientY: number) => {
    if (!dragStart.current) return
    const delta = dragStart.current.y - clientY
    if (delta < -60) {
      onClose()
    } else {
      const closest = snapPoints.reduce((a, b) => Math.abs(a - snap) < Math.abs(b - snap) ? a : b)
      setSnap(closest)
    }
    dragStart.current = null
  }

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 200,
        }}
      />

      {/* Sheet */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          height: `${snap}vh`,
          background: '#0f172a',
          borderTop: '1px solid #374151',
          borderRadius: '16px 16px 0 0',
          zIndex: 201,
          display: 'flex',
          flexDirection: 'column',
          transition: dragStart.current ? 'none' : 'height 0.25s ease',
          overflow: 'hidden',
        }}
      >
        {/* Drag handle */}
        <div
          style={{ padding: '10px 0 6px', cursor: 'grab', flexShrink: 0 }}
          onMouseDown={e => onDragStart(e.clientY)}
          onMouseMove={e => dragStart.current && onDragMove(e.clientY)}
          onMouseUp={e => onDragEnd(e.clientY)}
          onTouchStart={e => onDragStart(e.touches[0].clientY)}
          onTouchMove={e => { e.preventDefault(); onDragMove(e.touches[0].clientY) }}
          onTouchEnd={e => onDragEnd(e.changedTouches[0].clientY)}
        >
          <div style={{ width: 40, height: 4, background: '#374151', borderRadius: 2, margin: '0 auto' }} />
        </div>

        {/* Header */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '0 16px 8px', borderBottom: '1px solid #1e293b', flexShrink: 0,
        }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#f9fafb' }}>{title}</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', fontSize: 20, lineHeight: 1 }}>×</button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', WebkitOverflowScrolling: 'touch' } as React.CSSProperties}>
          {children}
        </div>
      </div>
    </>
  )
}
