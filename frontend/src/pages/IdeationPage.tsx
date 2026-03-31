import { Link } from 'react-router-dom'
import TopNav from '@/components/layout/TopNav'

export default function IdeationPage() {
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
            {/* Card 1 — violet accent */}
            <Link
              to="/ideate/questionnaire/new"
              className="card va"
              id="ideation-questionnaire"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '18px 22px',
                textDecoration: 'none',
                cursor: 'pointer',
              }}
            >
              <span style={{ fontSize: 26, flexShrink: 0 }}>💡</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 3 }}>Help me find an idea</div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>
                  8 adaptive questions · all skippable · 5 unique ideas generated
                </div>
              </div>
              <span style={{ color: '#63d9ff', fontSize: 18 }}>→</span>
            </Link>

            {/* Card 2 — forge accent */}
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

            {/* Card 3 — ember accent */}
            <Link
              to="/ideate/ideas/surprise"
              className="card ea"
              id="ideation-surprise"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '18px 22px',
                textDecoration: 'none',
                cursor: 'pointer',
              }}
            >
              <span style={{ fontSize: 26, flexShrink: 0 }}>🎲</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 3 }}>Surprise me</div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>
                  Zero input — AI generates from market signals instantly
                </div>
              </div>
              <span style={{ color: '#63d9ff', fontSize: 18 }}>→</span>
            </Link>
          </div>
        </div>
      </div>
    </>
  )
}
