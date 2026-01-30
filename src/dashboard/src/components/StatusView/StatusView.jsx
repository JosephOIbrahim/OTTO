import { useRef, useEffect } from 'react'

/**
 * StatusView - Original dashboard view extracted for toggle support
 *
 * Pentagram Rivian (70%) + Tendril (30%) design
 * Shows FULL system controls from CLAUDE.md substrate
 */

// ============================================================================
// DESIGN TOKENS - Pentagram Rivian inspired (shared with parent)
// ============================================================================

export const TOKENS = {
  colors: {
    bg: {
      primary: '#000000',
      secondary: '#0a0a0a',
      elevated: '#141414',
      card: '#0d0d0d'
    },
    text: {
      primary: '#ffffff',
      secondary: 'rgba(255,255,255,0.6)',
      muted: 'rgba(255,255,255,0.35)',
      dim: 'rgba(255,255,255,0.15)'
    },
    accent: {
      green: '#00d26a',
      yellow: '#fbbf24',
      orange: '#fb923c',
      red: '#f87171',
      blue: '#60a5fa',
      purple: '#a78bfa'
    },
    border: 'rgba(255,255,255,0.06)'
  },
  space: {
    xs: '8px',
    sm: '12px',
    md: '20px',
    lg: '32px',
    xl: '48px',
    xxl: '64px'
  },
  radius: {
    sm: '4px',
    md: '8px',
    lg: '12px'
  }
}

// ============================================================================
// FIXED STATE DEFINITIONS
// ============================================================================

export const STATES = {
  burnout: {
    GREEN: { color: TOKENS.colors.accent.green, label: 'GREEN' },
    YELLOW: { color: TOKENS.colors.accent.yellow, label: 'YELLOW' },
    ORANGE: { color: TOKENS.colors.accent.orange, label: 'ORANGE' },
    RED: { color: TOKENS.colors.accent.red, label: 'RED' }
  },
  mode: {
    work: { color: TOKENS.colors.accent.green, label: 'WORK' },
    delegate: { color: TOKENS.colors.accent.blue, label: 'DELEGATE' },
    protect: { color: TOKENS.colors.accent.purple, label: 'PROTECT' }
  },
  momentum: {
    cold_start: { progress: 0.1, label: 'COLD START' },
    building: { progress: 0.35, label: 'BUILDING' },
    rolling: { progress: 0.65, label: 'ROLLING' },
    peak: { progress: 1.0, label: 'PEAK' },
    crashed: { progress: 0.05, label: 'CRASHED' }
  },
  energy: {
    high: { level: 4, label: 'HIGH' },
    medium: { level: 3, label: 'MEDIUM' },
    low: { level: 2, label: 'LOW' },
    depleted: { level: 1, label: 'DEPLETED' }
  },
  altitude: {
    '30000ft': { label: '30K', desc: 'Vision' },
    '15000ft': { label: '15K', desc: 'Architecture' },
    '5000ft': { label: '5K', desc: 'Components' },
    'Ground': { label: 'GND', desc: 'Code' }
  },
  paradigm: {
    Cortex: { label: 'CORTEX', desc: 'Hierarchical' },
    Mycelium: { label: 'MYCELIUM', desc: 'Emergent' }
  },
  // === NEXUS 5-Phase States ===
  phase: {
    detect: { label: 'DETECT', desc: 'PRISM Signals' },
    cascade: { label: 'CASCADE', desc: 'Expert Routing' },
    lock: { label: 'LOCK', desc: 'Param Locking' },
    execute: { label: 'EXECUTE', desc: 'Work/Delegate' },
    update: { label: 'UPDATE', desc: 'Convergence' }
  },
  lockStatus: {
    unlocked: { label: 'UNLOCKED', color: TOKENS.colors.text.muted },
    locking: { label: 'LOCKING', color: TOKENS.colors.accent.yellow },
    locked: { label: 'LOCKED', color: TOKENS.colors.accent.green }
  },
  thinkDepth: {
    minimal: { label: 'MINIMAL', budget: '1K' },
    standard: { label: 'STANDARD', budget: '8K' },
    deep: { label: 'DEEP', budget: '32K' },
    ultradeep: { label: 'ULTRADEEP', budget: '128K' }
  },
  attractor: {
    focused: { label: 'FOCUSED', color: TOKENS.colors.accent.green },
    exploring: { label: 'EXPLORING', color: TOKENS.colors.accent.purple },
    recovery: { label: 'RECOVERY', color: TOKENS.colors.accent.orange },
    teaching: { label: 'TEACHING', color: TOKENS.colors.accent.blue }
  }
}

