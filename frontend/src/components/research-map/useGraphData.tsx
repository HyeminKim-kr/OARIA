import { useState, useEffect } from 'react';
import { GraphData } from './types';

export function useGraphData() {
    const [data, setData] = useState<GraphData>({ nodes: [], edges: [] });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch('/graph_data.json')
            .then(res => res.json())
            .then(json => {
                setData(json);
                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to load graph data", err);
                setLoading(false);
            });
    }, []);

    return { data, loading };
}
