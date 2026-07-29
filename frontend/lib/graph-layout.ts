import Dagre from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";

const NODE_WIDTH = 228;
const NODE_HEIGHT = 96;

export function layoutGraph<NodeType extends Node, EdgeType extends Edge>(
  nodes: NodeType[],
  edges: EdgeType[],
): NodeType[] {
  const graph = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  graph.setGraph({
    rankdir: "LR",
    ranksep: 92,
    nodesep: 34,
    edgesep: 18,
    marginx: 28,
    marginy: 28,
    acyclicer: "greedy",
    ranker: "network-simplex",
  });

  for (const node of [...nodes].sort((left, right) =>
    left.id.localeCompare(right.id),
  )) {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of [...edges].sort((left, right) =>
    left.id.localeCompare(right.id),
  )) {
    graph.setEdge(edge.source, edge.target);
  }
  Dagre.layout(graph);

  return nodes.map((node) => {
    const point = graph.node(node.id) as { x: number; y: number };
    return {
      ...node,
      position: {
        x: point.x - NODE_WIDTH / 2,
        y: point.y - NODE_HEIGHT / 2,
      },
    };
  });
}
