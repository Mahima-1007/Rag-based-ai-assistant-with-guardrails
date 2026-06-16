import React, { useState, useRef } from 'react';
import { UploadCloud, File, CheckCircle2, AlertCircle, X, Loader2 } from 'lucide-react';
import { uploadDocument, getDocumentStatus } from './documentService';
import toast from 'react-hot-toast';

export default function DocumentUpload({ onUploadComplete }) {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState(null); // processing, ready, failed
  const inputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile) => {
    const validTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain'
    ];
    
    if (!validTypes.includes(selectedFile.type) && !selectedFile.name.match(/\.(pdf|docx|txt)$/i)) {
      toast.error('Only PDF, DOCX, and TXT files are supported');
      return;
    }
    
    if (selectedFile.size > 50 * 1024 * 1024) {
      toast.error('File size must be under 50MB');
      return;
    }

    setFile(selectedFile);
    setStatus(null);
    setProgress(0);
  };

  const pollStatus = async (documentId) => {
    const checkInterval = setInterval(async () => {
      try {
        const docInfo = await getDocumentStatus(documentId);
        setStatus(docInfo.status);
        
        if (docInfo.status === 'ready') {
          clearInterval(checkInterval);
          toast.success('Document processed successfully!');
          onUploadComplete();
          resetUpload();
        } else if (docInfo.status === 'failed') {
          clearInterval(checkInterval);
          toast.error('Failed to process document.');
        }
      } catch (err) {
        clearInterval(checkInterval);
      }
    }, 2000);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setStatus('uploading');

    try {
      const result = await uploadDocument(file, (pct) => setProgress(pct));
      setStatus('processing');
      pollStatus(result.document_id);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed');
      setStatus('failed');
      setUploading(false);
    }
  };

  const resetUpload = () => {
    setFile(null);
    setUploading(false);
    setProgress(0);
    setStatus(null);
  };

  return (
    <div className="w-full bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="p-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">Add Document</h3>
        
        {!file ? (
          <div
            className={`relative border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center transition-colors cursor-pointer ${
              dragActive ? 'border-blue-500 bg-blue-50' : 'border-slate-300 hover:border-blue-400 hover:bg-slate-50'
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              className="hidden"
              accept=".pdf,.docx,.txt"
              onChange={handleChange}
            />
            <div className="p-3 bg-blue-100 text-blue-600 rounded-full mb-3">
              <UploadCloud className="w-6 h-6" />
            </div>
            <p className="text-sm font-medium text-slate-700">Click to upload or drag and drop</p>
            <p className="text-xs text-slate-500 mt-1">PDF, DOCX, or TXT (max. 50MB)</p>
          </div>
        ) : (
          <div className="border rounded-xl p-4 border-slate-200 bg-slate-50">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-3 overflow-hidden">
                <div className="p-2 bg-white rounded-lg shadow-sm">
                  <File className="w-5 h-5 text-blue-500" />
                </div>
                <div className="truncate">
                  <p className="text-sm font-medium text-slate-700 truncate">{file.name}</p>
                  <p className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
              </div>
              {!uploading && status !== 'processing' && (
                <button onClick={resetUpload} className="p-1 hover:bg-slate-200 rounded text-slate-500 transition-colors">
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {status === 'uploading' && (
              <div className="w-full bg-slate-200 rounded-full h-2 mt-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            )}

            {status === 'processing' && (
              <div className="flex items-center text-sm text-blue-600 font-medium mt-2">
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Processing document embeddings...
              </div>
            )}

            {status === 'failed' && (
              <div className="flex items-center text-sm text-red-600 font-medium mt-2">
                <AlertCircle className="w-4 h-4 mr-2" /> Processing failed
              </div>
            )}

            {!uploading && !status && (
              <button
                onClick={handleUpload}
                className="mt-3 w-full flex justify-center items-center py-2 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition-colors"
              >
                Upload File
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
