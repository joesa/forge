import { Link } from 'react-router-dom'
import TopNav from '@/components/layout/TopNav'

const stats = [
  { value: '26+', label: 'AI Agents' },
  { value: '10', label: 'Reliability Layers' },
  { value: '12', label: 'Validation Gates' },
  { value: '0', label: 'Broken Builds' },
  { value: '1M+', label: 'Req/Day' },
  { value: '<700ms', label: 'Preview' },
]

const pricingPlans = [
  {
    name: 'Free',
    price: '$0',
    features: ['3 projects', '100k tokens / month', 'Community support', 'Shared sandbox', 'Basic templates'],
    cta: 'Get Started',
    featured: false,
  },
  {
    name: 'Pro',
    price: '$49',
    tag: 'MOST POPULAR',
    features: ['Unlimited projects', '2M tokens / month', 'Priority support', 'Dedicated sandbox', 'All templates', 'Custom domains', 'Team collaboration'],
    cta: 'Start Pro Trial',
    featured: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    features: ['Everything in Pro', 'Unlimited tokens', 'Dedicated account manager', 'SLA guarantee', 'SSO / SAML', 'On-prem option', 'Custom integrations'],
    cta: 'Contact Sales',
    featured: false,
  },
]

export default function LandingPage() {
  return (
    <>
      {/* Background */}
      <div className="grid-bg" aria-hidden="true" />
      <div className="orb" style={{ width: 700, height: 700, top: '-10%', right: '-8%', background: 'rgba(176,107,255,0.04)' }} aria-hidden="true" />
      <div className="orb" style={{ width: 550, height: 550, bottom: '-5%', left: '-6%', background: 'rgba(99,217,255,0.04)' }} aria-hidden="true" />
      <div className="orb" style={{ width: 350, height: 350, top: '40%', left: '45%', background: 'rgba(255,107,53,0.03)' }} aria-hidden="true" />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <TopNav variant="landing" />

        {/* Hero Section — 100vh*/}
        <section
          id="hero-section"
          style={{
            minHeight: 'calc(100vh - 62px)',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <div style={{ maxWidth: 1160, margin: '0 auto', padding: '100px 32px 72px' }}>
            {/* Eyebrow */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
              <div style={{ width: 28, height: 1, background: '#63d9ff' }} />
              <span
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10,
                  letterSpacing: 3,
                  textTransform: 'uppercase',
                  color: '#63d9ff',
                }}
              >
                AI-Native Development Platform
              </span>
            </div>

            {/* Hero title */}
            <h1
              id="hero-title"
              style={{
                fontSize: 'clamp(48px, 6.5vw, 86px)',
                fontWeight: 800,
                letterSpacing: '-3px',
                lineHeight: 0.92,
                color: '#e8e8f0',
                marginBottom: 24,
              }}
            >
              Build anything.
              <br />
              <span style={{ fontFamily: "'Instrument Serif', serif", fontStyle: 'italic', color: '#63d9ff' }}>Ship</span>{' '}
              <span style={{ color: '#ff6b35' }}>everything.</span>
            </h1>

            {/* Subtitle */}
            <p
              style={{
                fontSize: 16,
                color: 'rgba(232,232,240,0.45)',
                maxWidth: 580,
                lineHeight: 1.7,
                marginBottom: 34,
              }}
            >
              FORGE takes your idea through a C-Suite of AI agents, a 10-layer
              reliability system, and delivers a live production application —
              zero broken builds, guaranteed.
            </p>

            {/* CTA row */}
            <div style={{ display: 'flex', gap: 11, flexWrap: 'wrap' }}>
              <Link to="/register" className="btn btn-primary btn-lg" id="hero-cta-build">
                Start Building →
              </Link>
              <Link to="/ideate" className="btn btn-ghost btn-lg" id="hero-cta-idea">
                💡 Generate an Idea
              </Link>
            </div>

            {/* Stats row */}
            <div
              id="hero-stats"
              style={{
                display: 'flex',
                gap: 36,
                paddingTop: 40,
                borderTop: '1px solid rgba(255,255,255,0.06)',
                marginTop: 52,
                flexWrap: 'wrap',
              }}
            >
              {stats.map((stat) => (
                <div key={stat.label}>
                  <div
                    style={{
                      fontSize: 28,
                      fontWeight: 800,
                      letterSpacing: '-1px',
                      background: 'linear-gradient(135deg, #63d9ff, #3dffa0)',
                      WebkitBackgroundClip: 'text',
                      WebkitTextFillColor: 'transparent',
                    }}
                  >
                    {stat.value}
                  </div>
                  <div
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 10,
                      color: 'rgba(232,232,240,0.42)',
                    }}
                  >
                    {stat.label}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Three Paths Section */}
        <section
          id="paths-section"
          style={{
            background: '#0d0d1f',
            borderTop: '1px solid rgba(255,255,255,0.06)',
            padding: '72px 0',
          }}
        >
          <div style={{ maxWidth: 1160, margin: '0 auto', padding: '0 32px' }}>
            <div className="section-tag" style={{ color: '#ff6b35' }}>Core Flow</div>
            <h2 style={{ fontSize: 'clamp(24px, 3.2vw, 34px)', fontWeight: 800, letterSpacing: '-1.2px', marginBottom: 28, color: '#e8e8f0' }}>
              Every path leads to production
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              {/* Card 1 — forge accent */}
              <Link to="/projects/new" className="card fa" id="path-card-prompt" style={{ textDecoration: 'none', cursor: 'pointer' }}>
                <div style={{ fontSize: 22, marginBottom: 9 }}>✍️</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#e8e8f0', marginBottom: 6 }}>Direct Prompt</div>
                <div style={{ fontSize: 12, color: 'rgba(232,232,240,0.45)', lineHeight: 1.6, marginBottom: 12 }}>
                  Describe your app. AI optionally enriches it before the pipeline.
                </div>
                <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                  <span className="tag tag-f">Instant</span>
                  <span className="tag tag-j">AI Enhancement</span>
                </div>
              </Link>

              {/* Card 2 — violet accent */}
              <Link to="/ideate" className="card va" id="path-card-ideate" style={{ textDecoration: 'none', cursor: 'pointer' }}>
                <div style={{ fontSize: 22, marginBottom: 9 }}>💡</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#e8e8f0', marginBottom: 6 }}>AI Ideation Engine</div>
                <div style={{ fontSize: 12, color: 'rgba(232,232,240,0.45)', lineHeight: 1.6, marginBottom: 12 }}>
                  8 adaptive questions, all skippable → 5 unique high-value ideas.
                </div>
                <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                  <span className="tag tag-v">5 Ideas</span>
                  <span className="tag tag-g">Skippable Q&A</span>
                  <span className="tag tag-e">Private 7d</span>
                </div>
              </Link>

              {/* Card 3 — ember accent */}
              <Link to="/ideate" className="card ea" id="path-card-random" style={{ textDecoration: 'none', cursor: 'pointer' }}>
                <div style={{ fontSize: 22, marginBottom: 9 }}>🎲</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#e8e8f0', marginBottom: 6 }}>Full AI Generation</div>
                <div style={{ fontSize: 12, color: 'rgba(232,232,240,0.45)', lineHeight: 1.6, marginBottom: 12 }}>
                  Zero input. AI generates ideas from live market signals.
                </div>
                <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                  <span className="tag tag-e">Zero Input</span>
                  <span className="tag tag-f">Market-Aware</span>
                </div>
              </Link>
            </div>
          </div>
        </section>

        {/* Preview System Highlight */}
        <section id="preview-section" style={{ maxWidth: 1160, margin: '0 auto', padding: '0 32px 72px' }}>
          <div
            style={{
              background: 'linear-gradient(135deg, rgba(99,217,255,0.04), rgba(176,107,255,0.03))',
              border: '1px solid rgba(99,217,255,0.14)',
              borderRadius: 16,
              padding: 36,
              marginTop: 72,
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, alignItems: 'center' }}>
              <div>
                <div className="section-tag" style={{ color: '#3dffa0' }}>Live Preview System</div>
                <h2 style={{ fontSize: 26, fontWeight: 800, color: '#e8e8f0', marginBottom: 18, letterSpacing: '-0.5px' }}>
                  Watch your app take shape in real time
                </h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                  {[
                    'HMR live reload <700ms after file save',
                    'Build snapshot timeline — 10 screenshots per build',
                    'Click-to-annotate overlay with AI context',
                    'Dev console (logs, network, errors, source maps)',
                    'Shareable preview links (24h, no auth required)',
                  ].map((item) => (
                    <div key={item} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'rgba(232,232,240,0.55)' }}>
                      <span style={{ color: '#3dffa0', fontWeight: 700 }}>✓</span>
                      {item}
                    </div>
                  ))}
                </div>
                <Link to="/projects/test/editor" className="btn btn-secondary" style={{ marginTop: 20 }} id="preview-cta">
                  See Editor Preview →
                </Link>
              </div>
              <div
                style={{
                  background: '#080812',
                  borderRadius: 10,
                  border: '1px solid rgba(255,255,255,0.06)',
                  height: 260,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  overflow: 'hidden',
                }}
              >
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 36, marginBottom: 8 }}>⬡</div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.25)' }}>
                    LIVE PREVIEW
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Pricing Section */}
        <section id="pricing-section" style={{ padding: '72px 0' }}>
          <div style={{ maxWidth: 1160, margin: '0 auto', padding: '0 32px' }}>
            <div className="section-tag" style={{ color: '#ff6b35' }}>Pricing</div>
            <h2 style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-1.2px', marginBottom: 28, color: '#e8e8f0' }}>
              Simple, transparent pricing
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              {pricingPlans.map((plan) => (
                <div
                  key={plan.name}
                  className="card"
                  id={`pricing-${plan.name.toLowerCase()}`}
                  style={{
                    ...(plan.featured
                      ? {
                          border: '2px solid #63d9ff',
                          transform: 'scale(1.02)',
                          background: 'linear-gradient(135deg, rgba(99,217,255,0.06), #0d0d1f)',
                        }
                      : {}),
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0' }}>{plan.name}</div>
                    {plan.tag && <span className="tag tag-f">{plan.tag}</span>}
                  </div>
                  <div style={{ marginBottom: 14 }}>
                    <span style={{ fontSize: 30, fontWeight: 800, color: '#63d9ff', letterSpacing: '-1px' }}>{plan.price}</span>
                    {plan.price !== 'Custom' && (
                      <span style={{ fontSize: 14, fontWeight: 400, color: 'rgba(232,232,240,0.40)' }}>/month</span>
                    )}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 18 }}>
                    {plan.features.map((feature) => (
                      <div key={feature} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 11, color: 'rgba(232,232,240,0.50)' }}>
                        <span style={{ color: '#3dffa0' }}>✓</span>
                        {feature}
                      </div>
                    ))}
                  </div>
                  <Link
                    to={plan.featured ? '/register' : '/register'}
                    className={`btn ${plan.featured ? 'btn-primary' : 'btn-ghost'}`}
                    style={{ width: '100%', textDecoration: 'none' }}
                  >
                    {plan.cta}
                  </Link>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer
          style={{
            borderTop: '1px solid rgba(255,255,255,0.06)',
            padding: '36px 32px',
            textAlign: 'center',
          }}
        >
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.25)' }}>
            © 2026 FORGE. AI-native development platform.
          </div>
        </footer>
      </div>
    </>
  )
}
