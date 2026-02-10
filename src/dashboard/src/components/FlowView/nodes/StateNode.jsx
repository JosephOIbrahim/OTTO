import { Handle, Position } from '@xyflow/react'
import { TOKENS, STATES } from '../../StatusView/StatusView'

/**
 * StateNode - DETECT Phase Visualization (Phase 1 of NEXUS)
 *
 * Shows:
 * - PRISM signal extraction (emotional, mode, domain, task)
 * - Cognitive state: burnout, energy, momentum
 * - Color-coded border by burnout level
 * - Glow animation when highlighted (active phase)
 *
 * FIXED signal priority
 * emotional > mode > domain > task
 */

// Signal priority display (highest first)
const SIGNAL_PRIORITY = [
  { key: 'emotional', label: 'EMOTIONAL', color: TOKENS.colors.accent.red },
  { key: 'mode', label: 'MODE', color: TOKENS.colors.accent.purple },
  { key: 'domain', label: 'DOMAIN', color: TOKENS.colors.accent.blue },
  { key: 'task', label: 'TASK', color: TOKENS.colors.accent.green }
]

function StateNode({ data }) {
  const {
    burnout,
    energy,
    momentum,
    highlighted,
    burnoutColor,
    // PRISM signals
    signalsEmotional = null,
    signalsMode = null,
    signalsDomain = null,
    signalsTask = null
  } = data

  const burnoutState = STATES.burnout[burnout] || STATES.burnout.GREEN
  const energyState = STATES.energy[energy] || STATES.energy.high
  const momentumState = STATES.momentum[momentum] || STATES.momentum.rolling

  // Build signals map
  const signals = {
    emotional: signalsEmotional,
    mode: signalsMode,
    domain: Array.isArray(signalsDomain) ? signalsDomain.join('|') : signalsDomain,
    task: signalsTask
  }

  // Check if any signals are active
  const hasActiveSignals = Object.values(signals).some(v => v)

  // Input handle for feedback loop
  const hasFeedbackInput = true

  return (
    <div style={{
      ...styles.container,
      borderColor: burnoutColor,
      boxShadow: highlighted
        ? `0 0 20px ${burnoutColor}40, 0 0 40px ${burnoutColor}20`
        : 'none'
    }}>
      {/* Input Handle - for feedback loop from UPDATE */}
      {hasFeedbackInput && (
        <Handle
          id="feedback"
          type="target"
          position={Position.Left}
          style={{ ...styles.handle, top: '50%' }}
        />
      )}

      {/* Phase Label */}
      <div style={styles.phaseLabel}>
        <span style={styles.phaseDot} />
        DETECT PHASE
      </div>

      {/* PRISM Signals Section */}
      <div style={styles.signalsSection}>
        <div style={styles.signalsHeader}>PRISM SIGNALS</div>
        <div style={styles.signalsList}>
          {SIGNAL_PRIORITY.map(sig => {
            const value = signals[sig.key]
            const isActive = !!value
            return (
              <div key={sig.key} style={styles.signalRow}>
                <span style={{
                  ...styles.signalLabel,
                  color: isActive ? sig.color : TOKENS.colors.text.dim
                }}>
                  {sig.label}
                </span>
                <span style={{
                  ...styles.signalValue,
                  backgroundColor: isActive ? `${sig.color}20` : TOKENS.colors.bg.elevated,
                  color: isActive ? sig.color : TOKENS.colors.text.dim
                }}>
                  {isActive ? value : '────────'}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Separator */}
      <div style={styles.separator} />

      {/* State Metrics */}
      <div style={styles.metricsGrid}>
        <div style={styles.metricRow}>
          <span style={styles.metricLabel}>BURNOUT</span>
          <span style={{ ...styles.metricValue, color: burnoutColor }}>
            {burnoutState.label}
          </span>
        </div>

        <div style={styles.metricRow}>
          <span style={styles.metricLabel}>ENERGY</span>
          <div style={styles.energyBars}>
            {[1, 2, 3, 4].map(i => (
              <div
                key={i}
                style={{
                  ...styles.energyBar,
                  backgroundColor: i <= energyState.level
                    ? burnoutColor
                    : TOKENS.colors.bg.elevated
                }}
              />
            ))}
          </div>
        </div>

        <div style={styles.metricRow}>
          <span style={styles.metricLabel}>MOMENTUM</span>
          <div style={styles.momentumContainer}>
            <div style={styles.progressTrack}>
              <div style={{
                ...styles.progressFill,
                width: `${momentumState.progress * 100}%`,
                backgroundColor: burnoutColor
              }} />
            </div>
            <span style={styles.momentumLabel}>{momentumState.label}</span>
          </div>
        </div>
      </div>

      {/* Output Handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        style={styles.handle}
      />
    </div>
  )
}

const styles = {
  container: {
    background: TOKENS.colors.bg.card,
    border: '2px solid',
    borderRadius: '8px',
    padding: '12px',
    minWidth: '180px',
    fontFamily: '"Space Grotesk", sans-serif',
    transition: 'box-shadow 0.3s ease, border-color 0.3s ease'
  },

  phaseLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    fontSize: '8px',
    fontWeight: '600',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted,
    marginBottom: '10px'
  },

  phaseDot: {
    width: '4px',
    height: '4px',
    borderRadius: '50%',
    backgroundColor: TOKENS.colors.accent.green
  },

  // PRISM Signals Section
  signalsSection: {
    marginBottom: '10px'
  },

  signalsHeader: {
    fontSize: '7px',
    fontWeight: '600',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted,
    marginBottom: '6px'
  },

  signalsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '3px'
  },

  signalRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '8px'
  },

  signalLabel: {
    fontSize: '7px',
    fontWeight: '600',
    letterSpacing: '0.05em',
    minWidth: '55px'
  },

  signalValue: {
    fontSize: '8px',
    fontFamily: '"JetBrains Mono", monospace',
    padding: '2px 5px',
    borderRadius: '3px',
    flex: 1,
    textAlign: 'center',
    maxWidth: '90px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  },

  separator: {
    height: '1px',
    backgroundColor: TOKENS.colors.border,
    marginBottom: '10px'
  },

  // State Metrics
  metricsGrid: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px'
  },

  metricRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },

  metricLabel: {
    fontSize: '7px',
    fontWeight: '500',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted
  },

  metricValue: {
    fontSize: '10px',
    fontWeight: '600',
    fontFamily: '"JetBrains Mono", monospace',
    letterSpacing: '0.05em'
  },

  energyBars: {
    display: 'flex',
    gap: '2px'
  },

  energyBar: {
    width: '10px',
    height: '10px',
    borderRadius: '2px',
    transition: 'background-color 0.3s ease'
  },

  momentumContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: '2px'
  },

  progressTrack: {
    width: '60px',
    height: '3px',
    backgroundColor: TOKENS.colors.bg.elevated,
    borderRadius: '2px',
    overflow: 'hidden'
  },

  progressFill: {
    height: '100%',
    borderRadius: '2px',
    transition: 'width 0.5s ease, background-color 0.3s ease'
  },

  momentumLabel: {
    fontSize: '7px',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.text.secondary
  },

  handle: {
    width: '8px',
    height: '8px',
    background: TOKENS.colors.bg.elevated,
    border: `2px solid ${TOKENS.colors.text.muted}`,
    borderRadius: '50%'
  }
}

export default StateNode
