import { Handle, Position } from '@xyflow/react'
import { TOKENS } from '../../StatusView/StatusView'

/**
 * UpdateNode - UPDATE Phase Visualization (Phase 5 of NEXUS)
 *
 * Shows:
 * - RC^+xi epistemic tension gauge (0.0 - 1.0)
 * - Epsilon threshold marker (ε = 0.1)
 * - Attractor basin indicator (focused/exploring/recovery/teaching)
 * - Convergence counter (0-3 stable exchanges)
 * - Feedback loop indicator
 *
 * xi_n = ||A_{n+1} - A_n||_2
 * Converged when xi < ε for 3 consecutive exchanges
 */

// Attractor basins with colors
const ATTRACTORS = {
  focused: { color: TOKENS.colors.accent.green, label: 'FOCUSED' },
  exploring: { color: TOKENS.colors.accent.purple, label: 'EXPLORING' },
  recovery: { color: TOKENS.colors.accent.orange, label: 'RECOVERY' },
  teaching: { color: TOKENS.colors.accent.blue, label: 'TEACHING' }
}

// Get tension color based on value
function getTensionColor(tension) {
  if (tension <= 0.1) return TOKENS.colors.accent.green  // Converged
  if (tension <= 0.3) return TOKENS.colors.accent.blue   // Stable
  if (tension <= 0.6) return TOKENS.colors.accent.yellow // Tension
  return TOKENS.colors.accent.red                        // High tension
}

