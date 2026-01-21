'use client';

import React, { useRef, useEffect, useState, useCallback } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';
import { MapNode, MapEdge } from './types';
import { useGraphData } from './useGraphData';

interface Graph3DCanvasProps {
    onNodeSelect: (node: MapNode | null) => void;
    selectedNode: MapNode | null;
}

interface GraphNode extends MapNode {
    name: string;
    val: number;
    color: string;
}

interface GraphLink {
    source: string;
    target: string;
    value: number;
}

interface ForceGraphInstance {
    cameraPosition: (position: { x: number; y: number; z: number }, lookAt?: GraphNode, duration?: number) => void;
    scene: () => THREE.Scene;
}

export function Graph3DCanvas({ onNodeSelect, selectedNode }: Graph3DCanvasProps) {
    const { data, loading } = useGraphData();
    const fgRef = useRef<ForceGraphInstance | null>(null);
    const [highlightNodes, setHighlightNodes] = useState(new Set<string>());
    const [highlightLinks, setHighlightLinks] = useState(new Set<MapEdge>());
    const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);

    // Transform data for force-graph
    const graphData = {
        nodes: data.nodes.map(node => ({
            ...node,
            id: node.id,
            name: node.label,
            val: Math.log(node.citation_count || 1) * 2,
            color: selectedNode?.id === node.id ? '#ff79c6' : '#4a90e2'
        })),
        links: data.edges.map(edge => ({
            source: edge.source,
            target: edge.target,
            value: edge.weight
        }))
    };

    useEffect(() => {
        if (fgRef.current) {
            fgRef.current.cameraPosition({ x: 0, y: 0, z: 400 });

            const scene = fgRef.current.scene();
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
            scene.add(ambientLight);

            const pointLight = new THREE.PointLight(0x64ffda, 1, 1000);
            pointLight.position.set(0, 0, 300);
            scene.add(pointLight);
        }
    }, []);

    useEffect(() => {
        if (selectedNode) {
            const neighbors = new Set<string>();
            const links = new Set<MapEdge>();

            data.edges.forEach(edge => {
                if (edge.source === selectedNode.id) {
                    neighbors.add(edge.target);
                    links.add(edge);
                } else if (edge.target === selectedNode.id) {
                    neighbors.add(edge.source);
                    links.add(edge);
                }
            });

            neighbors.add(selectedNode.id);
            setHighlightNodes(neighbors);
            setHighlightLinks(links);
        } else {
            setHighlightNodes(new Set());
            setHighlightLinks(new Set());
        }
    }, [selectedNode, data.edges]);

    const handleNodeClick = useCallback((node: GraphNode) => {
        onNodeSelect(node);

        if (fgRef.current && node.x !== undefined && node.y !== undefined && node.z !== undefined) {
            const distance = 150;
            const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);

            fgRef.current.cameraPosition(
                { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
                node,
                1000
            );
        }
    }, [onNodeSelect]);

    const handleNodeHover = useCallback((node: GraphNode | null) => {
        setHoverNode(node);
    }, []);

    if (loading) {
        return (
            <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                    <div className="inline-block animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-[#64ffda] mb-4"></div>
                    <div className="text-white text-xl">Loading 3D Research Map...</div>
                </div>
            </div>
        );
    }

    return (
        <div className="w-full h-full relative">
            <ForceGraph3D
                ref={fgRef as any}
                graphData={graphData}
                backgroundColor="#0a0a0a"
                nodeLabel="name"
                nodeAutoColorBy="type"
                nodeVal="val"
                nodeColor={(node: GraphNode) => {
                    if (selectedNode?.id === node.id) return '#ff79c6';
                    if (highlightNodes.has(node.id)) return '#64ffda';
                    return hoverNode?.id === node.id ? '#64ffda' : '#4a90e2';
                }}
                nodeOpacity={0.9}
                nodeResolution={16}
                linkColor={(link: GraphLink) => {
                    const isHighlighted = Array.from(highlightLinks).some(
                        hl => (hl.source === link.source && hl.target === link.target)
                    );
                    return isHighlighted ? '#64ffda' : 'rgba(255,255,255,0.1)';
                }}
                linkWidth={(link: GraphLink) => {
                    const isHighlighted = Array.from(highlightLinks).some(
                        hl => (hl.source === link.source && hl.target === link.target)
                    );
                    return isHighlighted ? 2 : 0.5;
                }}
                linkOpacity={0.6}
                linkDirectionalParticles={(link: GraphLink) => {
                    const isHighlighted = Array.from(highlightLinks).some(
                        hl => (hl.source === link.source && hl.target === link.target)
                    );
                    return isHighlighted ? 4 : 0;
                }}
                linkDirectionalParticleWidth={2}
                linkDirectionalParticleSpeed={0.005}
                onNodeClick={handleNodeClick}
                onNodeHover={handleNodeHover}
                enableNodeDrag={true}
                enableNavigationControls={true}
                showNavInfo={false}
                d3AlphaDecay={0.02}
                d3VelocityDecay={0.3}
            />

            {hoverNode && (
                <div className="absolute top-4 left-1/2 transform -translate-x-1/2 pointer-events-none">
                    <div className="bg-black/90 text-white px-4 py-3 rounded-lg border border-[#64ffda]/30 shadow-lg backdrop-blur-sm">
                        <div className="font-semibold text-sm">{hoverNode.name}</div>
                        {hoverNode.year && (
                            <div className="text-xs text-gray-400 mt-1">
                                {hoverNode.year} • {hoverNode.citation_count?.toLocaleString() || 0} citations
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
