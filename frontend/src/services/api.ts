// frontend/src/services/api.ts
import axios from 'axios';

const API_BASE_URL = '/api';
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 180000,  // 🔥 3 minutes
});

// Dashboard
export const getDashboardStats = () => api.get('/stats/');

// Incidents
export const getIncidents = (params?: any) => {
  const queryParams = new URLSearchParams();
  if (params?.type) queryParams.append('type', params.type);
  if (params?.secteur) queryParams.append('secteur', params.secteur);
  if (params?.severity) queryParams.append('severity', params.severity);
  if (params?.limit) queryParams.append('limit', params.limit);
  if (params?.offset) queryParams.append('offset', params.offset);
  const url = `/incidents/${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;
  return api.get(url);
};

// Sectors
export const getSectors = () => api.get('/sectors/');
export const getTypes = () => api.get('/types/');
export const getSectorReport = (secteur: string) => api.get(`/sector-report/${encodeURIComponent(secteur)}/`);

// ============================================================================
// CHATBOT - STREAMING
// ============================================================================

export interface ChatResponse {
  query: string;
  response: string;
  sources: string[];
  language: string;
  has_recommendations: boolean;
  has_statistics: boolean;
  has_news: boolean;
  status?: string;
  error?: string;
}

// 🔒 sessionId optionnel mais fortement recommandé : sans lui, le backend
// (voir views.py) retombe sur un id anonyme généré par requête, donc perd
// toute continuité de conversation. Le transmettre via le header
// X-Session-Id, lu côté Django par request.META['HTTP_X_SESSION_ID'].
export const sendChat = async (
  query: string,
  sessionId?: string
): Promise<ChatResponse> => {
  try {
    if (import.meta.env.DEV) {
      console.log('📤 Envoi de la requête:', query, 'session:', sessionId);
    }

    const response = await api.post(
      '/chat/',
      { query },
      sessionId ? { headers: { 'X-Session-Id': sessionId } } : undefined
    );

    if (import.meta.env.DEV) {
      console.log('📥 Réponse reçue:', response.status);
    }

    return response.data;
  } catch (error) {
    console.error('❌ Erreur sendChat:', error);

    if (axios.isAxiosError(error)) {
      if (error.code === 'ECONNABORTED') {
        throw new Error('Timeout: Le serveur met trop de temps à répondre.');
      } else if (error.response?.status === 500) {
        throw new Error('Erreur interne du serveur.');
      } else if (error.response?.status === 404) {
        throw new Error('Endpoint non trouvé. Vérifiez que le backend est en cours d\'exécution.');
      }
    }
    throw error;
  }
};

// 🔥 STREAMING
// 🔒 sessionId transmis dans le corps JSON, car chat_stream() côté backend
// le lit via data.get('session_id') (pas via un header, contrairement à
// l'endpoint non-streaming /chat/).
export const sendChatStream = async (
    query: string,
    onToken: (token: string) => void,
    onSources: (sources: string[]) => void,
    onError: (error: string) => void,
    onDone: (sources?: string[]) => void,
    sessionId?: string
) => {
  try {
    if (import.meta.env.DEV) {
      console.log('📤 Envoi de la requête streaming:', query, 'session:', sessionId);
    }

    const response = await fetch('/api/chat-stream/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query, session_id: sessionId }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('No reader available');
    }

    let doneSources: string[] = [];

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n').filter(line => line.trim());

      for (const line of lines) {
        try {
          const data = JSON.parse(line);
          switch (data.type) {
            case 'sources':
              if (import.meta.env.DEV) {
                console.log('📚 Sources:', data.content);
              }
              onSources(data.content);
              break;
            case 'token':
              onToken(data.content);
              break;
            case 'error':
              if (import.meta.env.DEV) {
                console.error('❌ Erreur streaming:', data.content);
              }
              onError(data.content);
              break;
            case 'done':
              doneSources = data.sources || [];
              if (import.meta.env.DEV) {
                console.log('✅ Streaming terminé');
              }
              onDone(doneSources);
              break;
          }
        } catch (e) {
          if (import.meta.env.DEV) {
            console.warn('⚠️ Erreur parsing JSON:', e);
          }
        }
      }
    }
  } catch (error) {
    console.error('❌ Erreur streaming:', error);
    onError(error instanceof Error ? error.message : 'Erreur inconnue');
  }
};

export default api;