function UpdateNode({ data }) {
  const {
    epistemicTension = 0.0,
    epsilon = 0.1,
    attractorBasin = 'focused',
    stableExchanges = 0,
    converged = false,
    feedbackActive = true,
    highlighted = false
  } = data

  const tensionColor = getTensionColor(epistemicTension)
  const attractor = ATTRACTORS[attractorBasin] || ATTRACTORS.focused
  const tensionPercent = Math.min(epistemicTension * 100, 100)
  const epsilonPercent = epsilon * 100

  return (
    <div style={{
      ...styles.container,
      borderColor: highlighted ? tensionColor : TOKENS.colors.border,
      boxShadow: highlighted
        ? `0 0 20px ${tensionColor}40, 0 0 40px ${tensionColor}20`
        : 'none'
    }}>
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        style={styles.handle}
      />

      {/* Phase Label */}
      <div style={styles.phaseLabel}>
        <span style={{ ...styles.phaseDot, backgroundColor: tensionColor }} />
        UPDATE PHASE
      </div>

      {/* Epistemic Tension Gauge */}
      <div style={styles.tensionSection}>
        <div style={styles.tensionHeader}>EPISTEMIC TENSION</div>
        <div style={styles.gaugeContainer}>
          <div style={styles.gaugeTrack}>
            {/* Tension fill */}
            <div style={{
              ...styles.gaugeFill,
              width: `${tensionPercent}%`,
              backgroundColor: tensionColor
            }} />
            {/* Epsilon threshold marker */}
            <div style={{
              ...styles.epsilonMarker,
              left: `${epsilonPercent}%`
            }}>
              <div style={styles.epsilonLine} />
              <span style={styles.epsilonLabel}>ε</span>
            </div>
          </div>
          <div style={styles.tensionValue}>
            <span style={{ color: tensionColor }}>
              {epistemicTension.toFixed(2)}
            </span>
            <span style={styles.tensionScale}> / 1.0</span>
          </div>
        </div>
      </div>

      {/* Attractor Basin */}
      <div style={styles.attractorSection}>
        <div style={styles.attractorHeader}>ATTRACTOR BASIN</div>
        <div style={styles.attractorList}>
          {Object.entries(ATTRACTORS).map(([key, attr]) => {
            const isActive = key === attractorBasin
            return (
              <div
                key={key}
                style={{
                  ...styles.attractorRow,
                  backgroundColor: isActive ? `${attr.color}15` : 'transparent'
                }}
              >
                <span style={{
                  ...styles.attractorIndicator,
                  backgroundColor: isActive ? attr.color : 'transparent',
                  borderColor: attr.color
                }}>
                  {isActive ? '◉' : '○'}
                </span>
                <span style={{
                  ...styles.attractorLabel,
                  color: isActive ? attr.color : TOKENS.colors.text.dim
                }}>
                  {attr.label}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Convergence Status */}
      <div style={styles.convergenceSection}>
        <div style={styles.convergenceRow}>
          <span style={styles.convergenceLabel}>CONVERGENCE</span>
          <div style={styles.convergenceValue}>
            {[0, 1, 2].map(i => (
              <span
                key={i}
                style={{
                  ...styles.stableDot,
                  backgroundColor: i < stableExchanges
                    ? TOKENS.colors.accent.green
                    : TOKENS.colors.bg.elevated
                }}
              />
            ))}
            <span style={styles.stableText}>
              {stableExchanges}/3 stable
            </span>
          </div>
        </div>
        {converged && (
          <div style={styles.convergedBadge}>
            ✓ CONVERGED
          </div>
        )}
      </div>

      {/* Feedback Loop Indicator */}
      {feedbackActive && (
        <div style={styles.feedbackIndicator}>
          <span style={styles.feedbackIcon}>↻</span>
          <span style={styles.feedbackText}>FEEDBACK TO DETECT</span>
        </div>
      )}

      {/* Output Handle - Feedback loop */}
      <Handle
        id="feedback"
        type="source"
        position={Position.Right}
        style={{ ...styles.handle, top: '50%' }}
      />
    </div>
  )
}

const styles = {
  container: {
    background: TOKENS.colors.bg.card,
    border: '1px solid',
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
    borderRadius: '50%'
  },

  tensionSection: {
    marginBottom: '12px'
  },

  tensionHeader: {
    fontSize: '7px',
    fontWeight: '600',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted,
    marginBottom: '6px'
  },

  gaugeContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px'
  },

  gaugeTrack: {
    position: 'relative',
    height: '8px',
    backgroundColor: TOKENS.colors.bg.elevated,
    borderRadius: '4px',
    overflow: 'visible'
  },

  gaugeFill: {
    height: '100%',
    borderRadius: '4px',
    transition: 'width 0.5s ease, background-color 0.3s ease'
  },

  epsilonMarker: {
    position: 'absolute',
    top: '-4px',
    transform: 'translateX(-50%)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center'
  },

  epsilonLine: {
    width: '1px',
    height: '16px',
    backgroundColor: TOKENS.colors.text.muted
  },

  epsilonLabel: {
    fontSize: '7px',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.text.muted
  },

  tensionValue: {
    fontSize: '11px',
    fontFamily: '"JetBrains Mono", monospace',
    fontWeight: '600',
    textAlign: 'right'
  },

  tensionScale: {
    color: TOKENS.colors.text.dim,
    fontSize: '9px'
  },

  attractorSection: {
    marginBottom: '10px',
    paddingBottom: '10px',
    borderBottom: `1px solid ${TOKENS.colors.border}`
  },

  attractorHeader: {
    fontSize: '7px',
    fontWeight: '600',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted,
    marginBottom: '6px'
  },

  attractorList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px'
  },

  attractorRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '2px 4px',
    borderRadius: '3px'
  },

  attractorIndicator: {
    fontSize: '8px',
    width: '12px',
    textAlign: 'center'
  },

  attractorLabel: {
    fontSize: '8px',
    fontWeight: '500',
    letterSpacing: '0.05em',
    transition: 'color 0.2s ease'
  },

  convergenceSection: {
    marginBottom: '8px'
  },

  convergenceRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },

  convergenceLabel: {
    fontSize: '7px',
    fontWeight: '600',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted
  },

  convergenceValue: {
    display: 'flex',
    alignItems: 'center',
    gap: '3px'
  },

  stableDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    transition: 'background-color 0.3s ease'
  },

  stableText: {
    fontSize: '8px',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.text.secondary,
    marginLeft: '4px'
  },

  convergedBadge: {
    marginTop: '6px',
    padding: '3px 8px',
    backgroundColor: `${TOKENS.colors.accent.green}20`,
    borderRadius: '4px',
    fontSize: '8px',
    fontWeight: '600',
    color: TOKENS.colors.accent.green,
    textAlign: 'center',
    letterSpacing: '0.05em'
  },

  feedbackIndicator: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    padding: '4px 6px',
    backgroundColor: TOKENS.colors.bg.elevated,
    borderRadius: '4px'
  },

  feedbackIcon: {
    fontSize: '10px',
    color: TOKENS.colors.accent.green,
    animation: 'spin 2s linear infinite'
  },

  feedbackText: {
    fontSize: '7px',
    fontWeight: '500',
    letterSpacing: '0.05em',
    color: TOKENS.colors.text.dim
  },

  handle: {
    width: '8px',
    height: '8px',
    background: TOKENS.colors.bg.elevated,
    border: `2px solid ${TOKENS.colors.text.muted}`,
    borderRadius: '50%'
  }
}

export default UpdateNode
