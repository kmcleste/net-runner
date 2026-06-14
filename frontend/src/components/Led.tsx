// The signature element: a gear front-panel status LED with a soft glow.
// Active failures pulse gently — the way you read a rack by its lights.
interface Props {
  color: string
  size?: number
  pulse?: boolean
  title?: string
}

export function Led({ color, size = 9, pulse = false, title }: Props) {
  return (
    <span
      className={pulse ? 'led led-pulse' : 'led'}
      title={title}
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        borderRadius: '50%',
        background: color,
        // inner highlight + outer bloom = a lit indicator, not a flat dot
        boxShadow: `0 0 ${size * 0.7}px ${color}, 0 0 ${size * 1.8}px ${color}66, inset 0 0 ${size * 0.4}px rgba(255,255,255,0.45)`,
        // expose color to the pulse keyframes
        ['--led-color' as string]: color,
        flexShrink: 0,
      }}
    />
  )
}
