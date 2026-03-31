interface HexLogoProps {
  size?: number
  showWordmark?: boolean
  wordmarkSize?: number
}

export default function HexLogo({ size = 26, showWordmark = true, wordmarkSize = 18 }: HexLogoProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
      <div
        style={{
          width: size,
          height: size,
          background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
          clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)',
          flexShrink: 0,
        }}
      />
      {showWordmark && (
        <span
          style={{
            fontFamily: "'Syne', sans-serif",
            fontSize: wordmarkSize,
            fontWeight: 800,
            letterSpacing: '-0.5px',
            background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >
          FORGE
        </span>
      )}
    </div>
  )
}
