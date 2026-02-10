/**
 * Flow Utilities - State to React Flow mapping
 *
 * Converts Orchestra WebSocket state to React Flow nodes and edges
 *
 * 5-Phase NEXUS Pipeline (ThinkingMachines):
 * 1. DETECT  - StateNode (PRISM signal extraction)
 * 2. CASCADE - CascadeNode (7-expert Cognitive Safety MoE routing)
 * 3. LOCK    - LockNode (MAX3 + parameter locking)
 * 4. EXECUTE - ExecutionNode/StorageNode (work/delegate/protect)
 * 5. UPDATE  - UpdateNode (RC^+xi convergence tracking)
 */

import { TOKENS, STATES } from '../StatusView/StatusView'

// Agent definitions for execution node
export const AGENTS = {
  echo_curator: { id: 'echo', label: 'ECHO', desc: 'LIVRPS Curator' },
  domain_intel: { id: 'domain', label: 'DOMAIN', desc: 'Phoenix v6' },
  moe_router: { id: 'moe', label: 'MoE', desc: 'V5 Intervention' },
  world_model: { id: 'world', label: 'WORLD', desc: 'CORTEX Model' },
  code_gen: { id: 'code', label: 'CODE', desc: 'MAX 3 + MNO' },
  determinism: { id: 'determ', label: 'DETERM', desc: 'ThinkingMachines' },
  reflector: { id: 'reflect', label: 'REFLECT', desc: 'RESONANCE' }
}

// Node positions for 5-phase NEXUS pipeline
export const NODE_POSITIONS = {
  state: { x: 200, y: 0 },      // DETECT
  cascade: { x: 200, y: 200 },  // CASCADE
  lock: { x: 200, y: 400 },     // LOCK
  execution: { x: 120, y: 580 }, // EXECUTE (work/delegate)
  storage: { x: 320, y: 580 },  // PROTECT
  update: { x: 200, y: 760 }    // UPDATE
}

// Expert color scheme (matches CascadeNode)
export const EXPERT_COLORS = {
  validator: '#f87171',   // RED
  scaffolder: '#fb923c',  // ORANGE
  restorer: '#fbbf24',    // YELLOW
  refocuser: '#60a5fa',   // BLUE
  celebrator: '#00d26a',  // GREEN
  socratic: '#a78bfa',    // PURPLE
  direct: 'rgba(255,255,255,0.6)'
}

/**
 * Get expert color from selected expert
 */
export function getExpertColor(expert) {
  return EXPERT_COLORS[expert] || EXPERT_COLORS.direct
}

/**
 * Get burnout color from state
 */
export function getBurnoutColor(burnout) {
  const state = STATES.burnout[burnout] || STATES.burnout.GREEN
  return state.color
}

/**
 * Get mode color from state
 */
export function getModeColor(mode) {
  const state = STATES.mode[mode] || STATES.mode.work
  return state.color
}

/**
 * Map Orchestra state to React Flow nodes
 *
 * 5-Phase NEXUS Pipeline:
 * DETECT → CASCADE → LOCK → EXECUTE/PROTECT → UPDATE → (feedback to DETECT)
 */
export function mapStateToNodes(state, onCommand = null) {
  const burnoutColor = getBurnoutColor(state.burnout)
  const modeColor = getModeColor(state.mode)
  const expertColor = getExpertColor(state.selectedExpert || 'direct')

  const nodes = [
    // === PHASE 1: DETECT (StateNode) ===
    {
      id: 'state',
      type: 'stateNode',
      position: NODE_POSITIONS.state,
      data: {
        burnout: state.burnout || 'GREEN',
        energy: state.energy || 'high',
        momentum: state.momentum || 'rolling',
        highlighted: state.currentPhase === 'detect',
        burnoutColor,
        // PRISM signals
        signalsEmotional: state.signalsEmotional || null,
        signalsMode: state.signalsMode || null,
        signalsDomain: state.signalsDomain || null,
        signalsTask: state.signalsTask || null,
        onCommand
      }
    },

    // === PHASE 2: CASCADE (CascadeNode) ===
    {
      id: 'cascade',
      type: 'cascadeNode',
      position: NODE_POSITIONS.cascade,
      data: {
        constitutionalPass: state.constitutionalPass !== false,
        safetyGatePass: state.safetyGatePass !== false,
        safetyRedirect: state.safetyRedirect || null,
        selectedExpert: state.selectedExpert || 'direct',
        expertTrigger: state.expertTrigger || null,
        highlighted: state.currentPhase === 'cascade',
        onCommand
      }
    },

    // === PHASE 3: LOCK (LockNode) ===
    {
      id: 'lock',
      type: 'lockNode',
      position: NODE_POSITIONS.lock,
      data: {
        lockStatus: state.lockStatus || 'unlocked',
        reflectionIteration: state.reflectionIteration || 0,
        lockedExpert: state.lockedExpert || state.selectedExpert || 'direct',
        lockedParadigm: state.lockedParadigm || state.paradigm || 'Cortex',
        lockedAltitude: state.lockedAltitude || state.altitude || '30000ft',
        lockedThinkDepth: state.lockedThinkDepth || 'standard',
        checksum: state.lockChecksum || null,
        highlighted: state.currentPhase === 'lock'
      }
    }
  ]

  // === PHASE 4: EXECUTE (ExecutionNode) - shown for work/delegate modes ===
  if (state.mode === 'work' || state.mode === 'delegate') {
    nodes.push({
      id: 'execution',
      type: 'executionNode',
      position: NODE_POSITIONS.execution,
      data: {
        mode: state.mode,
        activeAgents: state.activeAgents || [],
        agentStatus: state.agentStatus || {},
        highlighted: state.currentPhase === 'execute',
        burnoutColor
      }
    })
  }

  // === PHASE 4: PROTECT (StorageNode) - shown for protect mode or when queue > 0 ===
  if (state.mode === 'protect' || (state.queuedResultsCount || 0) > 0) {
    nodes.push({
      id: 'storage',
      type: 'storageNode',
      position: NODE_POSITIONS.storage,
      data: {
        queueCount: state.queuedResultsCount || 0,
        flowProtectionActive: state.flowProtectionActive || state.mode === 'protect',
        highlighted: state.currentPhase === 'protect'
      }
    })
  }

  // === PHASE 5: UPDATE (UpdateNode) - always present ===
  nodes.push({
    id: 'update',
    type: 'updateNode',
    position: NODE_POSITIONS.update,
    data: {
      epistemicTension: state.epistemicTension || 0.0,
      epsilon: state.epsilon || 0.1,
      attractorBasin: state.attractorBasin || 'focused',
      stableExchanges: state.stableExchanges || 0,
      converged: state.converged || false,
      feedbackActive: state.feedbackActive !== false,
      highlighted: state.currentPhase === 'update'
    }
  })

  return nodes
}

