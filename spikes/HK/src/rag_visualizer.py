"""
OARIA RAG Visualizer - Embedding & Vector Pipeline Visualization

Visualize the RAG pipeline process step by step:
- Text → Embedding transformation
- Dense vector heatmap
- Sparse vector (keyword weights)
- Similarity calculation
- Search process visualization

Run with: streamlit run src/rag_visualizer.py

Author: HK
Created: 2025-12-30
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from typing import Optional
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Page config
st.set_page_config(
    page_title="OARIA - RAG Visualizer",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=DM+Sans:wght@400;500;600&display=swap');

    .stApp { font-family: 'DM Sans', sans-serif; }
    h1, h2, h3 { font-family: 'Outfit', sans-serif !important; color: #1E293B !important; }

    .step-card {
        background: linear-gradient(135deg, #f0fdfa 0%, #ffffff 100%);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid #99f6e4;
        margin-bottom: 1rem;
    }

    .step-number {
        background: linear-gradient(135deg, #0D9488 0%, #0f766e 100%);
        color: white;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 1.1rem;
        margin-right: 12px;
    }

    .vector-info {
        background: #f8fafc;
        padding: 12px 16px;
        border-radius: 8px;
        border-left: 4px solid #0D9488;
        margin: 8px 0;
    }

    .similarity-high { color: #0D9488; font-weight: 700; }
    .similarity-mid { color: #F59E0B; font-weight: 600; }
    .similarity-low { color: #F97066; font-weight: 600; }

    .process-arrow {
        text-align: center;
        font-size: 2rem;
        color: #0D9488;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

@st.cache_resource
def load_embedder():
    """Load BGE-M3 embedder (cached)."""
    try:
        from src.rag.embedder import BGEM3Embedder
        return BGEM3Embedder()
    except ImportError as e:
        st.error(f"Cannot load embedder: {e}")
        return None


def mock_embedding(text: str) -> tuple:
    """Generate mock embedding for demo without real model."""
    np.random.seed(hash(text) % 2**32)
    dense = np.random.randn(1024).astype(np.float32)
    dense = dense / np.linalg.norm(dense)  # Normalize

    # Mock sparse: simulate token weights
    words = text.lower().split()
    sparse_indices = [hash(w) % 50000 for w in words[:20]]
    sparse_values = np.random.uniform(0.1, 1.0, len(sparse_indices)).tolist()

    return dense.tolist(), (sparse_indices, sparse_values), words[:20]


def cosine_similarity(v1: list, v2: list) -> float:
    """Compute cosine similarity between two vectors."""
    v1 = np.array(v1)
    v2 = np.array(v2)
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))


def plot_dense_vector_heatmap(vector: list, title: str = "Dense Vector (1024-dim)"):
    """Create a heatmap visualization of dense vector."""
    # Reshape to 32x32 grid
    arr = np.array(vector).reshape(32, 32)

    fig = px.imshow(
        arr,
        color_continuous_scale="RdBu_r",
        title=title,
        labels=dict(color="Value"),
    )
    fig.update_layout(
        height=400,
        coloraxis_colorbar=dict(title="Value"),
    )
    return fig


def plot_dense_vector_distribution(vector: list, title: str = "Value Distribution"):
    """Create histogram of vector values."""
    fig = px.histogram(
        x=vector,
        nbins=50,
        title=title,
        labels={"x": "Value", "y": "Count"},
        color_discrete_sequence=["#0D9488"],
    )
    fig.update_layout(height=300)
    return fig


def plot_sparse_vector(indices: list, values: list, tokens: list = None, title: str = "Sparse Vector (Keyword Weights)"):
    """Create bar chart of sparse vector weights."""
    # Use tokens as labels if available
    if tokens and len(tokens) == len(indices):
        labels = tokens
    else:
        labels = [f"Token {i}" for i in indices]

    # Sort by value
    sorted_data = sorted(zip(labels, values), key=lambda x: x[1], reverse=True)
    labels, values = zip(*sorted_data) if sorted_data else ([], [])

    fig = px.bar(
        x=list(values)[:20],
        y=list(labels)[:20],
        orientation='h',
        title=title,
        labels={"x": "Weight", "y": "Token"},
        color=list(values)[:20],
        color_continuous_scale=["#ccfbf1", "#0D9488"],
    )
    fig.update_layout(height=400, yaxis=dict(autorange="reversed"))
    return fig


def plot_vector_comparison(v1: list, v2: list, label1: str, label2: str):
    """Create side-by-side comparison of two vectors."""
    # Take first 100 dimensions for visibility
    dims = min(100, len(v1))

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=list(range(dims)),
        y=v1[:dims],
        mode='lines',
        name=label1,
        line=dict(color='#0D9488', width=1.5),
        fill='tozeroy',
        fillcolor='rgba(13, 148, 136, 0.2)',
    ))

    fig.add_trace(go.Scatter(
        x=list(range(dims)),
        y=v2[:dims],
        mode='lines',
        name=label2,
        line=dict(color='#F97066', width=1.5),
        fill='tozeroy',
        fillcolor='rgba(249, 112, 102, 0.2)',
    ))

    fig.update_layout(
        title=f"Vector Comparison (first {dims} dimensions)",
        xaxis_title="Dimension",
        yaxis_title="Value",
        height=350,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )

    return fig


def plot_similarity_gauge(similarity: float):
    """Create a gauge chart for similarity score."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=similarity,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Cosine Similarity", 'font': {'size': 16}},
        delta={'reference': 0.7, 'increasing': {'color': "#0D9488"}, 'decreasing': {'color': "#F97066"}},
        gauge={
            'axis': {'range': [0, 1], 'tickwidth': 1, 'tickcolor': "#1E293B"},
            'bar': {'color': "#0D9488" if similarity >= 0.7 else "#F59E0B" if similarity >= 0.5 else "#F97066"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "#e2e8f0",
            'steps': [
                {'range': [0, 0.5], 'color': '#FEE2E2'},
                {'range': [0.5, 0.7], 'color': '#FEF3C7'},
                {'range': [0.7, 1], 'color': '#CCFBF1'},
            ],
            'threshold': {
                'line': {'color': "#0D9488", 'width': 4},
                'thickness': 0.75,
                'value': 0.7
            }
        }
    ))
    fig.update_layout(height=250)
    return fig


