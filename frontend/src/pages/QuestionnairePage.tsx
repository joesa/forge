import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import TopNav from '@/components/layout/TopNav'
import ProgressPills from '@/components/shared/ProgressPills'
import { useCompleteQuestionnaire } from '@/hooks/queries/useIdeation'

interface Question {
  id: number
  text: string
  type: 'chips' | 'cards' | 'slider' | 'text'
  options?: string[]
  cardOptions?: { icon: string; label: string }[]
  min?: number
  max?: number
  minLabel?: string
  maxLabel?: string
}

const questions: Question[] = [
  { id: 1, text: 'What kind of product are you interested in building?', type: 'chips', options: ['SaaS', 'Mobile App', 'API / Backend', 'E-Commerce', 'Social Platform', 'Developer Tool', 'AI / ML Product', 'Marketplace', 'Fintech', 'Healthcare'] },
  { id: 2, text: 'Who is your target audience?', type: 'cards', cardOptions: [{ icon: '👤', label: 'Consumers (B2C)' }, { icon: '🏢', label: 'Businesses (B2B)' }, { icon: '👨‍💻', label: 'Developers' }, { icon: '🌐', label: 'Everyone' }] },
  { id: 3, text: 'How complex should the project be?', type: 'slider', min: 1, max: 10, minLabel: 'Simple MVP', maxLabel: 'Enterprise-grade' },
  { id: 4, text: 'What industries interest you most?', type: 'chips', options: ['Technology', 'Finance', 'Healthcare', 'Education', 'Entertainment', 'Real Estate', 'Travel', 'Food & Beverage', 'Sustainability', 'Gaming'] },
  { id: 5, text: 'What revenue model do you prefer?', type: 'cards', cardOptions: [{ icon: '💳', label: 'Subscription' }, { icon: '🛒', label: 'One-time purchase' }, { icon: '📢', label: 'Ad-supported' }, { icon: '🆓', label: 'Freemium' }] },
  { id: 6, text: 'What technologies are you comfortable with?', type: 'chips', options: ['React', 'Next.js', 'Python', 'Node.js', 'PostgreSQL', 'MongoDB', 'GraphQL', 'REST API', 'TypeScript', 'Docker'] },
  { id: 7, text: 'How much time do you want to invest initially?', type: 'slider', min: 1, max: 10, minLabel: '1 week', maxLabel: '6 months' },
  { id: 8, text: 'Any specific features or requirements?', type: 'text' },
]

