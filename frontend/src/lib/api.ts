const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export interface ChatResponse {
  response: string;
  risk_score: 'CRITICAL' | 'HIGH' | 'LOW' | 'APPROVED';
  report_id?: string;
  scan_result?: ScanResultSummary | null;
}

export interface ScanResultSummary {
  scan_id?: string;
  table_fqn?: string;
  risk_level?: string;
  carbon_saved_kg?: number;
  lineage_impact?: Record<string, number>;
  validation_summary?: Record<string, unknown>;
  drift_summary?: Record<string, unknown>;
  anomaly_summary?: Record<string, unknown>;
  pdf_path?: string | null;
  pdf_url?: string | null;
  openmetadata_task_id?: string | null;
}

export interface ValidationHistoryItem {
  id: string;
  dataset: string;
  risk_score: string;
  timestamp: string;
  action: string;
  report_url?: string;
}

export interface ReportItem {
  id: string;
  filename: string;
  dataset: string;
  created_at: string;
  download_url: string;
}

export interface HealthStatus {
  status: string;
  openmetadata_connected: boolean;
}

class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function fetchWithHandling<T>(url: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${url}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new ApiError(`Request failed with status ${response.status}`, response.status);
    }

    return await response.json() as T;
  } catch (error) {
    console.error(`API request failed [${url}]:`, error);
    throw error;
  }
}

export const api = {
  chat: (message: string) => 
    fetchWithHandling<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  validate: (body: { message: string; session_id?: string; dataset_path?: string; table_fqn?: string }) =>
    fetchWithHandling<ChatResponse>('/api/validate', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  uploadAndScan: async (file: File, tableFqn: string, sessionId: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('table_fqn', tableFqn);
    formData.append('session_id', sessionId);

    const response = await fetch(`${API_BASE}/agent/upload-and-scan`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new ApiError(`Request failed with status ${response.status}`, response.status);
    }

    return response.json() as Promise<ScanResultSummary>;
  },

  getHistory: () => 
    fetchWithHandling<ValidationHistoryItem[]>('/api/history'),

  getReports: () => 
    fetchWithHandling<ReportItem[]>('/api/reports'),

  getHealth: () => 
    fetchWithHandling<HealthStatus>('/api/health'),

  downloadLatestReportUrl: () => `${API_BASE}/api/report/latest`,
  downloadReportUrl: (url: string) => `${API_BASE}${url}`,
};