def plot_2d_projection(vectors: list, labels: list, highlight_idx: int = None):
    """Project vectors to 2D using simple PCA-like projection."""
    if len(vectors) < 2:
        return None

    # Simple 2D projection using first two principal components
    vectors_np = np.array(vectors)
    mean = np.mean(vectors_np, axis=0)
    centered = vectors_np - mean

    # Take first 2 components (simplified, not true PCA)
    x = centered[:, 0]
    y = centered[:, 1]

    colors = ['#0D9488' if i != highlight_idx else '#F97066' for i in range(len(vectors))]
    sizes = [15 if i != highlight_idx else 25 for i in range(len(vectors))]

    fig = go.Figure(data=go.Scatter(
        x=x,
        y=y,
        mode='markers+text',
        text=labels,
        textposition="top center",
        marker=dict(size=sizes, color=colors),
        hovertext=labels,
    ))

    fig.update_layout(
        title="Vector Space (2D Projection)",
        xaxis_title="Component 1",
        yaxis_title="Component 2",
        height=400,
    )

    return fig


# ============================================================================
# MAIN APP
# ============================================================================

# Header
st.markdown("""
<div style="background: linear-gradient(135deg, #0D9488 0%, #0f766e 100%); padding: 2rem; border-radius: 16px; margin-bottom: 2rem; text-align: center;">
    <h1 style="color: white !important; margin: 0; font-size: 2.5rem;">🔬 OARIA RAG Visualizer</h1>
    <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">See how text becomes vectors and enables semantic search</p>
</div>
""", unsafe_allow_html=True)

# Sidebar controls
st.sidebar.header("⚙️ Settings")

use_real_model = st.sidebar.checkbox(
    "Use Real BGE-M3 Model",
    value=False,
    help="Requires FlagEmbedding installed. Uses mock embeddings if unchecked."
)

