import { Handle, Position } from '@xyflow/react'
import { TOKENS } from '../../StatusView/StatusView'

/**
 * CascadeNode - CASCADE Phase Visualization (Phase 2 of NEXUS)
 *
 * Shows:
 * - Constitutional check (pass/fail)
 * - Safety gate check (pass/fail with redirect)
 * - 7-level Cognitive Safety MoE expert routing with first-match-wins
 *
 * ThinkingMachines [He2025]: Fixed priority order, first-match-wins
 * Expert priority: Validator > Scaffolder > Restorer > Refocuser > Celebrator > Socratic > Direct
 */

// Expert definitions with fixed priority order (first match wins)
const EXPERTS = [
  { id: 'validator', label: 'Validator', priority: 1, triggers: 'frustrated, RED, caps' },
  { id: 'scaffolder', label: 'Scaffolder', priority: 2, triggers: 'overwhelmed, stuck, too_many' },
  { id: 'restorer', label: 'Restorer', priority: 3, triggers: 'depleted, ORANGE, post-crash' },
  { id: 'refocuser', label: 'Refocuser', priority: 4, triggers: 'distracted, tangent_over' },
  { id: 'celebrator', label: 'Celebrator', priority: 5, triggers: 'task_complete, milestone' },
  { id: 'socratic', label: 'Socratic', priority: 6, triggers: 'exploring, what_if' },
  { id: 'direct', label: 'Direct', priority: 7, triggers: 'focused, flow' }
]

// Expert color scheme (from CLAUDE.md spec)
export const EXPERT_COLORS = {
  validator: '#f87171',   // RED - safety/emotional
  scaffolder: '#fb923c',  // ORANGE - reducing overwhelm
  restorer: '#fbbf24',    // YELLOW - recovery
  refocuser: '#60a5fa',   // BLUE - redirect
  celebrator: '#00d26a',  // GREEN - win/dopamine
  socratic: '#a78bfa',    // PURPLE - exploration
  direct: 'rgba(255,255,255,0.6)' // NEUTRAL - minimal
}

function CascadeNode({ data }) {
  const {
    constitutionalPass = true,
    safetyGatePass = true,
    safetyRedirect = null,
    selectedExpert = 'direct',
    expertTrigger = null,
    highlighted = false,
    onCommand
  } = data

  const expertColor = EXPERT_COLORS[selectedExpert] || EXPERT_COLORS.direct

  // Handle expert click - manual override
  const handleExpertClick = (e, expertId) => {
    e.stopPropagation()
    e.preventDefault()
    if (onCommand && expertId !== selectedExpert) {
      onCommand('override', 'selected_expert', expertId)
    }
  }

  return (
    <div style={{
      ...styles.container,
      borderColor: highlighted ? expertColor : TOKENS.colors.border,
      boxShadow: highlighted
        ? `0 0 20px ${expertColor}40, 0 0 40px ${expertColor}20`
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
        <span style={{ ...styles.phaseDot, backgroundColor: expertColor }} />
        CASCADE PHASE
      </div>

      {/* Gate Checks */}
      <div style={styles.gatesSection}>
        <div style={styles.gateRow}>
          <span style={styles.gateLabel}>CONSTITUTIONAL</span>
          <span style={{
            ...styles.gateStatus,
            color: constitutionalPass ? TOKENS.colors.accent.green : TOKENS.colors.accent.red
          }}>
            {constitutionalPass ? '✓ PASS' : '✗ FAIL'}
          </span>
        </div>
        <div style={styles.gateRow}>
          <span style={styles.gateLabel}>SAFETY GATE</span>
          <span style={{
            ...styles.gateStatus,
            color: safetyGatePass ? TOKENS.colors.accent.green : TOKENS.colors.accent.yellow
          }}>
            {safetyGatePass ? '✓ PASS' : `→ ${safetyRedirect?.toUpperCase() || 'REDIRECT'}`}
          </span>
        </div>
      </div>

      {/* Expert Routing - 7 level priority */}
      <div style={styles.expertSection}>
        <div style={styles.expertHeader}>EXPERT ROUTING</div>
        {EXPERTS.map((expert) => {
          const isSelected = expert.id === selectedExpert
          const color = EXPERT_COLORS[expert.id]

          return (
            <div
              key={expert.id}
              className="nodrag"
              style={{
                ...styles.expertRow,
                backgroundColor: isSelected ? `${color}15` : 'transparent',
                cursor: 'pointer'
              }}
              onClick={(e) => handleExpertClick(e, expert.id)}
              onMouseDown={(e) => e.stopPropagation()}
              title={`Triggers: ${expert.triggers}`}
            >
              <div style={styles.expertLeft}>
                <span style={styles.expertPriority}>{expert.priority}</span>
                <span style={{
                  ...styles.expertName,
                  color: isSelected ? color : TOKENS.colors.text.secondary
                }}>
                  {expert.label}
                </span>
              </div>
              <div style={styles.expertRight}>
                <span style={{
                  ...styles.expertIndicator,
                  backgroundColor: isSelected ? color : 'transparent',
                  borderColor: color
                }}>
                  {isSelected && '●'}
                </span>
                {isSelected && (
                  <span style={styles.selectedMarker}>◀</span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Trigger reason (if present) */}
      {expertTrigger && (
        <div style={styles.triggerBox}>
          <span style={styles.triggerLabel}>TRIGGER:</span>
          <span style={styles.triggerValue}>{expertTrigger}</span>
        </div>
      )}

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

  gatesSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    marginBottom: '10px',
    paddingBottom: '8px',
    borderBottom: `1px solid ${TOKENS.colors.border}`
  },

  gateRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },

  gateLabel: {
    fontSize: '7px',
    fontWeight: '500',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted
  },

  gateStatus: {
    fontSize: '8px',
    fontWeight: '600',
    fontFamily: '"JetBrains Mono", monospace',
    letterSpacing: '0.05em'
  },

  expertSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px'
  },

  expertHeader: {
    fontSize: '7px',
    fontWeight: '600',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.muted,
    marginBottom: '4px'
  },

  expertRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '3px 5px',
    borderRadius: '4px',
    transition: 'background-color 0.2s ease'
  },

  expertLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px'
  },

  expertPriority: {
    fontSize: '8px',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.text.dim,
    width: '10px'
  },

  expertName: {
    fontSize: '9px',
    fontWeight: '500',
    transition: 'color 0.2s ease'
  },

  expertRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px'
  },

  expertIndicator: {
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    border: '1px solid',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '6px',
    transition: 'background-color 0.2s ease'
  },

  selectedMarker: {
    fontSize: '8px',
    color: TOKENS.colors.text.secondary
  },

  triggerBox: {
    marginTop: '8px',
    padding: '5px',
    backgroundColor: TOKENS.colors.bg.elevated,
    borderRadius: '4px',
    display: 'flex',
    gap: '4px',
    alignItems: 'center'
  },

  triggerLabel: {
    fontSize: '7px',
    fontWeight: '600',
    letterSpacing: '0.05em',
    color: TOKENS.colors.text.dim
  },

  triggerValue: {
    fontSize: '8px',
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

export default CascadeNode
