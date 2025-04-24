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

/* ───────────────────────── helpers / utils ───────────────────────── */
const formatDate = (iso) =>
    new Date(iso).toLocaleString('en-US', { timeZone: 'America/New_York' });

const coerceId = (v) => Number(v); // ensures all ids are numbers

const LoadingBar = ({ phase }) => {
    const targets = { uploading: 10, parsing: 40, identifying: 60, summarizing: 80, storing: 100 };
    const [pct, setPct] = useState(0);
    useEffect(() => {
        if (!phase) return;
        const id = setInterval(() => {
            setPct((p) => (p < targets[phase] ? p + 2 : p));
        }, 60);
        return () => clearInterval(id);
    }, [phase]);
    return (
        <div className="w-full bg-gray-700 rounded-full h-2 mb-4 overflow-hidden">
            <div className="bg-blue-500 h-2 rounded-full transition-all duration-300 ease-out" style={{ width: `${pct}%` }} />
        </div>
    );
};

const PhaseMessage = ({ phase }) => {
    const map = {
        uploading: 'Uploading file…',
        parsing: 'Parsing PDF → Markdown…',
        identifying: 'Identifying relevant sections…',
        summarizing: 'Summarizing sections…',
        storing: 'Saving to database…',
    };
    return phase ? <p className="text-sm text-gray-400 mt-2">{map[phase]}</p> : null;
};

const Toast = ({ msg, onClose }) => {
    useEffect(() => {
        const id = setTimeout(onClose, 4000);
        return () => clearTimeout(id);
    }, [onClose]);
    return (
        <div className="fixed bottom-6 right-6 bg-gray-800 text-gray-100 px-4 py-3 rounded-lg shadow-lg flex items-center">
            {msg}
            <button onClick={onClose} className="ml-3 text-blue-400">✕</button>
        </div>
    );
};

const TruncatedText = ({ text, maxLength = 18 }) => {
    const truncated = text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
    return <span className="truncate max-w-[140px] block" title={text}>{truncated}</span>;
};

const SectionList = ({ sections }) => {
    if (!Array.isArray(sections))
        return <pre className="whitespace-pre-wrap text-gray-300">{String(sections)}</pre>;
    return (
        <div className="space-y-8">
            {sections.map((sec, i) => (
                <div key={i}>
                    <h3 className="text-lg font-semibold text-blue-300 mb-2">{sec.heading}</h3>
                    <pre className="whitespace-pre-wrap text-gray-300 leading-relaxed">{sec.summary}</pre>
                </div>
            ))}
        </div>
    );
};

const ConfirmationDialog = ({ isOpen, title, message, onConfirm, onCancel }) => {
    if (!isOpen) return null;
    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
            <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full">
                <div className="flex items-start mb-4">
                    <AlertTriangle className="h-6 w-6 text-yellow-500 mr-3 shrink-0" />
                    <div>
                        <h3 className="text-lg font-medium text-gray-100">{title}</h3>
                        <p className="text-gray-400 mt-1">{message}</p>
                    </div>
                </div>
                <div className="flex justify-end space-x-3">
                    <button onClick={onCancel} className="px-4 py-2 text-gray-300 bg-gray-700 rounded-lg hover:bg-gray-600">
                        Cancel
                    </button>
                    <button onClick={onConfirm} className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">
                        Confirm
                    </button>
                </div>
            </div>
        </div>
    );
};

