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

  const fileTypes = [
    { value: 'mp4', label: 'Videos (.mp4)' },
    { value: 'jpg', label: 'Images (.jpg)' },
    { value: 'gif', label: 'GIFs (.gif)' },
    { value: 'pdf', label: 'Documents (.pdf)' }
  ];

  // Reranker toggle state
  const [useReranker, setUseReranker] = useState(false);

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
    
    try {
      const response = await axios.post('/search', {
        query_text: query,
        filter_file_types: selectedFileTypes.length > 0 ? selectedFileTypes : undefined,
        use_reranker: useReranker
      });
      
      setResults(response.data);
      if (response.data.length > 0) {
        setSelectedResult(response.data[0]);
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

  const handleResultClick = (result) => {
    setSelectedResult(result);
    setCurrentImageIndex(0);
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
    return Math.max(0, timestamp - 3);
  };

  const renderMainContent = () => {
    if (!selectedResult) {
      return (
        <div className="flex items-center justify-center h-full text-dark-muted">
          <div className="text-center">
            <div className="text-6xl mb-4 retro-glow">🚀</div>
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
          <h2 className="text-xl font-semibold mb-4 text-dark-text flex-shrink-0">{title}</h2>
          <div className="flex-1 flex items-center justify-center min-h-0">
            <video
              key={`${source_s3_path}-${startTime}`}
              controls
              autoPlay
              className="max-w-full max-h-full rounded-lg bg-black"
              style={{ objectFit: 'contain' }}
              src={`${source_s3_path}#t=${startTime}`}
              onError={(e) => console.error("Video load error in main display:", e.target.error)}
            >
              Your browser does not support the video tag.
            </video>
          </div>
          {start_timestamp && (
            <p className="mt-4 text-dark-muted flex-shrink-0">
              Segment starts at: {formatTimestamp(start_timestamp)} (playing from {formatTimestamp(startTime)})
            </p>
          )}
        </div>
      );
    }

    if (file_type === 'pdf' && images.length > 0) {
      // For PDFs, embed them in an iframe or provide download link
      return (
        <div className="h-full flex flex-col overflow-hidden">
          <h2 className="text-xl font-semibold mb-4 text-dark-text flex-shrink-0">{title}</h2>
          <div className="flex-1 flex flex-col items-center justify-center relative min-h-0">
            <iframe
              src={images[currentImageIndex]}
              className="w-full h-full rounded-lg"
              title={`${title} - Page ${currentImageIndex + 1}`}
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
                  Page {currentImageIndex + 1} / {images.length}
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
              href={images[currentImageIndex]} 
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
    const { file_type, source_s3_path, title, start_timestamp, source_file_name } = result;
    const images = getImageSources(result);
    const uniqueKey = `${title}|||${source_file_name}|||${start_timestamp || 'no-ts'}-${index}`;
    const isSelected =
      selectedResult &&
      selectedResult.title === title &&
      selectedResult.source_file_name === source_file_name &&
      selectedResult.start_timestamp === result.start_timestamp;

    // Calculate progress percentage for video chunks (0-100%)
    const progressPercentage = start_timestamp ? Math.min((start_timestamp / 600) * 100, 100) : 0;

    return (
      <div
        key={uniqueKey}
        onClick={() => {
          setSelectedResult({ ...result });
          setCurrentImageIndex(0);
        }}
        className={`p-3 cursor-pointer transition-all border font-mono ${
          isSelected
            ? 'bg-dark-card neon-border shadow-neon'
            : 'bg-dark-surface border-neon-green-dark hover:border-neon-green hover:shadow-neon'
        }`}
      >
        <div className="flex gap-3">
          <div className="flex-shrink-0 w-16 h-16 bg-dark-bg border border-neon-green-dark flex items-center justify-center overflow-hidden relative">
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
              </>
            ) : images.length > 0 && file_type !== 'pdf' ? (
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
            ) : (
              <div className="text-2xl">
                {file_type === 'pdf' ? '📑' : file_type === 'mp4' || file_type === 'video_chunk' ? '🎥' : '📄'}
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-neon-green text-xs line-clamp-2 mb-1">
              {title}
              {source_file_name && (
                <span className="ml-1 text-[10px] text-dark-muted">{source_file_name}</span>
              )}
            </h3>
            <div className="flex items-center gap-2 text-[10px] text-neon-green-dark">
              <span className="px-2 py-0.5 bg-dark-bg border border-neon-green-dark">
                [{file_type?.toUpperCase()}]
              </span>
              {start_timestamp && (
                <span>[{formatTimestamp(start_timestamp)}]</span>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="h-screen bg-dark-bg text-dark-text flex flex-col overflow-hidden">
      {/* Header */}
      <header className="bg-dark-surface neon-border-lg p-6 flex-shrink-0">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-neon-green retro-glow mb-2" style={{ fontFamily: 'Courier New, monospace', letterSpacing: '2px' }}>
              NASA RECORDS AI SEARCH
            </h1>
            <p className="text-dark-muted italic text-sm">
              &gt; Source: National Archives and Records Administration
            </p>
          </div>
          <div className="flex-shrink-0">
            <img 
              src="/mdb-leaf.png" 
              alt="MongoDB Logo" 
              className="h-16 w-auto opacity-60 hover:opacity-100 transition-opacity"
              style={{ filter: 'brightness(0) saturate(100%) invert(88%) sepia(85%) saturate(2427%) hue-rotate(54deg) brightness(104%) contrast(119%)' }}
            />
          </div>
        </div>
      </header>

      {/* Search Bar */}
      <div className="bg-dark-surface neon-border p-6 flex-shrink-0">
        <div className="max-w-7xl mx-auto">
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="flex gap-4 items-center">
              <div className="flex-1">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="ENTER SEARCH QUERY..."
                  className="w-full px-4 py-3 bg-dark-bg neon-border text-neon-green placeholder-dark-muted focus:outline-none focus:shadow-neon transition-all font-mono blinking-cursor"
                />
              </div>
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="px-6 py-3 bg-neon-green text-black font-bold rounded neon-button disabled:opacity-50 disabled:cursor-not-allowed transition-all font-mono"
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
                Use reranker
              </label>
            </div>
            
            {/* File Types Filter - Now Below */}
            <div className="bg-dark-bg neon-border p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs text-neon-green font-mono">[ FILE TYPES ]</div>
                {selectedFileTypes.length === 0 && (
                  <div className="text-xs text-dark-muted font-mono">* All types selected</div>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {fileTypes.map(type => (
                  <label
                    key={type.value}
                    className={`flex items-center gap-1 px-3 py-1.5 text-xs cursor-pointer transition-all font-mono ${
                      selectedFileTypes.includes(type.value)
                        ? 'bg-neon-green text-black neon-button'
                        : 'bg-dark-surface text-neon-green-dark border border-neon-green-dark hover:border-neon-green hover:text-neon-green'
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
          </form>
          {error && (
            <div className="mt-4 p-4 bg-red-900/20 neon-border text-neon-green font-mono">
              [ ERROR ] {error}
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        <div className="flex flex-1">
          {/* Main Display */}
          <div className="flex-1 bg-dark-surface border-r-2 border-neon-green p-6">
            {renderMainContent()}
          </div>

          {/* Results Sidebar */}
          <div className="w-80 bg-dark-surface flex-shrink-0">
            <div className="p-4 border-b-2 border-neon-green">
              <h2 className="text-lg font-semibold text-neon-green font-mono">
                [ RESULTS: {results.length} ]
              </h2>
            </div>
            <div className="p-4 space-y-3 overflow-y-auto h-[calc(100%-80px)]">
              {results.length === 0 && !loading && (
                <p className="text-dark-muted text-center py-8 font-mono">
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
    </div>
  );
};

export default App;
