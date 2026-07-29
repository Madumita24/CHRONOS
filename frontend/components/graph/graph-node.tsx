"use client";

import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import { humanize } from "@/lib/format";
import type { GraphNodeRecord } from "@/lib/graph-contract";

export type FieldNodeData = GraphNodeRecord & {
  highlighted: boolean;
  dimmed: boolean;
};

export type FieldFlowNode = Node<FieldNodeData, "field">;

export function GraphFieldNode({ data, selected }: NodeProps<FieldFlowNode>) {
  const classes = [
    "graph-field-node",
    data.isChangeOrigin ? "change-origin" : "",
    data.isRootBoundaryTarget ? "boundary-target" : "",
    data.diffState ? `diff-${data.diffState}` : "",
    data.highlighted ? "highlighted" : "",
    data.dimmed ? "dimmed" : "",
    selected ? "selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <article className={classes}>
      <Handle type="target" position={Position.Left} />
      <div className="graph-node-topline">
        <span className="platform-pill">{data.platform}</span>
        {data.diffState && (
          <span className={`diff-pill ${data.diffState}`}>
            {humanize(data.diffState)}
          </span>
        )}
      </div>
      <strong title={data.fieldPath}>{data.fieldPath}</strong>
      <span className="graph-node-dataset" title={data.secondaryLabel}>
        {data.secondaryLabel}
      </span>
      <span className="graph-node-meta">
        Depth {data.depth} · {data.pathCount}{" "}
        {data.pathCount === 1 ? "path" : "paths"}
      </span>
      <Handle type="source" position={Position.Right} />
    </article>
  );
}
