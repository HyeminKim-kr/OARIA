/**
 * PubMed ETL System - React Frontend
 * 
 * 주요 기능:
 * 1. 검색어 입력 → 총 건수 조회
 * 2. 미리보기 (처음 N건 표시)
 * 3. 배치 크롤링 시작/중단
 * 4. 실시간 진행률 표시
 * 5. 논문 목록 표시 (제목, 저자, 초록)
 */

const { useState, useEffect, useCallback } = React;

// API 기본 URL
const API_BASE = '';

// ============================================================================
// API 함수들
// ============================================================================

const api = {
    async getCount(term, dateFrom, dateTo) {
        const params = new URLSearchParams({ term });
        if (dateFrom) params.append('date_from', dateFrom);
        if (dateTo) params.append('date_to', dateTo);
        
        const res = await fetch(`${API_BASE}/api/pubmed/count?${params}`);
        if (!res.ok) throw new Error('검색 실패');
        return res.json();
    },
    
    async preview(term, limit = 20, offset = 0, dateFrom, dateTo) {
        const res = await fetch(`${API_BASE}/api/pubmed/preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                term, 
                limit, 
                offset,
                date_from: dateFrom,
                date_to: dateTo 
            }),
        });
        if (!res.ok) throw new Error('미리보기 실패');
        return res.json();
    },
    
    async startCrawl(term, limit, offset = 0, batchSize = 500) {
        const res = await fetch(`${API_BASE}/api/pubmed/crawl/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ term, limit, offset, batch_size: batchSize }),
        });
        if (!res.ok) throw new Error('크롤링 시작 실패');
        return res.json();
    },
    
    async getStatus(jobId) {
        const res = await fetch(`${API_BASE}/api/pubmed/crawl/status?job_id=${jobId}`);
        if (!res.ok) throw new Error('상태 조회 실패');
        return res.json();
    },
    
    async stopCrawl(jobId) {
        const res = await fetch(`${API_BASE}/api/pubmed/crawl/stop?job_id=${jobId}`, {
            method: 'POST',
        });
        if (!res.ok) throw new Error('크롤링 중단 실패');
        return res.json();
    },
};

// ============================================================================
// 컴포넌트들
// ============================================================================

// 통계 카드
function StatCard({ value, label }) {
    return (
        <div className="stat-card">
            <div className="value">{value}</div>
            <div className="label">{label}</div>
        </div>
    );
}

// 논문 카드
function PaperCard({ paper }) {
    const [expanded, setExpanded] = useState(false);
    
    return (
        <div className="paper-card" onClick={() => setExpanded(!expanded)}>
            <div className="paper-title">{paper.metadata?.title || 'No Title'}</div>
            <div className="paper-meta">
                <span className="paper-pmid">PMID: {paper.pmid}</span>
                <span>📅 {paper.metadata?.pubdate || 'N/A'}</span>
                <span>📖 {paper.metadata?.journal || 'N/A'}</span>
                <span>👥 {(paper.metadata?.authors || []).slice(0, 3).join(', ')}{paper.metadata?.authors?.length > 3 ? ' ...' : ''}</span>
            </div>
            <div className={`paper-abstract ${expanded ? 'expanded' : ''}`}>
                {paper.abstract || '(초록 없음)'}
            </div>
        </div>
    );
}

// 진행률 바
function ProgressBar({ status }) {
    if (!status) return null;
    
    const getStatusBadge = () => {
        const statusMap = {
            running: { className: 'running', text: '수집 중' },
            completed: { className: 'completed', text: '완료' },
            paused: { className: 'paused', text: '일시정지' },
            error: { className: 'error', text: '오류' },
        };
        const s = statusMap[status.status] || { className: '', text: status.status };
        return <span className={`status-badge ${s.className}`}>{s.text}</span>;
    };
    
    return (
        <div className="progress-container">
            <div className="progress-header">
                <h3>크롤링 진행 상황</h3>
                {getStatusBadge()}
            </div>
            <div className="progress-bar">
                <div 
                    className="progress-fill" 
                    style={{ width: `${status.progress}%` }}
                />
            </div>
            <div className="progress-stats">
                <span>{status.collected.toLocaleString()} / {status.total.toLocaleString()} 건 수집</span>
                <span>{status.progress.toFixed(1)}%</span>
            </div>
        </div>
    );
}

