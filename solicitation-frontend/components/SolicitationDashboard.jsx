import React, { useState, useEffect } from 'react';
import { Upload, AlertCircle, Menu, Database, FileText, X, Trash, Search, AlertTriangle } from 'lucide-react';

const LoadingBar = () => {
    const [progress, setProgress] = useState(0);
    useEffect(() => {
        const interval = setInterval(() => {
            setProgress((prev) => (prev >= 90 ? 90 : prev + 2));
        }, 100);
        return () => clearInterval(interval);
    }, []);
    return (
        <div className="w-full bg-gray-700 rounded-full h-2 mb-4 overflow-hidden">
            <div className="bg-blue-500 h-2 rounded-full transition-all duration-300 ease-out" style={{ width: `${progress}%` }} />
        </div>
    );
};

const TruncatedText = ({ text, maxLength = 18 }) => {
    const truncated = text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    
    return (
        <span className="truncate max-w-[140px] block" title={text}>
            {truncated}
        </span>
    );
};

const ConfirmationDialog = ({ isOpen, onConfirm, onCancel, filename }) => {
    if (!isOpen) return null;
    
    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full">
                <div className="flex items-start mb-4">
                    <AlertTriangle className="h-6 w-6 text-yellow-500 mr-3 flex-shrink-0" />
                    <div>
                        <h3 className="text-lg font-medium text-gray-100">Document Already Exists</h3>
                        <p className="text-gray-400 mt-1">
                            A document with the filename "{filename}" already exists in the database. 
                            Do you want to continue and overwrite it?
                        </p>
                    </div>
                </div>
                <div className="flex justify-end space-x-3">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 text-gray-300 bg-gray-700 rounded-lg hover:bg-gray-600"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
                    >
                        Overwrite
                    </button>
                </div>
            </div>
        </div>
    );
};

