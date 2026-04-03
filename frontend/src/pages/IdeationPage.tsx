import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import TopNav from '@/components/layout/TopNav'
import { useStartQuestionnaire, useGenerateDirect } from '@/hooks/queries/useIdeation'

export default function IdeationPage() {
  const navigate = useNavigate()
  const startQuestionnaire = useStartQuestionnaire()
  const generateDirect = useGenerateDirect()
  const [loading, setLoading] = useState<'questionnaire' | 'surprise' | null>(null)

  const handleQuestionnaire = () => {
    setLoading('questionnaire')
    startQuestionnaire.mutate(undefined, {
      onSuccess: (data: { session_id: string }) => {
        navigate(`/ideate/questionnaire/${data.session_id}`)
      },
      onError: () => {
        setLoading(null)
      },
    })
  }

  const handleSurprise = () => {
    setLoading('surprise')
    generateDirect.mutate(undefined, {
      onSuccess: (data: { session_id: string }) => {
        navigate(`/ideate/ideas/${data.session_id}`)
      },
      onError: () => {
        setLoading(null)
      },
    })
  }

  return (
    <>
      <div className="grid-bg" aria-hidden="true" />
      <div className="orb" style={{ width: 600, height: 600, top: '-15%', right: '-5%', background: 'rgba(176,107,255,0.04)' }} aria-hidden="true" />
      <div className="orb" style={{ width: 500, height: 500, bottom: '-10%', left: '-8%', background: 'rgba(99,217,255,0.04)' }} aria-hidden="true" />
      <div className="orb" style={{ width: 350, height: 350, top: '50%', left: '20%', background: 'rgba(255,107,53,0.03)' }} aria-hidden="true" />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <TopNav
          variant="minimal"
          rightContent={
            <Link to="/dashboard" className="btn btn-ghost btn-sm" style={{ textDecoration: 'none' }}>← Dashboard</Link>
          }
        />

        <div
          style={{
            maxWidth: 580,
            margin: '0 auto',
            minHeight: 'calc(100vh - 112px)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '40px 20px',
          }}
        >
          {/* Hero */}
          <div style={{ fontSize: 44, marginBottom: 14, textAlign: 'center' }}>💡</div>
          <h1
            id="ideation-title"
            style={{
              fontSize: 38,
              fontWeight: 800,
              letterSpacing: '-1.2px',
              marginBottom: 10,
              color: '#e8e8f0',
              textAlign: 'center',
            }}
          >
            What will you build?
          </h1>
          <p style={{ fontSize: 14, color: 'rgba(232,232,240,0.45)', textAlign: 'center', marginBottom: 44 }}>
            Let AI help you find your next million-dollar idea
          </p>

          {/* 3 option cards */}
          <div id="ideation-options" style={{ display: 'flex', flexDirection: 'column', gap: 10, width: '100%' }}>
            {/* Card 1 — questionnaire */}
            <button
              id="ideation-questionnaire"
              className="card va"
              onClick={handleQuestionnaire}
              disabled={loading !== null}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '18px 22px',
                cursor: loading !== null ? 'not-allowed' : 'pointer',
                width: '100%',
                textAlign: 'left',
                background: 'none',
                border: 'none',
                opacity: loading !== null && loading !== 'questionnaire' ? 0.5 : 1,
              }}
            >
              <span style={{ fontSize: 26, flexShrink: 0 }}>
                {loading === 'questionnaire' ? '⏳' : '💡'}
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 3 }}>
                  {loading === 'questionnaire' ? 'Starting...' : 'Help me find an idea'}
                </div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>
                  8 adaptive questions · all skippable · 5 unique ideas generated
                </div>
              </div>
              <span style={{ color: '#63d9ff', fontSize: 18 }}>→</span>
            </button>

            {/* Card 2 — existing idea */}
            <Link
              to="/projects/new"
              className="card fa"
              id="ideation-existing"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '18px 22px',
                textDecoration: 'none',
                cursor: 'pointer',
                opacity: loading !== null ? 0.5 : 1,
              }}
            >
              <span style={{ fontSize: 26, flexShrink: 0 }}>✍️</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 3 }}>I already have an idea</div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>
                  Describe it and AI will enhance it before building
                </div>
              </div>
              <span style={{ color: '#63d9ff', fontSize: 18 }}>→</span>
            </Link>

            {/* Card 3 — surprise */}
            <button
              id="ideation-surprise"
              className="card ea"
              onClick={handleSurprise}
              disabled={loading !== null}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '18px 22px',
                cursor: loading !== null ? 'not-allowed' : 'pointer',
                width: '100%',
                textAlign: 'left',
                background: 'none',
                border: 'none',
                opacity: loading !== null && loading !== 'surprise' ? 0.5 : 1,
              }}
            >
              <span style={{ fontSize: 26, flexShrink: 0 }}>
                {loading === 'surprise' ? '⏳' : '🎲'}
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 3 }}>
                  {loading === 'surprise' ? 'Generating ideas...' : 'Surprise me'}
                </div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>
                  Zero input — AI generates from market signals instantly
                </div>
              </div>
              <span style={{ color: '#63d9ff', fontSize: 18 }}>→</span>
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
