const API_BASE = '/api/v1';

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const token = localStorage.getItem('access_token');
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'API Error' }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

async function fetchBlob(endpoint: string) {
  const token = localStorage.getItem('access_token');
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unable to retrieve image' }));
    throw new Error(error.detail || 'Unable to retrieve image');
  }
  return response.blob();
}

export const api = {
  fetchApi,
  // Auth
  login: (credentials: any) => fetchApi('/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
  getMe: () => fetchApi('/auth/me'),
  getHealth: async () => {
    const response = await fetch('/healthz');
    if (!response.ok) throw new Error('Backend health check failed');
    return response.json();
  },

  // Dashboard
  getDashboardSummary: () => fetchApi('/dashboard/summary'),

  // Cameras
  getCameras: () => fetchApi('/cameras'),
  getMonitoringCameras: () => fetchApi('/monitoring/cameras'),
  getCameraSnapshot: (id: string) => fetchBlob(`/monitoring/cameras/${id}/snapshot`),
  createCamera: (data: any) => fetchApi('/cameras', { method: 'POST', body: JSON.stringify(data) }),
  updateCamera: (id: string, data: any) => fetchApi(`/cameras/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteCamera: (id: string) => fetchApi(`/cameras/${id}`, { method: 'DELETE' }),
  testCamera: (id: string) => fetchApi(`/cameras/${id}/test`, { method: 'POST' }),

  // Members
  getMembers: (params?: Record<string, any> | string) => {
    if (typeof params === 'string') {
      return fetchApi(`/members${params}`);
    }
    if (params && typeof params === 'object') {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          searchParams.append(key, String(val));
        }
      });
      const queryStr = searchParams.toString();
      return fetchApi(`/members${queryStr ? `?${queryStr}` : ''}`);
    }
    return fetchApi('/members');
  },
  createMember: (data: any) => fetchApi('/members', { method: 'POST', body: JSON.stringify(data) }),
  enrollFace: (id: string, fileOrBase64: File | string, sample_label: string = 'Front') => {
    const formData = new FormData();
    formData.append('sample_label', sample_label);
    if (fileOrBase64 instanceof File) {
      formData.append('file', fileOrBase64);
    } else {
      formData.append('image_base64', fileOrBase64);
    }
    return fetchApi(`/members/${id}/enroll-face`, {
      method: 'POST',
      body: formData
    });
  },
  deleteMember: (id: string) => fetchApi(`/members/${id}`, { method: 'DELETE' }),

  // Person Identification
  identifyPerson: (fileOrBase64: File | string) => {
    const formData = new FormData();
    if (fileOrBase64 instanceof File) {
      formData.append('file', fileOrBase64);
    } else {
      formData.append('image_base64', fileOrBase64);
    }
    return fetchApi('/person-identification', {
      method: 'POST',
      body: formData
    });
  },
  getIdentificationHistory: () => fetchApi('/person-identification/history'),

  // Zones
  getZones: () => fetchApi('/zones'),
  createZone: (data: any) => fetchApi('/zones', { method: 'POST', body: JSON.stringify(data) }),
  updateZone: (id: string, data: any) => fetchApi(`/zones/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteZone: (id: string) => fetchApi(`/zones/${id}`, { method: 'DELETE' }),

  // Events & Alerts
  getEvents: (params = '') => fetchApi(`/events${params}`),
  getAlerts: (params = '') => fetchApi(`/alerts${params}`),
  updateAlertStatus: (id: string, status: string) => fetchApi(`/alerts/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  getNotifications: (unreadOnly = false) => fetchApi(`/notifications?unread_only=${unreadOnly}&limit=50`),
  getUnreadNotificationCount: () => fetchApi('/notifications/unread-count'),
  markNotificationRead: (id: string) => fetchApi(`/notifications/${id}/read`, { method: 'PATCH' }),
  markAllNotificationsRead: () => fetchApi('/notifications/read-all', { method: 'PATCH' }),
  downloadEventSnapshot: (eventId: string) => fetchBlob(`/events/${eventId}/snapshot`),

  // Analytics & Settings
  getAnalytics: () => fetchApi('/analytics'),
  getSettings: () => fetchApi('/settings'),
  updateSetting: (key: string, value: string) => fetchApi('/settings', { method: 'PUT', body: JSON.stringify({ key, value }) }),
  downloadCsvReport: async () => {
    const token = localStorage.getItem('access_token');
    const response = await fetch(`${API_BASE}/reports/export/csv`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Report export failed' }));
      throw new Error(error.detail || 'Report export failed');
    }
    return response.blob();
  },
};
