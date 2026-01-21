'use client';

import React from 'react';
import { Canvas } from '@react-three/fiber';
import { MapControls, Stars } from '@react-three/drei';
import { Nodes } from './Nodes';
import { Edges } from './Edges';
import { useGraphData } from './useGraphData';
import { MapNode } from './types';
import * as THREE from 'three';

interface MapCanvasProps {
    onNodeSelect: (node: MapNode | null) => void;
    selectedNode: MapNode | null;
}

export function MapCanvas({ onNodeSelect, selectedNode }: MapCanvasProps) {
    const { data, loading } = useGraphData();

    if (loading) {
        return (
            <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                    <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#64ffda] mb-4"></div>
                    <div className="text-white text-lg">Loading Research Map...</div>
                </div>
            </div>
        );
    }

    const handleNodeClick = (node: MapNode) => {
        onNodeSelect(node);
    };

    return (
        <div className="w-full h-full bg-[#0a0a0a] relative">
            {/* Background gradient overlay */}
            <div className="absolute inset-0 bg-gradient-to-br from-[#1a1a2e]/50 via-transparent to-[#16213e]/50 pointer-events-none" />

            <Canvas
                camera={{ position: [0, 0, 100], fov: 60, near: 0.1, far: 5000 }}
                gl={{ antialias: true, alpha: false }}
                onCreated={({ gl }) => {
                    gl.setClearColor(new THREE.Color('#0a0a0a'));
                }}
            >
                {/* Ambient stars for depth */}
                <Stars radius={300} depth={50} count={1000} factor={2} saturation={0} fade speed={0.5} />

                <MapControls
                    enableRotate={false}
                    screenSpacePanning={true}
                    minZoom={10}
                    maxZoom={500}
                    dampingFactor={0.05}
                    enableDamping
                />

                <ambientLight intensity={0.8} />
                <pointLight position={[0, 0, 50]} intensity={0.5} color="#64ffda" />

                {/* Render edges first (behind nodes) */}
                <Edges
                    edges={data.edges}
                    nodes={data.nodes}
                    selectedNode={selectedNode}
                    hoveredNode={null}
                />

                {/* Render nodes */}
                <Nodes
                    nodes={data.nodes}
                    onNodeClick={handleNodeClick}
                    selectedNode={selectedNode}
                />
            </Canvas>

            {/* Legend */}
            <div className="absolute bottom-6 left-6 bg-black/60 backdrop-blur-md rounded-lg p-4 border border-white/10">
                <div className="text-white text-sm font-semibold mb-2">Legend</div>
                <div className="space-y-2 text-xs text-gray-300">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#4a90e2]"></div>
                        <span>Paper Node</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#64ffda]"></div>
                        <span>Hovered</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#ff79c6]"></div>
                        <span>Selected</span>
                    </div>
                </div>
                <div className="mt-3 pt-3 border-t border-white/10 text-xs text-gray-400">
                    <div>Drag to pan • Scroll to zoom</div>
                    <div className="mt-1">Click node to view details</div>
                </div>
            </div>

            {/* Stats */}
            <div className="absolute top-6 right-6 bg-black/60 backdrop-blur-md rounded-lg p-4 border border-white/10">
                <div className="text-white text-sm font-semibold mb-2">Map Stats</div>
                <div className="space-y-1 text-xs text-gray-300">
                    <div className="flex justify-between gap-4">
                        <span>Papers:</span>
                        <span className="text-[#64ffda] font-mono">{data.nodes.length}</span>
                    </div>
                    <div className="flex justify-between gap-4">
                        <span>Connections:</span>
                        <span className="text-[#64ffda] font-mono">{data.edges.length}</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
