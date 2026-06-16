import { useState, useCallback } from 'react';
import toast from 'react-hot-toast';

export default function useStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamedText, setStreamedText] = useState('');
  const [metadata, setMetadata] = useState(null);

  const streamMessage = useCallback(async (sessionId, query, documentIds = null, onComplete = null) => {
    setIsStreaming(true);
    setStreamedText('');
    setMetadata(null);

    try {
      const token = localStorage.getItem('access_token');
      
      const response = await fetch('/api/chat/message', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          session_id: sessionId,
          query,
          document_ids: documentIds
        })
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Session expired. Please login again.');
        }
        throw new Error('Failed to send message');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;
      let buffer = '';

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || ''; // Keep the last partial line in buffer
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.substring(6));
                
                if (data.type === 'metadata') {
                  setMetadata(data);
                } else if (data.type === 'token') {
                  setStreamedText(prev => prev + data.text);
                } else if (data.type === 'regenerated') {
                  setStreamedText(data.text);
                } else if (data.type === 'error') {
                  toast.error(data.message || 'Error occurred');
                } else if (data.type === 'done') {
                  // Stream complete
                }
              } catch (e) {
                console.error('Error parsing SSE json', e);
              }
            }
          }
        }
      }
      
      // Cleanup buffer
      if (buffer && buffer.startsWith('data: ')) {
         try {
           const data = JSON.parse(buffer.substring(6));
           if (data.type === 'token') {
             setStreamedText(prev => prev + data.text);
           }
         } catch(e) {}
      }

    } catch (err) {
      toast.error(err.message || 'Connection error');
    } finally {
      setIsStreaming(false);
      if (onComplete) {
        onComplete();
      }
    }
  }, []);

  return { isStreaming, streamedText, setStreamedText, metadata, streamMessage };
}
