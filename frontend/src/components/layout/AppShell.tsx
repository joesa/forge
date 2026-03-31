import TopNav from './TopNav'
import Sidebar from './Sidebar'

interface AppShellProps {
  children: React.ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <>
      {/* Background decoration */}
      <div className="grid-bg" aria-hidden="true" />
      <div className="orb" style={{ width: 700, height: 700, top: '-10%', right: '-8%', background: 'rgba(176,107,255,0.04)' }} aria-hidden="true" />
      <div className="orb" style={{ width: 550, height: 550, bottom: '-5%', left: '-6%', background: 'rgba(99,217,255,0.04)' }} aria-hidden="true" />
      <div className="orb" style={{ width: 350, height: 350, top: '40%', left: '45%', background: 'rgba(255,107,53,0.03)' }} aria-hidden="true" />

      <div style={{ position: 'relative', zIndex: 1, minHeight: '100vh' }}>
        <TopNav variant="authenticated" />
        <Sidebar />
        <main
          style={{
            marginLeft: 220,
            paddingTop: 0,
            minHeight: 'calc(100vh - 62px)',
          }}
        >
          {children}
        </main>
      </div>
    </>
  )
}
