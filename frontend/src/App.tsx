import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import RequireAuth from '@/components/auth/RequireAuth'

/* ------------------------------------------------------------------ */
/*  Lazy-load all page components                                      */
/* ------------------------------------------------------------------ */
const LandingPage = lazy(() => import('@/pages/LandingPage'))
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))
const OnboardingPage = lazy(() => import('@/pages/OnboardingPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const ProjectsPage = lazy(() => import('@/pages/ProjectsPage'))
const NewProjectPage = lazy(() => import('@/pages/NewProjectPage'))
const IdeationPage = lazy(() => import('@/pages/IdeationPage'))
const QuestionnairePage = lazy(() => import('@/pages/QuestionnairePage'))
const IdeasPage = lazy(() => import('@/pages/IdeasPage'))
const PipelinePage = lazy(() => import('@/pages/PipelinePage'))
const EditorPage = lazy(() => import('@/pages/EditorPage'))

/* Settings */
const ProfilePage = lazy(() => import('@/pages/settings/ProfilePage'))
const AIProvidersPage = lazy(() => import('@/pages/settings/AIProvidersPage'))
const ModelRoutingPage = lazy(() => import('@/pages/settings/ModelRoutingPage'))
const IntegrationsPage = lazy(() => import('@/pages/settings/IntegrationsPage'))
const ApiKeysPage = lazy(() => import('@/pages/settings/ApiKeysPage'))
const SecurityPage = lazy(() => import('@/pages/settings/SecurityPage'))
const BillingPage = lazy(() => import('@/pages/settings/BillingPage'))

/* ------------------------------------------------------------------ */
/*  Loading fallback that matches the FORGE dark theme                 */
/* ------------------------------------------------------------------ */
function LoadingFallback() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: '#04040a',
      }}
    >
      <div style={{ textAlign: 'center' }}>
        <div
          style={{
            width: 36,
            height: 36,
            margin: '0 auto 14px',
            background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
            clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)',
            animation: 'pulse-f 1.8s ease-in-out infinite',
          }}
        />
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            color: 'rgba(232,232,240,0.30)',
            letterSpacing: 2,
            textTransform: 'uppercase',
          }}
        >
          Loading...
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Router                                                             */
/* ------------------------------------------------------------------ */
function App() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        {/* Public / Landing */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />

        {/* Main App — requires authentication */}
        <Route path="/dashboard" element={<RequireAuth><DashboardPage /></RequireAuth>} />
        <Route path="/projects" element={<RequireAuth><ProjectsPage /></RequireAuth>} />
        <Route path="/projects/new" element={<RequireAuth><NewProjectPage /></RequireAuth>} />
        <Route path="/projects/:id/editor" element={<RequireAuth><EditorPage /></RequireAuth>} />

        {/* Ideation — requires authentication */}
        <Route path="/ideate" element={<RequireAuth><IdeationPage /></RequireAuth>} />
        <Route path="/ideate/questionnaire/:id" element={<RequireAuth><QuestionnairePage /></RequireAuth>} />
        <Route path="/ideate/ideas/:id" element={<RequireAuth><IdeasPage /></RequireAuth>} />

        {/* Pipeline — requires authentication */}
        <Route path="/pipeline/:id" element={<RequireAuth><PipelinePage /></RequireAuth>} />

        {/* Settings — requires authentication */}
        <Route path="/settings/profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
        <Route path="/settings/ai-providers" element={<RequireAuth><AIProvidersPage /></RequireAuth>} />
        <Route path="/settings/model-routing" element={<RequireAuth><ModelRoutingPage /></RequireAuth>} />
        <Route path="/settings/integrations" element={<RequireAuth><IntegrationsPage /></RequireAuth>} />
        <Route path="/settings/api-keys" element={<RequireAuth><ApiKeysPage /></RequireAuth>} />
        <Route path="/settings/security" element={<RequireAuth><SecurityPage /></RequireAuth>} />
        <Route path="/settings/billing" element={<RequireAuth><BillingPage /></RequireAuth>} />

        {/* Fallback — redirect to landing */}
        <Route path="*" element={<LandingPage />} />
      </Routes>
    </Suspense>
  )
}

export default App