// 메인 앱
function App() {
    // 상태
    const [term, setTerm] = useState('breast cancer');
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [count, setCount] = useState(null);
    const [papers, setPapers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [crawlLimit, setCrawlLimit] = useState(100);
    const [jobId, setJobId] = useState(null);
    const [crawlStatus, setCrawlStatus] = useState(null);
    const [error, setError] = useState(null);
    
    // 검색 건수 조회
    const handleSearch = async () => {
        if (!term.trim()) return;
        
        setLoading(true);
        setError(null);
        try {
            const data = await api.getCount(term, dateFrom, dateTo);
            setCount(data);
            setPapers([]);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };
    
    // 미리보기
    const handlePreview = async () => {
        if (!term.trim()) return;
        
        setLoading(true);
        setError(null);
        try {
            const data = await api.preview(term, 20, 0, dateFrom, dateTo);
            setPapers(data.papers);
            if (!count) {
                setCount({ total: data.total, term: data.term, estimated_hours: 0 });
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };
    
    // 크롤링 시작
    const handleStartCrawl = async () => {
        if (!term.trim()) return;
        
        setLoading(true);
        setError(null);
        try {
            const data = await api.startCrawl(term, crawlLimit);
            setJobId(data.job_id);
            setCrawlStatus({ status: 'running', progress: 0, collected: 0, total: crawlLimit });
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };
    
    // 크롤링 중단
    const handleStopCrawl = async () => {
        if (!jobId) return;
        
        try {
            await api.stopCrawl(jobId);
            setCrawlStatus(prev => ({ ...prev, status: 'paused' }));
        } catch (err) {
            setError(err.message);
        }
    };
    
    // 크롤링 상태 폴링
    useEffect(() => {
        if (!jobId || crawlStatus?.status === 'completed' || crawlStatus?.status === 'paused') {
            return;
        }
        
        const interval = setInterval(async () => {
            try {
                const status = await api.getStatus(jobId);
                setCrawlStatus(status);
                
                // 수집된 논문 업데이트
                if (status.papers?.length > 0) {
                    setPapers(prev => {
                        const existingIds = new Set(prev.map(p => p.pmid));
                        const newPapers = status.papers.filter(p => !existingIds.has(p.pmid));
                        return [...prev, ...newPapers];
                    });
                }
                
                if (status.status === 'completed' || status.status === 'error') {
                    clearInterval(interval);
                }
            } catch (err) {
                console.error('Status polling error:', err);
            }
        }, 2000);
        
        return () => clearInterval(interval);
    }, [jobId, crawlStatus?.status]);
    
    return (
        <div>
            {/* Header */}
            <header className="header">
                <h1>🔬 PubMed ETL System</h1>
                <p>PubMed/PMC 논문 자동 수집 플랫폼</p>
            </header>
            
            {/* Search Form */}
            <div className="search-form">
                <div className="form-row">
                    <div className="form-group">
                        <label>검색어 (Keyword)</label>
                        <input
                            type="text"
                            value={term}
                            onChange={e => setTerm(e.target.value)}
                            placeholder="예: breast cancer, BRCA1, immunotherapy"
                            onKeyPress={e => e.key === 'Enter' && handleSearch()}
                        />
                    </div>
                    <div className="form-group">
                        <label>시작일</label>
                        <input
                            type="date"
                            value={dateFrom}
                            onChange={e => setDateFrom(e.target.value)}
                        />
                    </div>
                    <div className="form-group">
                        <label>종료일</label>
                        <input
                            type="date"
                            value={dateTo}
                            onChange={e => setDateTo(e.target.value)}
                        />
                    </div>
                    <button 
                        className="btn btn-primary" 
                        onClick={handleSearch}
                        disabled={loading}
                    >
                        {loading ? <span className="spinner" /> : '🔍'} 검색
                    </button>
                    <button 
                        className="btn btn-secondary" 
                        onClick={handlePreview}
                        disabled={loading}
                    >
                        👀 미리보기
                    </button>
                </div>
            </div>
            
            {/* Error */}
            {error && (
                <div className="alert alert-warning">
                    ⚠️ {error}
                </div>
            )}
            
            {/* Stats */}
            {count && (
                <div className="stats-grid">
                    <StatCard 
                        value={count.total.toLocaleString()} 
                        label="총 논문 수" 
                    />
                    <StatCard 
                        value={`~${count.estimated_hours.toFixed(1)}시간`} 
                        label="예상 수집 시간" 
                    />
                    <StatCard 
                        value={Math.ceil(count.total / 500).toLocaleString()} 
                        label="필요 배치 수" 
                    />
                    <StatCard 
                        value={papers.length.toLocaleString()} 
                        label="수집된 논문" 
                    />
                </div>
            )}
            
            {/* Crawl Controls */}
            {count && count.total > 0 && (
                <div className="search-form">
                    <div className="alert alert-info">
                        💡 무료 API는 초당 3회로 제한됩니다. 대량 수집 시 시간이 걸릴 수 있습니다.
                    </div>
                    <div className="crawl-controls">
                        <div className="form-group">
                            <label>수집할 논문 수:</label>
                            <input
                                type="number"
                                value={crawlLimit}
                                onChange={e => setCrawlLimit(Number(e.target.value))}
                                min={1}
                                max={count.total}
                            />
                        </div>
                        {!jobId || crawlStatus?.status === 'completed' || crawlStatus?.status === 'paused' ? (
                            <button 
                                className="btn btn-success" 
                                onClick={handleStartCrawl}
                                disabled={loading}
                            >
                                🚀 크롤링 시작
                            </button>
                        ) : (
                            <button 
                                className="btn btn-danger" 
                                onClick={handleStopCrawl}
                            >
                                ⏸️ 중단
                            </button>
                        )}
                    </div>
                </div>
            )}
            
            {/* Progress */}
            {crawlStatus && (
                <ProgressBar status={crawlStatus} />
            )}
            
            {/* Papers List */}
            <div className="papers-container">
                <div className="papers-header">
                    <h2>📚 논문 목록</h2>
                    <span>{papers.length.toLocaleString()}건</span>
                </div>
                
                {papers.length === 0 ? (
                    <div className="empty-state">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                        </svg>
                        <p>검색 또는 미리보기를 클릭하여 논문을 가져오세요</p>
                    </div>
                ) : (
                    papers.map(paper => (
                        <PaperCard key={paper.pmid} paper={paper} />
                    ))
                )}
            </div>
        </div>
    );
}

// 렌더링
const root = ReactDOM.createRoot(document.getElementById('app'));
root.render(<App />);
