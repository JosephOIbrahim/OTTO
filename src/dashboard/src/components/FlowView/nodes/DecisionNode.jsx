import { Handle, Position } from '@xyflow/react'
import { TOKENS, STATES } from '../../StatusView/StatusView'
import { formatChecksum } from '../flowUtils'

/**
 * DecisionNode - ROUTE Phase Visualization
 *
 * Shows: decision_mode, routing_rationale, checksum
 * 3 output handles: WORK | DELEGATE | PROTECT
 * Active handle illuminated based on current mode
 */

function DecisionNode({ data }) {
  const { mode, rationale, checksum, highlighted, modeColor, onCommand } = data

  const modeState = STATES.mode[mode] || STATES.mode.work

  // Handle mode switch click - stop propagation to prevent React Flow drag
  const handleModeClick = (e, newMode) => {
    e.stopPropagation()
    e.preventDefault()
    if (onCommand && newMode !== mode) {
      onCommand('override', 'decision_mode', newMode)
    }
  }

  return (
    <div style={{
      ...styles.container,
      boxShadow: highlighted
        ? `0 0 20px ${modeColor}40, 0 0 40px ${modeColor}20`
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
        <span style={{ ...styles.phaseDot, backgroundColor: modeColor }} />
        ROUTE PHASE
      </div>

      {/* Mode Display */}
      <div style={styles.modeDisplay}>
        <span style={{ ...styles.modeValue, color: modeColor }}>
          {modeState.label}
        </span>
        <span style={styles.checksum}>
          {formatChecksum(checksum)}
        </span>
      </div>

      {/* Rationale (if present) */}
      {rationale && (
        <div style={styles.rationale}>
          {rationale}
        </div>
      )}

      {/* Output Handles - 3 branches (clickable) */}
      <div style={styles.handleRow}>
        <div
          className="nodrag"
          style={styles.handleGroup}
          onClick={(e) => handleModeClick(e, 'work')}
          onMouseDown={(e) => e.stopPropagation()}
          title="Switch to WORK mode"
        >
          <Handle
            id="work"
            type="source"
            position={Position.Bottom}
            style={{
              ...styles.branchHandle,
              ...styles.handleLeft,
              borderColor: mode === 'work' ? TOKENS.colors.accent.green : TOKENS.colors.text.dim,
              backgroundColor: mode === 'work' ? TOKENS.colors.accent.green : TOKENS.colors.bg.elevated
            }}
          />
          <span style={{
            ...styles.handleLabel,
            color: mode === 'work' ? TOKENS.colors.accent.green : TOKENS.colors.text.dim
          }}>
            WORK
          </span>
        </div>

        <div
          className="nodrag"
          style={styles.handleGroup}
          onClick={(e) => handleModeClick(e, 'delegate')}
          onMouseDown={(e) => e.stopPropagation()}
          title="Switch to DELEGATE mode"
        >
          <Handle
            id="delegate"
            type="source"
            position={Position.Bottom}
            style={{
              ...styles.branchHandle,
              borderColor: mode === 'delegate' ? TOKENS.colors.accent.blue : TOKENS.colors.text.dim,
              backgroundColor: mode === 'delegate' ? TOKENS.colors.accent.blue : TOKENS.colors.bg.elevated
            }}
          />
          <span style={{
            ...styles.handleLabel,
            color: mode === 'delegate' ? TOKENS.colors.accent.blue : TOKENS.colors.text.dim
          }}>
            DELEGATE
          </span>
        </div>

        <div
          className="nodrag"
          style={styles.handleGroup}
          onClick={(e) => handleModeClick(e, 'protect')}
          onMouseDown={(e) => e.stopPropagation()}
          title="Switch to PROTECT mode"
        >
          <Handle
            id="protect"
            type="source"
            position={Position.Bottom}
            style={{
              ...styles.branchHandle,
              ...styles.handleRight,
              borderColor: mode === 'protect' ? TOKENS.colors.accent.purple : TOKENS.colors.text.dim,
              backgroundColor: mode === 'protect' ? TOKENS.colors.accent.purple : TOKENS.colors.bg.elevated
            }}
          />
          <span style={{
            ...styles.handleLabel,
            color: mode === 'protect' ? TOKENS.colors.accent.purple : TOKENS.colors.text.dim
          }}>
            PROTECT
          </span>
        </div>
      </div>
    </div>
  )
}

const styles = {
  container: {
    background: TOKENS.colors.bg.card,
    border: `1px solid ${TOKENS.colors.border}`,
    borderRadius: '8px',
    padding: '12px',
    minWidth: '160px',
    fontFamily: '"Space Grotesk", sans-serif',
    transition: 'box-shadow 0.3s ease'
  },

  phaseLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    fontSize: '8px',
    fontWeight: '600',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted,
    marginBottom: '8px'
  },

  phaseDot: {
    width: '4px',
    height: '4px',
    borderRadius: '50%'
  },

  modeDisplay: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: '4px'
  },

  modeValue: {
    fontSize: '14px',
    fontWeight: '600',
    fontFamily: '"JetBrains Mono", monospace',
    letterSpacing: '0.05em',
    transition: 'color 0.3s ease'
  },

  checksum: {
    fontSize: '8px',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.text.dim,
    letterSpacing: '0.05em'
  },

  rationale: {
    fontSize: '9px',
    color: TOKENS.colors.text.secondary,
    lineHeight: 1.3,
    marginBottom: '8px',
    padding: '5px',
    backgroundColor: TOKENS.colors.bg.elevated,
    borderRadius: '4px'
  },

  handleRow: {
    display: 'flex',
    justifyContent: 'space-between',
    marginTop: '10px',
    paddingTop: '8px',
    borderTop: `1px solid ${TOKENS.colors.border}`
  },

  handleGroup: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '3px',
    position: 'relative',
    cursor: 'pointer',
    padding: '4px',
    borderRadius: '4px',
    transition: 'background-color 0.2s ease'
  },

  handle: {
    width: '8px',
    height: '8px',
    background: TOKENS.colors.bg.elevated,
    border: `2px solid ${TOKENS.colors.text.muted}`,
    borderRadius: '50%'
  },

  branchHandle: {
    position: 'relative',
    width: '8px',
    height: '8px',
    border: '2px solid',
    borderRadius: '50%',
    transition: 'border-color 0.3s ease, background-color 0.3s ease'
  },

  handleLeft: {
    left: '-20px'
  },

  handleRight: {
    right: '-20px'
  },

  handleLabel: {
    fontSize: '6px',
    fontWeight: '600',
    letterSpacing: '0.1em',
    transition: 'color 0.3s ease'
  }
}

export default DecisionNode
