import { Handle, Position } from '@xyflow/react'
import { TOKENS } from '../../StatusView/StatusView'
import { AGENTS } from '../flowUtils'

/**
 * ExecutionNode - EXECUTE Phase Visualization
 *
 * For WORK: Direct action indicator
 * For DELEGATE: Agent mini-nodes with status
 * Shows: ECHO, Domain, MoE, World, Code, Determinism, Reflect
 */

function ExecutionNode({ data }) {
  const { mode, activeAgents, agentStatus, highlighted, burnoutColor } = data

  // Get agent status color
  const getStatusColor = (agentId) => {
    const status = agentStatus[agentId]
    switch (status) {
      case 'running': return TOKENS.colors.accent.blue
      case 'completed': return TOKENS.colors.accent.green
      case 'failed': return TOKENS.colors.accent.red
      case 'pending': return TOKENS.colors.accent.yellow
      default: return TOKENS.colors.text.dim
    }
  }

  // Check if agent is active
  const isActive = (agentId) => {
    return activeAgents.includes(agentId) || agentStatus[agentId]
  }

  return (
    <div style={{
      ...styles.container,
      boxShadow: highlighted
        ? `0 0 20px ${burnoutColor}40, 0 0 40px ${burnoutColor}20`
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
        <span style={{ ...styles.phaseDot, backgroundColor: burnoutColor }} />
        EXECUTE PHASE
      </div>

      {/* Mode Indicator */}
      <div style={styles.modeIndicator}>
        <span style={styles.modeLabel}>
          {mode === 'work' ? 'DIRECT ACTION' : 'DELEGATING TO AGENTS'}
        </span>
      </div>

      {/* Agent Grid */}
      {mode === 'delegate' && (
        <div style={styles.agentGrid}>
          {Object.entries(AGENTS).map(([key, agent]) => {
            const active = isActive(key)
            const statusColor = getStatusColor(key)

            return (
              <div
                key={key}
                style={{
                  ...styles.agentChip,
                  borderColor: active ? statusColor : TOKENS.colors.border,
                  backgroundColor: active
                    ? `${statusColor}15`
                    : TOKENS.colors.bg.elevated
                }}
              >
                <span style={{
                  ...styles.agentDot,
                  backgroundColor: active ? statusColor : TOKENS.colors.text.dim
                }} />
                <span style={{
                  ...styles.agentLabel,
                  color: active ? statusColor : TOKENS.colors.text.muted
                }}>
                  {agent.label}
                </span>
              </div>
            )
          })}
        </div>
      )}

      {/* Work Mode - Simple Indicator */}
      {mode === 'work' && (
        <div style={styles.workIndicator}>
          <div style={{
            ...styles.workPulse,
            backgroundColor: burnoutColor
          }} />
          <span style={styles.workLabel}>Processing...</span>
        </div>
      )}
    </div>
  )
}

const styles = {
  container: {
    background: TOKENS.colors.bg.card,
    border: `1px solid ${TOKENS.colors.border}`,
    borderRadius: '8px',
    padding: '10px',
    minWidth: '150px',
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
    marginBottom: '6px'
  },

  phaseDot: {
    width: '4px',
    height: '4px',
    borderRadius: '50%'
  },

  modeIndicator: {
    marginBottom: '8px'
  },

  modeLabel: {
    fontSize: '9px',
    fontWeight: '500',
    color: TOKENS.colors.text.secondary,
    letterSpacing: '0.05em'
  },

  agentGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: '4px'
  },

  agentChip: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    padding: '4px 6px',
    border: '1px solid',
    borderRadius: '4px',
    transition: 'border-color 0.3s ease, background-color 0.3s ease'
  },

  agentDot: {
    width: '4px',
    height: '4px',
    borderRadius: '50%',
    transition: 'background-color 0.3s ease'
  },

  agentLabel: {
    fontSize: '7px',
    fontWeight: '600',
    letterSpacing: '0.05em',
    fontFamily: '"JetBrains Mono", monospace',
    transition: 'color 0.3s ease'
  },

  workIndicator: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px',
    backgroundColor: TOKENS.colors.bg.elevated,
    borderRadius: '4px'
  },

  workPulse: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    animation: 'pulse 1.5s ease-in-out infinite'
  },

  workLabel: {
    fontSize: '9px',
    color: TOKENS.colors.text.secondary,
    fontFamily: '"JetBrains Mono", monospace'
  },

  handle: {
    width: '8px',
    height: '8px',
    background: TOKENS.colors.bg.elevated,
    border: `2px solid ${TOKENS.colors.text.muted}`,
    borderRadius: '50%'
  }
}

export default ExecutionNode
