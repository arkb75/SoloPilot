import React, { useMemo, useState } from 'react';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css';

import { htmlToText, normalizeToHtml, toSafeHtml } from '../utils/emailBody';

interface ReplyEditorProps {
  initialContent: string;
  onSave: (content: string) => void;
  onCancel: () => void;
}

const ReplyEditor: React.FC<ReplyEditorProps> = ({ initialContent, onSave, onCancel }) => {
  const [content, setContent] = useState(() => normalizeToHtml(initialContent));
  const [showPreview, setShowPreview] = useState(false);

  const plainText = htmlToText(content);
  const wordCount = plainText.trim().split(/\s+/).filter(Boolean).length;
  const charCount = plainText.length;

  const editorModules = useMemo(() => ({
    toolbar: [
      ['bold', 'italic', 'underline', 'strike'],
      [{ list: 'ordered' }, { list: 'bullet' }],
      ['link'],
      ['clean'],
    ],
  }), []);

  const editorFormats = [
    'bold',
    'italic',
    'underline',
    'strike',
    'list',
    'bullet',
    'link',
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex space-x-4">
          <button
            onClick={() => setShowPreview(false)}
            className={`text-sm font-medium ${!showPreview ? 'text-indigo-600' : 'text-gray-500'}`}
          >
            Edit
          </button>
          <button
            onClick={() => setShowPreview(true)}
            className={`text-sm font-medium ${showPreview ? 'text-indigo-600' : 'text-gray-500'}`}
          >
            Preview
          </button>
        </div>
        <div className="text-sm text-gray-500">
          {wordCount} words • {charCount} characters
        </div>
      </div>

      {showPreview ? (
        <div
          className="p-4 bg-gray-50 rounded-lg"
          dangerouslySetInnerHTML={{ __html: toSafeHtml(content) }}
        />
      ) : (
        <ReactQuill
          value={content}
          onChange={setContent}
          modules={editorModules}
          formats={editorFormats}
          className="bg-white"
          style={{ height: '16rem' }}
          placeholder="Edit the reply..."
        />
      )}

      <div className="flex justify-end space-x-2">
        <button
          onClick={onCancel}
          className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          Cancel
        </button>
        <button
          onClick={() => onSave(content)}
          className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          Save & Approve
        </button>
      </div>
    </div>
  );
};

export default ReplyEditor;