// ============================================================================
// EXPERT COLORS (Cognitive Safety MoE - 7 Intervention Experts)
// ============================================================================

export const EXPERT_COLORS = {
  validator: '#f87171',   // RED - safety/emotional
  scaffolder: '#fb923c',  // ORANGE - reducing overwhelm
  restorer: '#fbbf24',    // YELLOW - recovery
  refocuser: '#60a5fa',   // BLUE - redirect
  celebrator: '#00d26a',  // GREEN - win/dopamine
  socratic: '#a78bfa',    // PURPLE - exploration
  direct: 'rgba(255,255,255,0.6)'  // NEUTRAL - minimal
}

// ============================================================================
// STATUS VIEW COMPONENT
// ============================================================================

function StatusView({ state, time }) {
  const canvasRef = useRef(null)
  const animationRef = useRef(null)

  // Tendril wave animation
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1

    const resize = () => {
      canvas.width = canvas.offsetWidth * dpr
      canvas.height = canvas.offsetHeight * dpr
      ctx.scale(dpr, dpr)
    }
    resize()
    window.addEventListener('resize', resize)

    let frame = 0
    const burnoutState = STATES.burnout[state.burnout] || STATES.burnout.GREEN
    const momentumState = STATES.momentum[state.momentum] || STATES.momentum.rolling

    const animate = () => {
      const w = canvas.offsetWidth
      const h = canvas.offsetHeight

      ctx.clearRect(0, 0, w, h)

      ctx.beginPath()
      ctx.strokeStyle = burnoutState.color
      ctx.lineWidth = 1
      ctx.globalAlpha = 0.08 * momentumState.progress

      const baseY = h * 0.85
      const amp = 15 * momentumState.progress

      ctx.moveTo(0, baseY)
      for (let x = 0; x <= w; x += 4) {
        const y = baseY + Math.sin(x * 0.008 + frame * 0.015) * amp
        ctx.lineTo(x, y)
      }
      ctx.stroke()
      ctx.globalAlpha = 1

      frame++
      animationRef.current = requestAnimationFrame(animate)
    }

    animate()
    return () => {
      cancelAnimationFrame(animationRef.current)
      window.removeEventListener('resize', resize)
    }
  }, [state.burnout, state.momentum])

  const burnout = STATES.burnout[state.burnout] || STATES.burnout.GREEN
  const mode = STATES.mode[state.mode] || STATES.mode.work
  const momentum = STATES.momentum[state.momentum] || STATES.momentum.rolling
  const energy = STATES.energy[state.energy] || STATES.energy.high
  const altitude = STATES.altitude[state.altitude] || STATES.altitude['30000ft']
  const paradigm = STATES.paradigm[state.paradigm] || STATES.paradigm.Cortex

  return (
    <>
      <canvas ref={canvasRef} style={styles.canvas} />

      <div style={styles.content}>
        {/* Header */}
        <header style={styles.header}>
          <div style={styles.brand}>
            <span style={styles.brandName}>ORCHESTRA</span>
          </div>
          <div style={styles.headerRight}>
            <span style={styles.time}>
              {time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
            </span>
            <div style={{
              ...styles.connectionIndicator,
              backgroundColor: state.claudeConnected ? TOKENS.colors.accent.green : TOKENS.colors.text.dim
            }} />
          </div>
        </header>

        {/* Primary Status */}
        <section style={styles.primaryStatus}>
          <div style={styles.burnoutDisplay}>
            <span style={{ ...styles.burnoutValue, color: burnout.color }}>
              {burnout.label}
            </span>
            <span style={styles.burnoutLabel}>BURNOUT</span>
          </div>
        </section>

        {/* Mode Display */}
        <section style={styles.modeSection}>
          <div style={{ ...styles.modeIndicator, borderColor: mode.color }}>
            <span style={{ ...styles.modeValue, color: mode.color }}>{mode.label}</span>
          </div>
        </section>

        {/* Metrics Grid */}
        <section style={styles.metricsGrid}>
          <div style={styles.metric}>
            <span style={styles.metricLabel}>MOMENTUM</span>
            <div style={styles.progressContainer}>
              <div style={styles.progressTrack}>
                <div style={{
                  ...styles.progressFill,
                  width: `${momentum.progress * 100}%`,
                  backgroundColor: burnout.color
                }} />
              </div>
              <span style={styles.metricValue}>{momentum.label}</span>
            </div>
          </div>

          <div style={styles.metric}>
            <span style={styles.metricLabel}>ENERGY</span>
            <div style={styles.levelBars}>
              {[1, 2, 3, 4].map(i => (
                <div key={i} style={{
                  ...styles.levelBar,
                  backgroundColor: i <= energy.level ? burnout.color : TOKENS.colors.bg.elevated
                }} />
              ))}
            </div>
            <span style={styles.metricValue}>{energy.label}</span>
          </div>

          <div style={styles.metric}>
            <span style={styles.metricLabel}>WORKING MEMORY</span>
            <div style={styles.slots}>
              {[1, 2, 3].map(i => (
                <div key={i} style={{
                  ...styles.slot,
                  backgroundColor: i <= state.workingMemory ? burnout.color : TOKENS.colors.bg.elevated
                }} />
              ))}
            </div>
            <span style={styles.metricValue}>{state.workingMemory}/3</span>
          </div>

          <div style={styles.metric}>
            <span style={styles.metricLabel}>TANGENT BUDGET</span>
            <span style={styles.metricValueLarge}>{state.tangentBudget}</span>
            <span style={styles.metricValue}>OF 5</span>
          </div>

          <div style={styles.metric}>
            <span style={styles.metricLabel}>ALTITUDE</span>
            <span style={styles.metricValueLarge}>{altitude.label}</span>
            <span style={styles.metricValue}>{altitude.desc.toUpperCase()}</span>
          </div>

          <div style={styles.metric}>
            <span style={styles.metricLabel}>PARADIGM</span>
            <span style={styles.metricValueLarge}>{paradigm.label}</span>
            <span style={styles.metricValue}>{paradigm.desc.toUpperCase()}</span>
          </div>
        </section>

        {/* Current Task */}
        {state.currentTask && (
          <section style={styles.taskSection}>
            <span style={styles.taskLabel}>CURRENT TASK</span>
            <span style={styles.taskText}>{state.currentTask}</span>
          </section>
        )}

        {/* Footer */}
        <footer style={styles.footer}>
          <span style={styles.version}>v4.3.0</span>
          <span style={styles.footerText}>
            {state.claudeConnected ? 'CLAUDE CODE CONNECTED' : 'DISCONNECTED'}
          </span>
        </footer>
      </div>
    </>
  )
}