show_raw_vectors = st.sidebar.checkbox("Show Raw Vector Values", value=False)
vector_viz_dims = st.sidebar.slider("Dimensions to Visualize", 50, 1024, 100)

st.sidebar.divider()
st.sidebar.markdown("""
**Pipeline Steps:**
1. 📝 Text Input
2. 🔢 Tokenization
3. 🧮 Dense Embedding
4. 📊 Sparse Embedding
5. 🔍 Similarity Search
""")

# Main content
tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Single Text Embedding",
    "⚖️ Compare Two Texts",
    "🔍 Search Simulation",
    "📈 Batch Analysis"
])

# Tab 1: Single Text Embedding
with tab1:
    st.markdown("### Step-by-Step Embedding Visualization")
    st.markdown("Watch how your text transforms into a vector representation.")

    input_text = st.text_area(
        "Enter text to embed:",
        value="EGFR mutations are found in approximately 15% of non-small cell lung cancer patients in Western populations.",
        height=100,
    )

    if st.button("🚀 Generate Embedding", type="primary", key="embed_single"):
        if input_text.strip():
            with st.spinner("Processing..."):
                # Step 1: Show original text
                st.markdown('<div class="step-card">', unsafe_allow_html=True)
                st.markdown('<span class="step-number">1</span> **Original Text**', unsafe_allow_html=True)
                st.info(input_text)
                st.markdown('</div>', unsafe_allow_html=True)

                time.sleep(0.3)  # Animation delay
                st.markdown('<div class="process-arrow">⬇️</div>', unsafe_allow_html=True)

                # Step 2: Tokenization
                st.markdown('<div class="step-card">', unsafe_allow_html=True)
                st.markdown('<span class="step-number">2</span> **Tokenization**', unsafe_allow_html=True)
                words = input_text.split()
                st.markdown(f"Split into **{len(words)}** tokens")
                st.code(" | ".join(words[:15]) + (" | ..." if len(words) > 15 else ""))
                st.markdown('</div>', unsafe_allow_html=True)

                time.sleep(0.3)
                st.markdown('<div class="process-arrow">⬇️</div>', unsafe_allow_html=True)

                # Step 3: Generate embeddings
                if use_real_model:
                    try:
                        embedder = load_embedder()
                        if embedder:
                            result = embedder.embed(input_text, return_sparse=True)
                            dense_vec = result.dense_vector
                            sparse_indices = result.sparse_indices or []
                            sparse_values = result.sparse_values or []
                            tokens_for_sparse = words[:len(sparse_indices)]
                        else:
                            dense_vec, (sparse_indices, sparse_values), tokens_for_sparse = mock_embedding(input_text)
                    except Exception as e:
                        st.warning(f"Model loading failed, using mock: {e}")
                        dense_vec, (sparse_indices, sparse_values), tokens_for_sparse = mock_embedding(input_text)
                else:
                    dense_vec, (sparse_indices, sparse_values), tokens_for_sparse = mock_embedding(input_text)

                # Step 3: Dense Vector
                st.markdown('<div class="step-card">', unsafe_allow_html=True)
                st.markdown('<span class="step-number">3</span> **Dense Vector (Semantic Meaning)**', unsafe_allow_html=True)

                col1, col2 = st.columns([2, 1])

                with col1:
                    fig_heatmap = plot_dense_vector_heatmap(dense_vec, "Dense Vector Heatmap (32x32 = 1024 dims)")
                    st.plotly_chart(fig_heatmap, use_container_width=True)

                with col2:
                    st.markdown('<div class="vector-info">', unsafe_allow_html=True)
                    st.markdown(f"**Dimensions:** 1024")
                    st.markdown(f"**Min value:** {min(dense_vec):.4f}")
                    st.markdown(f"**Max value:** {max(dense_vec):.4f}")
                    st.markdown(f"**Mean:** {np.mean(dense_vec):.4f}")
                    st.markdown(f"**Std:** {np.std(dense_vec):.4f}")
                    st.markdown('</div>', unsafe_allow_html=True)

                    fig_dist = plot_dense_vector_distribution(dense_vec)
                    st.plotly_chart(fig_dist, use_container_width=True)

                if show_raw_vectors:
                    with st.expander("📋 Raw Dense Vector Values"):
                        st.code(str(dense_vec[:50]) + " ...")

                st.markdown('</div>', unsafe_allow_html=True)

                time.sleep(0.3)
                st.markdown('<div class="process-arrow">⬇️</div>', unsafe_allow_html=True)

                # Step 4: Sparse Vector
                st.markdown('<div class="step-card">', unsafe_allow_html=True)
                st.markdown('<span class="step-number">4</span> **Sparse Vector (Keyword Weights)**', unsafe_allow_html=True)

                if sparse_indices:
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        fig_sparse = plot_sparse_vector(sparse_indices, sparse_values, tokens_for_sparse)
                        st.plotly_chart(fig_sparse, use_container_width=True)

                    with col2:
                        st.markdown('<div class="vector-info">', unsafe_allow_html=True)
                        st.markdown(f"**Non-zero entries:** {len(sparse_indices)}")
                        st.markdown(f"**Max weight:** {max(sparse_values):.4f}")
                        st.markdown(f"**Top tokens:**")
                        top_tokens = sorted(zip(tokens_for_sparse, sparse_values), key=lambda x: x[1], reverse=True)[:5]
                        for token, weight in top_tokens:
                            st.markdown(f"- `{token}`: {weight:.3f}")
                        st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.info("No sparse vector available (model may not support it)")

                st.markdown('</div>', unsafe_allow_html=True)

                # Summary
                st.success("✅ Embedding complete! This vector can now be stored in Qdrant for similarity search.")


