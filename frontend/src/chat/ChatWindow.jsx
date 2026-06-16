import React, { useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import { Loader2 } from 'lucide-react';

export default function ChatWindow({ messages, isStreaming, streamedText, metadata }) {
  const endOfMessagesRef = useRef(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamedText]);

  // Create a temporary message object for the streaming text
  const streamingMessage = isStreaming || streamedText ? {
    id: 'streaming',
    role: 'assistant',
    content: streamedText || (isStreaming ? '' : ''),
    confidence_level: metadata?.confidence_level,
    source_documents: { sources: metadata?.sources || [] },
    latency_ms: null,
    guardrail_triggered: false,
    created_at: new Date().toISOString()
  } : null;

  return (
    <div className="flex-1 overflow-y-auto px-4 py-8 bg-slate-50 scroll-smooth">
      <div className="max-w-4xl mx-auto flex flex-col justify-end min-h-full">
        {messages.length === 0 && !isStreaming && !streamedText && (
          <div className="flex-1 flex flex-col items-center justify-center text-center opacity-70">
            <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mb-4">
              <span className="text-2xl">👋</span>
            </div>
            <h2 className="text-xl font-bold text-slate-800 mb-2">How can I help you today?</h2>
            <p className="text-slate-500 max-w-md">
              Ask me anything about the documents in your knowledge base. I'll provide grounded answers based only on the uploaded context.
            </p>
          </div>
        )}
        
        {messages.map((msg, idx) => (
          <MessageBubble key={msg.id || idx} message={msg} />
        ))}
        
        {streamingMessage && (
          <div className="message-enter">
            <MessageBubble message={streamingMessage} />
            {isStreaming && !streamedText && (
               <div className="ml-16 -mt-4 mb-4 flex items-center text-xs text-blue-500">
                 <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> Retrieving context...
               </div>
            )}
          </div>
        )}
        <div ref={endOfMessagesRef} className="h-4" />
      </div>
    </div>
  );
}