/* ─────────────────────────── main dashboard ─────────────────────────── */
const SolicitationDashboard = () => {
    const [file, setFile] = useState(null);
    const [phase, setPhase] = useState('');
    const [summaries, setSummaries] = useState([]);
    const [openSummaries, setOpenSummaries] = useState([]);
    const [view, setView] = useState('upload');
    const [error, setError] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [isSearching, setIsSearching] = useState(false);
    const [toast, setToast] = useState(null);
    const [overwriteInfo, setOverwriteInfo] = useState(null);
    const [deleteTarget, setDeleteTarget] = useState(null);

    /* api helpers */
    const fetchSummaries = async (q = '') => {
        setIsSearching(!!q);
        try {
            const url = q
                ? `http://localhost:8000/summaries/?search=${encodeURIComponent(q)}`
                : 'http://localhost:8000/summaries/';
            const res = await fetch(url);
            if (!res.ok) throw new Error('Failed to fetch summaries');
            const data = await res.json();
            setSummaries(data.map((s) => ({ ...s, id: coerceId(s.id) })));
        } catch (e) {
            setError(e.message);
        } finally {
            setIsSearching(false);
        }
    };

    useEffect(() => {
        if (view === 'database') fetchSummaries();
    }, [view]);

    const checkIfDocumentExists = async (filename) => {
        try {
            const res = await fetch(`http://localhost:8000/document-exists/${encodeURIComponent(filename)}`);
            if (!res.ok) return { exists: false };
            return await res.json();
        } catch {
            return { exists: false };
        }
    };

    /* summarise with SSE */
    const proceedWithSummarization = async () => {
        setError(null);
        setPhase('uploading');

        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch('http://localhost:8000/summarize-stream/', { method: 'POST', body: formData });
        if (!res.ok) {
            setError('Summarization failed');
            setPhase('');
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            buffer.split('\n\n').forEach((chunk) => {
                if (!chunk.startsWith('data:')) return;
                const payload = chunk.replace('data:', '').trim();

                if (payload === 'PARSING') setPhase('parsing');
                else if (payload.startsWith('IDENTIFYING')) setPhase('identifying');
                else if (payload.startsWith('SUMMARIZING')) setPhase('summarizing');
                else if (payload.startsWith('STORING')) setPhase('storing');
                else if (payload === 'COMPLETE') setPhase('');
                else if (payload.startsWith('{')) {
                    const raw = JSON.parse(payload);
                    const saved = { ...raw, id: coerceId(raw.id) };
                    setSummaries([saved]);
                    setOpenSummaries((p) => [...p, saved]);
                    setView(saved.id);
                    setToast('✅ Document summarized and saved!');
                }
            });
        }
    };

    /* JSX */
    return (
        <div className="min-h-screen bg-gray-900 text-gray-100 flex">
            {toast && <Toast msg={toast} onClose={() => setToast(null)} />}

            {/* overwrite + delete modals */}
            <ConfirmationDialog
                isOpen={!!overwriteInfo}
                title="Document Already Exists"
                message={`A document named “${overwriteInfo?.filename}” is already in the database. Replace it?`}
                onCancel={() => setOverwriteInfo(null)}
                onConfirm={() => {
                    setOverwriteInfo(null);
                    proceedWithSummarization();
                }}
            />
            <ConfirmationDialog
                isOpen={!!deleteTarget}
                title="Delete Summary"
                message={`Are you sure you want to permanently delete “${deleteTarget?.filename}”?`}
                onCancel={() => setDeleteTarget(null)}
                onConfirm={async () => {
                    await fetch(`http://localhost:8000/summaries/${deleteTarget.id}`, { method: 'DELETE' });
                    setSummaries((p) => p.filter((x) => x.id !== deleteTarget.id));
                    setOpenSummaries((p) => p.filter((x) => x.id !== deleteTarget.id));
                    if (view === deleteTarget.id) setView('database');
                    setDeleteTarget(null);
                }}
            />

            {/* sidebar */}
            <aside className="w-64 bg-gray-800 p-6 shrink-0">
                <h2 className="text-2xl font-bold text-blue-400 mb-6">Dashboard</h2>

                {['upload', 'database'].map((v) => (
                    <button
                        key={v}
                        onClick={() => setView(v)}
                        className={`w-full flex items-center p-3 mb-4 rounded-lg transition ${view === v ? 'bg-blue-500' : 'bg-gray-700 hover:bg-gray-600'}`}
                    >
                        {v === 'upload' ? <Upload className="mr-2" /> : <Database className="mr-2" />}
                        {v === 'upload' ? 'Upload & Summarize' : 'Summaries Database'}
                    </button>
                ))}

                {openSummaries.map((s) => (
                    <div
                        key={s.id}
                        className={`w-full flex items-center justify-between p-3 mt-2 rounded-lg transition ${view === s.id ? 'bg-blue-500' : 'bg-gray-700 hover:bg-gray-600'}`}
                        onClick={() => setView(s.id)}
                    >
                        <div className="flex flex-col">
                            <div className="flex items-center">
                                <FileText className="mr-2" />
                                <TruncatedText text={s.filename || s.id} />
                            </div>
                            <p className="text-xs text-gray-400 ml-6">{formatDate(s.upload_time)}</p>
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
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setDeleteTarget(s);
                                }}
                                className="text-red-500 hover:text-red-400"
                            >
                                <Trash className="h-4 w-4" />
                            </button>
                        </div>
                    </div>
                ))}
            </aside>

            {/* main panel */}
            <div className="flex-1 p-6">
                {/* upload page */}
                {view === 'upload' && (
                    <>
                        <h1 className="text-4xl font-bold text-blue-400 mb-4">Solicitation Summarizer</h1>
                        <p className="text-gray-400 mb-6">Upload a PDF or Word document to generate a section-based summary.</p>

                        <form
                            onSubmit={async (e) => {
                                e.preventDefault();
                                if (!file) return setError('Please select a file');
                                const res = await checkIfDocumentExists(file.name);
                                if (res.exists) setOverwriteInfo({ filename: file.name });
                                else proceedWithSummarization();
                            }}
                            className="space-y-4"
                        >
                            <div className="border-2 border-dashed border-gray-700 rounded-lg p-8 text-center bg-gray-800/50 hover:bg-gray-800 transition">
                                <input type="file" id="file-upload" accept=".pdf,.doc,.docx" onChange={(e) => setFile(e.target.files[0])} className="hidden" />
                                <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center">
                                    <Upload className="w-16 h-16 text-blue-400 mb-4" />
                                    <span className="text-gray-400">{file ? file.name : 'Click to upload or drag & drop'}</span>
                                </label>
                            </div>

                            {phase && (
                                <>
                                    <LoadingBar phase={phase} />
                                    <PhaseMessage phase={phase} />
                                </>
                            )}

                            <button type="submit" disabled={!file || !!phase} className="w-full bg-blue-500 text-white py-3 px-4 rounded-lg hover:bg-blue-600 disabled:bg-gray-700 transition font-medium">
                                {phase ? 'Working…' : 'Summarize Document'}
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

                {/* database page */}
                {view === 'database' && (
                    <>
                        <h1 className="text-4xl font-bold text-blue-400 mb-4">Summaries Database</h1>

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
                                    <div key={s.id} className="p-4 border border-gray-700 rounded-lg hover:border-gray-600 transition">
                                        <div className="flex justify-between items-center mb-2">
                                            <h3
                                                className="text-lg font-bold text-gray-200 cursor-pointer hover:text-blue-400"
                                                onClick={() => {
                                                    if (!openSummaries.find((x) => x.id === s.id))
                                                        setOpenSummaries((p) => [...p, s]);
                                                    setView(s.id);
                                                }}
                                            >
                                                {s.filename || `Document #${s.id}`}
                                            </h3>
                                            <button onClick={() => setDeleteTarget(s)} className="text-red-500 hover:text-red-400">
                                                <Trash className="h-4 w-4" />
                                            </button>
                                        </div>
                                        <p className="text-sm text-gray-400">Uploaded on: {formatDate(s.upload_time)}</p>
                                        <p
                                            className="text-gray-300 mt-2 line-clamp-2 cursor-pointer hover:text-blue-100"
                                            onClick={() => {
                                                if (!openSummaries.find((x) => x.id === s.id))
                                                    setOpenSummaries((p) => [...p, s]);
                                                setView(s.id);
                                            }}
                                        >
                                            {Array.isArray(s.summary)
                                                ? s.summary.map((sec) => sec.heading).join(' • ').slice(0, 120) + '…'
                                                : String(s.summary).slice(0, 120) + '…'}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-10 text-gray-400">
                                {searchQuery ? `No results for “${searchQuery}”` : 'No stored summaries yet.'}
                            </div>
                        )}
                    </>
                )}

                {/* single summary tab */}
                {view !== 'upload' && view !== 'database' && (() => {
                    const s = openSummaries.find((x) => x.id === view);
                    if (!s) return null;
                    return (
                        <>
                            <div className="flex justify-between items-center mb-6">
                                <div>
                                    <h1 className="text-3xl font-bold text-blue-400">{s.filename || `Document #${s.id}`}</h1>
                                    <p className="text-sm text-gray-400 mt-1">Uploaded on: {formatDate(s.upload_time)}</p>
                                </div>
                                <button onClick={() => setView('database')} className="text-gray-400 hover:text-gray-200">
                                    <X className="h-6 w-6" />
                                </button>
                            </div>
                            <div className="bg-gray-800 rounded-lg p-6">
                                <SectionList sections={s.summary} />
                            </div>
                        </>
                    );
                })()}
            </div>
        </div>
    );
};

export default SolicitationDashboard;