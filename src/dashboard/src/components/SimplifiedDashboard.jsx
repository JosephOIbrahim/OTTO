import { useState, useEffect, useCallback } from 'react'

/**
 * Orchestra Dashboard - John Maeda's Laws of Simplicity
 *
 * ACCURATE representation of Framework Orchestrator functionality:
 * - 7 Orchestrator Agents (actual names + frameworks)
 * - 7 MoE Intervention Experts with Safety Floors
 * - V5 5-phase routing visualization
 * - Circuit breaker status
 * - Convergence (RC^+xi) tracking
 * - Cognitive state (LIVRPS composition)
 *
 * Batch-invariance
 */

// ============================================================================
// ACCURATE 7 ORCHESTRATOR AGENTS (from framework_orchestrator.py)
// ============================================================================
const AGENTS = [
  { id: 'echo_curator', name: 'Echo Curator', short: 'EC', framework: 'ECHO 2.0 + LIVRPS', alignment: 'Context Memory Platform' },
  { id: 'domain_intelligence', name: 'Domain Intel', short: 'DI', framework: 'Phoenix v6 + PRISM', alignment: 'Multi-perspective reasoning' },
  { id: 'moe_router', name: 'MoE Router', short: 'MR', framework: 'V5 Intervention', alignment: 'Safety-floor bounded routing' },
  { id: 'world_modeler', name: 'World Model', short: 'WM', framework: 'CORTEX', alignment: 'Cosmos WFM + Object Permanence' },
  { id: 'code_generator', name: 'Code Gen', short: 'CG', framework: 'MAX 3 + MNO v3', alignment: 'AlphaEvolve patterns' },
  { id: 'determinism_guard', name: 'Determinism', short: 'DG', framework: 'ThinkingMachines', alignment: 'Reproducible inference' },
  { id: 'self_reflector', name: 'Reflector', short: 'SR', framework: 'RESONANCE + MCAW', alignment: 'Constitutional AI' }
]

// ============================================================================
// V5 MOE INTERVENTION EXPERTS (from MoERouterAgent)
// ============================================================================
const MOE_EXPERTS = {
  protector: { priority: 1, displayName: 'Safety Guardian', floor: 0.10, triggers: ['frustrated', 'overwhelmed', 'safety'] },
  decomposer: { priority: 2, displayName: 'Complexity Simplifier', floor: 0.05, triggers: ['stuck', 'complex', 'break_down'] },
  restorer: { priority: 3, displayName: 'Energy Recharger', floor: 0.05, triggers: ['depleted', 'burnout', 'tired'] },
  redirector: { priority: 4, displayName: 'Focus Redirector', floor: 0.00, triggers: ['tangent', 'distracted'] },
  acknowledger: { priority: 5, displayName: 'Progress Celebrator', floor: 0.00, triggers: ['done', 'complete', 'milestone'] },
  guide: { priority: 6, displayName: 'Discovery Guide', floor: 0.00, triggers: ['exploring', 'what_if', 'curious'] },
  executor: { priority: 7, displayName: 'Task Builder', floor: 0.00, triggers: ['implement', 'code', 'build'] }
}

// ============================================================================
// AGENT STATUS ENUM (from AgentStatus)
// ============================================================================
const AGENT_STATUS = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  SKIPPED: 'skipped',
  DEGRADED: 'degraded'
}

// ============================================================================
// DECISION MODE ENUM (v4.3.0 - Work/Delegate/Protect)
// ============================================================================
const DECISION_MODE = {
  WORK: 'work',           // Direct action - do it yourself
  DELEGATE: 'delegate',   // Spawn agents for parallel execution
  PROTECT: 'protect'      // Shield flow, queue results
}

const DECISION_MODE_INFO = {
  work: { color: 'var(--color-success)', icon: '⚡', label: 'Direct Work', description: 'Execute with minimal agents' },
  delegate: { color: 'var(--color-primary)', icon: '🔀', label: 'Delegate', description: 'Spawn agents for parallel execution' },
  protect: { color: 'var(--color-warning)', icon: '🛡️', label: 'Protect Flow', description: 'Queue task, preserve momentum' }
}

