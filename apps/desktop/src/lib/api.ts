const API_BASE = import.meta.env.VITE_YONTAI_API_URL ?? "http://127.0.0.1:8765/api/v1";

export interface ModelRecord {
  id: string;
  name: string;
  source: "local" | "huggingface" | "ollama";
  path: string | null;
  provider_id: string | null;
  model_family: string | null;
  parameter_count: number | null;
  quantization: string | null;
  context_length: number | null;
  architecture: string | null;
  actual_license: string | null;
  user_license_notes: string | null;
  tokenizer: string | null;
  dtype: string | null;
  size_bytes: number | null;
  metadata_json: Record<string, unknown>;
  analysis: ModelAnalysis | null;
}

export interface ModelDiscoveryResult {
  imported: ModelRecord[];
  skipped: string[];
  errors: string[];
}

export interface ModelAnalysis {
  model_id?: string;
  summary_tr: string;
  strengths: string[];
  weaknesses: string[];
  details: Record<string, unknown>;
  memory_requirements: Record<string, unknown>;
}

export interface DatasetRecord {
  id: string;
  name: string;
  path: string;
  format: string;
  task_type: string | null;
  row_count: number;
  token_count_estimate: number;
  average_tokens: number;
  duplicate_ratio: number;
  empty_ratio: number;
  quality_score: number;
  schema: Record<string, unknown>;
  preview: Record<string, unknown>[];
  statistics: Record<string, unknown>;
  report: {
    summary_tr?: string;
    findings?: string[];
    recommended_actions?: string[];
  };
}

export interface DoctorDiagnosis {
  risk_level: string;
  confidence_score: number;
  reasons: string[];
  recommendations: string[];
  expected_impact: string;
  evidence: Record<string, unknown>;
  summary_tr: string;
}

export interface SystemHealth {
  status: string;
  service: string;
}

export interface BenchmarkResult {
  model: string;
  response: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  token_per_sec: number | null;
  ttft_ms: number | null;
  total_time_ms: number | null;
  error: string | null;
}

export interface BenchmarkRunRecord {
  id: string;
  model_id: string;
  model_name?: string;
  benchmark_type: string;
  status: string;
  config: Record<string, unknown>;
  results: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
}

