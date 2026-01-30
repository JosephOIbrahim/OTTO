import { BaseEdge } from '@xyflow/react'
import { TOKENS } from '../../StatusView/StatusView'

/**
 * FeedbackEdge - Curved feedback loop from UPDATE to DETECT
 *
 * Features:
 * - Curved bezier path wrapping right side
 * - Dashed animation when active
 * - Green color to indicate feedback flow
 * - Always visible to show continuous loop
 *
 * ThinkingMachines [He2025]: 5-phase loop - UPDATE feeds back to DETECT
 */

function FeedbackEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data
}) {
  const { animated = true, active = true, color = TOKENS.colors.accent.green } = data || {}

  // Calculate curved path that wraps around the right side
  // Source: UPDATE node (right side)
  // Target: STATE node (left side)
  const offsetX = 80  // How far right to curve
  const midY = (sourceY + targetY) / 2

  // Create a smooth bezier curve that goes right then up/down to target
  const edgePath = `
    M ${sourceX} ${sourceY}
    C ${sourceX + offsetX} ${sourceY},
      ${targetX - offsetX} ${targetY},
      ${targetX} ${targetY}
  `

  const strokeWidth = active ? 2 : 1
  const strokeOpacity = active ? 0.8 : 0.3

  return (
    <>
      {/* Glow effect when active */}
      {active && (
        <path
          d={edgePath}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeOpacity={0.1}
          style={{
            filter: 'blur(6px)'
          }}
        />
      )}

      {/* Base edge - always visible */}
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: color,
          strokeWidth,
          strokeOpacity,
          fill: 'none',
          transition: 'stroke 0.3s ease, stroke-opacity 0.3s ease'
        }}
      />

      {/* Animated dashed overlay when active */}
      {animated && (
        <path
          d={edgePath}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray="6 4"
          strokeOpacity={0.9}
          style={{
            animation: 'feedbackDash 1.5s linear infinite'
          }}
        />
      )}

      {/* Arrow marker at target */}
      <defs>
        <marker
          id={`feedback-arrow-${id}`}
          markerWidth="10"
          markerHeight="10"
          refX="9"
          refY="3"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path
            d="M0,0 L0,6 L9,3 z"
            fill={color}
            opacity={strokeOpacity}
          />
        </marker>
      </defs>

      {/* Path with arrow */}
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={1}
        markerEnd={`url(#feedback-arrow-${id})`}
      />

      {/* Loop indicator icon */}
      <g transform={`translate(${sourceX + offsetX / 2}, ${midY})`}>
        <circle
          r="10"
          fill={TOKENS.colors.bg.card}
          stroke={color}
          strokeWidth="1"
          opacity={active ? 0.9 : 0.4}
        />
        <text
          textAnchor="middle"
          dominantBaseline="central"
          fontSize="10"
          fill={color}
          style={{
            fontFamily: 'system-ui',
            animation: active ? 'spin 3s linear infinite' : 'none'
          }}
        >
          ↻
        </text>
      </g>
    </>
  )
}

export default FeedbackEdge