// ============================================================================
// STYLES
// ============================================================================

const styles = {
  canvas: {
    position: 'absolute',
    inset: 0,
    width: '100%',
    height: '100%',
    pointerEvents: 'none'
  },

  content: {
    position: 'relative',
    width: '100%',
    maxWidth: '600px',
    padding: TOKENS.space.xl,
    display: 'flex',
    flexDirection: 'column',
    gap: TOKENS.space.xl
  },

  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingBottom: TOKENS.space.md
  },

  brand: {
    display: 'flex',
    alignItems: 'center'
  },

  brandName: {
    fontSize: '14px',
    fontWeight: '500',
    letterSpacing: '0.2em',
    color: TOKENS.colors.text.secondary
  },

  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: TOKENS.space.md
  },

  time: {
    fontSize: '14px',
    fontWeight: '400',
    fontFamily: '"JetBrains Mono", "SF Mono", monospace',
    color: TOKENS.colors.text.muted,
    letterSpacing: '0.05em'
  },

  connectionIndicator: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    transition: 'background-color 0.3s ease'
  },

  primaryStatus: {
    display: 'flex',
    justifyContent: 'center',
    padding: `${TOKENS.space.xxl} 0`
  },

  burnoutDisplay: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: TOKENS.space.sm
  },

  burnoutValue: {
    fontSize: '72px',
    fontWeight: '300',
    fontFamily: '"JetBrains Mono", monospace',
    letterSpacing: '-0.02em',
    lineHeight: 1,
    transition: 'color 0.5s ease'
  },

  burnoutLabel: {
    fontSize: '11px',
    fontWeight: '500',
    letterSpacing: '0.15em',
    color: TOKENS.colors.text.muted
  },

  modeSection: {
    display: 'flex',
    justifyContent: 'center',
    paddingBottom: TOKENS.space.lg
  },

  modeIndicator: {
    padding: `${TOKENS.space.sm} ${TOKENS.space.lg}`,
    border: '1px solid',
    borderRadius: TOKENS.radius.md,
    transition: 'border-color 0.3s ease'
  },

  modeValue: {
    fontSize: '13px',
    fontWeight: '600',
    letterSpacing: '0.15em',
    transition: 'color 0.3s ease'
  },

  metricsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: TOKENS.space.md
  },

  metric: {
    backgroundColor: TOKENS.colors.bg.card,
    border: `1px solid ${TOKENS.colors.border}`,
    borderRadius: TOKENS.radius.lg,
    padding: TOKENS.space.md,
    display: 'flex',
    flexDirection: 'column',
    gap: TOKENS.space.sm
  },

  metricLabel: {
    fontSize: '9px',
    fontWeight: '500',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted
  },

  metricValue: {
    fontSize: '10px',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.text.secondary,
    letterSpacing: '0.05em'
  },

  metricValueLarge: {
    fontSize: '24px',
    fontWeight: '400',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.text.primary,
    letterSpacing: '-0.02em'
  },

  progressContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: TOKENS.space.xs
  },

  progressTrack: {
    height: '4px',
    backgroundColor: TOKENS.colors.bg.elevated,
    borderRadius: '2px',
    overflow: 'hidden'
  },

  progressFill: {
    height: '100%',
    borderRadius: '2px',
    transition: 'width 0.5s ease, background-color 0.3s ease'
  },

  levelBars: {
    display: 'flex',
    gap: '4px'
  },

  levelBar: {
    width: '20px',
    height: '20px',
    borderRadius: TOKENS.radius.sm,
    transition: 'background-color 0.3s ease'
  },

  slots: {
    display: 'flex',
    gap: '6px'
  },

  slot: {
    width: '24px',
    height: '24px',
    borderRadius: TOKENS.radius.sm,
    transition: 'background-color 0.3s ease'
  },

  taskSection: {
    backgroundColor: TOKENS.colors.bg.card,
    border: `1px solid ${TOKENS.colors.border}`,
    borderRadius: TOKENS.radius.lg,
    padding: TOKENS.space.md,
    display: 'flex',
    flexDirection: 'column',
    gap: TOKENS.space.xs
  },

  taskLabel: {
    fontSize: '9px',
    fontWeight: '500',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted
  },

  taskText: {
    fontSize: '13px',
    color: TOKENS.colors.text.secondary,
    lineHeight: 1.5
  },

  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: TOKENS.space.lg,
    borderTop: `1px solid ${TOKENS.colors.border}`
  },

  version: {
    fontSize: '10px',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.text.dim,
    letterSpacing: '0.05em'
  },

  footerText: {
    fontSize: '9px',
    fontWeight: '500',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.dim
  }
}

export default StatusView
