import { ReviewResult } from '../types';
import { toSafeHtml } from '../utils/emailBody';

interface ReviewDisplayProps {
    review: ReviewResult;
}

const getScoreColor = (score: number) => {
    if (score >= 4) return 'text-green-600 bg-green-100';
    if (score >= 3) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
};

export const ReviewDisplay: React.FC<ReviewDisplayProps> = ({ review }) => (
    <div className="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-blue-900">AI Review</h4>
            <span className={`px-2 py-1 text-xs font-medium rounded-full ${getScoreColor(review.overall_score)}`}>
                Overall: {review.overall_score}/5
            </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-2">
            <div className={`px-2 py-1 text-xs rounded ${getScoreColor(review.relevance_score)}`}>
                Relevance: {review.relevance_score}/5
            </div>
            <div className={`px-2 py-1 text-xs rounded ${getScoreColor(review.completeness_score)}`}>
                Complete: {review.completeness_score}/5
            </div>
            <div className={`px-2 py-1 text-xs rounded ${getScoreColor(review.accuracy_score)}`}>
                Accuracy: {review.accuracy_score}/5
            </div>
            <div className={`px-2 py-1 text-xs rounded ${getScoreColor(review.next_steps_score)}`}>
                Next Steps: {review.next_steps_score}/5
            </div>
        </div>

        {review.red_flags.length > 0 && (
            <div className="mb-2">
                <div className="text-xs font-medium text-red-700 mb-1">⚠️ Red Flags:</div>
                <ul className="text-xs text-red-600">
                    {review.red_flags.map((flag, index) => (
                        <li key={index} className="ml-2">• {flag}</li>
                    ))}
                </ul>
            </div>
        )}

        <p className="text-xs text-blue-800">{review.summary}</p>
    </div>
);

interface RevisionComparisonProps {
    replyId: string;
    original: string;
    originalReview?: ReviewResult;
    revised?: string;
    revisedReview?: ReviewResult;
    selectedVersion: 'original' | 'revised';
    onSelectVersion: (version: 'original' | 'revised') => void;
}

export const RevisionComparison: React.FC<RevisionComparisonProps> = ({
    replyId,
    original,
    originalReview,
    revised,
    revisedReview,
    selectedVersion,
    onSelectVersion
}) => (
    <div className="mb-4">
        {revised && (
            <>
                {/* Version selector */}
                <div className="mb-3 flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                        <label className="flex items-center cursor-pointer">
                            <input
                                type="radio"
                                name={`version-${replyId}`}
                                value="original"
                                checked={selectedVersion === 'original'}
                                onChange={() => onSelectVersion('original')}
                                className="mr-2"
                            />
                            <span className="text-sm font-medium">
                                Original {originalReview && `(${originalReview.overall_score}/5)`}
                            </span>
                        </label>
                        <label className="flex items-center cursor-pointer">
                            <input
                                type="radio"
                                name={`version-${replyId}`}
                                value="revised"
                                checked={selectedVersion === 'revised'}
                                onChange={() => onSelectVersion('revised')}
                                className="mr-2"
                            />
                            <span className="text-sm font-medium">
                                Revised {revisedReview && `(${revisedReview.overall_score}/5)`}
                                {revisedReview && originalReview && revisedReview.overall_score > originalReview.overall_score && (
                                    <span className="ml-1 text-green-600">⬆️</span>
                                )}
                            </span>
                        </label>
                    </div>
                </div>

                {/* Side-by-side comparison */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    {/* Original */}
                    <div
                        className={`border rounded-lg p-3 cursor-pointer ${selectedVersion === 'original' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}
                        onClick={() => onSelectVersion('original')}
                    >
                        <h5 className="text-sm font-medium text-gray-700 mb-2">Original Response</h5>
                        <div
                            className="text-sm text-gray-900 mb-2 max-h-40 overflow-y-auto"
                            dangerouslySetInnerHTML={{ __html: toSafeHtml(original) }}
                        />
                        {originalReview && <ReviewDisplay review={originalReview} />}
                    </div>

                    {/* Revised */}
                    <div
                        className={`border rounded-lg p-3 cursor-pointer ${selectedVersion === 'revised' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}
                        onClick={() => onSelectVersion('revised')}
                    >
                        <h5 className="text-sm font-medium text-gray-700 mb-2">Revised Response</h5>
                        <div
                            className="text-sm text-gray-900 mb-2 max-h-40 overflow-y-auto"
                            dangerouslySetInnerHTML={{ __html: toSafeHtml(revised || '') }}
                        />
                        {revisedReview && <ReviewDisplay review={revisedReview} />}
                    </div>
                </div>
            </>
        )}
    </div>
);
