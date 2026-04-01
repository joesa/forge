/* ------------------------------------------------------------------ */
/*  FORGE — Auth Store (Zustand)                                       */
/*  Manages authentication state, tokens, and session persistence.     */
/* ------------------------------------------------------------------ */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'

/* ── Types ────────────────────────────────────────────────────────── */

interface AuthTokens {
  accessToken: string
  refreshToken: string
}

interface AuthState {
  /** Current authenticated user, or null if logged out */
  user: User | null
  /** JWT tokens — persisted in localStorage */
  tokens: AuthTokens | null
  /** Whether an auth check is in flight (e.g. token refresh) */
  isLoading: boolean

  /* ── Computed ──────────────────────────────────────────────────── */
  isAuthenticated: () => boolean

  /* ── Actions ──────────────────────────────────────────────────── */
  setAuth: (user: User, tokens: AuthTokens) => void
  setUser: (user: User) => void
  setLoading: (loading: boolean) => void
  logout: () => void
}

/* ── Store ─────────────────────────────────────────────────────── */

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      tokens: null,
      isLoading: false,

      isAuthenticated: () => {
        const { tokens, user } = get()
        return tokens !== null && user !== null
      },

      setAuth: (user, tokens) => {
        set({ user, tokens, isLoading: false })
      },

      setUser: (user) => {
        set({ user })
      },

      setLoading: (isLoading) => {
        set({ isLoading })
      },

      logout: () => {
        set({ user: null, tokens: null, isLoading: false })
      },
    }),
    {
      name: 'forge-auth',
      // Only persist tokens and user to localStorage
      partialize: (state) => ({
        user: state.user,
        tokens: state.tokens,
      }),
    },
  ),
)
