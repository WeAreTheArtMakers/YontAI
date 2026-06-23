from enum import StrEnum


class JobType(StrEnum):
    MODEL_ANALYSIS = "model_analysis"
    DATASET_ANALYSIS = "dataset_analysis"
    TRAINING = "training"
    BENCHMARK = "benchmark"
    DIAGNOSTIC = "diagnostic"
    EXPORT = "export"
    DEPLOYMENT_START = "deployment_start"
    DEPLOYMENT_STOP = "deployment_stop"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FAILED = "failed"
    COMPLETED = "completed"
