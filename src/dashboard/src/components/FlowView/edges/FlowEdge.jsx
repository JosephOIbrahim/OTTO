import { BaseEdge, getSmoothStepPath } from '@xyflow/react'
import { TOKENS } from '../../StatusView/StatusView'

/**
 * FlowEdge - Animated edge for active paths
 *
 * Uses smooth step path for clean routing
 * Animated dash pattern when active
 * Color changes based on mode
 */

function FlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data
}) {
  const { animated, color, active } = data || {}

  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 16
  })

  const edgeColor = color || TOKENS.colors.text.muted
  const strokeWidth = active ? 2 : 1

  return (
    <>
      {/* Base edge - always visible */}
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: edgeColor,
          strokeWidth,
          strokeOpacity: active ? 1 : 0.4,
          transition: 'stroke 0.3s ease, stroke-opacity 0.3s ease'
        }}
      />

      {/* Animated overlay when active */}
      {animated && (
        <path
          d={edgePath}
          fill="none"
          stroke={edgeColor}
          strokeWidth={strokeWidth}
          strokeDasharray="8 4"
          style={{
            animation: 'flowDash 1s linear infinite'
          }}
        />
      )}

      {/* Glow effect for active edges */}
      {active && (
        <path
          d={edgePath}
          fill="none"
          stroke={edgeColor}
          strokeWidth={6}
          strokeOpacity={0.15}
          style={{
            filter: 'blur(4px)'
          }}
        />
      )}
    </>
  )
}

export default FlowEdge
