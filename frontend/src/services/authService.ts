import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Create axios instance with default config
const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle token expiration
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authService = {
  async login(email: string, password: string) {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);
    
    const response = await api.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },

  async register(email: string, password: string, full_name: string) {
    const response = await api.post('/auth/register', {
      email,
      password,
      full_name,
    });
    return response.data;
  },

  async testToken() {
    const response = await api.post('/auth/test-token');
    return response.data;
  },

  async updateLinkedInCredentials(linkedinEmail: string, linkedinPassword: string) {
    const response = await api.post('/auth/linkedin-credentials', {
      linkedin_email: linkedinEmail,
      linkedin_password: linkedinPassword,
    });
    return response.data;
  },
};

export default api;