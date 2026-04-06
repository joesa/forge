/* ------------------------------------------------------------------ */
/*  FORGE — RequireAuth Guard                                          */
/*  Wraps protected routes; redirects unauthenticated users to /login. */
/* ------------------------------------------------------------------ */

import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

interface RequireAuthProps {
  children: React.ReactNode
}

/**
 * Route guard that checks the auth store for a valid session.
 *
 * The auth store is bootstrapped synchronously from localStorage
 * during module init (see authStore.ts), so isAuthenticated()
 * returns the correct value on the very first render — no
 * hydration delay, no race conditions.
 */
export default function RequireAuth({ children }: RequireAuthProps) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())
  const token = useAuthStore((s) => s.tokens?.accessToken)
  const location = useLocation()

  // In production, dev-mode tokens are not valid — force re-login
  if (import.meta.env.PROD && token?.startsWith('dev-')) {
    useAuthStore.getState().logout()
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
