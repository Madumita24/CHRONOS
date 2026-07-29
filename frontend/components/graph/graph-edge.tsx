"use client";

import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";

import type { GraphEdgeRecord } from "@/lib/graph-contract";

export type LineageEdgeData = GraphEdgeRecord & {
  highlighted: boolean;
  dimmed: boolean;
};

export type LineageFlowEdge = Edge<LineageEdgeData, "lineage">;

export function GraphLineageEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  data,
  selected,
}: EdgeProps<LineageFlowEdge>) {
  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });
  const state = data?.compatibilityState ?? "structural";
  const classes = [
    "graph-lineage-edge",
    `compat-${state}`,
    data?.isRootUncertainty ? "root-uncertainty" : "",
    data?.diffState ? `diff-${data.diffState}` : "",
    data?.highlighted ? "highlighted" : "",
    data?.dimmed ? "dimmed" : "",
    selected ? "selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        className={classes}
        interactionWidth={18}
      />
      {data?.isRootUncertainty && (
        <EdgeLabelRenderer>
          <button
            className="root-edge-label nodrag nopan"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            }}
            type="button"
            tabIndex={-1}
            aria-hidden="true"
          >
            UNKNOWN
          </button>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
