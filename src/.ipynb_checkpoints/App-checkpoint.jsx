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
  const [useReranker, setUseReranker] = useState(true);

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
            <div className="text-6xl mb-4">🚀</div>
            <p className="text-xl">Search NASA records to get started</p>
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
        <div className="h-full flex flex-col">
          <h2 className="text-xl font-semibold mb-4 text-dark-text">{title}</h2>
          <div className="flex-1 flex items-center justify-center">
            <video
              key={`${source_s3_path}-${startTime}`}
              controls
              autoPlay
              className="max-w-full max-h-full rounded-lg bg-black"
              src={`${source_s3_path}#t=${startTime}`}
              onError={(e) => console.error("Video load error in main display:", e.target.error)}
            >
              Your browser does not support the video tag.
            </video>
          </div>
          {start_timestamp && (
            <p className="mt-4 text-dark-muted">
              Segment starts at: {formatTimestamp(start_timestamp)} (playing from {formatTimestamp(startTime)})
            </p>
          )}
        </div>
      );
    }

    if (file_type === 'pdf' && images.length > 0) {
      // For PDFs, embed them in an iframe or provide download link
      return (
        <div className="h-full flex flex-col">
          <h2 className="text-xl font-semibold mb-4 text-dark-text">{title}</h2>
          <div className="flex-1 flex flex-col items-center justify-center relative">
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
        <div className="h-full flex flex-col">
          <h2 className="text-xl font-semibold mb-4 text-dark-text">{title}</h2>
          <div className="flex-1 flex items-center justify-center relative overflow-hidden">
            <img
              src={images[currentImageIndex]}
              alt={`${title} - Page ${currentImageIndex + 1}`}
              className="max-w-full max-h-full object-contain rounded-lg"
              style={{ maxWidth: '100%', maxHeight: '100%' }}
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

  // Group video chunks by unique video (title + source_file_name)
  const groupVideoChunks = (results) => {
    const groups = {};
    results.forEach((r) => {
      if ((r.file_type === 'mp4' || r.file_type === 'video_chunk')) {
        const groupKey = `${r.title}|||${r.source_file_name}`;
        if (!groups[groupKey]) groups[groupKey] = [];
        groups[groupKey].push(r);
      }
    });
    return groups;
  };

  // For non-video results, just return as is
  const getNonVideoResults = (results) =>
    results.filter(
      (r) => r.file_type !== 'mp4' && r.file_type !== 'video_chunk'
    );

  // For video results, group by title + source_file_name
  const videoGroups = groupVideoChunks(results);
  const nonVideoResults = getNonVideoResults(results);

  // UI state for open dropdowns
  const [openDropdown, setOpenDropdown] = useState(null);

  const renderResultItem = (result, index, groupKey = null, isTopChunk = false) => {
    const { file_type, source_s3_path, title, start_timestamp, source_file_name, chunk_text_content } = result;
    const images = getImageSources(result);
    // Unique key: title + source_file_name + start_timestamp
    const uniqueKey = `${title}|||${source_file_name}|||${start_timestamp || 'no-ts'}-${index}`;
    const isSelected =
      selectedResult &&
      selectedResult.title === title &&
      selectedResult.source_file_name === source_file_name &&
      selectedResult.start_timestamp === result.start_timestamp;

    // If rendering a video chunk in the dropdown
    if (groupKey && !isTopChunk) {
      // No thumbnail, just timestamp and chunk_text_content
      return (
        <div
          key={uniqueKey}
          onMouseDown={(e) => {
            e.stopPropagation();
            // Force re-render by creating a new object reference
            setSelectedResult({ ...result });
            setCurrentImageIndex(0);
          }}
          className={`pl-8 pr-2 py-2 cursor-pointer rounded transition-colors text-xs leading-tight ${
            isSelected
              ? 'bg-blue-900/40 text-blue-200'
              : 'hover:bg-dark-card/80 text-dark-muted'
          }`}
          style={{ borderLeft: '2px solid #334155' }}
        >
          <span className="font-mono text-[11px] text-blue-300 mr-2">
            {formatTimestamp(start_timestamp)}
          </span>
          <span className="truncate">{chunk_text_content || <em>No text</em>}</span>
        </div>
      );
    }

    // Otherwise, render the main result item (video group or non-video)
    return (
      <div
        key={uniqueKey}
        onClick={() => {
          // For video group, play top chunk; for non-video, play as usual
          if (groupKey) {
            setSelectedResult({ ...videoGroups[groupKey][0] });
          } else {
            setSelectedResult({ ...result });
          }
          setCurrentImageIndex(0);
        }}
        className={`p-4 rounded-lg cursor-pointer transition-colors border ${
          isSelected
            ? 'bg-dark-card border-blue-500'
            : 'bg-dark-surface border-dark-border hover:bg-dark-card'
        }`}
      >
        <div className="flex gap-3">
          <div className="flex-shrink-0 w-16 h-16 bg-dark-bg rounded-lg flex items-center justify-center overflow-hidden relative">
            {(file_type === 'mp4' || file_type === 'video_chunk') && source_s3_path && (!groupKey || isTopChunk) ? (
              <>
                <video
                  className="w-full h-full object-cover"
                  muted
                  preload="metadata"
                  src={source_s3_path}
                  onError={(e) => {
                    console.error("Video thumbnail load error:", e.target.error, source_s3_path);
                    e.target.style.display = 'none';
                    e.target.nextSibling.style.display = 'flex'; // Show fallback emoji
                  }}
                ></video>
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <div className="text-2xl bg-black/50 rounded-full p-1">🎥</div>
                </div>
              </>
            ) : images.length > 0 && file_type !== 'pdf' && (!groupKey || isTopChunk) ? (
              <img
                src={images[0]}
                alt={title}
                className="w-full h-full object-cover"
                onError={(e) => {
                  console.error("Image thumbnail load error:", e.target.error, images[0]);
                  e.target.style.display = 'none';
                  e.target.parentElement.innerHTML = '<div class="text-2xl">📄</div>'; // Fallback to emoji
                }}
              />
            ) : (
              <div className="text-2xl">
                {file_type === 'pdf' ? '📑' : file_type === 'mp4' || file_type === 'video_chunk' ? '🎥' : '📄'}
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-dark-text text-sm line-clamp-2 mb-1">
              {title}
              {source_file_name && (
                <span className="ml-1 text-xs text-dark-muted font-mono">{source_file_name}</span>
              )}
            </h3>
            <div className="flex items-center gap-2 text-xs text-dark-muted">
              <span className="px-2 py-1 bg-dark-bg rounded text-xs">
                {file_type?.toUpperCase()}
              </span>
              {start_timestamp && (
                <span>{formatTimestamp(start_timestamp)}</span>
              )}
            </div>
          </div>
          {/* Dropdown toggle for video groups */}
          {groupKey && videoGroups[groupKey].length > 1 && (
            <button
              className="ml-2 px-2 py-1 text-xs bg-dark-bg rounded hover:bg-blue-800/60 text-blue-300"
              onClick={(e) => {
                e.stopPropagation();
                setOpenDropdown(openDropdown === groupKey ? null : groupKey);
              }}
              aria-label="Show video chunks"
            >
              {openDropdown === groupKey ? '▲' : '▼'}
            </button>
          )}
        </div>
        {/* Dropdown for video chunks */}
        {groupKey && openDropdown === groupKey && (
          <div className="mt-2">
            {videoGroups[groupKey]
              .sort((a, b) => (a.start_timestamp || 0) - (b.start_timestamp || 0))
              .map((chunk, idx) =>
                // Only render the dropdown chunk, not recursively render the group
                renderResultItem(chunk, idx, null, false)
              )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-dark-bg text-dark-text">
      {/* Header */}
      <header className="bg-dark-surface border-b border-dark-border p-6">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-dark-text mb-2" style={{ fontFamily: 'Noto Serif JP, serif' }}>
              NASA Records Search
            </h1>
            <p className="text-dark-muted italic">
              Source: National Archives and Records Administration
            </p>
          </div>
          <div className="flex-shrink-0">
            <img 
              src="/mdb-leaf.png" 
              alt="MongoDB Logo" 
              className="h-16 w-auto opacity-80 hover:opacity-100 transition-opacity"
            />
          </div>
        </div>
      </header>

      {/* Search Bar */}
      <div className="bg-dark-surface border-b border-dark-border p-6">
        <div className="max-w-7xl mx-auto">
          <form onSubmit={handleSearch} className="flex gap-4 items-center">
            <div className="flex-1">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search NASA records..."
                className="w-full px-4 py-3 bg-dark-bg border border-dark-border rounded-lg text-dark-text placeholder-dark-muted focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div className="w-64">
              <div className="bg-dark-bg border border-dark-border rounded-lg p-3">
                <div className="text-xs text-dark-muted mb-2">File Types:</div>
                <div className="flex flex-wrap gap-2">
                  {fileTypes.map(type => (
                    <label
                      key={type.value}
                      className={`flex items-center gap-1 px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
                        selectedFileTypes.includes(type.value)
                          ? 'bg-blue-600 text-white'
                          : 'bg-dark-surface text-dark-muted hover:bg-dark-card'
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
                {selectedFileTypes.length === 0 && (
                  <div className="text-xs text-dark-muted mt-1">All types selected</div>
                )}
              </div>
            </div>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Searching...' : 'Search'}
            </button>
            {/* Reranker toggle */}
            <label className="ml-4 flex items-center gap-2 text-xs text-dark-muted select-none cursor-pointer">
              <input
                type="checkbox"
                checked={useReranker}
                onChange={() => setUseReranker((v) => !v)}
                className="accent-blue-600"
              />
              Use reranker
            </label>
          </form>
          {error && (
            <div className="mt-4 p-4 bg-red-900/20 border border-red-500/30 rounded-lg text-red-400">
              {error}
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="max-w-7xl mx-auto p-6">
        <div className="flex gap-6 h-[calc(100vh-280px)]">
          {/* Main Display */}
          <div className="flex-1 bg-dark-surface rounded-lg p-6 border border-dark-border">
            {renderMainContent()}
          </div>

          {/* Results Sidebar */}
          <div className="w-80 bg-dark-surface rounded-lg border border-dark-border">
            <div className="p-4 border-b border-dark-border">
              <h2 className="text-lg font-semibold text-dark-text">
                Results ({results.length})
              </h2>
            </div>
            <div className="p-4 space-y-3 overflow-y-auto h-[calc(100%-80px)]">
              {results.length === 0 && !loading && (
                <p className="text-dark-muted text-center py-8">
                  No results yet. Try searching for something!
                </p>
              )}
              {/* Render grouped video results */}
              {Object.keys(videoGroups).map((groupKey, idx) =>
                renderResultItem(videoGroups[groupKey][0], idx, groupKey, true)
              )}
              {/* Render non-video results */}
              {nonVideoResults.map((result, index) =>
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
