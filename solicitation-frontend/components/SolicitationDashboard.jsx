// src/components/SolicitationDashboard.jsx
import React, { useState, useEffect } from 'react';
import {
    Upload,
    AlertCircle,
    Database,
    FileText,
    X,
    Trash,
    Search,
    AlertTriangle,
} from 'lucide-react';

/* ────────────────────────────────────────────────────────────────────────── */
/* 🔸 Helper components                                                      */
/* ────────────────────────────────────────────────────────────────────────── */

// animated bar while LLM + parsing work
const LoadingBar = () => {
    const [progress, setProgress] = useState(0);
    useEffect(() => {
        const id = setInterval(() => {
            setProgress((p) => (p >= 90 ? 90 : p + 2));
        }, 100);
        return () => clearInterval(id);
    }, []);
    return (
        <div className="w-full bg-gray-700 rounded-full h-2 mb-4 overflow-hidden">
            <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${progress}%` }}
            />
        </div>
    );
};

// shorten long filenames in the sidebar
const TruncatedText = ({ text, maxLength = 18 }) => {
    const truncated = text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
    return (
        <span className="truncate max-w-[140px] block" title={text}>
            {truncated}
        </span>
    );
};

// overwrite‑confirmation modal
const ConfirmationDialog = ({ isOpen, onConfirm, onCancel, filename }) => {
    if (!isOpen) return null;
    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
            <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full">
                <div className="flex items-start mb-4">
                    <AlertTriangle className="h-6 w-6 text-yellow-500 mr-3 shrink-0" />
                    <div>
                        <h3 className="text-lg font-medium text-gray-100">
                            Document Already Exists
                        </h3>
                        <p className="text-gray-400 mt-1">
                            A document named “{filename}” is already in the database. Replace it?
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

// **NEW** component: turns an array of {heading, summary} into JSX
const SectionList = ({ sections }) => {
    // handle legacy rows that stored a plain string
    if (!Array.isArray(sections)) {
        return (
            <pre className="whitespace-pre-wrap text-gray-300">
                {String(sections)}
            </pre>
        );
    }

    return (
        <div className="space-y-8">
            {sections.map((sec, idx) => (
                <div key={idx}>
                    <h3 className="text-lg font-semibold text-blue-300 mb-2">
                        {sec.heading}
                    </h3>
                    <pre className="whitespace-pre-wrap text-gray-300 leading-relaxed">
                        {sec.summary}
                    </pre>
                </div>
            ))}
        </div>
    );
};

/* ────────────────────────────────────────────────────────────────────────── */
/* 🔸 Main dashboard                                                         */
/* ────────────────────────────────────────────────────────────────────────── */

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

    /* ───── helpers ───── */
    const formatDate = (d) =>
        d ? new Date(d).toLocaleString() : 'Unknown date';

    /* ───── DB fetch ───── */
    const fetchSummaries = async (q = '') => {
        setIsSearching(!!q);
        try {
            const url = q
                ? `http://localhost:8000/summaries/?search=${encodeURIComponent(q)}`
                : 'http://localhost:8000/summaries/';
            const res = await fetch(url);
            if (!res.ok) throw new Error('Failed to fetch stored summaries');
            setSummaries(await res.json());
        } catch (e) {
            setError(e.message);
        } finally {
            setIsSearching(false);
        }
    };

    useEffect(() => {
        if (view === 'database') fetchSummaries();
    }, [view]);

    /* ───── upload flow ───── */
    const checkIfDocumentExists = async (filename) => {
        try {
            const res = await fetch(
                `http://localhost:8000/document-exists/${encodeURIComponent(filename)}`
            );
            if (!res.ok) throw new Error();
            return await res.json();
        } catch {
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
            const res = await fetch('http://localhost:8000/summarize/', {
                method: 'POST',
                body: formData,
            });
            if (!res.ok) throw new Error('Summarization failed');
            const data = await res.json();
            setSummaries(data.summaries || []);
            if (existingDocumentId && view === 'database') fetchSummaries();
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
            setExistingDocumentId(null);
        }
    };

    /* ───── JSX ───── */
    return (
        <div className="min-h-screen bg-gray-900 text-gray-100 flex">
            {/* ─── overwrite modal ─── */}
            <ConfirmationDialog
                isOpen={showConfirmation}
                onConfirm={proceedWithSummarization}
                onCancel={() => setShowConfirmation(false)}
                filename={file?.name || ''}
            />

            {/* ─── sidebar ─── */}
            <aside className="w-64 bg-gray-800 p-6 shrink-0">
                <h2 className="text-2xl font-bold text-blue-400 mb-6">Dashboard</h2>
                <button
                    onClick={() => setView('upload')}
                    className={`w-full flex items-center p-3 mb-4 rounded-lg transition ${view === 'upload' ? 'bg-blue-500' : 'bg-gray-700 hover:bg-gray-600'
                        }`}
                >
                    <Upload className="mr-2" /> Upload &amp; Summarize
                </button>
                <button
                    onClick={() => setView('database')}
                    className={`w-full flex items-center p-3 rounded-lg transition ${view === 'database'
                        ? 'bg-blue-500'
                        : 'bg-gray-700 hover:bg-gray-600'
                        }`}
                >
                    <Database className="mr-2" /> Summaries Database
                </button>

                {/* open tabs */}
                {openSummaries.map((s) => (
                    <div
                        key={s.id}
                        className={`w-full flex items-center justify-between p-3 mt-2 rounded-lg transition ${view === s.id ? 'bg-blue-500' : 'bg-gray-700 hover:bg-gray-600'
                            }`}
                        onClick={() => setView(s.id)}
                    >
                        <div className="flex flex-col">
                            <div className="flex items-center">
                                <FileText className="mr-2" />
                                <TruncatedText text={s.filename || s.id} />
                            </div>
                            <p className="text-xs text-gray-400 ml-6">
                                {formatDate(s.upload_time)}
                            </p>
                        </div>
                        <div className="flex items-center space-x-2">
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setOpenSummaries((p) => p.filter((x) => x.id !== s.id));
                                    if (view === s.id) setView('database');
                                }}
                                className="text-gray-400 hover:text-white"
                            >
                                <X className="h-4 w-4" />
                            </button>
                            <button
                                onClick={async (e) => {
                                    e.stopPropagation();
                                    const res = await fetch(
                                        `http://localhost:8000/summaries/${s.id}`,
                                        { method: 'DELETE' }
                                    );
                                    if (res.ok) {
                                        setSummaries((p) => p.filter((x) => x.id !== s.id));
                                        setOpenSummaries((p) => p.filter((x) => x.id !== s.id));
                                        if (view === s.id) setView('database');
                                    }
                                }}
                                className="text-red-500 hover:text-red-400"
                            >
                                <Trash className="h-4 w-4" />
                            </button>
                        </div>
                    </div>
                ))}
            </aside>

            {/* ─── main panel ─── */}
            <div className="flex-1 p-6">
                {/* ───────────────── Upload page ───────────────── */}
                {view === 'upload' && (
                    <>
                        <h1 className="text-4xl font-bold text-blue-400 mb-4">
                            Solicitation Summarizer
                        </h1>
                        <p className="text-gray-400 mb-6">
                            Upload a document (PDF/Word) to generate a section‑based summary.
                        </p>
                        <form
                            onSubmit={async (e) => {
                                e.preventDefault();
                                if (!file) return setError('Please select a file');
                                const { exists, id } = await checkIfDocumentExists(file.name);
                                if (exists) {
                                    setShowConfirmation(true);
                                    setExistingDocumentId(id);
                                } else {
                                    proceedWithSummarization();
                                }
                            }}
                            className="space-y-4"
                        >
                            <div className="border-2 border-dashed border-gray-700 rounded-lg p-8 text-center bg-gray-800/50 hover:bg-gray-800 transition">
                                <input
                                    type="file"
                                    onChange={(e) => {
                                        const f = e.target.files[0];
                                        if (f) setFile(f);
                                    }}
                                    accept=".pdf,.doc,.docx"
                                    className="hidden"
                                    id="file-upload"
                                />
                                <label
                                    htmlFor="file-upload"
                                    className="cursor-pointer flex flex-col items-center justify-center"
                                >
                                    <Upload className="w-16 h-16 text-blue-400 mb-4" />
                                    <span className="text-gray-400">
                                        {file ? file.name : 'Click to upload or drag & drop'}
                                    </span>
                                </label>
                            </div>

                            {loading && <LoadingBar />}

                            <button
                                type="submit"
                                disabled={loading || !file}
                                className="w-full bg-blue-500 text-white py-3 px-4 rounded-lg hover:bg-blue-600 disabled:bg-gray-700 transition font-medium"
                            >
                                {loading ? 'Summarizing…' : 'Summarize Document'}
                            </button>
                        </form>
                        {error && (
                            <div className="bg-red-900/50 border-l-4 border-red-500 p-4 mt-4 rounded-r-lg flex items-center">
                                <AlertCircle className="h-5 w-5 text-red-400 mr-2" />
                                {error}
                            </div>
                        )}
                    </>
                )}

                {/* ───────────────── Database page ───────────────── */}
                {view === 'database' && (
                    <>
                        <h1 className="text-4xl font-bold text-blue-400 mb-4">
                            Summaries Database
                        </h1>

                        {/* search bar */}
                        <form
                            onSubmit={(e) => {
                                e.preventDefault();
                                fetchSummaries(searchQuery);
                            }}
                            className="mb-6"
                        >
                            <div className="relative">
                                <Search className="absolute left-3 top-2.5 w-5 h-5 text-gray-400 pointer-events-none" />
                                <input
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    placeholder="Search summaries…"
                                    className="bg-gray-800 border border-gray-700 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full pl-10 p-2.5 text-gray-100"
                                />
                                {searchQuery && (
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setSearchQuery('');
                                            fetchSummaries();
                                        }}
                                        className="absolute right-3 top-2.5 text-gray-400 hover:text-white"
                                    >
                                        <X className="w-5 h-5" />
                                    </button>
                                )}
                            </div>
                        </form>

                        {isSearching ? (
                            <div className="flex justify-center py-10">
                                <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-blue-500" />
                            </div>
                        ) : summaries.length ? (
                            <div className="bg-gray-800 rounded-lg shadow-xl p-6 space-y-6">
                                {summaries.map((s) => (
                                    <div
                                        key={s.id}
                                        className="p-4 border border-gray-700 rounded-lg hover:border-gray-600 transition"
                                    >
                                        <div className="flex justify-between items-center mb-2">
                                            <h3
                                                className="text-lg font-bold text-gray-200 cursor-pointer hover:text-blue-400"
                                                onClick={() => {
                                                    if (!openSummaries.find((x) => x.id === s.id))
                                                        setOpenSummaries((p) => [...p, s]);
                                                    setView(s.id);
                                                }}
                                            >
                                                {s.filename || `Document #${s.id}`}
                                            </h3>
                                            <button
                                                onClick={() =>
                                                    fetch(`http://localhost:8000/summaries/${s.id}`, {
                                                        method: 'DELETE',
                                                    }).then((res) => {
                                                        if (res.ok) {
                                                            setSummaries((p) => p.filter((x) => x.id !== s.id));
                                                            setOpenSummaries((p) =>
                                                                p.filter((x) => x.id !== s.id)
                                                            );
                                                        }
                                                    })
                                                }
                                                className="text-red-500 hover:text-red-400"
                                            >
                                                <Trash className="h-4 w-4" />
                                            </button>
                                        </div>
                                        <p className="text-sm text-gray-400">
                                            Uploaded on: {formatDate(s.upload_time)}
                                        </p>
                                        {/* teaser created from headings */}
                                        <p
                                            className="text-gray-300 mt-2 line-clamp-2 cursor-pointer hover:text-blue-100"
                                            onClick={() => {
                                                if (!openSummaries.find((x) => x.id === s.id))
                                                    setOpenSummaries((p) => [...p, s]);
                                                setView(s.id);
                                            }}
                                        >
                                            {Array.isArray(s.summary)
                                                ? s.summary
                                                    .map((sec) => sec.heading)
                                                    .join(' • ')
                                                    .slice(0, 120) + '…'
                                                : String(s.summary).slice(0, 120) + '…'}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-10 text-gray-400">
                                {searchQuery
                                    ? `No results for “${searchQuery}”`
                                    : 'No stored summaries yet.'}
                            </div>
                        )}
                    </>
                )}

                {/* ───────────────── Single‑summary view (tab) ───────────────── */}
                {view !== 'upload' &&
                    view !== 'database' &&
                    openSummaries.find((x) => x.id === view) && (
                        <>
                            {(() => {
                                const s = openSummaries.find((x) => x.id === view);
                                return (
                                    <>
                                        <div className="flex justify-between items-center mb-6">
                                            <div>
                                                <h1 className="text-3xl font-bold text-blue-400">
                                                    {s.filename || `Document #${view}`}
                                                </h1>
                                                <p className="text-sm text-gray-400 mt-1">
                                                    Uploaded on: {formatDate(s.upload_time)}
                                                </p>
                                            </div>
                                            <button
                                                onClick={() => setView('database')}
                                                className="text-gray-400 hover:text-gray-200"
                                            >
                                                <X className="h-6 w-6" />
                                            </button>
                                        </div>
                                        <div className="bg-gray-800 rounded-lg p-6">
                                            <SectionList sections={s.summary} />
                                        </div>
                                    </>
                                );
                            })()}
                        </>
                    )}
            </div>
        </div>
    );
};

export default SolicitationDashboard;
