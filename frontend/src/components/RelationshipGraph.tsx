import React, { useEffect, useRef, useState } from 'react';
import cytoscape, { Core, EventObject } from 'cytoscape';
import { GraphEdge, GraphNode } from '../types/evidence';

interface RelationshipGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onSelectNode?: (nodeId: string) => void;
  onSelectEdge?: (edgeId: string) => void;
}

const BOUNDARY = 'UNVERIFIED ALLEGATION / EPISTEMOLOGICAL BOUNDARY UNMET';

export const RelationshipGraph: React.FC<RelationshipGraphProps> = ({
  nodes,
  edges,
  onSelectNode,
  onSelectEdge,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [selectedDetails, setSelectedDetails] = useState<string | null>(null);
  const [rejectedEdgesCount, setRejectedEdgesCount] = useState(0);

  useEffect(() => {
    if (!containerRef.current) return;

    let rejectedCount = 0;
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
        rejectedCount += 1;
        return false;
      }
      return true;
    });
    setRejectedEdgesCount(rejectedCount);

    const cyNodes = nodes.map((n) => {
      const unproven = n.evidentiary_status !== 'JUDICIAL_CONVICTION' && n.evidentiary_status !== 'JUDICIAL_ACQUITTAL';
      return {
        data: {
          id: n.id,
          label: `${n.label}\n[${n.evidentiary_status.replace(/_/g, ' ')}]`,
          rawLabel: n.label,
          type: n.type,
          status: n.evidentiary_status,
          nodeBg: '#121212',
          borderColor: unproven ? '#D32F2F' : '#f4f4f1',
        },
      };
    });

    const cyEdges = validatedEdges.map((e) => {
      const isJudicial = e.evidentiary_status === 'JUDICIAL_CONVICTION';
      return {
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          label: isJudicial
            ? `${e.contextual_label.toUpperCase()} [CONVICTED]`
            : `${e.contextual_label.toUpperCase()} [UNPROVEN]`,
          status: e.evidentiary_status,
          edgeColor: isJudicial ? '#f4f4f1' : '#888888',
          lineStyle: isJudicial ? 'solid' : 'dashed',
        },
      };
    });

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...cyNodes, ...cyEdges],
      style: [
        {
          selector: 'node',
          style: {
            shape: 'rectangle',
            label: 'data(label)',
            color: '#f4f4f1',
            'font-family': 'Consolas, "IBM Plex Mono", monospace',
            'font-size': '9px',
            'font-weight': 'bold',
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '130px',
            'background-color': 'data(nodeBg)',
            'border-width': 2,
            'border-color': 'data(borderColor)',
            width: '140px',
            height: '46px',
            'overlay-opacity': 0,
          },
        },
        {
          selector: 'edge',
          style: {
            label: 'data(label)',
            'font-family': 'Consolas, "IBM Plex Mono", monospace',
            'font-size': '8px',
            'font-weight': 'bold',
            color: '#d2d2ce',
            'text-background-color': '#121212',
            'text-background-opacity': 1,
            'text-background-padding': '3px',
            'curve-style': 'straight',
            'target-arrow-shape': 'triangle',
            'line-color': 'data(edgeColor)',
            'target-arrow-color': 'data(edgeColor)',
            'line-style': 'data(lineStyle)' as 'solid' | 'dashed',
            width: 1.5,
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
      setSelectedDetails(
        `NODE ${node.data('rawLabel')} | TYPE ${node.data('type')} | STATUS ${node.data('status')}`,
      );
      onSelectNode?.(node.id());
    });
    cy.on('tap', 'edge', (evt: EventObject) => {
      const edge = evt.target;
      setSelectedDetails(`EDGE ${edge.data('label')} | STATUS ${edge.data('status')}`);
      onSelectEdge?.(edge.id());
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
    };
  }, [nodes, edges, onSelectNode, onSelectEdge]);

  return (
    <section className="graph-shell" aria-label="Relationship DAG">
      <header className="panel-head">
        <div>
          <p className="eyebrow">DETERMINISTIC DAG · PHYSICS DISABLED</p>
          <h2>RELATIONSHIP GRAPH</h2>
        </div>
        <div className="action-row" style={{ border: 0, padding: 0 }}>
          <button type="button" onClick={() => cyRef.current?.zoom((cyRef.current.zoom() || 1) * 1.25)}>
            ZOOM+
          </button>
          <button type="button" onClick={() => cyRef.current?.zoom((cyRef.current.zoom() || 1) * 0.8)}>
            ZOOM-
          </button>
          <button type="button" onClick={() => cyRef.current?.fit()}>
            RESET
          </button>
        </div>
      </header>
      {rejectedEdgesCount > 0 && (
        <p className="panel-alert catastrophic">
          {rejectedEdgesCount} UNPROVEN NAKED ASSOCIATE EDGES REFUSED. {BOUNDARY}
        </p>
      )}
      <div ref={containerRef} className="graph-canvas" />
      <footer>
        <span>{selectedDetails || 'SELECT NODE OR EDGE'}</span>
        <span>HASH INTEGRITY ≠ TRUTH</span>
      </footer>
    </section>
  );
};
