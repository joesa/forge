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
  /** Shorthand for the current access token (used by API interceptor) */
  readonly accessToken: string | null

  /* ── Actions ──────────────────────────────────────────────────── */
  setAuth: (user: User, tokens: AuthTokens) => void
  setUser: (user: User) => void
  setLoading: (loading: boolean) => void
  setAccessToken: (token: string) => void
  logout: () => void
}

/* ── Synchronous localStorage bootstrap ───────────────────────── */
/* Zustand persist rehydrates via Promise.resolve() which is async */
/* (microtask). By reading localStorage directly during module     */
/* init, the store's INITIAL state already contains persisted      */
/* auth data — zero delay, zero race conditions.                   */

function getPersistedAuth(): { user: User | null; tokens: AuthTokens | null } {
  try {
    const raw = localStorage.getItem('forge-auth')
    if (raw) {
      const parsed = JSON.parse(raw) as { state?: { user?: User; tokens?: AuthTokens } }
      if (parsed?.state?.user && parsed?.state?.tokens) {
        return { user: parsed.state.user, tokens: parsed.state.tokens }
      }
    }
  } catch {
    // localStorage unavailable or corrupt — start fresh
  }
  return { user: null, tokens: null }
}

const bootstrapped = getPersistedAuth()

/* ── Store ─────────────────────────────────────────────────────── */

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Use synchronously-bootstrapped values as initial state
      user: bootstrapped.user,
      tokens: bootstrapped.tokens,
      isLoading: false,

      get accessToken() {
        return get().tokens?.accessToken ?? null
      },

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

      setAccessToken: (token) => {
        const currentTokens = get().tokens
        if (currentTokens) {
          set({ tokens: { ...currentTokens, accessToken: token } })
        }
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
