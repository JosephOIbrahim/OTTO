import { useMemo, useCallback, useEffect, useRef } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import StateNode from './nodes/StateNode'
import DecisionNode from './nodes/DecisionNode'
import ExecutionNode from './nodes/ExecutionNode'
import StorageNode from './nodes/StorageNode'
import CascadeNode from './nodes/CascadeNode'
import LockNode from './nodes/LockNode'
import UpdateNode from './nodes/UpdateNode'
import FlowEdge from './edges/FlowEdge'
import FeedbackEdge from './edges/FeedbackEdge'
import { mapStateToNodes, mapStateToEdges, getInitialViewport } from './flowUtils'
import { TOKENS } from '../StatusView/StatusView'

/**
 * FlowView - React Flow visualization of Orchestra cognitive flow
 *
 * 5-Phase NEXUS Pipeline (ThinkingMachines Determinism):
 * DETECT → CASCADE → LOCK → EXECUTE/PROTECT → UPDATE → (feedback to DETECT)
 *
 * Real-time updates from WebSocket state
 * Rivian aesthetic with dark theme
 *
 * Key architecture: Node POSITIONS persist across state updates.
 * Only node DATA updates from WebSocket - positions are user-controlled.
 */

// Custom node types - 5-phase NEXUS pipeline
const nodeTypes = {
  stateNode: StateNode,       // Phase 1: DETECT
  cascadeNode: CascadeNode,   // Phase 2: CASCADE (7-expert Cognitive Safety MoE)
  lockNode: LockNode,         // Phase 3: LOCK (MAX3 + params)
  executionNode: ExecutionNode, // Phase 4: EXECUTE (work/delegate)
  storageNode: StorageNode,   // Phase 4: PROTECT
  updateNode: UpdateNode,     // Phase 5: UPDATE (RC^+xi)
  // Legacy support
  decisionNode: DecisionNode
}

// Custom edge types
const edgeTypes = {
  flowEdge: FlowEdge,
  feedbackEdge: FeedbackEdge  // Curved feedback loop UPDATE → DETECT
}

// Dark theme for React Flow
const proOptions = { hideAttribution: true }