# Tab 2: Compare Two Texts
with tab2:
    st.markdown("### Compare Similarity Between Two Texts")
    st.markdown("See how similar or different two texts are in vector space.")

    col1, col2 = st.columns(2)

    with col1:
        text1 = st.text_area(
            "Text 1 (e.g., Query):",
            value="EGFR mutations in lung cancer treatment",
            height=100,
            key="compare_text1"
        )

    with col2:
        text2 = st.text_area(
            "Text 2 (e.g., Document):",
            value="EGFR tyrosine kinase inhibitors show efficacy in non-small cell lung cancer with EGFR mutations",
            height=100,
            key="compare_text2"
        )

    if st.button("⚖️ Compare Texts", type="primary", key="compare_btn"):
        if text1.strip() and text2.strip():
            with st.spinner("Computing embeddings..."):
                # Get embeddings
                if use_real_model:
                    try:
                        embedder = load_embedder()
                        if embedder:
                            result1 = embedder.embed(text1)
                            result2 = embedder.embed(text2)
                            vec1, vec2 = result1.dense_vector, result2.dense_vector
                        else:
                            vec1, _, _ = mock_embedding(text1)
                            vec2, _, _ = mock_embedding(text2)
                    except:
                        vec1, _, _ = mock_embedding(text1)
                        vec2, _, _ = mock_embedding(text2)
                else:
                    vec1, _, _ = mock_embedding(text1)
                    vec2, _, _ = mock_embedding(text2)

                # Compute similarity
                similarity = cosine_similarity(vec1, vec2)

                # Display results
                col1, col2, col3 = st.columns([1, 1, 1])

                with col1:
                    st.markdown("#### Text 1")
                    st.info(text1[:100] + "..." if len(text1) > 100 else text1)
                    fig1 = plot_dense_vector_heatmap(vec1, "Vector 1")
                    st.plotly_chart(fig1, use_container_width=True)

                with col2:
                    st.markdown("#### Similarity")
                    fig_gauge = plot_similarity_gauge(similarity)
                    st.plotly_chart(fig_gauge, use_container_width=True)

                    if similarity >= 0.7:
                        st.success(f"✅ HIGH similarity ({similarity:.3f}) - Good match!")
                    elif similarity >= 0.5:
                        st.warning(f"⚠️ MEDIUM similarity ({similarity:.3f}) - Somewhat related")
                    else:
                        st.error(f"❌ LOW similarity ({similarity:.3f}) - Different topics")

                with col3:
                    st.markdown("#### Text 2")
                    st.info(text2[:100] + "..." if len(text2) > 100 else text2)
                    fig2 = plot_dense_vector_heatmap(vec2, "Vector 2")
                    st.plotly_chart(fig2, use_container_width=True)

                # Vector comparison chart
                st.markdown("---")
                st.markdown("#### Vector Overlay Comparison")
                fig_compare = plot_vector_comparison(vec1, vec2, "Text 1", "Text 2")
                st.plotly_chart(fig_compare, use_container_width=True)

                st.markdown("""
                <div class="vector-info">
                <p><strong>How to interpret:</strong></p>
                <ul>
                    <li>Where lines overlap = similar semantic features</li>
                    <li>Where lines diverge = different meanings</li>
                    <li>Cosine similarity measures the angle between vectors (1.0 = identical direction)</li>
                </ul>
                </div>
                """, unsafe_allow_html=True)