export interface JobRecord {
  id: string;
  project_id: string | null;
  type: string;
  status: "pending" | "queued" | "running" | "paused" | "cancelled" | "failed" | "completed";
  priority: number;
  progress: number;
  current_step: string | null;
  error_message: string | null;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface JobEventRecord {
  id: string;
  job_id: string;
  event_type: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface JobMaintenanceAdvice {
  count: number;
  summary_tr: string;
  items: Array<{
    job_id: string;
    status: string;
    can_retry: boolean;
    can_delete: boolean;
    notes_tr: string[];
  }>;
}

export interface ExtractedContextFile {
  name: string;
  type: "text" | "pdf";
  size: number;
  content: string;
  truncated: boolean;
}

export interface SystemCapabilities {
  database: string;
  database_status: string;
  ollama_status: string;
  metadata_engine_status: string;
  benchmark_engine_status: string;
  job_worker_status: string;
  events: string[];
  ai_runtimes: string[];
}

export interface PublicDatasetCatalogItem {
  repository_id: string;
  title: string;
  task_type: string;
  language: string;
  license: string | null;
  description_tr: string;
  recommended_limit: number;
}

export interface FineTunePlan {
  ready: boolean;
  model_id: string;
  dataset_id: string;
  method: string;
  framework: string;
  estimated_vram_gb: number;
  estimated_steps: number;
  warnings: string[];
  recommendations: string[];
  config: Record<string, unknown>;
}

export interface TrainingRunRecord {
  id: string;
  project_id: string | null;
  base_model_id: string;
  dataset_id: string;
  output_model_id: string | null;
  job_id: string | null;
  method: string;
  framework: string;
  config: Record<string, unknown>;
  metrics: Record<string, unknown>;
  mlflow_run_id: string | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface TrainingRunCreated {
  run: TrainingRunRecord;
  job: JobRecord;
  plan: FineTunePlan;
  message_tr: string;
}

export interface KnowledgePackResponse {
  model_id: string;
  dataset_id: string;
  artifact_id: string;
  artifact_path: string;
  message_tr: string;
  details: Record<string, unknown>;
}

function formatApiErrorDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg?: unknown }).msg);
        }
        return JSON.stringify(item);
      })
      .join(" ");
  }
  if (detail && typeof detail === "object") {
    if ("message" in detail) return String((detail as { message?: unknown }).message);
    if ("detail" in detail) return formatApiErrorDetail((detail as { detail?: unknown }).detail);
    return JSON.stringify(detail);
  }
  return "İstek başarısız oldu.";
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...options?.headers
    }
  });
  if (!response.ok) {
    let message = "İstek başarısız oldu.";
    try {
      const payload = await response.json();
      message = formatApiErrorDetail(payload.detail ?? payload);
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function requestText(path: string, options?: RequestInit): Promise<string> {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let message = "İstek başarısız oldu.";
    try {
      const payload = await response.json();
      message = formatApiErrorDetail(payload.detail ?? payload);
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  return response.text();
}

export const api = {
  jobsStreamUrl: () => `${API_BASE}/jobs/stream`,
  health: () => request<SystemHealth>("/system/health"),
  capabilities: () => request<SystemCapabilities>("/system/capabilities"),
  listJobs: () => request<JobRecord[]>("/jobs"),
  listJobEvents: (jobId: string) => request<JobEventRecord[]>(`/jobs/${jobId}/events`),
  jobMaintenanceAdvice: () => request<JobMaintenanceAdvice>("/jobs/maintenance/advice"),
  deleteJob: (jobId: string) =>
    request<{ deleted: boolean; message_tr: string }>(`/jobs/${jobId}`, { method: "DELETE" }),
  deleteIncompleteJobs: () =>
    request<{ deleted_count: number; message_tr: string }>("/jobs/maintenance/incomplete", {
      method: "DELETE"
    }),
  readContextFile: (path: string) =>
    requestText(`/files/read?path=${encodeURIComponent(path)}`),
  extractContextFile: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<ExtractedContextFile>("/files/extract", {
      method: "POST",
      body: formData
    });
  },
  listModels: () => request<ModelRecord[]>("/models"),
  registerModel: (payload: Record<string, unknown>) =>
    request<ModelRecord>("/models", { method: "POST", body: JSON.stringify(payload) }),
  importModelFile: (formData: FormData) =>
    request<ModelRecord>("/models/import-file", { method: "POST", body: formData }),
  scanModelFolder: (folderPath: string) =>
    request<ModelDiscoveryResult>("/models/scan-folder", {
      method: "POST",
      body: JSON.stringify({ folder_path: folderPath })
    }),
  discoverOllama: () =>
    request<ModelDiscoveryResult>("/models/discover/ollama", { method: "POST" }),
  registerHuggingFace: (repositoryId: string) =>
    request<ModelRecord>("/models/huggingface", {
      method: "POST",
      body: JSON.stringify({ repository_id: repositoryId })
    }),
  analyzeModel: (modelId: string) =>
    request<ModelAnalysis>(`/models/${modelId}/analyze`, { method: "POST" }),
  updateModel: (modelId: string, payload: Record<string, unknown>) =>
    request<ModelRecord>(`/models/${modelId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  listDatasets: () => request<DatasetRecord[]>("/datasets"),
  publicDatasetCatalog: () => request<PublicDatasetCatalogItem[]>("/datasets/public/catalog"),
  importPublicDataset: (payload: Record<string, unknown>) =>
    request<DatasetRecord>("/datasets/public/import", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  uploadDataset: (formData: FormData) =>
    request<DatasetRecord>("/datasets/upload", { method: "POST", body: formData }),
  analyzeDataset: (datasetId: string) =>
    request<DatasetRecord>(`/datasets/${datasetId}/analyze`, { method: "POST" }),
  diagnose: (modelId: string, datasetId: string) =>
    request<DoctorDiagnosis>("/diagnostics/doctor", {
      method: "POST",
      body: JSON.stringify({ model_id: modelId, dataset_id: datasetId })
    }),
  listBenchmarkRuns: () => request<BenchmarkRunRecord[]>("/benchmarks/runs"),
  executeBenchmark: (models: string[], prompt: string, maxTokens = 128) =>
    request<BenchmarkResult[]>("/benchmarks/execute", {
      method: "POST",
      body: JSON.stringify({ models, prompt, max_tokens: maxTokens })
    }),
  systemHardware: () => request<Record<string, any>>("/system/hardware"),
  chat: (modelId: string, prompt: string, images?: string[]) =>
    request<{ response: string }>("/models/chat", {
      method: "POST",
      body: JSON.stringify({ model_id: modelId, prompt, images })
    }),
  searchHuggingFaceDatasets: (query: string, limit: number = 10) =>
    request<Array<{ id: string; name: string; author: string; downloads: number; likes: number; description: string }>>(`/datasets/huggingface/search?query=${encodeURIComponent(query)}&limit=${limit}`),
  createDatasetFromDocuments: (files: File[], name: string, projectId?: string, taskType: string = "instruction") => {
    const formData = new FormData();
    files.forEach(file => formData.append("files", file));
    formData.append("name", name);
    if (projectId) formData.append("project_id", projectId);
    formData.append("task_type", taskType);
    
    return request<DatasetRecord>("/datasets/from-documents", {
      method: "POST",
      body: formData
    });
  },
  augmentDataset: (datasetId: string) =>
    request<DatasetRecord>(`/datasets/${datasetId}/augment`, { method: "POST" }),
  listTrainingRuns: () => request<TrainingRunRecord[]>("/training/runs"),
  planTrainingRun: (payload: Record<string, unknown>) =>
    request<FineTunePlan>("/training/plan", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createTrainingRun: (payload: Record<string, unknown>) =>
    request<TrainingRunCreated>("/training/runs", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  attachKnowledgePack: (payload: Record<string, unknown>) =>
    request<KnowledgePackResponse>("/training/knowledge-pack", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  cancelTrainingRun: (runId: string) =>
    request<TrainingRunRecord>(`/training/runs/${runId}/cancel`, {
      method: "POST"
    }),
  doctorFix: (action: string, payload: Record<string, any>) =>
    request<any>("/diagnostics/doctor/fix", {
      method: "POST",
      body: JSON.stringify({ action, ...payload })
    })
};
