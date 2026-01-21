'use client';

import React, { useRef, useMemo } from 'react';
import * as THREE from 'three';
import { MapEdge, MapNode } from './types';

interface EdgesProps {
    edges: MapEdge[];
    nodes: MapNode[];
    selectedNode: MapNode | null;
    hoveredNode: MapNode | null;
}

export function Edges({ edges, nodes, selectedNode, hoveredNode }: EdgesProps) {
    const linesRef = useRef<THREE.LineSegments>(null);

    const nodeMap = useMemo(() => {
        const map = new Map<string, MapNode>();
        nodes.forEach(node => map.set(node.id, node));
        return map;
    }, [nodes]);

    const { positions, colors } = useMemo(() => {
        const positions: number[] = [];
        const colors: number[] = [];

        edges.forEach(edge => {
            const sourceNode = nodeMap.get(edge.source);
            const targetNode = nodeMap.get(edge.target);

            if (!sourceNode || !targetNode) return;

            // Scale coordinates
            const sx = sourceNode.x * 0.1;
            const sy = sourceNode.y * 0.1;
            const tx = targetNode.x * 0.1;
            const ty = targetNode.y * 0.1;

            positions.push(sx, sy, 0, tx, ty, 0);

            // Determine opacity based on selection/hover state
            let opacity = 0.05;

            if (selectedNode && (edge.source === selectedNode.id || edge.target === selectedNode.id)) {
                opacity = 0.6;
            } else if (hoveredNode && (edge.source === hoveredNode.id || edge.target === hoveredNode.id)) {
                opacity = 0.4;
            }

            // Add color with opacity (white)
            colors.push(1, 1, 1, opacity, 1, 1, 1, opacity);
        });

        return { positions: new Float32Array(positions), colors: new Float32Array(colors) };
    }, [edges, nodeMap, selectedNode, hoveredNode]);

    return (
        <lineSegments ref={linesRef}>
            <bufferGeometry>
                <bufferAttribute
                    attach="attributes-position"
                    args={[positions, 3]}
                />
                <bufferAttribute
                    attach="attributes-color"
                    args={[colors, 4]}
                />
            </bufferGeometry>
            <lineBasicMaterial vertexColors transparent opacity={1} />
        </lineSegments>
    );
}
