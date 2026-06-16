import api from '../api';

export const loginUser = async (email, password) => {
  const response = await api.post('/auth/login', { email, password });
  return response.data;
};

export const registerUser = async (email, username, password) => {
  const response = await api.post('/auth/register', { email, username, password });
  return response.data;
};

export const logoutUser = async () => {
  try {
    await api.post('/auth/logout');
  } catch (err) {
    // Ignore errors on logout
  }
};

export const fetchCurrentUser = async () => {
  const response = await api.get('/auth/me');
  return response.data.user;
};
