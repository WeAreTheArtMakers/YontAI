export type JobStatus = "queued" | "running" | "paused" | "cancelled" | "failed" | "completed";

export interface JobSummary {
  id: string;
  type: string;
  status: JobStatus;
  progress: number;
  currentStep?: string;
  createdAt: string;
}
