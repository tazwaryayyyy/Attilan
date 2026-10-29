import React, { useEffect, useRef, useState } from 'react';
import cytoscape, { Core, EventObject } from 'cytoscape';
import { GraphEdge, GraphNode } from '../types/evidence';
import { Network, ZoomIn, ZoomOut, RotateCcw, AlertOctagon } from 'lucide-react';

interface RelationshipGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onSelectNode?: (nodeId: string) => void;
  onSelectEdge?: (edgeId: string) => void;
}

export const RelationshipGraph: React.FC<RelationshipGraphProps> = ({
  nodes,
  edges,
  onSelectNode,
  onSelectEdge,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [selectedDetails, setSelectedDetails] = useState<string | null>(null);
  const [rejectedEdgesCount, setRejectedEdgesCount] = useState<number>(0);

  useEffect(() => {
    if (!containerRef.current) return;

    let rejectedCount = 0;

    // Strict Rule: Refuse to draw unproven generic "associate" edges (RT-04 Anti-Bias Gate)
    const validatedEdges = edges.filter((edge) => {
      const labelUpper = (edge.contextual_label || edge.relationship_type || '').toUpperCase().trim();
      const isUnproven = edge.evidentiary_status !== 'JUDICIAL_CONVICTION';

      const isNakedAssociate =
        labelUpper === 'ASSOCIATE' ||
        labelUpper === 'ASSOCIATES' ||
        labelUpper === 'ASSOCIATE_OF' ||
        labelUpper === 'CO-CONSPIRATOR' ||
        labelUpper === 'SUSPECTED ASSOCIATE';

      if (isUnproven && isNakedAssociate) {
        rejectedCount++;
        return false;
      }
      return true;
    });

    setRejectedEdgesCount(rejectedCount);

    // Format elements for deterministic Cytoscape rendering
    const cyNodes = nodes.map((n) => {
      let nodeBg = '#09090b'; // zinc-950
      let borderColor = '#52525b'; // zinc-600

      if (n.evidentiary_status === 'JUDICIAL_CONVICTION') {
        nodeBg = '#022c22'; // emerald-950
        borderColor = '#10b981'; // emerald-500
      } else if (n.evidentiary_status === 'CHARGE_SHEET_ALLEGED') {
        nodeBg = '#172554'; // blue-950
        borderColor = '#3b82f6'; // blue-500
      } else if (
        n.evidentiary_status === 'FIR_COGNIZANCE' ||
        n.evidentiary_status === 'GD_REGISTERED'
      ) {
        nodeBg = '#451a03'; // amber-950
        borderColor = '#d97706'; // amber-600
      } else if (n.evidentiary_status === 'JUDICIAL_ACQUITTAL') {
        nodeBg = '#134e4a'; // teal-900
        borderColor = '#14b8a6'; // teal-500
      }

      return {
        data: {
          id: n.id,
          label: `${n.label}\n[${n.evidentiary_status.replace(/_/g, ' ')}]`,
          rawLabel: n.label,
          type: n.type,
          status: n.evidentiary_status,
          nodeBg,
          borderColor,
        },
      };
    });

    const cyEdges = validatedEdges.map((e) => {
      const isJudicial = e.evidentiary_status === 'JUDICIAL_CONVICTION';
      const edgeColor = isJudicial ? '#10b981' : '#a1a1aa';
      const lineStyle = isJudicial ? 'solid' : 'dashed';

      // Mandate legally qualified boundary in label
      const literalLabel = isJudicial
        ? `${e.contextual_label.toUpperCase()} [CONVICTED]`
        : `${e.contextual_label.toUpperCase()} [UNPROVEN]`;

      return {
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          label: literalLabel,
          status: e.evidentiary_status,
          edgeColor,
          lineStyle,
        },
      };
    });

    // Deterministic Directed Acyclic Graph (DAG) Layout - Zero Physics / Spring Force
    const cy = cytoscape({
      container: containerRef.current,
      elements: [...cyNodes, ...cyEdges],
      style: [
        {
          selector: 'node',
          style: {
            shape: 'rectangle',
            label: 'data(label)',
            color: '#f4f4f5',
            'font-family': 'ui-monospace, monospace',
            'font-size': '9px',
            'font-weight': 'bold',
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '130px',
            'background-color': 'data(nodeBg)',
            'border-width': 1.5,
            'border-color': 'data(borderColor)',
            width: '140px',
            height: '46px',
            'overlay-opacity': 0,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 2.5,
            'border-color': '#ffffff',
          },
        },
        {
          selector: 'edge',
          style: {
            label: 'data(label)',
            'font-family': 'ui-monospace, monospace',
            'font-size': '8px',
            'font-weight': 'bold',
            color: '#d4d4d8',
            'text-background-color': '#09090b',
            'text-background-opacity': 1,
            'text-background-padding': '3px',
            'text-background-shape': 'rectangle',
            'text-border-color': '#3f3f46',
            'text-border-width': 1,
            'text-border-opacity': 1,
            'curve-style': 'straight', // Strict straight edges, no bezier curves
            'target-arrow-shape': 'triangle',
            'line-color': 'data(edgeColor)',
            'target-arrow-color': 'data(edgeColor)',
            'line-style': 'data(lineStyle)' as any,
            width: 1.5,
            'arrow-scale': 1.0,
          },
        },
      ],
      layout: {
        name: 'breadthfirst',
        directed: true,
        spacingFactor: 1.15,
        avoidOverlap: true,
        circle: false,
        grid: false,
        fit: true,
        padding: 30,
      },
    });

    cy.on('tap', 'node', (evt: EventObject) => {
      const node = evt.target;
      setSelectedDetails(`NODE: ${node.data('rawLabel')} | TYPE: ${node.data('type')} | EVIDENTIARY STATUS: ${node.data('status')}`);
      onSelectNode?.(node.id());
    });

    cy.on('tap', 'edge', (evt: EventObject) => {
      const edge = evt.target;
      setSelectedDetails(`EDGE: ${edge.data('label')} | STATUS: ${edge.data('status')}`);
      onSelectEdge?.(edge.id());
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
  }, [nodes, edges]);

  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleReset = () => cyRef.current?.fit();

  return (
    <div className="relative w-full h-[580px] border border-zinc-800 bg-zinc-950 flex flex-col rounded-none">
      {/* Top Controls & Status Bar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800 bg-zinc-900 text-zinc-200">
        <div className="flex items-center gap-2">
          <Network className="h-3.5 w-3.5 text-zinc-400" />
          <span className="text-[11px] font-mono font-bold tracking-wider uppercase text-zinc-300">
            DETERMINISTIC RELATIONSHIP DAG
          </span>
          <span className="font-mono text-[9px] bg-zinc-800 text-zinc-400 px-1.5 py-0.5 border border-zinc-700">
            PHYSICS DISABLED
          </span>
        </div>

        {rejectedEdgesCount > 0 && (
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-amber-300 bg-amber-950/80 px-2 py-0.5 border border-amber-700">
            <AlertOctagon className="h-3 w-3 text-amber-400" />
            <span>{rejectedEdgesCount} UNPROVEN NAKED ASSOCIATE EDGES REFUSED</span>
          </div>
        )}

        <div className="flex items-center gap-1">
          <button
            onClick={handleZoomIn}
            className="p-1 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded-none border border-zinc-700 text-xs"
            title="Zoom In"
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={handleZoomOut}
            className="p-1 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded-none border border-zinc-700 text-xs"
            title="Zoom Out"
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={handleReset}
            className="p-1 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded-none border border-zinc-700 text-xs"
            title="Reset View"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Deterministic DAG Canvas */}
      <div ref={containerRef} className="w-full flex-1 bg-zinc-950" />

      {/* Selected Element Technical Diagnostic Bar */}
      <div className="px-3 py-1.5 border-t border-zinc-800 bg-zinc-900 text-[10px] font-mono text-zinc-400 flex items-center justify-between">
        <span className="truncate">{selectedDetails || 'SELECT NODE OR EDGE TO INSPECT EVIDENTIARY CHAIN OF CUSTODY'}</span>
        <span className="text-zinc-500 shrink-0 ml-2">POSTGRESQL 17 RECURSIVE CTE ENGINE</span>
      </div>
    </div>
  );
};
