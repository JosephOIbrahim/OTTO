import { useState, useEffect, useRef, useCallback } from 'react'
import StatusView, { TOKENS } from './StatusView/StatusView'
import FlowView from './FlowView/FlowView'

/**
 * Orchestra Dashboard - Pentagram Rivian (70%) + Tendril (30%)
 *
 * Design Philosophy:
 * - Pentagram Rivian: Generous whitespace, monospace numerals, automotive dashboard
 *   precision, clean modern powerful + warm organic human
 * - Tendril (reduced): Single subtle wave, minimal organic touches
 *
 * View Modes:
 * - STATUS: Original dashboard view (default) - "where we are"
 * - FLOW: React Flow node visualization - "what's happening"
 *
 * ThinkingMachines [He2025] compliant
 */

// ============================================================================
// VIEW TOGGLE COMPONENT
// ============================================================================

function ViewToggle({ viewMode, onChange }) {
  return (
    <div style={toggleStyles.container}>
      <button
        onClick={() => onChange('status')}
        style={{
          ...toggleStyles.button,
          ...(viewMode === 'status' ? toggleStyles.buttonActive : {})
        }}
      >
        STATUS
      </button>
      <button
        onClick={() => onChange('flow')}
        style={{
          ...toggleStyles.button,
          ...(viewMode === 'flow' ? toggleStyles.buttonActive : {})
        }}
      >
        FLOW
      </button>
    </div>
  )
}

const toggleStyles = {
  container: {
    position: 'fixed',
    top: TOKENS.space.md,
    left: '50%',
    transform: 'translateX(-50%)',
    display: 'flex',
    gap: '2px',
    backgroundColor: TOKENS.colors.bg.card,
    padding: '4px',
    borderRadius: TOKENS.radius.md,
    border: `1px solid ${TOKENS.colors.border}`,
    zIndex: 100
  },

  button: {
    padding: '8px 16px',
    border: 'none',
    borderRadius: TOKENS.radius.sm,
    backgroundColor: 'transparent',
    color: TOKENS.colors.text.muted,
    fontSize: '10px',
    fontWeight: '600',
    fontFamily: '"Space Grotesk", sans-serif',
    letterSpacing: '0.1em',
    cursor: 'pointer',
    transition: 'all 0.2s ease'
  },

  buttonActive: {
    backgroundColor: TOKENS.colors.bg.elevated,
    color: TOKENS.colors.text.primary
  }
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

function OrchestraDashboard() {
  const [viewMode, setViewMode] = useState('status') // 'status' | 'flow'
  const [state, setState] = useState({
    burnout: 'GREEN',
    mode: 'work',
    momentum: 'rolling',
    energy: 'high',
    workingMemory: 2,
    tangentBudget: 5,
    altitude: '30000ft',
    paradigm: 'Cortex',
    currentTask: null,
    claudeConnected: false,
    // FlowView-specific state
    currentPhase: 'detect',
    routingRationale: '',
    routingChecksum: '',
    activeAgents: [],
    agentStatus: {},
    queuedResultsCount: 0,
    flowProtectionActive: false
  })

  const [time, setTime] = useState(new Date())
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef(null)

  // Time update
  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(interval)
  }, [])

  // Send command to WebSocket server
  const sendCommand = useCallback((type, field, value) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, field, value }))
    }
  }, [])

  // WebSocket connection
  useEffect(() => {
    const connectWebSocket = () => {
      try {
        const ws = new WebSocket('ws://localhost:8081/ws/state')
        wsRef.current = ws
        ws.onopen = () => {
          setWsConnected(true)
          setState(prev => ({ ...prev, claudeConnected: true }))
        }
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            setState(prev => ({
              ...prev,
              burnout: data.burnout_level || prev.burnout,
              mode: data.decision_mode || prev.mode,
              momentum: data.momentum_phase || prev.momentum,
              energy: data.energy_level || prev.energy,
              workingMemory: data.working_memory_used ?? prev.workingMemory,
              tangentBudget: data.tangent_budget ?? prev.tangentBudget,
              altitude: data.altitude || prev.altitude,
              paradigm: data.paradigm || prev.paradigm,
              currentTask: data.current_task || prev.currentTask,
              // FlowView-specific fields (optional from backend)
              currentPhase: data.current_phase || prev.currentPhase,
              routingRationale: data.routing_rationale || prev.routingRationale,
              routingChecksum: data.routing_checksum || prev.routingChecksum,
              activeAgents: data.active_agents || prev.activeAgents,
              agentStatus: data.agent_status || prev.agentStatus,
              queuedResultsCount: data.queued_results_count ?? prev.queuedResultsCount,
              flowProtectionActive: data.flow_protection_active ?? prev.flowProtectionActive
            }))
          } catch (e) { console.error('Parse error:', e) }
        }
        ws.onclose = () => {
          setWsConnected(false)
          wsRef.current = null
          setState(prev => ({ ...prev, claudeConnected: false }))
          setTimeout(connectWebSocket, 3000)
        }
        ws.onerror = () => ws.close()
        return ws
      } catch (e) { return null }
    }
    const ws = connectWebSocket()
    return () => ws?.close()
  }, [])

  // HTTP fallback
  useEffect(() => {
    if (wsConnected) return
    const fetchState = async () => {
      try {
        const res = await fetch('http://localhost:8080/api/state')
        if (res.ok) {
          const data = await res.json()
          setState(prev => ({
            ...prev,
            burnout: data.burnout_level || prev.burnout,
            mode: data.decision_mode || prev.mode,
            momentum: data.momentum_phase || prev.momentum,
            energy: data.energy_level || prev.energy,
            workingMemory: data.working_memory_used ?? prev.workingMemory,
            claudeConnected: true
          }))
        }
      } catch (e) {
        setState(prev => ({ ...prev, claudeConnected: false }))
      }
    }
    fetchState()
    const interval = setInterval(fetchState, 2000)
    return () => clearInterval(interval)
  }, [wsConnected])

  return (
    <div style={styles.container}>
      {/* View Toggle */}
      <ViewToggle viewMode={viewMode} onChange={setViewMode} />

      {/* Render active view */}
      {viewMode === 'status' ? (
        <StatusView state={state} time={time} />
      ) : (
        <FlowView state={state} time={time} onCommand={sendCommand} />
      )}
    </div>
  )
}

// ============================================================================
// STYLES
// ============================================================================

const styles = {
  container: {
    position: 'fixed',
    inset: 0,
    backgroundColor: TOKENS.colors.bg.primary,
    fontFamily: '"Space Grotesk", "Inter", -apple-system, system-ui, sans-serif',
    color: TOKENS.colors.text.primary,
    overflow: 'hidden',
    display: 'flex',
    justifyContent: 'center'
  }
}

export default OrchestraDashboard
