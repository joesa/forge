import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { projectsApi, pipelineApi } from '@/lib/api'

const cloudServices = ['Supabase', 'Stripe', 'OpenAI', 'Resend', 'Twilio', 'AWS S3', 'Cloudflare', 'Auth0', 'Pinecone', 'SendGrid']
const frameworks = ['Next.js', 'React + Vite', 'Remix', 'FastAPI + React']
const frameworkApiValues: Record<string, string> = {
  'Next.js': 'nextjs',
  'React + Vite': 'react_vite',
  'Remix': 'remix',
  'FastAPI + React': 'fastapi_react',
}

export default function NewProjectPage() {
  const [path, setPath] = useState<'prompt' | 'ideate' | null>(null)
  const [prompt, setPrompt] = useState('')
  const [aiEnhance, setAiEnhance] = useState(true)
  const [selectedServices, setSelectedServices] = useState<string[]>([])
  const [selectedFramework, setSelectedFramework] = useState('Next.js')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const navigate = useNavigate()

  const handleStartBuild = async () => {
    if (!prompt.trim() || isSubmitting) return
    setIsSubmitting(true)
    try {
      const name = prompt.trim().split('\n')[0].slice(0, 80)
      const frameworkValue = frameworkApiValues[selectedFramework] ?? 'react_vite'
      const projectRes = await projectsApi.create({
        name,
        description: prompt,
        framework: frameworkValue,
      })
      const projectId = projectRes.data.id as string
      const pipelineRes = await pipelineApi.run({
        project_id: projectId,
        idea_spec: {
          prompt,
          framework: frameworkValue,
          cloud_services: selectedServices,
          ai_enhance: aiEnhance,
        },
      })
      navigate(`/pipeline/${pipelineRes.data.pipeline_id as string}`)
    } catch (err) {
      console.error('Failed to start build:', err)
      setIsSubmitting(false)
    }
  }

  const toggleService = (s: string) => {
    setSelectedServices((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    )
  }

  return (
    <AppShell>
      <div style={{ padding: '34px 32px', maxWidth: 800, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
          <Link to="/projects" className="btn btn-ghost btn-sm" style={{ textDecoration: 'none' }}>← Projects</Link>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: '#e8e8f0' }}>New Project</h1>
          <span className="tag tag-m" style={{ fontSize: 8 }}>/projects/new</span>
        </div>

        {/* Two-path choice */}
        <div id="path-choice" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 24 }}>
          <button
            id="path-prompt"
            onClick={() => setPath('prompt')}
            style={{
              textAlign: 'center',
              padding: 26,
              background: path === 'prompt' ? 'rgba(99,217,255,0.08)' : '#0d0d1f',
              border: `2px solid ${path === 'prompt' ? '#63d9ff' : 'rgba(255,255,255,0.06)'}`,
              borderRadius: 12,
              cursor: 'pointer',
              transition: 'all 200ms',
              color: '#e8e8f0',
            }}
          >
            <div style={{ fontSize: 28, marginBottom: 9 }}>✍️</div>
            <div style={{ fontSize: 13, fontWeight: 700 }}>I have an idea</div>
          </button>
          <Link
            to="/ideate"
            id="path-ideate"
            style={{
              textAlign: 'center',
              padding: 26,
              background: '#0d0d1f',
              border: '2px solid rgba(255,255,255,0.06)',
              borderRadius: 12,
              cursor: 'pointer',
              textDecoration: 'none',
              color: '#e8e8f0',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 200ms',
            }}
          >
            <div style={{ fontSize: 28, marginBottom: 9 }}>💡</div>
            <div style={{ fontSize: 13, fontWeight: 700 }}>Generate an idea</div>
          </Link>
        </div>

        {path === 'prompt' && (
          <div style={{ animation: 'fade-in 280ms ease' }}>
            {/* Prompt textarea */}
            <div style={{ marginBottom: 18 }}>
              <label className="lbl" htmlFor="project-prompt">DESCRIBE YOUR APPLICATION</label>
              <textarea
                id="project-prompt"
                className="input"
                rows={5}
                style={{ height: 'auto', resize: 'none', padding: '12px 14px', lineHeight: 1.6 }}
                placeholder="Build a SaaS dashboard with user authentication, real-time analytics charts, team management, and billing with Stripe..."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value.slice(0, 2000))}
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.30)' }}>
                  {prompt.length} / 2000
                </span>
              </div>
            </div>

            {/* AI Enhancement toggle */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
                borderRadius: 8,
                padding: '11px 14px',
                marginBottom: 18,
              }}
            >
              <button
                id="ai-enhance-toggle"
                onClick={() => setAiEnhance(!aiEnhance)}
                style={{
                  width: 38,
                  height: 20,
                  borderRadius: 10,
                  background: aiEnhance ? '#63d9ff' : 'rgba(255,255,255,0.12)',
                  border: 'none',
                  position: 'relative',
                  cursor: 'pointer',
                  transition: 'background 200ms',
                  flexShrink: 0,
                }}
              >
                <div
                  style={{
                    width: 16,
                    height: 16,
                    borderRadius: '50%',
                    background: '#fff',
                    position: 'absolute',
                    top: 2,
                    left: aiEnhance ? 20 : 2,
                    transition: 'left 200ms',
                  }}
                />
              </button>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#e8e8f0' }}>AI Enhancement</div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>
                  Let AI expand and improve your prompt before building
                </div>
              </div>
            </div>

            {/* Cloud Services */}
            <div style={{ marginBottom: 18 }}>
              <label className="lbl">CLOUD SERVICES</label>
              <div id="cloud-services" style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
                {cloudServices.map((s) => {
                  const isSelected = selectedServices.includes(s)
                  return (
                    <button
                      key={s}
                      onClick={() => toggleService(s)}
                      style={{
                        padding: '5px 13px',
                        borderRadius: 6,
                        fontSize: 11,
                        fontWeight: 600,
                        cursor: 'pointer',
                        border: `1px solid ${isSelected ? '#63d9ff' : 'rgba(255,255,255,0.08)'}`,
                        color: isSelected ? '#63d9ff' : 'rgba(232,232,240,0.45)',
                        background: isSelected ? 'rgba(99,217,255,0.10)' : 'transparent',
                        transition: 'all 150ms',
                      }}
                    >
                      {s}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Framework selector */}
            <div style={{ marginBottom: 26 }}>
              <label className="lbl">FRAMEWORK</label>
              <div id="framework-selector" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                {frameworks.map((fw) => {
                  const isSelected = selectedFramework === fw
                  return (
                    <button
                      key={fw}
                      onClick={() => setSelectedFramework(fw)}
                      style={{
                        padding: '9px 7px',
                        borderRadius: 7,
                        textAlign: 'center',
                        fontSize: 10,
                        fontWeight: 600,
                        cursor: 'pointer',
                        border: `1px solid ${isSelected ? '#63d9ff' : 'rgba(255,255,255,0.07)'}`,
                        color: isSelected ? '#63d9ff' : 'rgba(232,232,240,0.45)',
                        background: isSelected ? 'rgba(99,217,255,0.08)' : 'transparent',
                        transition: 'all 150ms',
                      }}
                    >
                      {fw}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Submit */}
            <button
              className="btn btn-primary"
              id="start-build-btn"
              style={{ width: '100%', height: 50, fontSize: 14 }}
              disabled={!prompt.trim() || isSubmitting}
              onClick={handleStartBuild}
            >
              {isSubmitting ? 'Starting...' : 'Start Building →'}
            </button>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textAlign: 'center', color: 'rgba(232,232,240,0.30)', marginTop: 9 }}>
              Estimated build time: 8–15 minutes · Zero broken builds guaranteed
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
