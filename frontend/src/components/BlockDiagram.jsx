import { useEffect, useMemo } from 'react'
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

const KIND_STYLES = {
  composition: { stroke: '#7c3aed' },
  aggregation: { stroke: '#7c3aed', strokeDasharray: '2 3' },
  association: { stroke: '#6b7280' },
  dependency: { stroke: '#d97706', strokeDasharray: '6 4' },
  generalization: { stroke: '#0891b2' },
}

// Composition is the dominant edge (nearly every block has one from the
// root) and its meaning is already conveyed by tree position, so labeling
// it just adds visual noise -- only the more informative kinds get labels.
const LABELED_KINDS = new Set(['aggregation', 'association', 'dependency', 'generalization'])

const TIER_GAP = 70
const SUBROW_HEIGHT = 240
const MAX_PER_ROW = 4
const NODE_WIDTH = 230
const NODE_GAP = 80

function BlockNode({ data }) {
  return (
    <div className={`uml-block${data.isRoot ? ' uml-block-root' : ''}`}>
      <Handle type="target" position={Position.Top} id="t-top" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Bottom} id="t-bottom" style={{ opacity: 0 }} />
      <div className="uml-block-name">{data.name}</div>
      <div className="uml-block-stereotype">«{data.isRoot ? 'system' : 'block'}»</div>
      {data.description && <div className="uml-block-description">{data.description}</div>}
      <Handle type="source" position={Position.Bottom} id="s-bottom" style={{ opacity: 0 }} />
    </div>
  )
}

const NODE_TYPES = { block: BlockNode }

function computeTiers(blocks, connectors) {
  const root = blocks.find((b) => b.isRoot) ?? blocks[0]
  const childrenMap = new Map()
  connectors
    .filter((c) => c.kind === 'composition' || c.kind === 'aggregation')
    .forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      childrenMap.get(c.source).push(c.target)
    })

  const tierOf = new Map()
  if (root) {
    const queue = [[root.id, 0]]
    while (queue.length) {
      const [id, tier] = queue.shift()
      if (tierOf.has(id)) continue
      tierOf.set(id, tier)
      for (const childId of childrenMap.get(id) ?? []) {
        if (!tierOf.has(childId)) queue.push([childId, tier + 1])
      }
    }
  }

  const maxTier = tierOf.size ? Math.max(...tierOf.values()) : 0
  blocks.forEach((b) => {
    if (!tierOf.has(b.id)) tierOf.set(b.id, maxTier + 1)
  })

  return tierOf
}

function buildLayout(blocks, connectors) {
  const tierOf = computeTiers(blocks, connectors)
  const byTier = new Map()
  blocks.forEach((b) => {
    const tier = tierOf.get(b.id)
    if (!byTier.has(tier)) byTier.set(tier, [])
    byTier.get(tier).push(b)
  })
  const sortedTiers = [...byTier.keys()].sort((a, b) => a - b)

  const nodes = []
  const yOf = new Map()
  let yCursor = 0

  sortedTiers.forEach((tier) => {
    const tierBlocks = byTier.get(tier)
    // Wrap a wide tier into multiple rows instead of one row that keeps
    // growing wider forever as a system gets more subsystems.
    const rows = []
    for (let i = 0; i < tierBlocks.length; i += MAX_PER_ROW) {
      rows.push(tierBlocks.slice(i, i + MAX_PER_ROW))
    }

    rows.forEach((rowBlocks, rowIndex) => {
      const y = yCursor + rowIndex * SUBROW_HEIGHT
      const rowWidth = rowBlocks.length * (NODE_WIDTH + NODE_GAP) - NODE_GAP
      rowBlocks.forEach((block, i) => {
        yOf.set(block.id, y)
        nodes.push({
          id: block.id,
          type: 'block',
          position: { x: i * (NODE_WIDTH + NODE_GAP) - rowWidth / 2, y },
          data: {
            name: block.name,
            description: block.description,
            isRoot: block.isRoot,
          },
          style: { width: NODE_WIDTH },
        })
      })
    })

    yCursor += rows.length * SUBROW_HEIGHT + TIER_GAP
  })

  const edges = connectors.map((connector, i) => {
    const style = KIND_STYLES[connector.kind] ?? KIND_STYLES.association
    const sameRow = yOf.get(connector.source) === yOf.get(connector.target)

    return {
      id: `edge-${i}`,
      source: connector.source,
      target: connector.target,
      // Links between boxes on the same visual row arc below it
      // (bottom-to-bottom) instead of cutting straight across through
      // whatever sits in between; everything else routes top-to-bottom.
      sourceHandle: 's-bottom',
      targetHandle: sameRow ? 't-bottom' : 't-top',
      type: sameRow ? 'default' : 'smoothstep',
      label: LABELED_KINDS.has(connector.kind) ? connector.label || connector.kind : undefined,
      style: { stroke: style.stroke, strokeDasharray: style.strokeDasharray },
      markerEnd: { type: MarkerType.ArrowClosed, color: style.stroke },
      labelStyle: { fontSize: 11, fill: 'var(--text)' },
      labelBgStyle: { fill: 'var(--bg)' },
      labelBgPadding: [4, 2],
    }
  })

  return { nodes, edges }
}

export function BlockDiagram({ blocks, connectors }) {
  const layout = useMemo(() => {
    if (blocks.length === 0) return { nodes: [], edges: [] }
    return buildLayout(blocks, connectors)
  }, [blocks, connectors])

  // React Flow only applies drag/selection changes back onto the nodes you
  // hand it if you own that state via useNodesState + onNodesChange -- a
  // plain `nodes={...}` prop with no change handler makes dragging a no-op.
  const [nodes, setNodes, onNodesChange] = useNodesState(layout.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(layout.edges)

  useEffect(() => {
    setNodes(layout.nodes)
    setEdges(layout.edges)
  }, [layout, setNodes, setEdges])

  if (blocks.length === 0) {
    return (
      <p className="empty-state">
        No diagram yet — describe a system and click Generate.
      </p>
    )
  }

  return (
    <div className="diagram-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={NODE_TYPES}
        nodesDraggable
        nodesConnectable={false}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  )
}
