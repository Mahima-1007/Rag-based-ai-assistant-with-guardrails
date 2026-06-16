import React from 'react';
import { User, BrainCircuit, CheckCircle2, AlertCircle, FileText } from 'lucide-react';

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user';

  const formatContent = (text) => {
    // Simple line break parsing
    return text.split('\n').map((line, i) => (
      <React.Fragment key={i}>
        {line}
        {i !== text.split('\n').length - 1 && <br />}
      </React.Fragment>
    ));
  };

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mb-6`}>
      <div className={`flex max-w-[85%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        <div className={`flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-full ${isUser ? 'ml-4 bg-slate-200 text-slate-600' : 'mr-4 bg-blue-100 text-blue-600'}`}>
          {isUser ? <User className="w-5 h-5" /> : <BrainCircuit className="w-5 h-5" />}
        </div>
        
        <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
          <div
            className={`px-5 py-4 rounded-2xl shadow-sm border ${
              isUser
                ? 'bg-blue-600 text-white rounded-tr-none border-blue-700'
                : 'bg-white text-slate-800 rounded-tl-none border-slate-200'
            }`}
          >
            <div className="text-[15px] leading-relaxed">
              {formatContent(message.content)}
            </div>
            
            {/* Metadata Badges for Assistant */}
            {!isUser && message.confidence_level && (
              <div className="mt-4 pt-3 border-t border-slate-100 flex flex-wrap items-center gap-2">
                <span className={`inline-flex items-center px-2 py-1 rounded text-[11px] font-semibold tracking-wide uppercase ${
                  message.confidence_level === 'HIGH' ? 'bg-emerald-100 text-emerald-700' :
                  message.confidence_level === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                  'bg-rose-100 text-rose-700'
                }`}>
                  {message.confidence_level === 'HIGH' && <CheckCircle2 className="w-3 h-3 mr-1" />}
                  {message.confidence_level !== 'HIGH' && <AlertCircle className="w-3 h-3 mr-1" />}
                  {message.confidence_level} CONFIDENCE
                </span>
                
                {message.latency_ms && (
                  <span className="text-[11px] text-slate-400 font-medium bg-slate-50 px-2 py-1 rounded">
                    {message.latency_ms}ms
                  </span>
                )}
              </div>
            )}
            
            {/* Sources for Assistant */}
            {!isUser && message.source_documents?.sources?.length > 0 && (
              <div className="mt-2 space-y-1">
                {message.source_documents.sources.map((src, i) => (
                  <div key={i} className="flex items-center text-[11px] text-slate-500 bg-slate-50 px-2 py-1.5 rounded border border-slate-100 w-fit">
                    <FileText className="w-3 h-3 mr-1.5 text-blue-500" />
                    <span className="truncate max-w-[200px]" title={src.filename}>{src.filename}</span>
                    <span className="ml-2 text-slate-400">({src.reranker_score.toFixed(2)})</span>
                  </div>
                ))}
              </div>
            )}
            
            {/* Guardrail flag */}
            {!isUser && message.guardrail_triggered && (
              <div className="mt-2 flex items-center text-[11px] text-amber-600 bg-amber-50 px-2 py-1 rounded w-fit">
                <AlertCircle className="w-3 h-3 mr-1" />
                Safety guardrail triggered
              </div>
            )}
          </div>
          
          <span className="text-[11px] text-slate-400 mt-1 mx-1">
            {new Date(message.created_at || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>
    </div>
  );
}
