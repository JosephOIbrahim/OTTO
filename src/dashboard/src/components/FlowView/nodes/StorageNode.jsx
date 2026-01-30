import { Handle, Position } from '@xyflow/react'
import { TOKENS } from '../../StatusView/StatusView'

/**
 * StorageNode - PROTECT Mode Visualization
 *
 * Shows: Queue counter, flow protection indicator
 * Visible when protect mode active or queue > 0
 */

function StorageNode({ data }) {
  const { queueCount, flowProtectionActive, highlighted } = data

  return (
    <div style={{
      ...styles.container,
      borderColor: flowProtectionActive
        ? TOKENS.colors.accent.purple
        : TOKENS.colors.border,
      boxShadow: highlighted
        ? `0 0 20px ${TOKENS.colors.accent.purple}40, 0 0 40px ${TOKENS.colors.accent.purple}20`
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
        <span style={{
          ...styles.phaseDot,
          backgroundColor: flowProtectionActive
            ? TOKENS.colors.accent.purple
            : TOKENS.colors.text.dim
        }} />
        PROTECT MODE
      </div>

      {/* Protection Status */}
      <div style={styles.statusSection}>
        <div style={{
          ...styles.shield,
          borderColor: flowProtectionActive
            ? TOKENS.colors.accent.purple
            : TOKENS.colors.text.dim
        }}>
          <span style={styles.shieldIcon}>
            {flowProtectionActive ? '◉' : '○'}
          </span>
        </div>
        <span style={{
          ...styles.statusLabel,
          color: flowProtectionActive
            ? TOKENS.colors.accent.purple
            : TOKENS.colors.text.muted
        }}>
          {flowProtectionActive ? 'FLOW PROTECTED' : 'STANDBY'}
        </span>
      </div>

      {/* Queue Counter */}
      <div style={styles.queueSection}>
        <span style={styles.queueLabel}>QUEUED RESULTS</span>
        <div style={styles.queueBadge}>
          <span style={styles.queueCount}>{queueCount}</span>
        </div>
      </div>
    </div>
  )
}

const styles = {
  container: {
    background: TOKENS.colors.bg.card,
    border: '2px solid',
    borderRadius: '8px',
    padding: '10px',
    minWidth: '120px',
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
    marginBottom: '8px'
  },

  phaseDot: {
    width: '4px',
    height: '4px',
    borderRadius: '50%',
    transition: 'background-color 0.3s ease'
  },

  statusSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '8px'
  },

  shield: {
    width: '20px',
    height: '20px',
    border: '2px solid',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'border-color 0.3s ease'
  },

  shieldIcon: {
    fontSize: '10px',
    color: TOKENS.colors.accent.purple
  },

  statusLabel: {
    fontSize: '8px',
    fontWeight: '600',
    letterSpacing: '0.1em',
    transition: 'color 0.3s ease'
  },

  queueSection: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '6px 8px',
    backgroundColor: TOKENS.colors.bg.elevated,
    borderRadius: '4px'
  },

  queueLabel: {
    fontSize: '7px',
    fontWeight: '500',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted
  },

  queueBadge: {
    backgroundColor: TOKENS.colors.accent.purple,
    borderRadius: '3px',
    padding: '2px 6px'
  },

  queueCount: {
    fontSize: '10px',
    fontWeight: '600',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.bg.primary
  },

  handle: {
    width: '8px',
    height: '8px',
    background: TOKENS.colors.bg.elevated,
    border: `2px solid ${TOKENS.colors.text.muted}`,
    borderRadius: '50%'
  }
}

export default StorageNode