const SolicitationDashboard = () => {
    const [file, setFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [summaries, setSummaries] = useState([]);
    const [error, setError] = useState(null);
    const [view, setView] = useState('upload');
    const [openSummaries, setOpenSummaries] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [isSearching, setIsSearching] = useState(false);
    const [showConfirmation, setShowConfirmation] = useState(false);
    const [existingDocumentId, setExistingDocumentId] = useState(null);

    const fetchSummaries = async (query = '') => {
        setIsSearching(!!query);
        try {
            const url = query 
                ? `http://localhost:8000/summaries/?search=${encodeURIComponent(query)}`
                : 'http://localhost:8000/summaries/';
                
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error('Failed to fetch stored summaries');
            }
            const data = await response.json();
            setSummaries(data);
            setIsSearching(false);
        } catch (err) {
            setError(err.message);
            setIsSearching(false);
        }
    };

    useEffect(() => {
        if (view === 'database') {
            fetchSummaries();
        }
    }, [view]);

    const handleSearch = (e) => {
        e.preventDefault();
        fetchSummaries(searchQuery);
    };

    const handleSearchChange = (e) => {
        setSearchQuery(e.target.value);
    };

    const clearSearch = () => {
        setSearchQuery('');
        fetchSummaries();
    };

    const handleFileChange = (event) => {
        const selectedFile = event.target.files[0];
        if (selectedFile) {
            setFile(selectedFile);
            setError(null);
            setSummaries([]);
        }
    };

    const checkIfDocumentExists = async (filename) => {
        try {
            const response = await fetch(`http://localhost:8000/document-exists/${encodeURIComponent(filename)}`);
            if (!response.ok) {
                throw new Error('Failed to check if document exists');
            }
            const data = await response.json();
            return data;
        } catch (err) {
            console.error("Error checking if document exists:", err);
            return { exists: false };
        }
    };

    const proceedWithSummarization = async () => {
        setLoading(true);
        setError(null);
        setShowConfirmation(false);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('http://localhost:8000/summarize/', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Summarization failed');
            }

            const data = await response.json();
            setSummaries(data.summaries || []);
            
            // If we overwrote an existing document, refresh the database view
            if (existingDocumentId && view === 'database') {
                fetchSummaries();
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
            setExistingDocumentId(null);
        }
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!file) {
            setError('Please select a file to summarize');
            return;
        }

        // Check if document already exists
        const { exists, id } = await checkIfDocumentExists(file.name);
        
        if (exists) {
            setShowConfirmation(true);
            setExistingDocumentId(id);
        } else {
            // No existing document, proceed with summarization
            proceedWithSummarization();
        }
    };

    const openSummary = (summary) => {
        const exists = openSummaries.find((s) => s.id === summary.id);
        if (!exists) {
            setOpenSummaries((prev) => [...prev, summary]);
        }
        setView(summary.id);
    };

    const exitSummary = () => {
        setView('database');
    };

    // Format date helper function
    const formatDate = (dateString) => {
        if (!dateString) return 'Unknown date';
        return new Date(dateString).toLocaleString();
    };

    return (
        <div className="min-h-screen bg-gray-900 text-gray-100 flex">
            <ConfirmationDialog 
                isOpen={showConfirmation}
                onConfirm={proceedWithSummarization}
                onCancel={() => setShowConfirmation(false)}
                filename={file?.name || ''}
            />
            
            <aside className="w-64 bg-gray-800 p-6 flex-shrink-0">
                <h2 className="text-2xl font-bold text-blue-400 mb-6">Dashboard</h2>
                <button onClick={() => setView('upload')} className={`w-full flex items-center p-3 mb-4 rounded-lg transition ${view === 'upload' ? 'bg-blue-500' : 'bg-gray-700 hover:bg-gray-600'}`}>
                    <Upload className="mr-2" /> Upload & Summarize
                </button>
                <button onClick={() => setView('database')} className={`w-full flex items-center p-3 rounded-lg transition ${view === 'database' ? 'bg-blue-500' : 'bg-gray-700 hover:bg-gray-600'}`}>
                    <Database className="mr-2" /> Summaries Database
                </button>
                {openSummaries.map((summary) => (
                    <div
                        key={summary.id}
                        className={`w-full flex items-center justify-between p-3 mt-2 rounded-lg transition ${
                            view === summary.id ? 'bg-blue-500' : 'bg-gray-700 hover:bg-gray-600'
                        }`}
                        onClick={() => setView(summary.id)}
                    >
                        <div className="flex flex-col">
                            <div className="flex items-center">
                                <FileText className="mr-2" />
                                <span className="truncate">{summary.filename || summary.id}</span>
                            </div>
                            <p className="text-xs text-gray-400 ml-6">{formatDate(summary.upload_time)}</p>
                        </div>
                        <div className="flex items-center space-x-2">
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setOpenSummaries((prev) => prev.filter((s) => s.id !== summary.id));
                                    if (view === summary.id) setView('database');
                                }}
                                className="text-gray-400 hover:text-white"
                                title="Close Tab"
                            >
                                <X className="h-4 w-4" />
                            </button>
                            <button
                                onClick={async (e) => {
                                    e.stopPropagation();
                                    try {
                                        const response = await fetch(`http://localhost:8000/summaries/${summary.id}`, {
                                            method: 'DELETE',
                                        });
                                        if (response.ok) {
                                            setSummaries((prev) => prev.filter((s) => s.id !== summary.id));
                                            setOpenSummaries((prev) => prev.filter((s) => s.id !== summary.id));
                                            if (view === summary.id) setView('database');
                                        } else {
                                            throw new Error('Failed to delete summary');
                                        }
                                    } catch (err) {
                                        setError(err.message);
                                    }
                                }}
                                className="text-red-500 hover:text-red-400"
                                title="Delete Summary"
                            >
                                <Trash className="h-4 w-4" />
                            </button>
                        </div>
                    </div>
                ))}
            </aside>

            <div className="flex-1 p-6">
                {view === 'upload' ? (
                    <div>
                        <h1 className="text-4xl font-bold text-blue-400 mb-4">Solicitation Summarizer</h1>
                        <p className="text-gray-400 mb-6">Upload a document (PDF/Word) to generate a section-based summary.</p>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="border-2 border-dashed border-gray-700 rounded-lg p-8 text-center bg-gray-800/50 hover:bg-gray-800 transition-colors">
                                <input type="file" onChange={handleFileChange} accept=".pdf,.doc,.docx" className="hidden" id="file-upload" />
                                <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center justify-center">
                                    <Upload className="w-16 h-16 text-blue-400 mb-4" />
                                    <span className="text-gray-400">{file ? file.name : 'Click to upload or drag and drop'}</span>
                                </label>
                            </div>
                            {loading && <LoadingBar />}
                            <button type="submit" disabled={loading || !file} className="w-full bg-blue-500 text-white py-3 px-4 rounded-lg hover:bg-blue-600 disabled:bg-gray-700 transition-colors font-medium">
                                {loading ? 'Summarizing...' : 'Summarize Document'}
                            </button>
                        </form>
                        {error && <div className="bg-red-900/50 border-l-4 border-red-500 p-4 mt-4 rounded-r-lg flex items-center"><AlertCircle className="h-5 w-5 text-red-400 mr-2" /> {error}</div>}
                    </div>
                ) : view === 'database' ? (
                    <div>
                        <h1 className="text-4xl font-bold text-blue-400 mb-4">Summaries Database</h1>
                        
                        {/* Search Bar */}
                        <form onSubmit={handleSearch} className="mb-6">
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                                    <Search className="w-5 h-5 text-gray-400" />
                                </div>
                                <input
                                    type="text"
                                    value={searchQuery}
                                    onChange={handleSearchChange}
                                    className="bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full pl-10 p-2.5"
                                    placeholder="Search summaries..."
                                />
                                {searchQuery && (
                                    <button
                                        type="button"
                                        onClick={clearSearch}
                                        className="absolute inset-y-0 right-0 flex items-center pr-3"
                                    >
                                        <X className="w-5 h-5 text-gray-400 hover:text-white" />
                                    </button>
                                )}
                            </div>
                        </form>
                        
                        {isSearching ? (
                            <div className="flex justify-center items-center py-10">
                                <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-blue-500"></div>
                            </div>
                        ) : summaries.length > 0 ? (
                            <div className="bg-gray-800 rounded-lg shadow-xl p-6 space-y-6">
                                {summaries.map((summary, index) => (
                                    <div key={index} className="p-4 border border-gray-700 rounded-lg hover:border-gray-600 transition-colors">
                                        <div className="flex justify-between items-center mb-2">
                                            <h3 className="text-lg font-bold text-gray-200 cursor-pointer hover:text-blue-400" onClick={() => openSummary(summary)}>
                                                {summary.filename || `Document #${summary.id}`}
                                            </h3>
                                            <button onClick={() => {
                                                fetch(`http://localhost:8000/summaries/${summary.id}`, { method: 'DELETE' })
                                                    .then(res => {
                                                        if (res.ok) {
                                                            setSummaries((prev) => prev.filter((s) => s.id !== summary.id));
                                                            setOpenSummaries((prev) => prev.filter((s) => s.id !== summary.id));
                                                        }
                                                    })
                                                    .catch(err => setError(err.message));
                                            }} className="text-red-500 hover:text-red-400">
                                                <Trash className="h-4 w-4" />
                                            </button>
                                        </div>
                                        <p className="text-sm text-gray-400">
                                            Uploaded on: {formatDate(summary.upload_time)}
                                        </p>
                                        <p className="text-gray-300 mt-2 line-clamp-2 cursor-pointer hover:text-blue-100" onClick={() => openSummary(summary)}>
                                            {typeof summary.summary === 'string' ? summary.summary.substring(0, 120) + '...' : 'Click to view summary'}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-10">
                                <p className="text-gray-400">
                                    {searchQuery ? `No results found for "${searchQuery}"` : 'No stored summaries available.'}
                                </p>
                                {searchQuery && (
                                    <button 
                                        onClick={clearSearch}
                                        className="mt-4 text-blue-400 hover:text-blue-300"
                                    >
                                        Clear search
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                ) : (
                    openSummaries.find((s) => s.id === view) && (
                        <div>
                            <div className="flex justify-between items-center mb-6">
                                <div>
                                    <h1 className="text-3xl font-bold text-blue-400">{openSummaries.find((s) => s.id === view).filename || `Document #${view}`}</h1>
                                    <p className="text-sm text-gray-400 mt-1">Uploaded on: {formatDate(openSummaries.find((s) => s.id === view).upload_time)}</p>
                                </div>
                                <button onClick={exitSummary} className="text-gray-400 hover:text-gray-200">
                                    <X className="h-6 w-6" />
                                </button>
                            </div>
                            <div className="bg-gray-800 rounded-lg p-6">
                                <p className="text-gray-300">{openSummaries.find((s) => s.id === view).summary}</p>
                            </div>
                        </div>
                    )
                )}
            </div>
        </div>
    );
};

export default SolicitationDashboard;