# Tab 3: Search Simulation
with tab3:
    st.markdown("### Simulate Vector Search Process")
    st.markdown("See how a query finds similar documents in vector space.")

    query = st.text_input(
        "Search Query:",
        value="EGFR inhibitor efficacy",
        key="search_query"
    )

    # Sample documents
    sample_docs = [
        "EGFR mutations predict response to tyrosine kinase inhibitors in lung cancer",
        "Immunotherapy with pembrolizumab shows durable responses in NSCLC",
        "Osimertinib overcomes T790M resistance in EGFR-mutant tumors",
        "Chemotherapy remains standard treatment for small cell lung cancer",
        "KRAS mutations are associated with poor prognosis in colorectal cancer",
        "Breast cancer HER2 amplification predicts response to trastuzumab",
        "Gefitinib demonstrates efficacy in EGFR-positive non-small cell lung cancer",
        "PD-L1 expression level correlates with immunotherapy response",
    ]

    st.markdown("**Document Corpus:**")
    for i, doc in enumerate(sample_docs, 1):
        st.markdown(f"{i}. {doc}")

    if st.button("🔍 Run Search", type="primary", key="search_btn"):
        with st.spinner("Computing vectors and similarities..."):
            # Get embeddings
            if use_real_model:
                try:
                    embedder = load_embedder()
                    if embedder:
                        query_result = embedder.embed(query)
                        query_vec = query_result.dense_vector
                        doc_vecs = [embedder.embed(doc).dense_vector for doc in sample_docs]
                    else:
                        query_vec, _, _ = mock_embedding(query)
                        doc_vecs = [mock_embedding(doc)[0] for doc in sample_docs]
                except:
                    query_vec, _, _ = mock_embedding(query)
                    doc_vecs = [mock_embedding(doc)[0] for doc in sample_docs]
            else:
                query_vec, _, _ = mock_embedding(query)
                doc_vecs = [mock_embedding(doc)[0] for doc in sample_docs]

            # Compute similarities
            similarities = [cosine_similarity(query_vec, dv) for dv in doc_vecs]

            # Rank results
            ranked = sorted(enumerate(similarities), key=lambda x: x[1], reverse=True)

            # Display process
            st.markdown("---")
            st.markdown("### Search Results")

            col1, col2 = st.columns([1, 2])

            with col1:
                st.markdown("#### Query Vector")
                fig_q = plot_dense_vector_heatmap(query_vec, "Query")
                st.plotly_chart(fig_q, use_container_width=True)

            with col2:
                st.markdown("#### Ranked Documents")

                for rank, (idx, sim) in enumerate(ranked, 1):
                    if sim >= 0.7:
                        color = "#0D9488"
                        icon = "🟢"
                    elif sim >= 0.5:
                        color = "#F59E0B"
                        icon = "🟡"
                    else:
                        color = "#F97066"
                        icon = "🔴"

                    st.markdown(f"""
                    <div style="padding: 10px; margin: 5px 0; background: #f8fafc; border-radius: 8px; border-left: 4px solid {color};">
                        <span style="font-weight: 700; color: {color};">#{rank}</span>
                        {icon} <span style="color: {color}; font-weight: 600;">{sim:.3f}</span>
                        <br><span style="color: #64748b; font-size: 0.9rem;">{sample_docs[idx]}</span>
                    </div>
                    """, unsafe_allow_html=True)

            # 2D projection
            st.markdown("---")
            st.markdown("#### Vector Space Visualization")

            all_vecs = [query_vec] + doc_vecs
            all_labels = ["QUERY"] + [f"Doc {i+1}" for i in range(len(doc_vecs))]

            fig_2d = plot_2d_projection(all_vecs, all_labels, highlight_idx=0)
            if fig_2d:
                st.plotly_chart(fig_2d, use_container_width=True)
                st.caption("Query vector shown in red. Distance in this projection approximates similarity.")


