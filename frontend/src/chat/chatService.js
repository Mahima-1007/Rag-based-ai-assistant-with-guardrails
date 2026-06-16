import api from '../api';

export const createSession = async (title = 'New Chat') => {
  const response = await api.post('/chat/sessions', { title });
  return response.data;
};

export const listSessions = async () => {
  const response = await api.get('/chat/sessions');
  return response.data.sessions;
};

export const getHistory = async (sessionId) => {
  const response = await api.get(`/chat/history/${sessionId}`);
  return response.data.messages;
};

export const deleteSession = async (sessionId) => {
  const response = await api.delete(`/chat/sessions/${sessionId}`);
  return response.data;
};
