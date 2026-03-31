import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'

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

        {/* Main App */}
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/new" element={<NewProjectPage />} />
        <Route path="/projects/:id/editor" element={<EditorPage />} />

        {/* Ideation */}
        <Route path="/ideate" element={<IdeationPage />} />
        <Route path="/ideate/questionnaire/:id" element={<QuestionnairePage />} />
        <Route path="/ideate/ideas/:id" element={<IdeasPage />} />

        {/* Pipeline */}
        <Route path="/pipeline/:id" element={<PipelinePage />} />

        {/* Settings */}
        <Route path="/settings/profile" element={<ProfilePage />} />
        <Route path="/settings/ai-providers" element={<AIProvidersPage />} />
        <Route path="/settings/model-routing" element={<ModelRoutingPage />} />
        <Route path="/settings/integrations" element={<IntegrationsPage />} />
        <Route path="/settings/api-keys" element={<ApiKeysPage />} />
        <Route path="/settings/security" element={<SecurityPage />} />
        <Route path="/settings/billing" element={<BillingPage />} />

        {/* Fallback — redirect to landing */}
        <Route path="*" element={<LandingPage />} />
      </Routes>
    </Suspense>
  )
}

export default App