# Tab 4: Batch Analysis
with tab4:
    st.markdown("### Batch Embedding Analysis")
    st.markdown("Analyze multiple texts at once and compare their embeddings.")

    texts_input = st.text_area(
        "Enter multiple texts (one per line):",
        value="""EGFR mutations in lung cancer
Immunotherapy for melanoma
BRCA1 mutations in breast cancer
Chemotherapy side effects
Targeted therapy for colorectal cancer""",
        height=150,
        key="batch_texts"
    )

    if st.button("📊 Analyze Batch", type="primary", key="batch_btn"):
        texts = [t.strip() for t in texts_input.strip().split("\n") if t.strip()]

        if len(texts) >= 2:
            with st.spinner(f"Processing {len(texts)} texts..."):
                # Get embeddings
                if use_real_model:
                    try:
                        embedder = load_embedder()
                        if embedder:
                            vecs = [embedder.embed(t).dense_vector for t in texts]
                        else:
                            vecs = [mock_embedding(t)[0] for t in texts]
                    except:
                        vecs = [mock_embedding(t)[0] for t in texts]
                else:
                    vecs = [mock_embedding(t)[0] for t in texts]

                # Compute similarity matrix
                n = len(texts)
                sim_matrix = np.zeros((n, n))
                for i in range(n):
                    for j in range(n):
                        sim_matrix[i, j] = cosine_similarity(vecs[i], vecs[j])

                # Display
                col1, col2 = st.columns([1, 1])

                with col1:
                    st.markdown("#### Similarity Matrix")
                    short_labels = [t[:30] + "..." if len(t) > 30 else t for t in texts]

                    fig_matrix = px.imshow(
                        sim_matrix,
                        x=short_labels,
                        y=short_labels,
                        color_continuous_scale="Teal",
                        title="Pairwise Similarity",
                        labels=dict(color="Similarity"),
                    )
                    fig_matrix.update_layout(height=400)
                    st.plotly_chart(fig_matrix, use_container_width=True)

                with col2:
                    st.markdown("#### 2D Projection")
                    fig_2d = plot_2d_projection(vecs, short_labels)
                    if fig_2d:
                        st.plotly_chart(fig_2d, use_container_width=True)

                # Summary stats
                st.markdown("---")
                st.markdown("#### Statistics")

                # Find most/least similar pairs
                pairs = []
                for i in range(n):
                    for j in range(i+1, n):
                        pairs.append((i, j, sim_matrix[i, j]))

                pairs.sort(key=lambda x: x[2], reverse=True)

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Most Similar Pairs:**")
                    for i, j, sim in pairs[:3]:
                        st.markdown(f"- `{texts[i][:30]}...` ↔ `{texts[j][:30]}...`: **{sim:.3f}**")

                with col2:
                    st.markdown("**Least Similar Pairs:**")
                    for i, j, sim in pairs[-3:]:
                        st.markdown(f"- `{texts[i][:30]}...` ↔ `{texts[j][:30]}...`: **{sim:.3f}**")
        else:
            st.warning("Please enter at least 2 texts to compare.")


# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 1rem; color: #64748b;">
    <p><strong>OARIA RAG Visualizer</strong> - Understanding embeddings and vector search</p>
    <p style="font-size: 0.8rem;">Tip: Enable "Use Real BGE-M3 Model" in sidebar for actual embeddings (requires FlagEmbedding)</p>
</div>
""", unsafe_allow_html=True)
