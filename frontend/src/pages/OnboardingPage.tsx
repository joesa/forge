import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import TopNav from '@/components/layout/TopNav'
import ProgressPills from '@/components/shared/ProgressPills'

const startOptions = [
  { icon: '✍️', title: 'I have an idea', desc: 'Describe my app and FORGE builds it' },
  { icon: '💡', title: 'Help me find an idea', desc: 'Answer questions, get 5 AI-generated ideas' },
  { icon: '🎲', title: 'Surprise me', desc: 'AI generates ideas with zero input from me' },
]

const providers = [
  { name: 'Anthropic', note: 'FORGE Default — no key needed', status: 'active' as const },
  { name: 'OpenAI', note: 'Add your API key', status: 'inactive' as const },
  { name: 'Gemini', note: 'Add your API key', status: 'inactive' as const },
]

export default function OnboardingPage() {
  const [step, setStep] = useState(0)
  const [selectedStart, setSelectedStart] = useState<number | null>(null)
  const navigate = useNavigate()

  const nextStep = () => {
    if (step < 2) {
      setStep(step + 1)
    } else {
      navigate('/dashboard')
    }
  }

  return (
    <>
      <div className="grid-bg" aria-hidden="true" />
      <div className="orb" style={{ width: 600, height: 600, top: '-15%', right: '-5%', background: 'rgba(176,107,255,0.04)' }} aria-hidden="true" />
      <div className="orb" style={{ width: 500, height: 500, bottom: '-10%', left: '-8%', background: 'rgba(99,217,255,0.04)' }} aria-hidden="true" />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <TopNav
          variant="minimal"
          rightContent={
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.35)' }}>
              Step {step + 1} of 3
            </span>
          }
        />

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 'calc(100vh - 62px)',
            padding: '40px 20px',
          }}
        >
          <div style={{ width: '100%', maxWidth: 580 }}>
            <ProgressPills total={3} current={step} />

            <div
              key={step}
              id="onboarding-card"
              style={{
                background: '#0d0d1f',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 16,
                padding: 36,
                animation: 'fade-in 280ms ease',
              }}
            >
              {/* Step 1: Welcome */}
              {step === 0 && (
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 44, marginBottom: 14 }}>⬡</div>
                  <h2 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.8px', marginBottom: 9, color: '#e8e8f0' }}>
                    Welcome to FORGE
                  </h2>
                  <p style={{ fontSize: 13, color: 'rgba(232,232,240,0.45)', lineHeight: 1.7, marginBottom: 24 }}>
                    The AI-native platform that builds production apps for you.
                    <br />
                    Let&apos;s get you set up in 2 minutes.
                  </p>
                  <button
                    className="btn btn-primary"
                    id="onboarding-start"
                    style={{ width: '100%', height: 48 }}
                    onClick={nextStep}
                  >
                    Let&apos;s go →
                  </button>
                </div>
              )}

              {/* Step 2: How to start */}
              {step === 1 && (
                <>
                  <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 5, color: '#e8e8f0' }}>
                    How do you want to start?
                  </h2>
                  <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)', marginBottom: 20 }}>
                    You can always change this later
                  </p>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 9, marginBottom: 22 }}>
                    {startOptions.map((opt, i) => {
                      const isSelected = selectedStart === i
                      return (
                        <button
                          key={opt.title}
                          id={`onboarding-option-${i}`}
                          onClick={() => setSelectedStart(i)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 13,
                            textAlign: 'left',
                            background: isSelected ? 'rgba(99,217,255,0.08)' : 'rgba(255,255,255,0.03)',
                            border: `2px solid ${isSelected ? '#63d9ff' : 'rgba(255,255,255,0.06)'}`,
                            borderRadius: 10,
                            padding: '13px 16px',
                            cursor: 'pointer',
                            transition: 'all 200ms',
                            color: '#e8e8f0',
                          }}
                        >
                          <span style={{ fontSize: 22 }}>{opt.icon}</span>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: 13, fontWeight: 700 }}>{opt.title}</div>
                            <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>{opt.desc}</div>
                          </div>
                          {isSelected && <span style={{ color: '#63d9ff', fontSize: 16 }}>✓</span>}
                        </button>
                      )
                    })}
                  </div>

                  <button
                    className="btn btn-primary"
                    id="onboarding-continue"
                    style={{ width: '100%', height: 48 }}
                    onClick={nextStep}
                  >
                    Continue →
                  </button>
                </>
              )}

              {/* Step 3: Connect AI */}
              {step === 2 && (
                <>
                  <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 5, color: '#e8e8f0' }}>
                    Connect an AI provider
                  </h2>
                  <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)', marginBottom: 20 }}>
                    FORGE includes Anthropic Claude on Free tier. Add your keys for unlimited usage.
                  </p>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 22 }}>
                    {providers.map((p) => (
                      <div
                        key={p.name}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 11,
                          background: 'rgba(255,255,255,0.03)',
                          border: '1px solid rgba(255,255,255,0.07)',
                          borderRadius: 8,
                          padding: '11px 13px',
                        }}
                      >
                        <div
                          style={{
                            width: 18,
                            height: 18,
                            borderRadius: 4,
                            background: 'rgba(255,255,255,0.08)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 10,
                            flexShrink: 0,
                          }}
                        >
                          {p.name[0]}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: '#e8e8f0' }}>{p.name}</div>
                          <div style={{ fontSize: 10, color: 'rgba(232,232,240,0.42)' }}>{p.note}</div>
                        </div>
                        {p.status === 'active' ? (
                          <span className="tag tag-j">Active</span>
                        ) : (
                          <button className="btn btn-ghost btn-sm">Add Key</button>
                        )}
                      </div>
                    ))}
                  </div>

                  <div style={{ display: 'flex', gap: 9 }}>
                    <button
                      className="btn btn-ghost"
                      style={{ flex: 1 }}
                      onClick={() => navigate('/dashboard')}
                    >
                      Skip for now
                    </button>
                    <button
                      className="btn btn-primary"
                      id="onboarding-finish"
                      style={{ flex: 1, height: 48 }}
                      onClick={nextStep}
                    >
                      Get Started →
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
