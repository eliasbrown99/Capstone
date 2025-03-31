import React, { useState, useEffect } from 'react';
// Example icons from 'lucide-react' for styling
import { Upload, AlertCircle } from 'lucide-react';

// A simple loading bar that increments up to ~90% while waiting.
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
            <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${progress}%` }}
            />
        </div>
    );
};

const SolicitationDashboard = () => {
    const [file, setFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [summaries, setSummaries] = useState([]);
    const [error, setError] = useState(null);

    // Handle file selection
    const handleFileChange = (event) => {
        const selectedFile = event.target.files[0];
        if (selectedFile) {
            setFile(selectedFile);
            setError(null);
            setSummaries([]);
        }
    };

    // Submit the file to the backend
    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!file) {
            setError('Please select a file to summarize');
            return;
        }

        setLoading(true);
        setError(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            // Updated to the new endpoint for summarization
            const response = await fetch('http://localhost:8000/summarize/', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Summarization failed');
            }

            const data = await response.json();
            // The backend returns something like { summaries: [ { heading: "", summary: "" }, ... ] }
            console.log('Response data:', data);

            setSummaries(data.summaries || []);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-900 text-gray-100">
            <div className="container mx-auto p-6 max-w-4xl">
                <div className="mb-8">
                    <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-500 text-transparent bg-clip-text">
                        Solicitation Summarizer
                    </h1>
                    <p className="text-gray-400">Upload a document (PDF/Word) to generate a section-based summary.</p>
                </div>

                {/* File upload & submission form */}
                <div className="mb-8">
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="border-2 border-dashed border-gray-700 rounded-lg p-8 text-center bg-gray-800/50 hover:bg-gray-800 transition-colors">
                            <input
                                type="file"
                                onChange={handleFileChange}
                                accept=".pdf,.doc,.docx,.md"
                                className="hidden"
                                id="file-upload"
                            />
                            <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center justify-center">
                                <Upload className="w-16 h-16 text-blue-400 mb-4" />
                                <span className="text-gray-400">
                                    {file ? file.name : 'Click to upload or drag and drop'}
                                </span>
                            </label>
                        </div>

                        {/* Loading bar appears while waiting for the server */}
                        {loading && <LoadingBar />}

                        <button
                            type="submit"
                            disabled={loading || !file}
                            className="w-full bg-blue-500 text-white py-3 px-4 rounded-lg hover:bg-blue-600 
                         disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed 
                         transition-colors font-medium"
                        >
                            {loading ? 'Summarizing...' : 'Summarize Document'}
                        </button>
                    </form>
                </div>

                {/* Error display */}
                {error && (
                    <div className="bg-red-900/50 border-l-4 border-red-500 p-4 mb-6 rounded-r-lg">
                        <div className="flex items-center">
                            <AlertCircle className="h-5 w-5 text-red-400 mr-2" />
                            <p className="text-red-400">{error}</p>
                        </div>
                    </div>
                )}

                {/* Summaries result */}
                {summaries.length > 0 && (
                    <div className="bg-gray-800 rounded-lg shadow-xl p-6 space-y-6">
                        <h2 className="text-xl font-semibold text-blue-400 mb-4">Document Summary</h2>
                        {summaries.map((sec, index) => {
                            // If there's no summary text, skip rendering
                            if (!sec.summary || !sec.summary.trim()) {
                                return null;
                            }
                            return (
                                <div key={index} className="mb-6">
                                    <h3 className="text-lg font-bold text-gray-200 mb-2">{sec.heading}</h3>
                                    <div className="pl-4">
                                        {/* Each bullet or line from the summary in <p> tags */}
                                        {sec.summary.split('\n').map((line, idx) => (
                                            <p key={idx} className="text-gray-300 mb-1">
                                                {line}
                                            </p>
                                        ))}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

export default SolicitationDashboard;