/**
 * Map Orchestra state to React Flow edges
 *
 * 5-Phase NEXUS Pipeline connections:
 * DETECT → CASCADE → LOCK → EXECUTE/PROTECT → UPDATE → (feedback to DETECT)
 */
export function mapStateToEdges(state) {
  const modeColor = getModeColor(state.mode)
  const expertColor = getExpertColor(state.selectedExpert || 'direct')
  const burnoutColor = getBurnoutColor(state.burnout)
  const isExecutePhase = state.currentPhase === 'execute'

  const edges = [
    // === DETECT → CASCADE ===
    {
      id: 'detect-cascade',
      source: 'state',
      target: 'cascade',
      type: 'flowEdge',
      data: {
        animated: state.currentPhase === 'detect',
        color: TOKENS.colors.text.muted,
        active: state.currentPhase === 'detect' || state.currentPhase === 'cascade'
      }
    },

    // === CASCADE → LOCK ===
    {
      id: 'cascade-lock',
      source: 'cascade',
      target: 'lock',
      type: 'flowEdge',
      data: {
        animated: state.currentPhase === 'cascade',
        color: expertColor,
        active: state.currentPhase === 'cascade' || state.currentPhase === 'lock'
      }
    }
  ]

  // === LOCK → EXECUTION (for work/delegate) ===
  if (state.mode === 'work' || state.mode === 'delegate') {
    edges.push({
      id: 'lock-execution',
      source: 'lock',
      sourceHandle: 'execute',
      target: 'execution',
      type: 'flowEdge',
      data: {
        animated: state.currentPhase === 'lock' || isExecutePhase,
        color: modeColor,
        active: true
      }
    })

    // === EXECUTION → UPDATE ===
    edges.push({
      id: 'execution-update',
      source: 'execution',
      target: 'update',
      type: 'flowEdge',
      data: {
        animated: isExecutePhase,
        color: burnoutColor,
        active: isExecutePhase || state.currentPhase === 'update'
      }
    })
  }

  // === LOCK → STORAGE (for protect or when queue exists) ===
  if (state.mode === 'protect' || (state.queuedResultsCount || 0) > 0) {
    edges.push({
      id: 'lock-storage',
      source: 'lock',
      sourceHandle: 'storage',
      target: 'storage',
      type: 'flowEdge',
      data: {
        animated: state.mode === 'protect',
        color: TOKENS.colors.accent.purple,
        active: state.mode === 'protect'
      }
    })
  }

  // === UPDATE → DETECT (FEEDBACK LOOP) - always present ===
  edges.push({
    id: 'update-detect',
    source: 'update',
    sourceHandle: 'feedback',
    target: 'state',
    targetHandle: 'feedback',
    type: 'feedbackEdge',
    data: {
      animated: state.feedbackActive !== false,
      color: TOKENS.colors.accent.green,
      active: state.currentPhase === 'update' || state.feedbackActive !== false
    }
  })

  return edges
}

/**
 * Get initial viewport settings
 */
export function getInitialViewport() {
  return {
    x: 50,
    y: 50,
    zoom: 0.9
  }
}

/**
 * Format checksum for display
 */
export function formatChecksum(checksum) {
  if (!checksum) return '------'
  return checksum.slice(0, 6)
}
