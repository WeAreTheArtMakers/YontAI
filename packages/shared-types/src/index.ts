export type JobStatus = "queued" | "running" | "paused" | "cancelled" | "failed" | "completed";

export interface ApiEnvelope<T> {
  data: T;
  requestId?: string;
}
