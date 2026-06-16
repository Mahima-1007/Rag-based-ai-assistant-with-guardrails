import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';

export default function InputBar({ onSend, disabled, isStreaming }) {
  const [input, setInput] = useState('');
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !disabled && !isStreaming) {
      onSend(input.trim());
      setInput('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="bg-white border-t border-slate-200 p-4 w-full relative z-10">
      <div className="max-w-4xl mx-auto relative flex items-end shadow-sm border border-slate-300 bg-white rounded-2xl overflow-hidden focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-transparent transition-all">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your documents..."
          disabled={disabled}
          className="flex-1 max-h-[200px] min-h-[56px] py-4 pl-5 pr-14 resize-none bg-transparent focus:outline-none text-slate-800 placeholder-slate-400"
          rows={1}
        />
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || disabled || isStreaming}
          className={`absolute right-2 bottom-2 p-2.5 rounded-xl flex items-center justify-center transition-colors ${
            input.trim() && !disabled && !isStreaming
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-slate-100 text-slate-400 cursor-not-allowed'
          }`}
        >
          {isStreaming ? (
             <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
             <Send className="w-5 h-5" />
          )}
        </button>
      </div>
      <div className="max-w-4xl mx-auto mt-2 text-center">
        <p className="text-[11px] text-slate-400">
          AI can make mistakes. Consider verifying important information from the source documents.
        </p>
      </div>
    </div>
  );
}
