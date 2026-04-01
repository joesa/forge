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
 * If the user is not authenticated, they are redirected to `/login`
 * with the original URL saved in `location.state.from` so the login
 * page can redirect back after a successful sign-in.
 */
export default function RequireAuth({ children }: RequireAuthProps) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
