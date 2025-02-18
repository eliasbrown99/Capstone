import React, { useState, useEffect } from 'react';
import { Upload, FileText, AlertCircle, CheckCircle, XCircle } from 'lucide-react';

const LoadingBar = () => {
    const [progress, setProgress] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setProgress(prev => {
                if (prev >= 90) return 90; // Stop at 90% until complete
                return prev + 2;
            });
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
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const handleFileChange = (event) => {
        const selectedFile = event.target.files[0];
        if (selectedFile) {
            setFile(selectedFile);
            setError(null);
            setResult(null);
        }
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!file) {
            setError('Please select a file to classify');
            return;
        }

        setLoading(true);
        setError(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('http://localhost:8000/classify/', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Classification failed');
            }

            const data = await response.json();
            setResult(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const getClassificationColor = (classification) => {
        switch (classification) {
            case 'good_fit':
                return 'text-green-400';
            case 'needs_partners':
                return 'text-yellow-400';
            case 'bad_fit':
                return 'text-red-400';
            default:
                return 'text-gray-400';
        }
    };

    const getClassificationIcon = (classification) => {
        switch (classification) {
            case 'good_fit':
                return <CheckCircle className="w-5 h-5 text-green-400" />;
            case 'needs_partners':
                return <AlertCircle className="w-5 h-5 text-yellow-400" />;
            case 'bad_fit':
                return <XCircle className="w-5 h-5 text-red-400" />;
            default:
                return null;
        }
    };

    return (
        <div className="min-h-screen bg-gray-900 text-gray-100">
            <div className="container mx-auto p-6 max-w-4xl">
                <div className="mb-8">
                    <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-500 text-transparent bg-clip-text">
                        Solicitation Classifier
                    </h1>
                    <p className="text-gray-400">Upload a solicitation document (PDF or Word) for classification</p>
                </div>

                <div className="mb-8">
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="border-2 border-dashed border-gray-700 rounded-lg p-8 text-center bg-gray-800/50 hover:bg-gray-800 transition-colors">
                            <input
                                type="file"
                                onChange={handleFileChange}
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
                                    {file ? file.name : 'Click to upload or drag and drop'}
                                </span>
                            </label>
                        </div>

                        {loading && <LoadingBar />}
                        <button
                            type="submit"
                            disabled={loading || !file}
                            className="w-full bg-blue-500 text-white py-3 px-4 rounded-lg hover:bg-blue-600 
                       disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed 
                       transition-colors font-medium"
                        >
                            {loading ? 'Analyzing...' : 'Classify Solicitation'}
                        </button>
                    </form>
                </div>

                {error && (
                    <div className="bg-red-900/50 border-l-4 border-red-500 p-4 mb-6 rounded-r-lg">
                        <div className="flex items-center">
                            <AlertCircle className="h-5 w-5 text-red-400 mr-2" />
                            <p className="text-red-400">{error}</p>
                        </div>
                    </div>
                )}

                {result && (
                    <div className="bg-gray-800 rounded-lg shadow-xl p-6 space-y-6">
                        <div className="flex items-center justify-between border-b border-gray-700 pb-4">
                            <div className="flex items-center space-x-2">
                                {getClassificationIcon(result.classification)}
                                <h2 className={`text-xl font-semibold ${getClassificationColor(result.classification)}`}>
                                    {result.classification.replace('_', ' ').toUpperCase()}
                                </h2>
                            </div>
                            <span className="text-gray-400">
                                Confidence: {(result.confidence * 100).toFixed(1)}%
                            </span>
                        </div>

                        <div className="space-y-6">
                            <div>
                                <h3 className="text-lg font-semibold mb-2 text-blue-400">Reasoning</h3>
                                <p className="text-gray-300">{result.reasoning}</p>
                            </div>

                            {result.keyword_matches && Object.keys(result.keyword_matches).length > 0 && (
                                <div>
                                    <h3 className="text-lg font-semibold mb-2 text-blue-400">Keyword Matches</h3>
                                    <div className="space-y-2">
                                        {Object.entries(result.keyword_matches).map(([category, matches]) => (
                                            <div key={category} className="bg-gray-700/50 p-4 rounded-lg">
                                                <h4 className="font-medium text-gray-200 mb-2">
                                                    {category.replace('_', ' ').toUpperCase()}
                                                </h4>
                                                <ul className="space-y-1">
                                                    {matches.map((match, index) => (
                                                        <li key={index} className="text-gray-400">
                                                            "...{match}..."
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {result.exclusion_flags && result.exclusion_flags.length > 0 && (
                                <div>
                                    <h3 className="text-lg font-semibold mb-2 text-blue-400">Exclusion Flags</h3>
                                    <ul className="list-disc list-inside space-y-1">
                                        {result.exclusion_flags.map((flag, index) => (
                                            <li key={index} className="text-red-400">
                                                {flag}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default SolicitationDashboard;