function FlowView({ state, time, onCommand }) {
  // Track if initial nodes have been set
  const initializedRef = useRef(false)

  // Get initial nodes/edges only once
  const initialNodes = useMemo(() => mapStateToNodes(state, onCommand), [])
  const initialEdges = useMemo(() => mapStateToEdges(state), [])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  // Update node DATA without changing positions
  useEffect(() => {
    if (!initializedRef.current) {
      initializedRef.current = true
      return
    }

    const newNodesData = mapStateToNodes(state, onCommand)
    const newEdges = mapStateToEdges(state)

    // Update existing nodes' data while preserving positions
    setNodes(currentNodes => {
      const nodeMap = new Map(currentNodes.map(n => [n.id, n]))

      return newNodesData.map(newNode => {
        const existing = nodeMap.get(newNode.id)
        if (existing) {
          // Preserve position, update data
          return {
            ...newNode,
            position: existing.position
          }
        }
        // New node - use default position
        return newNode
      })
    })

    setEdges(newEdges)
  }, [state, onCommand, setNodes, setEdges])

  return (
    <div style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.brandName}>ORCHESTRA</span>
          <span style={styles.viewBadge}>FLOW VIEW</span>
        </div>
        <div style={styles.headerRight}>
          <span style={styles.time}>
            {time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
          </span>
          <div style={{
            ...styles.connectionIndicator,
            backgroundColor: state.claudeConnected ? TOKENS.colors.accent.green : TOKENS.colors.text.dim
          }} />
        </div>
      </header>

      {/* Flow Canvas */}
      <div style={styles.flowContainer}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          defaultViewport={getInitialViewport()}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          proOptions={proOptions}
          nodesDraggable={true}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnScroll
          zoomOnScroll
          minZoom={0.5}
          maxZoom={1.5}
        >
          <Background
            color={TOKENS.colors.text.dim}
            gap={24}
            size={1}
            variant="dots"
          />
          <Controls
            showInteractive={false}
            style={styles.controls}
          />
          <MiniMap
            nodeColor={(node) => {
              if (node.type === 'stateNode') return node.data.burnoutColor
              if (node.type === 'decisionNode') return node.data.modeColor
              if (node.type === 'storageNode') return TOKENS.colors.accent.purple
              return TOKENS.colors.text.muted
            }}
            maskColor={`${TOKENS.colors.bg.primary}90`}
            style={styles.minimap}
          />
        </ReactFlow>
      </div>

      {/* Footer */}
      <footer style={styles.footer}>
        <span style={styles.version}>v4.3.0</span>
        <span style={styles.footerText}>
          {state.claudeConnected ? 'CLAUDE CODE CONNECTED' : 'DISCONNECTED'}
        </span>
      </footer>

      {/* CSS Animations */}
      <style>
        {`
          @keyframes flowDash {
            to {
              stroke-dashoffset: -12;
            }
          }

          @keyframes feedbackDash {
            to {
              stroke-dashoffset: -20;
            }
          }

          @keyframes pulse {
            0%, 100% {
              opacity: 1;
              transform: scale(1);
            }
            50% {
              opacity: 0.5;
              transform: scale(1.1);
            }
          }

          @keyframes lockPulse {
            0%, 100% {
              transform: translateX(0%);
              opacity: 1;
            }
            50% {
              transform: translateX(100%);
              opacity: 0.5;
            }
          }

          @keyframes spin {
            from {
              transform: rotate(0deg);
            }
            to {
              transform: rotate(360deg);
            }
          }

          .react-flow__controls {
            background: ${TOKENS.colors.bg.card} !important;
            border: 1px solid ${TOKENS.colors.border} !important;
            border-radius: 8px !important;
          }

          .react-flow__controls-button {
            background: ${TOKENS.colors.bg.elevated} !important;
            border: none !important;
            border-bottom: 1px solid ${TOKENS.colors.border} !important;
          }

          .react-flow__controls-button:hover {
            background: ${TOKENS.colors.bg.secondary} !important;
          }

          .react-flow__controls-button svg {
            fill: ${TOKENS.colors.text.secondary} !important;
          }

          .react-flow__minimap {
            background: ${TOKENS.colors.bg.card} !important;
            border: 1px solid ${TOKENS.colors.border} !important;
            border-radius: 8px !important;
          }
        `}
      </style>
    </div>
  )
}

const styles = {
  container: {
    position: 'absolute',
    inset: 0,
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: TOKENS.colors.bg.primary,
    fontFamily: '"Space Grotesk", "Inter", -apple-system, system-ui, sans-serif'
  },

  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: `${TOKENS.space.md} ${TOKENS.space.xl}`,
    borderBottom: `1px solid ${TOKENS.colors.border}`,
    zIndex: 10
  },

  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: TOKENS.space.md
  },

  brandName: {
    fontSize: '14px',
    fontWeight: '500',
    letterSpacing: '0.2em',
    color: TOKENS.colors.text.secondary
  },

  viewBadge: {
    fontSize: '9px',
    fontWeight: '600',
    letterSpacing: '0.1em',
    color: TOKENS.colors.accent.blue,
    backgroundColor: `${TOKENS.colors.accent.blue}15`,
    padding: '4px 8px',
    borderRadius: '4px'
  },

  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: TOKENS.space.md
  },

  time: {
    fontSize: '14px',
    fontWeight: '400',
    fontFamily: '"JetBrains Mono", "SF Mono", monospace',
    color: TOKENS.colors.text.muted,
    letterSpacing: '0.05em'
  },

  connectionIndicator: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    transition: 'background-color 0.3s ease'
  },

  flowContainer: {
    flex: 1,
    position: 'relative'
  },

  controls: {
    borderRadius: '8px'
  },

  minimap: {
    borderRadius: '8px'
  },

  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: `${TOKENS.space.sm} ${TOKENS.space.xl}`,
    borderTop: `1px solid ${TOKENS.colors.border}`,
    zIndex: 10
  },

  version: {
    fontSize: '10px',
    fontFamily: '"JetBrains Mono", monospace',
    color: TOKENS.colors.text.dim,
    letterSpacing: '0.05em'
  },

  footerText: {
    fontSize: '9px',
    fontWeight: '500',
    letterSpacing: '0.1em',
    color: TOKENS.colors.text.dim
  }
}

export default FlowView
