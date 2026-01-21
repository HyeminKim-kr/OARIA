'use client';

import React, { useRef, useLayoutEffect, useState } from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import { MapNode } from './types';

interface NodesProps {
    nodes: MapNode[];
    onNodeClick: (node: MapNode) => void;
    selectedNode: MapNode | null;
}

const TEMP_OBJECT = new THREE.Object3D();
const COLOR_NORMAL = new THREE.Color('#4a90e2');
const COLOR_HOVER = new THREE.Color('#64ffda');
const COLOR_SELECTED = new THREE.Color('#ff79c6');

export function Nodes({ nodes, onNodeClick, selectedNode }: NodesProps) {
    const meshRef = useRef<THREE.InstancedMesh>(null);
    const [hovered, setHover] = useState<number | null>(null);

    // Update instances when nodes change
    useLayoutEffect(() => {
        if (!meshRef.current) return;

        nodes.forEach((node, i) => {
            const x = node.x * 0.1;
            const y = node.y * 0.1;
            const z = node.z || 0;

            // Size based on citation count
            const baseSize = 1;
            const sizeMultiplier = node.citation_count
                ? Math.log(node.citation_count + 1) * 0.3
                : 1;

            TEMP_OBJECT.position.set(x, y, z);
            TEMP_OBJECT.scale.setScalar(baseSize * sizeMultiplier);
            TEMP_OBJECT.updateMatrix();

            meshRef.current!.setMatrixAt(i, TEMP_OBJECT.matrix);
        });
        meshRef.current.instanceMatrix.needsUpdate = true;
    }, [nodes]);

    // Handle Color Updates
    useLayoutEffect(() => {
        if (!meshRef.current) return;

        for (let i = 0; i < nodes.length; i++) {
            let color = COLOR_NORMAL;

            if (selectedNode && nodes[i].id === selectedNode.id) {
                color = COLOR_SELECTED;
            } else if (hovered === i) {
                color = COLOR_HOVER;
            } else if (selectedNode) {
                // Dim unselected nodes
                color = new THREE.Color('#2a4a6a');
            }

            meshRef.current.setColorAt(i, color);
        }

        meshRef.current.instanceColor!.needsUpdate = true;
    }, [hovered, nodes, selectedNode]);

    return (
        <>
            <instancedMesh
                ref={meshRef}
                args={[undefined, undefined, nodes.length]}
                onPointerOver={(e) => {
                    e.stopPropagation();
                    setHover(e.instanceId!);
                    document.body.style.cursor = 'pointer';
                }}
                onPointerOut={() => {
                    setHover(null);
                    document.body.style.cursor = 'auto';
                }}
                onClick={(e) => {
                    e.stopPropagation();
                    if (e.instanceId !== undefined) {
                        onNodeClick(nodes[e.instanceId]);
                    }
                }}
            >
                <circleGeometry args={[0.5, 32]} />
                <meshBasicMaterial />
            </instancedMesh>

            {hovered !== null && nodes[hovered] && (
                <Html position={[nodes[hovered].x * 0.1, nodes[hovered].y * 0.1, 0]}>
                    <div className="pointer-events-none px-3 py-2 bg-black/90 text-white text-sm rounded-lg border border-[#64ffda]/30 whitespace-nowrap transform -translate-y-full -mt-3 shadow-lg backdrop-blur-sm">
                        <div className="font-semibold">{nodes[hovered].label}</div>
                        {nodes[hovered].year && (
                            <div className="text-xs text-gray-400 mt-1">{nodes[hovered].year}</div>
                        )}
                    </div>
                </Html>
            )}
        </>
    );
}