// ============================================================================
// HEALTH STATUS ENUM (from HealthStatus)
// ============================================================================
const HEALTH_STATUS = {
  HEALTHY: 'healthy',
  DEGRADED: 'degraded',
  UNHEALTHY: 'unhealthy'
}

function SimplifiedDashboard() {
  // System state
  const [status, setStatus] = useState(HEALTH_STATUS.HEALTHY)
  const [agents, setAgents] = useState(AGENTS.map(a => ({ ...a, status: AGENT_STATUS.COMPLETED })))
  const [uptime, setUptime] = useState(0)
  const [seed] = useState(42) // ThinkingMachines determinism seed

  // MoE Router state (V5 5-phase)
  const [moeState, setMoeState] = useState({
    selectedExpert: 'executor',
    activationVector: Object.fromEntries(Object.keys(MOE_EXPERTS).map(e => [e, 0.14])),
    boundedScores: Object.fromEntries(Object.keys(MOE_EXPERTS).map(e => [e, 0.14])),
    safetyIntervention: false,
    routingPhase: 'idle'
  })

  // Cognitive state (LIVRPS composition)
  const [cognitive, setCognitive] = useState({
    burnout: 'GREEN',
    momentum: 'rolling',
    paradigm: 'Cortex',
    altitude: '30000ft',
    energy: 'high',
    memoryMode: 'focused_recall'
  })

  // Convergence (RC^+xi)
  const [xi, setXi] = useState(0.08)
  const [convergence, setConvergence] = useState('STABLE')
  const [attractor, setAttractor] = useState('focused')
  const [stability, setStability] = useState(3)

  // Circuit breaker state
  const [circuitBreakers, setCircuitBreakers] = useState({
    open: 0,
    halfOpen: 0,
    total: 7
  })

  // Decision Engine state (v4.3.0 - Work/Delegate/Protect)
  const [decisionState, setDecisionState] = useState({
    mode: DECISION_MODE.WORK,
    rationale: 'Ready for direct work',
    cognitiveBudget: 0.85,
    canSpawn: true,
    flowProtection: false,
    queuedResults: 0
  })

  // Task
  const [task, setTask] = useState('')
  const [isRunning, setIsRunning] = useState(false)

  // Activity log
  const [activity, setActivity] = useState([
    { time: '21:28:45', agent: 'system', message: 'Orchestrator initialized (seed: 42)' },
    { time: '21:28:46', agent: 'determinism_guard', message: 'ThinkingMachines settings applied' },
    { time: '21:28:46', agent: 'echo_curator', message: 'LIVRPS memory layers loaded (6 tiers)' },
    { time: '21:28:47', agent: 'moe_router', message: 'V5 5-phase routing ready (safety floors active)' }
  ])

  // Metrics (accurate structure from metrics.py)
  const [metrics, setMetrics] = useState({
    tasksTotal: 42,
    tasksSucceeded: 40,
    tasksFailed: 2,
    latencyP50: 156,
    latencyP99: 450,
    activeAgents: 0,
    retriesTotal: 3
  })

  // Simulate uptime
  useEffect(() => {
    const interval = setInterval(() => {
      setUptime(prev => prev + 1)
    }, 1000)
    return () => clearInterval(interval)
  }, [])

  // Simulate xi convergence (RC^+xi formula)
  useEffect(() => {
    const interval = setInterval(() => {
      setXi(prev => {
        // xi_n = ||A_{n+1} - A_n||_2  (epistemic tension)
        const next = Math.max(0.02, Math.min(0.3, prev + (Math.random() - 0.52) * 0.015))
        return next
      })
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  // Update convergence based on xi (epsilon = 0.1)
  useEffect(() => {
    const epsilon = 0.1
    if (xi < 0.05) {
      setConvergence('CONVERGED')
      setStability(3)
      setAttractor('focused')
    } else if (xi < epsilon) {
      setConvergence('STABLE')
      setStability(prev => Math.min(3, prev + 1))
    } else if (xi < 0.2) {
      setConvergence('CONVERGING')
      setStability(1)
    } else {
      setConvergence('UNSTABLE')
      setStability(0)
      setAttractor('exploring')
    }
  }, [xi])

  // Format uptime
  const formatUptime = (seconds) => {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    if (h > 0) return `${h}h ${m}m`
    return `${m}m ${seconds % 60}s`
  }

  // V5 5-phase routing simulation
  const routeTask = useCallback((taskText) => {
    const taskLower = taskText.toLowerCase()

    // PHASE 1: ACTIVATE - Signal detection
    const activation = {}
    for (const [expert, config] of Object.entries(MOE_EXPERTS)) {
      const matches = config.triggers.filter(t => taskLower.includes(t)).length
      activation[expert] = Math.min(matches / config.triggers.length, 1.0)
    }

    // PHASE 2: WEIGHT - Apply weights (uniform for now)
    const weighted = { ...activation }

    // PHASE 3: BOUND - Enforce safety floors + normalize
    const bounded = {}
    for (const [expert, score] of Object.entries(weighted)) {
      bounded[expert] = Math.max(score, MOE_EXPERTS[expert].floor)
    }
    const total = Object.values(bounded).reduce((a, b) => a + b, 0)
    for (const expert of Object.keys(bounded)) {
      bounded[expert] = bounded[expert] / total
    }

    // PHASE 4: SELECT - argmax with priority tiebreaker
    let selected = 'executor'
    let maxScore = -1
    for (const [expert, score] of Object.entries(bounded)) {
      if (score > maxScore || (score === maxScore && MOE_EXPERTS[expert].priority < MOE_EXPERTS[selected].priority)) {
        maxScore = score
        selected = expert
      }
    }

    // Check if safety intervention occurred
    const rawWinner = Object.entries(weighted).reduce((a, b) => a[1] > b[1] ? a : b)[0]
    const safetyIntervention = selected !== rawWinner && weighted[rawWinner] > weighted[selected]

    // v4.3.0: Determine decision mode (Work/Delegate/Protect)
    let decisionMode = DECISION_MODE.WORK
    let decisionRationale = 'Direct work with standard support'

    // PROTECT: Peak flow or emotional signals
    if (cognitive.momentum === 'peak') {
      decisionMode = DECISION_MODE.PROTECT
      decisionRationale = 'Peak flow detected - protecting momentum'
    } else if (selected === 'protector' || selected === 'restorer') {
      decisionMode = DECISION_MODE.PROTECT
      decisionRationale = `Safety signal: ${selected} activated`
    }
    // DELEGATE: Complex tasks with high budget
    else if (taskLower.length > 50 && cognitive.energy === 'high' && cognitive.burnout === 'GREEN') {
      decisionMode = DECISION_MODE.DELEGATE
      decisionRationale = 'Complex task + high budget - parallel delegation'
    }
    // WORK: Default for simple/moderate tasks
    else {
      decisionMode = DECISION_MODE.WORK
      decisionRationale = 'Direct work with minimal overhead'
    }

    return { activation, bounded, selected, safetyIntervention, decisionMode, decisionRationale }
  }, [cognitive])

  // Submit task
  const handleSubmit = useCallback((e) => {
    e.preventDefault()
    if (!task.trim() || isRunning) return

    setIsRunning(true)
    const now = new Date().toLocaleTimeString('en-US', { hour12: false })

    // Run V5 5-phase routing
    setMoeState(prev => ({ ...prev, routingPhase: 'activate' }))

    const routing = routeTask(task)

    // Update MoE state with routing result
    setMoeState({
      selectedExpert: routing.selected,
      activationVector: routing.activation,
      boundedScores: routing.bounded,
      safetyIntervention: routing.safetyIntervention,
      routingPhase: 'complete'
    })

    // v4.3.0: Update decision engine state
    setDecisionState(prev => ({
      ...prev,
      mode: routing.decisionMode,
      rationale: routing.decisionRationale,
      flowProtection: routing.decisionMode === DECISION_MODE.PROTECT
    }))

    // Update agents to running state
    setAgents(prev => prev.map(a =>
      a.id === 'moe_router' ? { ...a, status: AGENT_STATUS.RUNNING } : a
    ))

    // Add activity
    const modeInfo = DECISION_MODE_INFO[routing.decisionMode]
    setActivity(prev => [
      { time: now, agent: 'decision_engine', message: `${modeInfo.icon} ${modeInfo.label}: ${routing.decisionRationale.slice(0, 40)}` },
      { time: now, agent: 'moe_router', message: `V5 routing → ${MOE_EXPERTS[routing.selected].displayName}` },
      { time: now, agent: 'task', message: `"${task.slice(0, 35)}..."` },
      ...prev.slice(0, 7)
    ])

    // Simulate task execution
    setTimeout(() => {
      setMetrics(prev => ({
        ...prev,
        tasksTotal: prev.tasksTotal + 1,
        tasksSucceeded: prev.tasksSucceeded + 1
      }))
      setAgents(prev => prev.map(a => ({ ...a, status: AGENT_STATUS.COMPLETED })))
      setActivity(prev => [
        { time: new Date().toLocaleTimeString('en-US', { hour12: false }), agent: 'system', message: 'Task completed (all 7 agents)' },
        ...prev.slice(0, 8)
      ])
      setIsRunning(false)
      setMoeState(prev => ({ ...prev, routingPhase: 'idle' }))
    }, 2000)

    setTask('')
  }, [task, isRunning, routeTask])

  const statusColors = {
    [HEALTH_STATUS.HEALTHY]: 'var(--color-success)',
    [HEALTH_STATUS.DEGRADED]: 'var(--color-warning)',
    [HEALTH_STATUS.UNHEALTHY]: 'var(--color-error)'
  }

  const agentStatusColors = {
    [AGENT_STATUS.COMPLETED]: 'var(--color-success)',
    [AGENT_STATUS.RUNNING]: 'var(--color-primary)',
    [AGENT_STATUS.PENDING]: 'var(--color-text-muted)',
    [AGENT_STATUS.FAILED]: 'var(--color-error)',
    [AGENT_STATUS.DEGRADED]: 'var(--color-warning)',
    [AGENT_STATUS.SKIPPED]: 'var(--color-text-muted)'
  }

  return (
    <div className="maeda-container">
      {/* Header */}
      <header className="maeda-header">
        <h1 className="maeda-title">Orchestra</h1>
        <span className="maeda-subtitle">7-Agent Cognitive System | ThinkingMachines</span>
      </header>

      <main className="maeda-main">
        {/* Row 1: Status + 7 Agents */}

        {/* Hero Status */}
        <section className="maeda-panel maeda-hero">
          <div
            className="maeda-status-orb"
            style={{ backgroundColor: statusColors[status] }}
            title={`System ${status}`}
          />
          <div className="maeda-hero-text">
            <span className="maeda-hero-label">System</span>
            <span className="maeda-hero-value">{status}</span>
          </div>
          <div style={{ marginLeft: 'auto', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            Circuits: {circuitBreakers.open}/{circuitBreakers.total} open
          </div>
        </section>

        {/* 7 Orchestrator Agents */}
        <section className="maeda-panel maeda-agents">
          <h2 className="maeda-panel-title">7 Agents</h2>
          <div className="maeda-agent-dots">
            {agents.map(agent => (
              <div
                key={agent.id}
                className={`maeda-agent-dot`}
                style={{
                  backgroundColor: agentStatusColors[agent.status],
                  opacity: agent.status === AGENT_STATUS.RUNNING ? 1 : 0.8
                }}
                title={`${agent.name}\n${agent.framework}\n${agent.alignment}\nStatus: ${agent.status}`}
              >
                {agent.short}
              </div>
            ))}
          </div>
        </section>

        {/* Row 2: MoE V5 Experts + Convergence */}

        {/* MoE V5 Intervention Experts */}
        <section className="maeda-panel maeda-cognitive" style={{ gridColumn: 'span 6' }}>
          <h2 className="maeda-panel-title">V5 Intervention Experts</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-2)' }}>
            {Object.entries(MOE_EXPERTS).map(([key, expert]) => {
              const score = moeState.boundedScores[key] || 0
              const isSelected = moeState.selectedExpert === key
              const hasFloor = expert.floor > 0
              return (
                <div
                  key={key}
                  style={{
                    padding: 'var(--space-2)',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: isSelected ? 'var(--color-primary-subtle)' : 'var(--color-surface)',
                    border: isSelected ? '2px solid var(--color-primary)' : '1px solid var(--color-border)',
                    textAlign: 'center'
                  }}
                  title={`Priority: ${expert.priority}\nFloor: ${(expert.floor * 100).toFixed(0)}%\nTriggers: ${expert.triggers.join(', ')}`}
                >
                  <div style={{ fontSize: 'var(--font-size-xs)', fontWeight: 500 }}>
                    {expert.displayName}
                  </div>
                  <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>
                    {(score * 100).toFixed(0)}%
                  </div>
                  {hasFloor && (
                    <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-warning)' }}>
                      floor: {(expert.floor * 100).toFixed(0)}%
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          {moeState.safetyIntervention && (
            <div style={{ marginTop: 'var(--space-2)', padding: 'var(--space-2)', backgroundColor: 'var(--color-warning-subtle)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--font-size-xs)' }}>
              Safety floor intervention active
            </div>
          )}
        </section>

        {/* Convergence (RC^+xi) */}
        <section className="maeda-panel maeda-convergence">
          <h2 className="maeda-panel-title">Convergence (RC^+xi)</h2>
          <div className="maeda-xi">
            <span className="maeda-xi-value">{xi.toFixed(3)}</span>
            <span className="maeda-xi-label">xi (epsilon=0.1)</span>
          </div>
          <div className={`maeda-convergence-status maeda-convergence-${convergence.toLowerCase()}`}>
            {convergence}
          </div>
          <div style={{ marginTop: 'var(--space-3)', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            Attractor: {attractor} | Stability: {stability}/3
          </div>
        </section>

        {/* Row 3: Decision Engine (v4.3.0) */}
        <section className="maeda-panel" style={{ gridColumn: 'span 12' }}>
          <h2 className="maeda-panel-title">Decision Engine (v4.3.0) - Work/Delegate/Protect</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-4)' }}>
            {Object.entries(DECISION_MODE_INFO).map(([mode, info]) => {
              const isActive = decisionState.mode === mode
              return (
                <div
                  key={mode}
                  style={{
                    padding: 'var(--space-4)',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: isActive ? `${info.color}22` : 'var(--color-surface)',
                    border: isActive ? `2px solid ${info.color}` : '1px solid var(--color-border)',
                    textAlign: 'center',
                    transition: 'all 0.3s ease'
                  }}
                >
                  <div style={{ fontSize: '2rem', marginBottom: 'var(--space-2)' }}>{info.icon}</div>
                  <div style={{ fontSize: 'var(--font-size-md)', fontWeight: 600, color: isActive ? info.color : 'var(--color-text)' }}>
                    {info.label}
                  </div>
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: 'var(--space-1)' }}>
                    {info.description}
                  </div>
                  {isActive && (
                    <div style={{
                      marginTop: 'var(--space-2)',
                      padding: 'var(--space-1) var(--space-2)',
                      backgroundColor: info.color,
                      color: 'white',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: 'var(--font-size-xs)',
                      fontWeight: 500
                    }}>
                      ACTIVE
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          <div style={{
            marginTop: 'var(--space-3)',
            padding: 'var(--space-2)',
            backgroundColor: 'var(--color-surface)',
            borderRadius: 'var(--radius-sm)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <span style={{ fontSize: 'var(--font-size-sm)' }}>
              <strong>Rationale:</strong> {decisionState.rationale}
            </span>
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
              Budget: {(decisionState.cognitiveBudget * 100).toFixed(0)}% |
              Queued: {decisionState.queuedResults} |
              Flow: {decisionState.flowProtection ? '🛡️' : '—'}
            </span>
          </div>
        </section>

        {/* Row 4: Cognitive State (LIVRPS) */}
        <section className="maeda-panel" style={{ gridColumn: 'span 12' }}>
          <h2 className="maeda-panel-title">Cognitive State (LIVRPS Composition)</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--space-4)' }}>
            <div className="maeda-cognitive-item">
              <span className="maeda-cognitive-label">Burnout</span>
              <span className={`maeda-cognitive-value maeda-burnout-${cognitive.burnout}`}>
                {cognitive.burnout}
              </span>
            </div>
            <div className="maeda-cognitive-item">
              <span className="maeda-cognitive-label">Momentum</span>
              <span className="maeda-cognitive-value">{cognitive.momentum}</span>
            </div>
            <div className="maeda-cognitive-item">
              <span className="maeda-cognitive-label">Paradigm</span>
              <span className="maeda-cognitive-value">{cognitive.paradigm}</span>
            </div>
            <div className="maeda-cognitive-item">
              <span className="maeda-cognitive-label">Altitude</span>
              <span className="maeda-cognitive-value">{cognitive.altitude}</span>
            </div>
            <div className="maeda-cognitive-item">
              <span className="maeda-cognitive-label">Energy</span>
              <span className="maeda-cognitive-value">{cognitive.energy}</span>
            </div>
            <div className="maeda-cognitive-item">
              <span className="maeda-cognitive-label">Memory</span>
              <span className="maeda-cognitive-value">{cognitive.memoryMode.replace('_', ' ')}</span>
            </div>
          </div>
        </section>

        {/* Row 4: Task Input (full width) */}
        <section className="maeda-panel maeda-task">
          <h2 className="maeda-panel-title">Task</h2>
          <form onSubmit={handleSubmit} className="maeda-task-form">
            <input
              type="text"
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="Enter task for orchestration... (try: 'I'm stuck on this complex problem')"
              className="maeda-task-input"
              disabled={isRunning}
            />
            <button
              type="submit"
              className="maeda-task-button"
              disabled={isRunning || !task.trim()}
              style={{ opacity: isRunning || !task.trim() ? 0.5 : 1 }}
            >
              {isRunning ? 'Routing...' : 'Orchestrate'}
            </button>
          </form>
          <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            V5 5-phase: ACTIVATE → WEIGHT → BOUND → SELECT → UPDATE
          </div>
        </section>

        {/* Row 5: Activity + Metrics */}

        {/* Activity Log */}
        <section className="maeda-panel maeda-activity">
          <h2 className="maeda-panel-title">Activity</h2>
          <ul className="maeda-activity-list">
            {activity.map((item, i) => (
              <li key={i} className="maeda-activity-item">
                <span className="maeda-activity-time">{item.time}</span>
                <span className="maeda-activity-agent">{item.agent}</span>
                <span className="maeda-activity-message">{item.message}</span>
              </li>
            ))}
          </ul>
        </section>

        {/* Metrics (accurate from metrics.py) */}
        <section className="maeda-panel maeda-metrics">
          <h2 className="maeda-panel-title">Metrics</h2>
          <div className="maeda-metrics-grid">
            <div className="maeda-metric">
              <div className="maeda-metric-value">{metrics.tasksTotal}</div>
              <div className="maeda-metric-label">Total</div>
            </div>
            <div className="maeda-metric">
              <div className="maeda-metric-value" style={{ color: 'var(--color-success)' }}>
                {metrics.tasksSucceeded}
              </div>
              <div className="maeda-metric-label">Success</div>
            </div>
            <div className="maeda-metric">
              <div className="maeda-metric-value" style={{ color: 'var(--color-error)' }}>
                {metrics.tasksFailed}
              </div>
              <div className="maeda-metric-label">Failed</div>
            </div>
            <div className="maeda-metric">
              <div className="maeda-metric-value">{metrics.latencyP50}ms</div>
              <div className="maeda-metric-label">P50</div>
            </div>
            <div className="maeda-metric">
              <div className="maeda-metric-value">{metrics.latencyP99}ms</div>
              <div className="maeda-metric-label">P99</div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="maeda-footer">
        <span>Seed: {seed}</span>
        <span>Uptime: {formatUptime(uptime)}</span>
        <span>ThinkingMachines</span>
      </footer>
    </div>
  )
}

export default SimplifiedDashboard
