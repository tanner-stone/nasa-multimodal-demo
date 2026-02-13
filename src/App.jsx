import React, { useState, useEffect } from 'react';
import axios from 'axios';

const App = () => {
  const [query, setQuery] = useState('');
  const [selectedFileTypes, setSelectedFileTypes] = useState([]);
  const [results, setResults] = useState([]);
  const [selectedResult, setSelectedResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [currentImageIndex, setCurrentImageIndex] = useState(0);

  // Vector index state
  const [vectorIndexes, setVectorIndexes] = useState({});
  const [selectedIndex, setSelectedIndex] = useState('float32');
  
  // Query metadata state
  const [queryMetadata, setQueryMetadata] = useState(null);
  const [showPipeline, setShowPipeline] = useState(false);
  
  // Full document viewer state
  const [fullDocument, setFullDocument] = useState(null);
  const [showFullDocument, setShowFullDocument] = useState(false);
  const [loadingDocument, setLoadingDocument] = useState(false);

  const fileTypes = [
    { value: 'mp4', label: 'Videos (.mp4)' },
    { value: 'jpg', label: 'Images (.jpg)' },
    { value: 'gif', label: 'GIFs (.gif)' },
    { value: 'pdf', label: 'Documents (.pdf)' }
  ];

  // Reranker toggle state
  const [useReranker, setUseReranker] = useState(false);

  // Fetch available vector indexes on mount
  useEffect(() => {
    const fetchIndexes = async () => {
      try {
        const response = await axios.get('/api/indexes');
        setVectorIndexes(response.data);
      } catch (err) {
        console.error('Failed to fetch indexes:', err);
      }
    };
    fetchIndexes();
  }, []);

  const handleFileTypeToggle = (fileType) => {
    setSelectedFileTypes(prev => 
      prev.includes(fileType) 
        ? prev.filter(type => type !== fileType)
        : [...prev, fileType]
    );
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError('');
    setQueryMetadata(null);
    setShowPipeline(false);
    setFullDocument(null);
    setShowFullDocument(false);
    
    try {
      const response = await axios.post('/search', {
        query_text: query,
        filter_file_types: selectedFileTypes.length > 0 ? selectedFileTypes : undefined,
        use_reranker: useReranker,
        vector_index: selectedIndex
      });
      
      // Handle new response format with results and metadata
      const { results: searchResults, metadata } = response.data;
      
      setResults(searchResults);
      setQueryMetadata(metadata);
      
      if (searchResults.length > 0) {
        setSelectedResult(searchResults[0]);
        setCurrentImageIndex(0);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Search failed');
      setResults([]);
      setSelectedResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleResultClick = async (result) => {
    setSelectedResult(result);
    setCurrentImageIndex(0);
    setShowFullDocument(false);
    setFullDocument(null);
  };

  const fetchFullDocument = async (docId) => {
    if (!docId) return;
    
    setLoadingDocument(true);
    try {
      const response = await axios.get(`/api/document/${docId}`);
      setFullDocument(response.data);
      setShowFullDocument(true);
    } catch (err) {
      console.error('Failed to fetch document:', err);
    } finally {
      setLoadingDocument(false);
    }
  };

  const getImageSources = (result) => {
    if (!result) return [];
    
    // For images/PDFs, use source_s3_paths (plural)
    if (result.source_s3_paths && Array.isArray(result.source_s3_paths)) {
      return result.source_s3_paths;
    }
    
    // Fallback to source_s3_path (singular) for backwards compatibility
    if (Array.isArray(result.source_s3_path)) {
      return result.source_s3_path;
    } else if (typeof result.source_s3_path === 'string') {
      return [result.source_s3_path];
    }
    return [];
  };

  const nextImage = () => {
    const images = getImageSources(selectedResult);
    if (currentImageIndex < images.length - 1) {
      setCurrentImageIndex(currentImageIndex + 1);
    }
  };

  const prevImage = () => {
    if (currentImageIndex > 0) {
      setCurrentImageIndex(currentImageIndex - 1);
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return '';
    const minutes = Math.floor(timestamp / 60);
    const seconds = Math.floor(timestamp % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const getVideoStartTime = (timestamp) => {
    return timestamp || 0;
  };

  const formatScore = (score) => {
    if (score === undefined || score === null) return 'N/A';
    return (score * 100).toFixed(1) + '%';
  };

  const getScoreBadgeClass = (score) => {
    if (score === undefined || score === null) return '';
    if (score >= 0.75) return 'score-badge-high';
    if (score >= 0.60) return 'score-badge-medium';
    return 'score-badge-low';
  };

  const renderMainContent = () => {
    if (!selectedResult) {
      return (
        <div className="flex items-center justify-center h-full text-dark-muted">
          <div className="text-center">
            <div className="text-6xl mb-4 retro-glow rocket-float">🚀</div>
            <p className="text-xl font-mono text-neon-green">[ SEARCH NASA RECORDS TO GET STARTED ]</p>
          </div>
        </div>
      );
    }

    const { file_type, source_s3_path, title, start_timestamp } = selectedResult;
    const images = getImageSources(selectedResult);

    if ((file_type === 'mp4' || file_type === 'video_chunk') && source_s3_path) {
      const startTime = getVideoStartTime(start_timestamp || 0);
      console.log(`Main video display: Loading video from ${source_s3_path} at ${startTime}s`);
      return (
        <div className="h-full flex flex-col overflow-hidden">
          <h2 className="text-lg font-semibold mb-2 text-lime-green flex-shrink-0">{title}</h2>
          <div className="flex-1 flex items-center justify-center min-h-0 bg-black rounded-lg">
            <video
              key={`${source_s3_path}-${startTime}`}
              controls
              autoPlay
              className="w-full h-full rounded-lg"
              style={{ objectFit: 'contain' }}
              src={`${source_s3_path}#t=${startTime}`}
              onError={(e) => console.error("Video load error in main display:", e.target.error)}
            >
              Your browser does not support the video tag.
            </video>
          </div>
          {start_timestamp && (
            <p className="mt-2 text-muted-green flex-shrink-0 text-sm font-mono">
              Segment starts at: {formatTimestamp(start_timestamp)} (playing from {formatTimestamp(startTime)})
            </p>
          )}
        </div>
      );
    }

    if (file_type === 'pdf' && images.length > 0) {
      // For PDFs, embed them in an iframe with page navigation
      // Use page_start from the result to jump to the relevant page
      const { page_start, page_end, total_pages } = selectedResult;
      
      // Build PDF URL with page fragment to jump to relevant page
      // Most PDF viewers support #page=N fragment
      const pdfUrl = page_start 
        ? `${images[currentImageIndex]}#page=${page_start}`
        : images[currentImageIndex];
      
      return (
        <div className="h-full flex flex-col overflow-hidden">
          <h2 className="text-xl font-semibold mb-2 text-dark-text flex-shrink-0">{title}</h2>
          {page_start && (
            <p className="text-sm text-electric-cyan mb-4 flex-shrink-0 font-mono">
              [ Relevant pages: {page_start}{page_end && page_end !== page_start ? `-${page_end}` : ''} of {total_pages || '?'} ]
            </p>
          )}
          <div className="flex-1 flex flex-col items-center justify-center relative min-h-0">
            <iframe
              key={pdfUrl}
              src={pdfUrl}
              className="w-full h-full rounded-lg"
              title={`${title} - Page ${page_start || 1}`}
            />
            {images.length > 1 && (
              <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 flex gap-2 bg-dark-surface/90 backdrop-blur-sm rounded-lg p-2">
                <button
                  onClick={prevImage}
                  disabled={currentImageIndex === 0}
                  className="px-4 py-2 bg-dark-bg text-dark-text rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-dark-card transition-colors"
                >
                  Previous
                </button>
                <span className="px-4 py-2 bg-dark-bg text-dark-text rounded-lg">
                  Doc {currentImageIndex + 1} / {images.length}
                </span>
                <button
                  onClick={nextImage}
                  disabled={currentImageIndex === images.length - 1}
                  className="px-4 py-2 bg-dark-bg text-dark-text rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-dark-card transition-colors"
                >
                  Next
                </button>
              </div>
            )}
            <a 
              href={pdfUrl} 
              target="_blank" 
              rel="noopener noreferrer"
              className="absolute top-4 right-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Open in New Tab
            </a>
          </div>
        </div>
      );
    }

    if (['jpg', 'gif'].includes(file_type) && images.length > 0) {
      return (
        <div className="h-full flex flex-col overflow-hidden">
          <h2 className="text-xl font-semibold mb-4 text-dark-text flex-shrink-0">{title}</h2>
          <div className="flex-1 flex items-center justify-center relative min-h-0">
            <img
              src={images[currentImageIndex]}
              alt={`${title} - Page ${currentImageIndex + 1}`}
              className="max-w-full max-h-full object-contain rounded-lg"
            />
            {images.length > 1 && (
              <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 flex gap-2">
                <button
                  onClick={prevImage}
                  disabled={currentImageIndex === 0}
                  className="px-4 py-2 bg-dark-surface text-dark-text rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-dark-card transition-colors"
                >
                  Previous
                </button>
                <span className="px-4 py-2 bg-dark-surface text-dark-text rounded-lg">
                  {currentImageIndex + 1} / {images.length}
                </span>
                <button
                  onClick={nextImage}
                  disabled={currentImageIndex === images.length - 1}
                  className="px-4 py-2 bg-dark-surface text-dark-text rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-dark-card transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </div>
      );
    }

    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-dark-muted">
          <p className="text-xl mb-2">{title}</p>
          <p>Preview not available for this file type</p>
        </div>
      </div>
    );
  };

  const renderResultItem = (result, index) => {
    const { file_type, source_s3_path, title, start_timestamp, source_file_name, page_start, page_end, score } = result;
    const images = getImageSources(result);
    const uniqueKey = `${title}|||${source_file_name}|||${start_timestamp || 'no-ts'}|||${page_start || 'no-page'}-${index}`;
    const isSelected =
      selectedResult &&
      selectedResult.title === title &&
      selectedResult.source_file_name === source_file_name &&
      selectedResult.start_timestamp === result.start_timestamp &&
      selectedResult.page_start === result.page_start;

    // Calculate progress percentage for video chunks (0-100%)
    const progressPercentage = start_timestamp ? Math.min((start_timestamp / 600) * 100, 100) : 0;

    return (
      <div
        key={uniqueKey}
        onClick={() => {
          setSelectedResult({ ...result });
          setCurrentImageIndex(0);
          setShowFullDocument(false);
          setFullDocument(null);
        }}
        className={`p-3 cursor-pointer transition-all border font-mono result-card-hover ${
          isSelected
            ? 'bg-dark-card neon-border shadow-neon'
            : 'bg-dark-surface border-neon-green-dark'
        }`}
      >
        <div className="flex gap-3">
          <div className="flex-shrink-0 w-16 h-16 bg-dark-bg border border-neon-green-dark flex items-center justify-center overflow-hidden relative group">
            {(file_type === 'mp4' || file_type === 'video_chunk') && source_s3_path ? (
              <>
                <video
                  className="w-full h-full object-cover"
                  muted
                  preload="metadata"
                  src={source_s3_path}
                  onError={(e) => {
                    console.error("Video thumbnail load error:", e.target.error, source_s3_path);
                    e.target.style.display = 'none';
                    e.target.parentElement.innerHTML = '<div class="text-2xl flex items-center justify-center h-full">🎥</div>';
                  }}
                ></video>
                {start_timestamp && (
                  <div className="video-progress-bar" style={{ width: `${progressPercentage}%` }}></div>
                )}
                {/* Play button overlay */}
                <div className="absolute inset-0 flex items-center justify-center bg-black/40 group-hover:bg-black/60 transition-colors">
                  <svg className="w-8 h-8 text-neon-green" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z"/>
                  </svg>
                </div>
              </>
            ) : images.length > 0 && file_type !== 'pdf' ? (
              <>
                <img
                  src={images[0]}
                  alt={title}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    console.error("Image thumbnail load error:", e.target.error, images[0]);
                    e.target.style.display = 'none';
                    e.target.parentElement.innerHTML = '<div class="text-2xl">📄</div>';
                  }}
                />
                {/* Image icon overlay */}
                <div className="absolute inset-0 flex items-center justify-center bg-black/40 group-hover:bg-black/60 transition-colors">
                  <svg className="w-8 h-8 text-neon-green" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                  </svg>
                </div>
              </>
            ) : (
              <div className="text-2xl">
                {file_type === 'pdf' ? (
                  <>
                    📑
                    {/* Document icon overlay */}
                    <div className="absolute inset-0 flex items-center justify-center bg-black/40 group-hover:bg-black/60 transition-colors">
                      <svg className="w-8 h-8 text-neon-green" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                        <polyline points="10 9 9 9 8 9"/>
                      </svg>
                    </div>
                  </>
                ) : file_type === 'mp4' || file_type === 'video_chunk' ? '🎥' : '📄'}
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-lime-green text-xs line-clamp-2 mb-1">
              {title}
              {source_file_name && (
                <span className="ml-1 text-[10px] text-dark-muted">{source_file_name}</span>
              )}
            </h3>
            <div className="flex items-center gap-2 text-[10px] text-electric-cyan flex-wrap">
              <span className="px-2 py-0.5 bg-dark-bg border border-electric-cyan">
                [{file_type?.toUpperCase()}]
              </span>
              {start_timestamp && (
                <span>[{formatTimestamp(start_timestamp)}]</span>
              )}
              {page_start && (
                <span>[p.{page_start}{page_end && page_end !== page_start ? `-${page_end}` : ''}]</span>
              )}
              {/* Vector search score badge */}
              {score !== undefined && (
                <span className={`px-2 py-0.5 border border-neon-green text-neon-green ${getScoreBadgeClass(score)}`}>
                  {formatScore(score)}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="h-screen bg-dark-bg text-dark-text flex flex-col overflow-hidden border-4 border-neon-green">
      {/* Header */}
      <header className="bg-dark-surface neon-border-lg px-6 py-3 flex-shrink-0 border-b-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-3xl font-black text-neon-green title-glow tracking-wider" style={{ fontFamily: 'Courier New, monospace', textTransform: 'uppercase' }}>
              NASA RECORDS AI SEARCH
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <p className="text-dark-lime italic text-xs font-mono">
              &gt; Source: National Archives and Records Administration
            </p>
            <img 
              src="/mdb-leaf.png" 
              alt="MongoDB Logo" 
              className="h-10 w-auto opacity-60 hover:opacity-100 transition-opacity"
              style={{ filter: 'brightness(0) saturate(100%) invert(88%) sepia(85%) saturate(2427%) hue-rotate(54deg) brightness(104%) contrast(119%)' }}
            />
          </div>
        </div>
      </header>

      {/* Search Bar */}
      <div className="bg-dark-surface neon-border px-6 py-3 flex-shrink-0">
        <div>
          <form onSubmit={handleSearch} className="space-y-2">
            <div className="flex gap-3 items-center">
              <div className="flex-1">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="ENTER SEARCH QUERY..."
                  className="w-full px-4 py-2 bg-dark-bg border-2 border-dark-gray-green text-lime-green placeholder-dark-muted focus:outline-none focus:border-lime-green transition-all font-mono blinking-cursor text-sm"
                />
              </div>
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className={`px-4 py-2 bg-electric-cyan text-black font-bold rounded disabled:opacity-50 disabled:cursor-not-allowed transition-all font-mono hover:bg-electric-cyan/80 text-sm ${!loading && query.trim() ? 'search-btn-pulse' : ''}`}
              >
                {loading ? '[ SEARCHING... ]' : '[ SEARCH ]'}
              </button>
              {/* Reranker toggle */}
              <label className="flex items-center gap-2 text-xs text-neon-green-dark select-none cursor-pointer font-mono whitespace-nowrap">
                <input
                  type="checkbox"
                  checked={useReranker}
                  onChange={() => setUseReranker((v) => !v)}
                  className="accent-neon-green"
                />
                Reranker
              </label>
            </div>
            
            {/* File Types and Index Selection Row */}
            <div className="flex gap-4">
              {/* File Types Filter */}
              <div className="flex-1 bg-dark-bg neon-border p-2">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-[10px] text-neon-green font-mono">[ FILE TYPES ]</div>
                  {selectedFileTypes.length === 0 && (
                    <div className="text-[10px] text-dark-muted font-mono">* All</div>
                  )}
                </div>
                <div className="flex flex-wrap gap-1">
                  {fileTypes.map(type => (
                    <label
                      key={type.value}
                      className={`flex items-center gap-1 px-2 py-1 text-[10px] cursor-pointer transition-all font-mono ${
                        selectedFileTypes.includes(type.value)
                          ? 'bg-neon-cyan text-black neon-button'
                          : 'bg-dark-surface text-neo-mint border border-neo-mint hover:border-neon-cyan hover:text-neon-cyan'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedFileTypes.includes(type.value)}
                        onChange={() => handleFileTypeToggle(type.value)}
                        className="sr-only"
                      />
                      {type.label}
                    </label>
                  ))}
                </div>
              </div>

              {/* Quantization Selector */}
              <div className="bg-dark-bg neon-border p-2 min-w-[320px]">
                <div className="text-[10px] text-neon-green font-mono mb-1">[ QUANTIZATION ]</div>
                <div className="flex gap-1">
                  {/* Always render in order: float32, scalar, binary (largest to smallest) */}
                  {[
                    { key: 'float32', label: 'FLOAT32', storage: '~47 MB', tooltip: 'Full precision (32-bit float per dimension). Highest accuracy, largest storage.', colorClass: 'quant-float32' },
                    { key: 'scalar', label: 'SCALAR', storage: '~12 MB', tooltip: 'Scalar quantization (8-bit int per dimension). ~75% storage reduction with minimal accuracy loss.', colorClass: 'quant-scalar' },
                    { key: 'binary', label: 'BINARY', storage: '~1.5 MB', tooltip: 'Binary quantization (1-bit per dimension). ~97% storage reduction, best for high-recall pre-filtering.', colorClass: 'quant-binary' }
                  ].map(({ key, label, storage, tooltip, colorClass }) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setSelectedIndex(key)}
                      title={tooltip}
                      className={`flex-1 px-2 py-1 text-[10px] font-mono transition-all relative group ${
                        selectedIndex === key
                          ? `${colorClass} text-black`
                          : 'bg-dark-surface text-neon-green border border-neon-green-dark hover:border-neon-green'
                      }`}
                    >
                      <div className="font-bold">{label}</div>
                      <div className="text-[8px] opacity-75">{storage}</div>
                      {/* Tooltip */}
                      <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-dark-bg border border-neon-green text-neon-green text-[9px] rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 max-w-[200px] text-wrap">
                        {tooltip}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </form>
          
          {error && (
            <div className="mt-3 p-3 bg-red-900/20 neon-border text-neon-green font-mono text-sm">
              [ ERROR ] {error}
            </div>
          )}

          {/* Query Metadata Display */}
          {queryMetadata && (
            <div className="mt-3 bg-dark-bg neon-border p-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 text-xs font-mono">
                  <span className="text-electric-cyan">
                    ⚡ Latency: <span className="text-neon-green font-bold">{queryMetadata.latency_ms}ms</span>
                  </span>
                  <span className="text-electric-cyan">
                    📊 Results: <span className="text-neon-green font-bold">{queryMetadata.result_count}</span>
                  </span>
                  <span className="text-electric-cyan">
                    🔍 Index: <span className="text-neon-green font-bold">{queryMetadata.index_type}</span>
                  </span>
                </div>
                <button
                  onClick={() => setShowPipeline(!showPipeline)}
                  className="text-[10px] font-mono text-electric-cyan hover:text-neon-green transition-colors"
                >
                  {showPipeline ? '[ HIDE PIPELINE ▲ ]' : '[ SHOW PIPELINE ▼ ]'}
                </button>
              </div>
              
              {/* Aggregation Pipeline Dropdown */}
              {showPipeline && (
                <div className="mt-2 p-2 bg-dark-surface border border-neon-green-dark rounded overflow-x-auto">
                  <pre className="text-[10px] text-lime-green font-mono whitespace-pre-wrap">
                    {JSON.stringify(queryMetadata.pipeline, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex flex-1 overflow-hidden">
          {/* Main Display */}
          <div className="flex-1 bg-dark-surface border-r-2 border-neon-green p-4 flex flex-col overflow-hidden">
            <div className="flex-1 overflow-hidden">
              {renderMainContent()}
            </div>
            
            {/* View Full Document Button */}
            {selectedResult && selectedResult._id && (
              <div className="mt-2 flex-shrink-0">
                <button
                  onClick={() => {
                    if (showFullDocument) {
                      setShowFullDocument(false);
                    } else {
                      fetchFullDocument(selectedResult._id);
                    }
                  }}
                  disabled={loadingDocument}
                  className="text-xs font-mono text-electric-cyan hover:text-neon-green transition-colors"
                >
                  {loadingDocument ? '[ LOADING... ]' : showFullDocument ? '[ HIDE DOCUMENT ▲ ]' : '[ VIEW FULL DOCUMENT ▼ ]'}
                </button>
              </div>
            )}
            
            {/* Full Document Viewer */}
            {showFullDocument && fullDocument && (
              <div className="mt-2 flex-shrink-0 max-h-48 overflow-y-auto bg-dark-bg neon-border p-2 rounded">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-[10px] text-neon-green font-mono">[ FULL DOCUMENT ]</span>
                  <button
                    onClick={() => setShowFullDocument(false)}
                    className="text-[10px] text-electric-cyan hover:text-neon-green"
                  >
                    ✕
                  </button>
                </div>
                <pre className="text-[10px] text-lime-green font-mono whitespace-pre-wrap">
                  {JSON.stringify(fullDocument, null, 2)}
                </pre>
              </div>
            )}
          </div>

          {/* Results Sidebar */}
          <div className="w-72 bg-dark-surface flex-shrink-0 flex flex-col">
            <div className="p-3 border-b-2 border-neon-green flex-shrink-0">
              <h2 className="text-sm font-semibold text-lime-green font-mono">
                [ RESULTS: {results.length} ]
              </h2>
            </div>
            <div className="p-3 space-y-2 overflow-y-auto flex-1">
              {loading && (
                <div className="py-8">
                  <div className="h-2 w-full loading-bar rounded"></div>
                  <p className="text-dark-muted text-center mt-4 font-mono text-xs">
                    &gt; Searching...
                  </p>
                </div>
              )}
              {results.length === 0 && !loading && (
                <p className="text-dark-muted text-center py-8 font-mono text-xs">
                  &gt; No results yet. Try searching!
                </p>
              )}
              {/* Render all results individually */}
              {results.map((result, index) =>
                renderResultItem(result, index)
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-dark-surface border-t-2 border-neon-green p-2 flex-shrink-0">
        <div className="max-w-7xl mx-auto text-center">
          <p className="text-[10px] text-neon-green-dark font-mono">
            © 2025 MongoDB | Vector Search Demo
          </p>
        </div>
      </footer>
    </div>
  );
};

export default App;
