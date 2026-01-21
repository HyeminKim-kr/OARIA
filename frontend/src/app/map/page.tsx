'use client';

import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { SidePanel } from '@/components/research-map/SidePanel';
import { MapNode } from '@/components/research-map/types';
import { Search, Layers, Maximize2, Minimize2 } from 'lucide-react';

// Dynamically import Graph3DCanvas to avoid SSR issues
const Graph3DCanvas = dynamic(
    () => import('@/components/research-map/Graph3DCanvas').then(mod => mod.Graph3DCanvas),
    {
        ssr: false,
        loading: () => (
            <div className="absolute inset-0 flex items-center justify-center bg-[#0a0a0a]">
                <div className="text-center">
                    <div className="inline-block animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-[#64ffda] mb-4"></div>
                    <div className="text-white text-xl font-semibold">Loading 3D Map...</div>
                    <div className="text-gray-400 text-sm mt-2">Preparing force-directed graph...</div>
                </div>
            </div>
        )
    }
);

export default function MapPage() {
    const [selectedNode, setSelectedNode] = useState<MapNode | null>(null);
    const [mounted, setMounted] = useState(false);
    const [isFullscreen, setIsFullscreen] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    const toggleFullscreen = () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
            setIsFullscreen(true);
        } else {
            document.exitFullscreen();
            setIsFullscreen(false);
        }
    };

    if (!mounted) return null;

    return (
        <div className="w-screen h-screen relative overflow-hidden bg-[#0a0a0a]">
            {/* Header */}
            <div className="absolute top-0 left-0 right-0 z-30 pointer-events-none">
                <div className="flex items-center justify-between p-6">
                    <div className="pointer-events-auto">
                        <h1 className="text-white font-bold text-2xl flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#64ffda] to-[#4a90e2] flex items-center justify-center shadow-lg shadow-[#64ffda]/20">
                                <Layers size={20} className="text-white" />
                            </div>
                            <div>
                                <div>Research Map 3D</div>
                                <div className="text-xs text-gray-400 font-normal">Force-directed graph visualization</div>
                            </div>
                        </h1>
                    </div>

                    <div className="flex items-center gap-3 pointer-events-auto">
                        {/* Search bar */}
                        <div className="flex items-center gap-2 bg-black/60 backdrop-blur-md rounded-xl px-4 py-2.5 border border-white/10 min-w-[300px]">
                            <Search size={18} className="text-gray-400" />
                            <input
                                type="text"
                                placeholder="Search papers..."
                                className="bg-transparent text-white text-sm outline-none flex-1 placeholder-gray-500"
                            />
                        </div>

                        {/* Fullscreen toggle */}
                        <button
                            onClick={toggleFullscreen}
                            className="p-2.5 bg-black/60 backdrop-blur-md rounded-xl border border-white/10 hover:bg-white/10 transition-colors"
                            title="Toggle fullscreen"
                        >
                            {isFullscreen ? (
                                <Minimize2 size={18} className="text-gray-400" />
                            ) : (
                                <Maximize2 size={18} className="text-gray-400" />
                            )}
                        </button>
                    </div>
                </div>
            </div>

            {/* Controls hint */}
            <div className="absolute bottom-6 left-6 z-30 bg-black/60 backdrop-blur-md rounded-lg p-4 border border-white/10 pointer-events-none">
                <div className="text-white text-sm font-semibold mb-2">Controls</div>
                <div className="space-y-1 text-xs text-gray-300">
                    <div>• <span className="text-[#64ffda]">Left click + drag</span> - Rotate</div>
                    <div>• <span className="text-[#64ffda]">Right click + drag</span> - Pan</div>
                    <div>• <span className="text-[#64ffda]">Scroll</span> - Zoom</div>
                    <div>• <span className="text-[#64ffda]">Click node</span> - Select & focus</div>
                    <div>• <span className="text-[#64ffda]">Drag node</span> - Reposition</div>
                </div>
            </div>

            {/* Legend */}
            <div className="absolute bottom-6 right-6 z-30 bg-black/60 backdrop-blur-md rounded-lg p-4 border border-white/10 pointer-events-none">
                <div className="text-white text-sm font-semibold mb-2">Legend</div>
                <div className="space-y-2 text-xs text-gray-300">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#4a90e2]"></div>
                        <span>Paper Node</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#64ffda]"></div>
                        <span>Connected / Hovered</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-[#ff79c6]"></div>
                        <span>Selected</span>
                    </div>
                    <div className="flex items-center gap-2 mt-3 pt-2 border-t border-white/10">
                        <div className="w-8 h-0.5 bg-gradient-to-r from-[#64ffda] to-transparent"></div>
                        <span>Active connections</span>
                    </div>
                </div>
            </div>

            <Graph3DCanvas
                onNodeSelect={setSelectedNode}
                selectedNode={selectedNode}
            />

            <SidePanel
                node={selectedNode}
                onClose={() => setSelectedNode(null)}
            />
        </div>
    );
}
