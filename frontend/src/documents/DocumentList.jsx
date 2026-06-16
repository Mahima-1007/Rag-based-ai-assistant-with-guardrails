import React from 'react';
import { FileText, File, Trash2, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

export default function DocumentList({ documents, loading, onRemove }) {
  if (loading) {
    return (
      <div className="flex justify-center p-8">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (!documents || documents.length === 0) {
    return (
      <div className="text-center p-8 border border-dashed rounded-xl border-slate-200 bg-slate-50">
        <FileText className="w-8 h-8 text-slate-400 mx-auto mb-2" />
        <p className="text-sm font-medium text-slate-600">No documents yet</p>
        <p className="text-xs text-slate-500 mt-1">Upload a document to start chatting</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
        <h3 className="text-sm font-semibold text-slate-800">Your Knowledge Base</h3>
        <span className="bg-blue-100 text-blue-700 text-xs font-medium px-2.5 py-0.5 rounded-full">
          {documents.length} File{documents.length !== 1 ? 's' : ''}
        </span>
      </div>
      <ul className="divide-y divide-slate-100 max-h-[400px] overflow-y-auto">
        {documents.map((doc) => (
          <li key={doc.id} className="p-4 hover:bg-slate-50 transition-colors flex items-center justify-between group">
            <div className="flex items-center space-x-3 overflow-hidden flex-1">
              <div className="p-2 bg-slate-100 rounded-lg flex-shrink-0">
                <File className="w-5 h-5 text-slate-500" />
              </div>
              <div className="truncate pr-4">
                <p className="text-sm font-medium text-slate-800 truncate" title={doc.filename}>{doc.filename}</p>
                <div className="flex items-center mt-1 space-x-3 text-xs text-slate-500">
                  <span className="uppercase">{doc.file_type}</span>
                  <span>•</span>
                  <span>{doc.file_size ? (doc.file_size / 1024 / 1024).toFixed(2) + ' MB' : 'Unknown size'}</span>
                  <span>•</span>
                  <span className="flex items-center">
                    {doc.status === 'ready' && <><CheckCircle2 className="w-3 h-3 text-emerald-500 mr-1" /> Ready</>}
                    {doc.status === 'processing' && <><Loader2 className="w-3 h-3 text-blue-500 animate-spin mr-1" /> Processing</>}
                    {doc.status === 'failed' && <><AlertCircle className="w-3 h-3 text-red-500 mr-1" /> Failed</>}
                  </span>
                </div>
              </div>
            </div>
            
            <button
              onClick={() => onRemove(doc.id)}
              className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg opacity-0 group-hover:opacity-100 transition-all focus:opacity-100"
              title="Delete Document"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
