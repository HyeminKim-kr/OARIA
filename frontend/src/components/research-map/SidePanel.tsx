'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MapNode } from './types';
import { X, ExternalLink, Calendar, Quote } from 'lucide-react';

interface SidePanelProps {
    node: MapNode | null;
    onClose: () => void;
}

export function SidePanel({ node, onClose }: SidePanelProps) {
    return (
        <AnimatePresence>
            {node && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
                    />

                    {/* Panel */}
                    <motion.div
                        initial={{ x: '100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '100%' }}
                        transition={{ type: 'spring', damping: 30, stiffness: 300 }}
                        className="fixed top-0 right-0 h-full w-[480px] bg-gradient-to-br from-[#1a1a2e] to-[#16213e] border-l border-[#64ffda]/20 shadow-2xl z-50 overflow-hidden"
                    >
                        {/* Glow effect */}
                        <div className="absolute top-0 right-0 w-64 h-64 bg-[#64ffda]/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />

                        <div className="relative h-full overflow-y-auto p-8">
                            {/* Close button */}
                            <button
                                onClick={onClose}
                                className="absolute top-6 right-6 text-white/50 hover:text-white hover:bg-white/10 rounded-lg p-2 transition-all"
                            >
                                <X size={20} />
                            </button>

                            {/* Header */}
                            <div className="mb-6">
                                <div className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-mono bg-[#64ffda]/10 text-[#64ffda] rounded-full mb-4 border border-[#64ffda]/20">
                                    <div className="w-2 h-2 rounded-full bg-[#64ffda] animate-pulse" />
                                    {node.type || 'PAPER'}
                                </div>

                                <h2 className="text-2xl font-bold leading-tight mb-4 text-white pr-8">
                                    {node.label}
                                </h2>

                                <div className="flex items-center gap-4 text-sm text-gray-400">
                                    {node.year && (
                                        <div className="flex items-center gap-1.5">
                                            <Calendar size={14} />
                                            <span>{node.year}</span>
                                        </div>
                                    )}
                                    {node.citation_count !== undefined && (
                                        <div className="flex items-center gap-1.5">
                                            <Quote size={14} />
                                            <span>{node.citation_count.toLocaleString()} Citations</span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Stats Grid */}
                            <div className="grid grid-cols-2 gap-3 mb-6">
                                <div className="bg-white/5 backdrop-blur-sm rounded-xl p-4 border border-white/10">
                                    <div className="text-2xl font-bold text-[#64ffda] mb-1">
                                        {node.citation_count?.toLocaleString() || '0'}
                                    </div>
                                    <div className="text-xs text-gray-400 uppercase tracking-wider">Citations</div>
                                </div>
                                <div className="bg-white/5 backdrop-blur-sm rounded-xl p-4 border border-white/10">
                                    <div className="text-2xl font-bold text-[#ff79c6] mb-1">
                                        {node.year || 'N/A'}
                                    </div>
                                    <div className="text-xs text-gray-400 uppercase tracking-wider">Year</div>
                                </div>
                            </div>

                            {/* Abstract */}
                            <div className="mb-6">
                                <h3 className="text-sm font-semibold text-white/80 uppercase tracking-wider mb-3">Abstract</h3>
                                <div className="bg-white/5 backdrop-blur-sm rounded-xl p-5 border border-white/10">
                                    <p className="text-sm leading-relaxed text-gray-300">
                                        {node.description || "No abstract available for this entry. This paper is part of the research graph and may contain valuable connections to related work."}
                                    </p>
                                </div>
                            </div>

                            {/* Related Papers */}
                            <div>
                                <h3 className="text-sm font-semibold text-white/80 uppercase tracking-wider mb-3">Related Papers</h3>
                                <div className="space-y-2">
                                    {[1, 2, 3].map((i) => (
                                        <div
                                            key={i}
                                            className="group bg-white/5 backdrop-blur-sm rounded-xl p-4 border border-white/10 hover:border-[#64ffda]/30 hover:bg-white/10 cursor-pointer transition-all"
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="flex-1">
                                                    <div className="font-medium text-sm text-white group-hover:text-[#64ffda] transition-colors mb-1">
                                                        Related Research Paper {i}
                                                    </div>
                                                    <div className="text-xs text-gray-500">
                                                        Author Name • {(node.year || 2024) - i}
                                                    </div>
                                                </div>
                                                <ExternalLink size={14} className="text-gray-500 group-hover:text-[#64ffda] transition-colors flex-shrink-0 mt-1" />
                                            </div>
                                            <div className="mt-2 flex items-center gap-2">
                                                <div className="h-1 flex-1 bg-white/10 rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full bg-gradient-to-r from-[#64ffda] to-[#4a90e2]"
                                                        style={{ width: `${100 - i * 15}%` }}
                                                    />
                                                </div>
                                                <span className="text-xs text-gray-500 font-mono">{100 - i * 15}%</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
