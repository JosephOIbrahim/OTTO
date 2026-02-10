import { Handle, Position } from '@xyflow/react'
import { TOKENS } from '../../StatusView/StatusView'
import { EXPERT_COLORS } from './CascadeNode'

/**
 * LockNode - LOCK Phase Visualization (Phase 3 of NEXUS)
 *
 * Shows:
 * - Lock status (unlocked/locking/locked)
 * - MAX3 reflection iteration counter (0-3)
 * - All locked parameters with lock icons
 * - Deterministic checksum for verification
 *
 * Parameters LOCKED before generation
 * Same inputs → Same locked params → Same checksum
 */

// Lock status display config
const LOCK_STATUS = {
  unlocked: { icon: '○', label: 'UNLOCKED', color: TOKENS.colors.text.muted },
  locking: { icon: '◐', label: 'LOCKING', color: TOKENS.colors.accent.yellow },
  locked: { icon: '●', label: 'LOCKED', color: TOKENS.colors.accent.green }
}

function LockNode({ data }) {
  const {
    lockStatus = 'unlocked',
    reflectionIteration = 0,
    lockedExpert = 'direct',
    lockedParadigm = 'Cortex',
    lockedAltitude = '30000ft',
    lockedThinkDepth = 'standard',
    checksum = null,
    highlighted = false
  } = data

  const status = LOCK_STATUS[lockStatus] || LOCK_STATUS.unlocked
  const expertColor = EXPERT_COLORS[lockedExpert] || EXPERT_COLORS.direct

  // Locked parameters display
  const lockedParams = [
    { key: 'expert', value: lockedExpert, color: expertColor },
    { key: 'paradigm', value: lockedParadigm, color: TOKENS.colors.text.primary },
    { key: 'altitude', value: lockedAltitude, color: TOKENS.colors.text.primary },
    { key: 'think_depth', value: lockedThinkDepth, color: TOKENS.colors.text.primary }
  ]

  return (
    <div style={{
      ...styles.container,
      borderColor: highlighted ? status.color : TOKENS.colors.border,
      boxShadow: highlighted
        ? `0 0 20px ${status.color}40, 0 0 40px ${status.color}20`
        : 'none'
    }}>
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        style={styles.handle}
      />

      {/* Phase Label with Checksum */}
      <div style={styles.headerRow}>
        <div style={styles.phaseLabel}>
          <span style={{ ...styles.phaseDot, backgroundColor: status.color }} />
          LOCK PHASE
        </div>
        {checksum && (
          <span style={styles.checksum}>
            [{checksum.slice(0, 6)}]
          </span>
        )}
      </div>

      {/* MAX3 Reflection Counter */}
      <div style={styles.reflectionRow}>
        <span style={styles.reflectionLabel}>REFLECTION</span>
        <div style={styles.reflectionCounter}>
          {[0, 1, 2, 3].map(i => (
            <span
              key={i}
              style={{
                ...styles.reflectionDot,
                backgroundColor: i < reflectionIteration
                  ? TOKENS.colors.accent.blue
                  : TOKENS.colors.bg.elevated
              }}
            />
          ))}
          <span style={styles.reflectionText}>{reflectionIteration}/3</span>
        </div>
      </div>

      {/* Lock Status Indicator */}
      <div style={styles.statusRow}>
        <span style={styles.statusIcon}>{status.icon}</span>
        <span style={{ ...styles.statusLabel, color: status.color }}>
          {status.label}
        </span>
      </div>

      {/* Locked Parameters */}
      <div style={styles.paramsSection}>
        <div style={styles.paramsHeader}>LOCKED PARAMETERS</div>
        {lockedParams.map(param => (
          <div key={param.key} style={styles.paramRow}>
            <span style={styles.paramKey}>{param.key}</span>
            <div style={styles.paramRight}>
              <span style={{ ...styles.paramValue, color: param.color }}>
                {param.value}
              </span>
              <span style={{
                ...styles.lockIcon,
                opacity: lockStatus === 'locked' ? 1 : 0.3
              }}>
                🔒
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Lock Animation Bar */}
      {lockStatus === 'locking' && (
        <div style={styles.lockingBar}>
          <div style={styles.lockingFill} />
        </div>
      )}

      {/* Output Handles - Split to execution and storage */}
      <div style={styles.handleRow}>
        <Handle
          id="execute"
          type="source"
          position={Position.Bottom}
          style={{ ...styles.branchHandle, left: '30%' }}
        />
        <Handle
          id="storage"
          type="source"
          position={Position.Bottom}
          style={{ ...styles.branchHandle, left: '70%' }}
        />
      </div>
    </div>
  )
}

const styles = {
  container: {
    background: TOKENS.colors.bg.card,
    border: '1px solid',
    borderRadius: '8px',
    padding: '12px',
    minWidth: '170px',
    fontFamily: '"Space Grotesk", sans-serif',
    transition: 'box-shadow 0.3s ease, border-color 0.3s ease'
  },

  headerRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '10px'
  },

  phaseLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    fontSize: '8px',
    fontWeight: '600',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted
  },

  phaseDot: {
    width: '4px',
    height: '4px',
    borderRadius: '50%'
  },

  checksum: {
    fontSize: '8px',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.text.dim,
    letterSpacing: '0.05em'
  },

  reflectionRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '8px',
    paddingBottom: '8px',
    borderBottom: `1px solid ${TOKENS.colors.border}`
  },

  reflectionLabel: {
    fontSize: '7px',
    fontWeight: '500',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted
  },

  reflectionCounter: {
    display: 'flex',
    alignItems: 'center',
    gap: '3px'
  },

  reflectionDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    transition: 'background-color 0.3s ease'
  },

  reflectionText: {
    fontSize: '8px',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.text.secondary,
    marginLeft: '4px'
  },

  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    marginBottom: '10px'
  },

  statusIcon: {
    fontSize: '12px'
  },

  statusLabel: {
    fontSize: '10px',
    fontWeight: '600',
    fontFamily: '"JetBrains Mono", monospace',
    letterSpacing: '0.05em'
  },

  paramsSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '3px'
  },

  paramsHeader: {
    fontSize: '7px',
    fontWeight: '600',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted,
    marginBottom: '4px'
  },

  paramRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '3px 0'
  },

  paramKey: {
    fontSize: '8px',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.text.dim
  },

  paramRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px'
  },

  paramValue: {
    fontSize: '9px',
    fontWeight: '500',
    fontFamily: '"JetBrains Mono", monospace'
  },

  lockIcon: {
    fontSize: '8px',
    transition: 'opacity 0.3s ease'
  },

  lockingBar: {
    marginTop: '10px',
    height: '2px',
    backgroundColor: TOKENS.colors.bg.elevated,
    borderRadius: '1px',
    overflow: 'hidden'
  },

  lockingFill: {
    height: '100%',
    width: '50%',
    backgroundColor: TOKENS.colors.accent.yellow,
    animation: 'lockPulse 1s ease-in-out infinite'
  },

  handleRow: {
    marginTop: '12px',
    position: 'relative',
    height: '8px'
  },

  handle: {
    width: '8px',
    height: '8px',
    background: TOKENS.colors.bg.elevated,
    border: `2px solid ${TOKENS.colors.text.muted}`,
    borderRadius: '50%'
  },

  branchHandle: {
    position: 'absolute',
    width: '8px',
    height: '8px',
    background: TOKENS.colors.bg.elevated,
    border: `2px solid ${TOKENS.colors.text.muted}`,
    borderRadius: '50%'
  }
}

export default LockNode