export default function QuestionnairePage() {
  const { id: sessionId = '' } = useParams<{ id: string }>()
  const [currentQ, setCurrentQ] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string | string[] | number>>({})
  const [sliderVal, setSliderVal] = useState(5)
  const [textVal, setTextVal] = useState('')
  const [completing, setCompleting] = useState(false)
  const navigate = useNavigate()
  const completeQuestionnaire = useCompleteQuestionnaire(sessionId)

  const question = questions[currentQ]
  const selectedChips = (answers[question.id] as string[] | undefined) ?? []

  const toggleChip = (chip: string) => {
    const current = selectedChips
    const updated = current.includes(chip)
      ? current.filter((c) => c !== chip)
      : [...current, chip]
    setAnswers({ ...answers, [question.id]: updated })
  }

  const selectCard = (label: string) => {
    setAnswers({ ...answers, [question.id]: label })
  }

  const finishQuestionnaire = () => {
    setCompleting(true)
    if (sessionId && sessionId !== 'new') {
      completeQuestionnaire.mutate(undefined, {
        onSuccess: (data: { session_id: string }) => {
          navigate(`/ideate/ideas/${data.session_id || sessionId}`)
        },
        onError: () => {
          // Fall back to session ID from URL
          navigate(`/ideate/ideas/${sessionId}`)
        },
      })
    } else {
      navigate('/ideate')
    }
  }

  const goNext = () => {
    if (question.type === 'slider') {
      setAnswers({ ...answers, [question.id]: sliderVal })
    }
    if (question.type === 'text') {
      setAnswers({ ...answers, [question.id]: textVal })
    }
    if (currentQ < questions.length - 1) {
      setCurrentQ(currentQ + 1)
      setSliderVal(5)
      setTextVal('')
    } else {
      finishQuestionnaire()
    }
  }

  const goBack = () => {
    if (currentQ > 0) setCurrentQ(currentQ - 1)
  }

  return (
    <>
      <div className="grid-bg" aria-hidden="true" />
      <div className="orb" style={{ width: 500, height: 500, top: '-10%', right: '-5%', background: 'rgba(176,107,255,0.04)' }} aria-hidden="true" />
      <div className="orb" style={{ width: 400, height: 400, bottom: '-8%', left: '-5%', background: 'rgba(99,217,255,0.04)' }} aria-hidden="true" />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <TopNav
          variant="minimal"
          rightContent={
            <>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.35)' }}>
                Question {currentQ + 1} of {questions.length}
              </span>
              <button
                className="btn btn-sm"
                onClick={finishQuestionnaire}
                disabled={completing}
                style={{ color: '#ff6b35', border: '1px solid rgba(255,107,53,0.22)', background: 'transparent' }}
              >
                {completing ? 'Generating...' : 'Skip All →'}
              </button>
            </>
          }
        />

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 'calc(100vh - 62px)',
            padding: '40px 20px',
          }}
        >
          <div style={{ maxWidth: 620, width: '100%' }}>
            <ProgressPills total={questions.length} current={currentQ} />

            <div
              key={currentQ}
              id="question-card"
              style={{
                background: '#0d0d1f',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: 12,
                padding: 36,
                animation: 'fade-in 280ms ease',
              }}
            >
              {/* Step number */}
              <div
                style={{
                  fontSize: 52,
                  fontWeight: 800,
                  letterSpacing: '-2px',
                  color: 'rgba(232,232,240,0.10)',
                  lineHeight: 1,
                  marginBottom: 7,
                }}
              >
                {String(currentQ + 1).padStart(2, '0')}
              </div>

              {/* Question text */}
              <div style={{ fontSize: 21, fontWeight: 700, letterSpacing: '-0.5px', marginBottom: 22, color: '#e8e8f0' }}>
                {question.text}
              </div>

              {/* Answer Type A — Chips */}
              {question.type === 'chips' && question.options && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginBottom: 26 }}>
                  {question.options.map((opt) => {
                    const isSelected = selectedChips.includes(opt)
                    return (
                      <button
                        key={opt}
                        onClick={() => toggleChip(opt)}
                        style={{
                          padding: '7px 15px',
                          borderRadius: 20,
                          fontSize: 11,
                          fontWeight: 600,
                          cursor: 'pointer',
                          border: `1px solid ${isSelected ? '#63d9ff' : 'rgba(255,255,255,0.08)'}`,
                          color: isSelected ? '#63d9ff' : 'rgba(232,232,240,0.50)',
                          background: isSelected ? 'rgba(99,217,255,0.10)' : 'transparent',
                          transition: 'all 150ms',
                        }}
                      >
                        {opt}
                      </button>
                    )
                  })}
                </div>
              )}

              {/* Answer Type B — Cards */}
              {question.type === 'cards' && question.cardOptions && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9, marginBottom: 26 }}>
                  {question.cardOptions.map((opt) => {
                    const isSelected = answers[question.id] === opt.label
                    return (
                      <button
                        key={opt.label}
                        onClick={() => selectCard(opt.label)}
                        style={{
                          textAlign: 'center',
                          padding: '13px 16px',
                          borderRadius: 10,
                          cursor: 'pointer',
                          border: `2px solid ${isSelected ? '#63d9ff' : 'rgba(255,255,255,0.06)'}`,
                          background: isSelected ? 'rgba(99,217,255,0.08)' : 'transparent',
                          transition: 'all 200ms',
                          color: '#e8e8f0',
                        }}
                      >
                        <div style={{ fontSize: 22, marginBottom: 6 }}>{opt.icon}</div>
                        <div style={{ fontSize: 11, fontWeight: 600 }}>{opt.label}</div>
                      </button>
                    )
                  })}
                </div>
              )}

              {/* Answer Type C — Slider */}
              {question.type === 'slider' && (
                <div style={{ marginBottom: 26 }}>
                  <input
                    type="range"
                    min={question.min}
                    max={question.max}
                    value={sliderVal}
                    onChange={(e) => setSliderVal(Number(e.target.value))}
                    style={{ width: '100%', accentColor: '#63d9ff' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'rgba(232,232,240,0.40)' }}>
                    <span>{question.minLabel}</span>
                    <span style={{ color: '#63d9ff', fontWeight: 700 }}>{sliderVal}</span>
                    <span>{question.maxLabel}</span>
                  </div>
                </div>
              )}

              {/* Answer Type D — Text */}
              {question.type === 'text' && (
                <div style={{ marginBottom: 26 }}>
                  <input
                    className="input"
                    placeholder="Type your answer..."
                    value={textVal}
                    onChange={(e) => setTextVal(e.target.value)}
                    id="question-text-input"
                  />
                </div>
              )}

              {/* Bottom row */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <button
                  className="btn btn-ghost"
                  onClick={goBack}
                  style={{ opacity: currentQ === 0 ? 0.3 : 1 }}
                  disabled={currentQ === 0}
                >
                  ← Back
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ color: 'rgba(232,232,240,0.40)' }}
                  onClick={goNext}
                >
                  Skip this →
                </button>
                <button className="btn btn-primary" onClick={goNext} id="question-next" disabled={completing}>
                  {completing ? 'Generating...' : currentQ === questions.length - 1 ? 'Generate Ideas →' : 'Next →'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
