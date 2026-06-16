import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../auth/AuthContext';
import { createSession, getHistory, listSessions } from './chatService';
import useStream from '../hooks/useStream';
import ChatWindow from './ChatWindow';
import InputBar from './InputBar';
import DocumentUpload from '../documents/DocumentUpload';
import DocumentList from '../documents/DocumentList';
import useDocuments from '../hooks/useDocuments';
import { MessageSquare, PlusCircle, BrainCircuit, LogOut, FileText, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';

export default function ChatPage() {
  const { user, logout } = useContext(AuthContext);
  const { documents, loading: docsLoading, loadDocs, removeDoc } = useDocuments();
  const { isStreaming, streamedText, setStreamedText, metadata, streamMessage } = useStream();
  
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const sess = await listSessions();
      setSessions(sess);
      if (sess.length > 0 && !currentSessionId) {
        handleSelectSession(sess[0].id);
      } else if (sess.length === 0) {
        handleNewChat();
      }
    } catch (e) {
      toast.error('Failed to load chat sessions');
    }
  };

  const handleSelectSession = async (id) => {
    setCurrentSessionId(id);
    setLoadingHistory(true);
    try {
      const hist = await getHistory(id);
      setMessages(hist);
    } catch (e) {
      toast.error('Failed to load chat history');
      setMessages([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleNewChat = async () => {
    try {
      const newSession = await createSession('New Chat');
      setSessions(prev => [newSession, ...prev]);
      setCurrentSessionId(newSession.id);
      setMessages([]);
    } catch (e) {
      toast.error('Failed to create new chat');
    }
  };

  const handleSend = async (query) => {
    if (!currentSessionId) {
       await handleNewChat();
    }
    
    // Optimistic UI update for user message
    const userMsg = {
      id: Date.now().toString(),
      role: 'user',
      content: query,
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    
    await streamMessage(currentSessionId, query, null, async () => {
      // Reload history to get the saved assistant message with all DB fields
      if (currentSessionId) {
         try {
           const hist = await getHistory(currentSessionId);
           setMessages(hist);
           setStreamedText('');
         } catch(e) {}
      }
    });
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Sidebar */}
      <div className="w-80 bg-white border-r border-slate-200 flex flex-col h-full flex-shrink-0 z-20 shadow-[4px_0_24px_rgba(0,0,0,0.02)]">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-600 rounded-xl text-white shadow-sm shadow-blue-200">
              <BrainCircuit className="w-5 h-5" />
            </div>
            <div>
              <h1 className="font-bold text-slate-800 tracking-tight">RAG Assistant</h1>
              <p className="text-[10px] uppercase font-bold tracking-wider text-blue-600 mt-0.5">Enterprise Edition</p>
            </div>
          </div>
        </div>

        {/* User Info */}
        <div className="px-5 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
          <div className="truncate">
            <p className="text-sm font-semibold text-slate-800">{user?.username}</p>
            <p className="text-xs text-slate-500 truncate">{user?.email}</p>
          </div>
          <button onClick={logout} className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors" title="Logout">
            <LogOut className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
          {/* Documents Section */}
          <div className="space-y-3">
            <div className="flex items-center text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 px-1">
              <FileText className="w-3.5 h-3.5 mr-1.5" /> Knowledge Base
            </div>
            <DocumentUpload onUploadComplete={loadDocs} />
            <DocumentList documents={documents} loading={docsLoading} onRemove={removeDoc} />
          </div>

          <hr className="border-slate-100" />

          {/* Chat Sessions */}
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 px-1">
              <div className="flex items-center">
                <MessageSquare className="w-3.5 h-3.5 mr-1.5" /> Recent Chats
              </div>
              <button onClick={handleNewChat} className="text-blue-600 hover:text-blue-700 transition-colors" title="New Chat">
                <PlusCircle className="w-4 h-4" />
              </button>
            </div>
            
            <ul className="space-y-1">
              {sessions.map(sess => (
                <li key={sess.id}>
                  <button
                    onClick={() => handleSelectSession(sess.id)}
                    className={`w-full text-left px-3 py-2.5 rounded-xl text-sm transition-all flex items-center group ${
                      currentSessionId === sess.id 
                        ? 'bg-blue-50 text-blue-700 font-medium shadow-sm border border-blue-100' 
                        : 'text-slate-600 hover:bg-slate-100 border border-transparent'
                    }`}
                  >
                    <MessageSquare className={`w-4 h-4 mr-2.5 ${currentSessionId === sess.id ? 'text-blue-500' : 'text-slate-400 group-hover:text-slate-500'}`} />
                    <span className="truncate">{sess.title || 'New Chat'}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col h-full bg-[#f8fafc] relative">
        {loadingHistory ? (
           <div className="flex-1 flex justify-center items-center">
             <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
           </div>
        ) : (
          <>
            <ChatWindow 
              messages={messages} 
              isStreaming={isStreaming} 
              streamedText={streamedText} 
              metadata={metadata} 
            />
            <div className="w-full bg-gradient-to-t from-[#f8fafc] to-transparent h-6 absolute bottom-[88px] z-10 pointer-events-none"></div>
            <InputBar onSend={handleSend} disabled={isStreaming} isStreaming={isStreaming} />
          </>
        )}
      </div>
    </div>
  );
}
