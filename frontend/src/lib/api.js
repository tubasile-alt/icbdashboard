import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
});

export const getDashboard = async () => {
  const { data } = await api.get('/dashboard');
  return data;
};
