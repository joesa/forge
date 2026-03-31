interface ProgressPillsProps {
  total: number
  current: number
}

export default function ProgressPills({ total, current }: ProgressPillsProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center', marginBottom: 28 }}>
      {Array.from({ length: total }, (_, i) => {
        const isDone = i < current
        const isCurrent = i === current
        return (
          <div
            key={i}
            style={{
              width: isCurrent ? 28 : 8,
              height: 8,
              borderRadius: isCurrent ? 4 : '50%',
              background: isDone ? '#3dffa0' : isCurrent ? '#63d9ff' : 'rgba(255,255,255,0.12)',
              transition: 'all 0.25s ease',
            }}
          />
        )
      })}
    </div>
  )
}
