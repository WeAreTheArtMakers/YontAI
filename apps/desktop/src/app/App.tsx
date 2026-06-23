import { DragEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  Boxes,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  Database,
  FileText,
  FolderSearch,
  HardDrive,
  Home,
  Loader2,
  Search,
  Server,
  Stethoscope
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { HelpScreen } from "@/components/HelpScreen";
import { formatOSName, formatRAM } from "@/utils/os-formatter";
import {
  api,
  BenchmarkResult,
  DatasetRecord,
  DoctorDiagnosis,
  FineTunePlan,
  JobEventRecord,
  JobRecord,
  ModelAnalysis,
  ModelRecord,
  PublicDatasetCatalogItem,
  TrainingRunRecord
} from "@/lib/api";

type Section = 
  | "Ana Panel" 
  | "Model Hub" 
  | "Chat & Workspace" 
  | "Data Recipes" 
  | "Fine-Tuning & RL" 
  | "Observability"
  | "İşlem Logları"
  | "Model Doktoru" 
  | "Benchmark"
  | "Yardım & Rehber";

export type GlobalTask = { id: string; title: string; progress: number; status: "running" | "done" | "error"; message?: string };
export const globalTasksAtom = { tasks: [] as GlobalTask[], listeners: [] as (() => void)[] };
export function addGlobalTask(task: GlobalTask) {
  globalTasksAtom.tasks.push(task);
  globalTasksAtom.listeners.forEach(l => l());
}
export function updateGlobalTask(id: string, updates: Partial<GlobalTask>) {
  const t = globalTasksAtom.tasks.find(x => x.id === id);
  if (t) { Object.assign(t, updates); globalTasksAtom.listeners.forEach(l => l()); }
}
export function removeGlobalTask(id: string) {
  globalTasksAtom.tasks = globalTasksAtom.tasks.filter(t => t.id !== id);
  globalTasksAtom.listeners.forEach(l => l());
}
export function useGlobalTasks() {
  const [tasks, setTasks] = useState(globalTasksAtom.tasks);
  useEffect(() => {
    const l = () => setTasks([...globalTasksAtom.tasks]);
    globalTasksAtom.listeners.push(l);
    return () => { globalTasksAtom.listeners = globalTasksAtom.listeners.filter(x => x !== l); };
  }, []);
  return tasks;
}

function syncJobTasks(jobs: JobRecord[]) {
  const activeStatuses = new Set(["pending", "queued", "running"]);
  const incomingIds = new Set(jobs.map((job) => `job:${job.id}`));
  for (const job of jobs) {
    const id = `job:${job.id}`;
    if (!activeStatuses.has(job.status)) {
      if (globalTasksAtom.tasks.some((task) => task.id === id)) {
        removeGlobalTask(id);
      }
      continue;
    }
    const existing = globalTasksAtom.tasks.some((task) => task.id === id);
    const task = {
      id,
      title: job.current_step ?? job.type,
      progress: Math.round(job.progress),
      status: "running",
      message: job.error_message ?? job.current_step ?? undefined
    } satisfies GlobalTask;

    if (existing) {
      updateGlobalTask(id, task);
    } else {
      addGlobalTask(task);
    }
  }
  for (const task of [...globalTasksAtom.tasks]) {
    if (task.id.startsWith("job:") && !incomingIds.has(task.id)) {
      removeGlobalTask(task.id);
    }
  }
}

const navGroups = [
  {
    title: "Platform",
    items: [
      { label: "Ana Panel" as const, icon: Home },
      { label: "Yardım & Rehber" as const, icon: BookOpen },
    ]
  },
  {
    title: "Inference",
    items: [
      { label: "Model Hub" as const, icon: Boxes },
      { label: "Chat & Workspace" as const, icon: BrainCircuit },
      { label: "Benchmark" as const, icon: BarChart3 }
    ]
  },
  {
    title: "Training",
    items: [
      { label: "Data Recipes" as const, icon: Database },
      { label: "Fine-Tuning & RL" as const, icon: Cpu },
      { label: "Observability" as const, icon: BarChart3 },
      { label: "İşlem Logları" as const, icon: FileText },
      { label: "Model Doktoru" as const, icon: Stethoscope }
    ]
  }
];

const emptyArray: never[] = [];

export function App() {
  const [section, setSection] = useState<Section>("Ana Panel");
  const [backendReady, setBackendReady] = useState(false);
  
  // Backend hazır olana kadar bekle (max 30 saniye)
  useEffect(() => {
    let attempts = 0;
    const maxAttempts = 60; // 30 saniye (500ms * 60)
    
    const checkBackend = async () => {
      try {
        const response = await fetch(`${import.meta.env.VITE_YONTAI_API_URL ?? "http://127.0.0.1:8765"}/api/v1/system/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(1000)
        });
        if (response.ok) {
          setBackendReady(true);
          return true;
        }
      } catch {
        // Backend henüz hazır değil
      }
      return false;
    };
    
    const pollBackend = async () => {
      while (attempts < maxAttempts && !backendReady) {
        attempts++;
        const ready = await checkBackend();
        if (ready) break;
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    };
    
    pollBackend();
  }, []);
  
  const health = useQuery({ 
    queryKey: ["health"], 
    queryFn: api.health, 
    retry: 3,
    retryDelay: 1000,
    enabled: backendReady,
    refetchInterval: 10000
  });
  
  const capabilities = useQuery({ 
    queryKey: ["capabilities"], 
    queryFn: api.capabilities, 
    retry: 3,
    retryDelay: 1000,
    enabled: backendReady,
    refetchInterval: 5000 
  });
  
  const models = useQuery({ 
    queryKey: ["models"], 
    queryFn: api.listModels, 
    retry: 2,
    enabled: backendReady && health.data?.status === "ok"
  });
  
  const datasets = useQuery({ 
    queryKey: ["datasets"], 
    queryFn: api.listDatasets, 
    retry: 2,
    enabled: backendReady && health.data?.status === "ok"
  });

  useEffect(() => {
    const eventSource = new EventSource(api.jobsStreamUrl());
    eventSource.addEventListener("jobs", (event) => {
      try {
        syncJobTasks(JSON.parse((event as MessageEvent).data) as JobRecord[]);
      } catch {
        // Ignore malformed progress events; the next SSE snapshot will retry.
      }
    });
    return () => eventSource.close();
  }, []);

  const content = useMemo(() => {
    // Backend hazır değilse loading göster
    if (!backendReady) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center space-y-4">
            <Loader2 className="size-12 animate-spin text-primary mx-auto" />
            <div>
              <h2 className="text-xl font-semibold">Backend Başlatılıyor...</h2>
              <p className="text-sm text-muted-foreground mt-2">
                YontAI backend servisi hazırlanıyor. Bu işlem 5-10 saniye sürebilir.
              </p>
            </div>
          </div>
        </div>
      );
    }
    
    if (section === "Model Hub") return <ModelsScreen models={models.data ?? emptyArray} />;
    if (section === "Data Recipes") return <DatasetsScreen datasets={datasets.data ?? emptyArray} />;
    if (section === "Model Doktoru") return <DoctorScreen models={models.data ?? emptyArray} datasets={datasets.data ?? emptyArray} />;
    if (section === "Benchmark") return <BenchmarkScreen models={models.data ?? emptyArray} />;
    if (section === "Chat & Workspace") return <ChatWorkspaceScreen models={models.data ?? emptyArray} />;
    if (section === "Fine-Tuning & RL") return <FineTuningScreen models={models.data ?? emptyArray} datasets={datasets.data ?? emptyArray} />;
    if (section === "Observability") return <ObservabilityScreen />;
    if (section === "İşlem Logları") return <LogsScreen />;
    if (section === "Yardım & Rehber") return <HelpScreen />;
    
    return (
      <Dashboard
        backendOnline={health.data?.status === "ok"}
        backendError={health.error instanceof Error ? health.error.message : null}
        capabilities={capabilities.data ?? null}
        models={models.data ?? emptyArray}
        datasets={datasets.data ?? emptyArray}
      />
    );
  }, [section, backendReady, health.data, health.error, capabilities.data, models.data, datasets.data]);

  return (
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-primary/20 via-background to-background text-foreground selection:bg-primary/30">
      <div className="grid min-h-screen grid-cols-[260px_1fr]">
        <aside className="glass-sidebar flex flex-col">
          <div className="flex h-16 items-center gap-3 border-b border-white/5 px-5">
            <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary/60 text-white shadow-lg shadow-primary/20">
              <Boxes className="size-5" />
            </div>
            <div>
              <div className="text-base font-bold tracking-tight">YontAI Studio</div>
              <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Local AI Engine</div>
            </div>
          </div>
          <nav className="flex-1 space-y-6 p-4">
            {navGroups.map((group) => (
              <div key={group.title}>
                <div className="px-3 mb-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase">{group.title}</div>
                <div className="space-y-1">
                  {group.items.map((item) => (
                    <Button
                      key={item.label}
                      variant={section === item.label ? "secondary" : "ghost"}
                      className={`w-full justify-start gap-3 rounded-xl transition-all duration-300 ${
                        section === item.label 
                          ? "bg-primary/10 text-primary hover:bg-primary/20 shadow-sm" 
                          : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
                      }`}
                      onClick={() => setSection(item.label)}
                    >
                      <item.icon className="size-4.5" />
                      <span className="font-medium">{item.label}</span>
                    </Button>
                  ))}
                </div>
              </div>
            ))}
          </nav>
        </aside>
        <section className="min-w-0 flex flex-col h-screen overflow-y-auto custom-scrollbar relative">
          <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:32px_32px] pointer-events-none" />
          <div className="relative z-10 flex-1">
            {content}
          </div>
        </section>
      </div>
      {/* Global Task Logger */}
      <GlobalTaskLogger />
    </main>
  );
}

function Header({ title, description }: { title: string; description: string }) {
  return (
    <header className="flex h-24 items-center justify-between border-b border-white/5 px-8 glass-panel sticky top-0 z-20 rounded-none border-t-0 border-l-0 border-r-0 backdrop-blur-2xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
    </header>
  );
}

function PlaceholderScreen({ title, description, icon }: { title: string; description: string; icon: React.ReactNode }) {
  return (
    <>
      <Header title={title} description="Bu özellik geliştirme aşamasındadır." />
      <div className="flex h-[calc(100vh-6rem)] items-center justify-center p-8">
        <div className="glass-panel max-w-lg p-12 text-center flex flex-col items-center">
          <div className="mb-6 rounded-full bg-primary/10 p-4 ring-1 ring-primary/20">
            {icon}
          </div>
          <h2 className="mb-3 text-2xl font-bold tracking-tight text-white">{title}</h2>
          <p className="mb-8 text-muted-foreground leading-relaxed">{description}</p>
          <Button variant="outline" className="gap-2 pointer-events-none opacity-50">
            <Boxes className="size-4" />
            <span>YontAI Engine Hazırlanıyor...</span>
          </Button>
        </div>
      </div>
    </>
  );
}

function Dashboard({
  backendOnline,
  backendError,
  capabilities,
  models,
  datasets
}: {
  backendOnline: boolean;
  backendError: string | null;
  capabilities: import("@/lib/api").SystemCapabilities | null;
  models: ModelRecord[];
  datasets: DatasetRecord[];
}) {
  const analyzedModels = models.filter((m) => m.analysis != null).length;
  const benchmarkRuns = useQuery({
    queryKey: ["benchmark-runs"],
    queryFn: api.listBenchmarkRuns,
    enabled: backendOnline,
    retry: 1
  });
  const benchmarkCount = benchmarkRuns.data?.length ?? 0;

  return (
    <>
      <Header title="AI Engineering Dashboard" description="Modellerin, veri setlerinin ve kıyaslamaların (benchmarks) genel durumu." />
      <div className="space-y-6 p-8 max-w-[1400px] mx-auto">
        {backendError ? <ErrorBanner message={`Backend bağlantısı kurulamadı: ${backendError}`} /> : null}
        <div className="grid grid-cols-4 gap-6">
          <Metric title="Kayıtlı Model" value={String(models.length)} />
          <Metric title="Veri Seti" value={String(datasets.length)} />
          <Metric title="Benchmark Sayısı" value={String(benchmarkCount)} />
          <Metric title="Analizi Tamamlanan Model" value={String(analyzedModels)} />
        </div>
        <div className="grid grid-cols-2 gap-6">
          <section className="glass-panel rounded-2xl p-6">
            <h2 className="text-base font-semibold">Sistem Durumu (System Health)</h2>
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Backend</span>
                <span className={`text-sm font-medium flex items-center gap-2 ${backendOnline ? "text-primary" : "text-destructive"}`}>
                  {backendOnline ? <CheckCircle2 className="size-4" /> : <AlertTriangle className="size-4" />}
                  {backendOnline ? "Aktif" : "Hata"}
                </span>
              </div>
              <HealthRow label="Ollama" ok={capabilities?.ollama_status === "ok"} fallback={backendOnline ? "Bekleniyor" : "Hata"} />
              <HealthRow label="Database" ok={capabilities?.database_status === "ok"} fallback={backendOnline ? "Bekleniyor" : "Hata"} />
              <HealthRow label="Metadata Engine" ok={capabilities?.metadata_engine_status === "ok"} fallback={backendOnline ? "Bekleniyor" : "Hata"} />
              <HealthRow label="Benchmark Engine" ok={capabilities?.benchmark_engine_status === "ok"} fallback={backendOnline ? "Bekleniyor" : "Hata"} />
              <HealthRow label="Job Worker" ok={capabilities?.job_worker_status === "ok"} fallback={backendOnline ? "Bekleniyor" : "Hata"} />
            </div>
          </section>
          
          <section className="glass-panel rounded-2xl p-6">
            <h2 className="text-base font-semibold mb-4">Metadata Coverage</h2>
            <div className="space-y-3 max-h-[220px] overflow-y-auto pr-2">
              {models.length === 0 && <span className="text-sm text-muted-foreground">Model bulunamadı.</span>}
              {models.map(m => {
                const cov = m.analysis?.details?.metadata_coverage as any;
                const score = cov?.quality_score ?? 0;
                return (
                  <div key={m.id} className="flex items-center justify-between border-b border-border pb-2 last:border-0 last:pb-0">
                    <span className="text-sm font-medium truncate max-w-[200px]" title={m.name}>{m.name}</span>
                    <span className={`text-sm font-semibold ${score >= 80 ? 'text-green-500' : score >= 50 ? 'text-yellow-500' : 'text-red-500'}`}>
                      %{score}
                    </span>
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}

function HealthRow({ label, ok, fallback }: { label: string; ok: boolean; fallback: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`text-sm font-medium flex items-center gap-2 ${ok ? "text-primary" : "text-destructive"}`}>
        {ok ? <CheckCircle2 className="size-4" /> : <AlertTriangle className="size-4" />}
        {ok ? "Aktif" : fallback}
      </span>
    </div>
  );
}

function GlobalTaskLogger() {
  const tasks = useGlobalTasks();
  if (tasks.length === 0) return null;
  
  return (
    <div className="fixed bottom-0 left-0 right-0 p-4 pointer-events-none z-50 flex flex-col items-end gap-2">
      {tasks.map(task => (
        <div key={task.id} className="glass-panel pointer-events-auto p-4 rounded-xl w-96 shadow-2xl border-primary/20 bg-background/95 backdrop-blur-3xl flex flex-col gap-2 transition-all">
          <div className="flex justify-between items-start gap-2">
            <div className="flex-1">
              <div className="flex justify-between text-sm font-semibold">
                <span>{task.title}</span>
                <span className={task.status === "done" ? "text-primary" : task.status === "error" ? "text-red-400" : "text-muted-foreground"}>
                  {task.status === "done" ? "Tamamlandı ✓" : task.status === "error" ? "Hata ✗" : `${task.progress}%`}
                </span>
              </div>
            </div>
            <button 
              onClick={() => removeGlobalTask(task.id)}
              className="text-muted-foreground hover:text-foreground transition-colors p-1 -mt-1 -mr-1"
              title="Kapat"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          {task.status === "running" && (
            <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
              <div className="h-full bg-primary transition-all duration-300" style={{ width: `${task.progress}%` }} />
            </div>
          )}
          {task.message && <p className="text-xs text-muted-foreground">{task.message}</p>}
        </div>
      ))}
    </div>
  );
}

function LogsScreen() {
  const queryClient = useQueryClient();
  const [selectedJobId, setSelectedJobId] = useState("");
  const [viewMode, setViewMode] = useState<"jobs" | "activity">("jobs");
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: api.listJobs, refetchInterval: 2000 });
  const advice = useQuery({
    queryKey: ["job-maintenance-advice"],
    queryFn: api.jobMaintenanceAdvice,
    refetchInterval: 5000
  });
  const selectedJob = jobs.data?.find((job) => job.id === selectedJobId) ?? jobs.data?.[0];
  const selectedAdvice = advice.data?.items.find((item) => item.job_id === selectedJob?.id);
  const events = useQuery({
    queryKey: ["job-events", selectedJob?.id],
    queryFn: () => api.listJobEvents(selectedJob!.id),
    enabled: Boolean(selectedJob?.id),
    refetchInterval: 2000
  });
  const refreshJobs = async () => {
    await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    await queryClient.invalidateQueries({ queryKey: ["job-maintenance-advice"] });
    await queryClient.invalidateQueries({ queryKey: ["job-events"] });
  };
  const deleteJobMutation = useMutation({
    mutationFn: api.deleteJob,
    onSuccess: refreshJobs
  });
  const deleteIncompleteMutation = useMutation({
    mutationFn: api.deleteIncompleteJobs,
    onSuccess: async () => {
      setSelectedJobId("");
      await refreshJobs();
    }
  });

  useEffect(() => {
    if (!selectedJobId && jobs.data?.[0]?.id) {
      setSelectedJobId(jobs.data[0].id);
    }
  }, [jobs.data, selectedJobId]);

  // Tüm aktiviteleri birleştir (jobs + events)
  const allActivities = useMemo(() => {
    const activities: Array<{
      id: string;
      type: string;
      title: string;
      status: string;
      progress: number;
      timestamp: string;
      details?: string;
    }> = [];

    // Jobs'ları ekle
    jobs.data?.forEach(job => {
      activities.push({
        id: job.id,
        type: job.type,
        title: job.current_step ?? job.type,
        status: job.status,
        progress: job.progress,
        timestamp: job.created_at,
        details: job.error_message ?? undefined
      });
    });

    // Seçili job'un eventlerini ekle
    if (selectedJob && events.data) {
      events.data.forEach((event: JobEventRecord) => {
        activities.push({
          id: event.id,
          type: event.event_type,
          title: event.message,
          status: "info",
          progress: 0,
          timestamp: event.created_at,
          details: undefined
        });
      });
    }

    // Timestamp'e göre sırala (en yeni en üstte)
    return activities.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }, [jobs.data, events.data, selectedJob]);

  return (
    <div className="flex h-screen flex-col overflow-y-auto">
      <Header title="İşlem Logları" description="Uzun süren işler, eğitim kayıtları, export/deploy akışları ve canlı job olayları." />
      
      {/* View Mode Tabs */}
      <div className="px-8 pt-6">
        <div className="flex gap-2 border-b border-white/5">
          <button
            onClick={() => setViewMode("jobs")}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
              viewMode === "jobs" 
                ? "border-primary text-primary" 
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Job Detayları
          </button>
          <button
            onClick={() => setViewMode("activity")}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
              viewMode === "activity" 
                ? "border-primary text-primary" 
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Tüm Aktiviteler
          </button>
        </div>
      </div>

      {viewMode === "jobs" ? (
        <div className="grid grid-cols-[420px_1fr] gap-8 p-8 max-w-[1600px] mx-auto w-full">
          <section className="glass-panel rounded-2xl overflow-hidden">
            <div className="border-b border-white/5 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Job Kuyruğu</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{jobs.data?.length ?? 0} kayıt</p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!advice.data?.count || deleteIncompleteMutation.isPending}
                  onClick={() => deleteIncompleteMutation.mutate()}
                >
                  Hatalıları Temizle
                </Button>
              </div>
              {advice.data?.count ? (
                <div className="mt-4 rounded-xl border border-yellow-500/20 bg-yellow-500/10 p-3 text-xs text-yellow-100">
                  {advice.data.summary_tr}
                </div>
              ) : null}
            </div>
            <div className="max-h-[calc(100vh-180px)] overflow-y-auto divide-y divide-border">
              {jobs.isLoading ? <EmptyState text="İşler yükleniyor..." /> : null}
              {jobs.data?.length === 0 ? <EmptyState text="Henüz job kaydı yok." /> : null}
              {jobs.data?.map((job) => (
                <button
                  key={job.id}
                  className={`w-full p-4 text-left hover:bg-muted ${selectedJob?.id === job.id ? "bg-primary/10" : ""}`}
                  onClick={() => setSelectedJobId(job.id)}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium">{job.current_step ?? job.type}</div>
                    <StatusPill status={job.status} />
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    {job.type} · %{Math.round(job.progress)} · {new Date(job.created_at).toLocaleString("tr-TR")}
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section className="glass-panel rounded-2xl p-6">
            {selectedJob ? (
              <div className="space-y-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-semibold">{selectedJob.current_step ?? selectedJob.type}</h2>
                    <p className="mt-1 text-sm text-muted-foreground font-mono">{selectedJob.id}</p>
                  </div>
                  <StatusPill status={selectedJob.status} />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <Metric title="İlerleme" value={`%${Math.round(selectedJob.progress)}`} />
                  <Metric title="Tip" value={selectedJob.type} />
                  <Metric title="Başlama" value={selectedJob.started_at ? new Date(selectedJob.started_at).toLocaleTimeString("tr-TR") : "Bekliyor"} />
                </div>
                {selectedJob.error_message ? <ErrorBanner message={selectedJob.error_message} /> : null}
                {selectedAdvice?.notes_tr.length ? (
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                    <h3 className="text-sm font-semibold">Öneri Notları</h3>
                    <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                      {selectedAdvice.notes_tr.map((note) => (
                        <li key={note}>• {note}</li>
                      ))}
                    </ul>
                    {selectedAdvice.can_delete ? (
                      <Button
                        className="mt-4"
                        variant="outline"
                        size="sm"
                        disabled={deleteJobMutation.isPending}
                        onClick={() => deleteJobMutation.mutate(selectedJob.id)}
                      >
                        Bu Kaydı Temizle
                      </Button>
                    ) : null}
                  </div>
                ) : null}
                <div>
                  <h3 className="text-sm font-semibold mb-3">Olay Akışı</h3>
                  <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
                    {events.data?.length === 0 ? <EmptyState text="Bu job için olay kaydı yok." /> : null}
                    {events.data?.map((event: JobEventRecord) => (
                      <div key={event.id} className="rounded-xl border border-white/5 bg-background/60 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-medium">{event.message}</div>
                          <div className="text-xs text-muted-foreground">{new Date(event.created_at).toLocaleTimeString("tr-TR")}</div>
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">{event.event_type}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState text="Log görüntülemek için bir job seçin." />
            )}
          </section>
        </div>
      ) : (
        <div className="p-8 max-w-[1600px] mx-auto w-full">
          <div className="glass-panel rounded-2xl overflow-hidden">
            <div className="border-b border-white/5 p-5">
              <h2 className="text-base font-semibold">Tüm Sistem Aktiviteleri</h2>
              <p className="mt-1 text-sm text-muted-foreground">{allActivities.length} işlem kaydı</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-muted/50 border-b border-white/5">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Zaman</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Tip</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">İşlem</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Durum</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">İlerleme</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Detay</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {allActivities.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                        Henüz aktivite kaydı yok
                      </td>
                    </tr>
                  ) : null}
                  {allActivities.map((activity) => (
                    <tr key={activity.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3 text-sm text-muted-foreground whitespace-nowrap">
                        {new Date(activity.timestamp).toLocaleString("tr-TR", {
                          day: "2-digit",
                          month: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit"
                        })}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <span className="inline-flex items-center px-2 py-1 rounded-md bg-primary/10 text-primary text-xs font-medium">
                          {activity.type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm font-medium">{activity.title}</td>
                      <td className="px-4 py-3 text-sm">
                        <StatusPill status={activity.status} />
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {activity.progress > 0 ? `%${Math.round(activity.progress)}` : "-"}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground max-w-xs truncate">
                        {activity.details ?? "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    completed: "text-primary border-primary/30 bg-primary/10",
    failed: "text-destructive border-destructive/30 bg-destructive/10",
    running: "text-yellow-500 border-yellow-500/30 bg-yellow-500/10",
    queued: "text-blue-500 border-blue-500/30 bg-blue-500/10",
    pending: "text-blue-500 border-blue-500/30 bg-blue-500/10",
    cancelled: "text-gray-500 border-gray-500/30 bg-gray-500/10",
    info: "text-cyan-500 border-cyan-500/30 bg-cyan-500/10"
  };
  const color = colorMap[status] ?? "text-muted-foreground border-muted/30 bg-muted/10";
  const label: Record<string, string> = {
    queued: "Kuyrukta",
    pending: "Bekliyor",
    running: "Çalışıyor",
    completed: "Tamamlandı",
    failed: "Hata",
    cancelled: "İptal",
    info: "Bilgi"
  };
  return <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${color}`}>{label[status] ?? status}</span>;
}

type AttachmentType = 'text' | 'pdf' | 'image';

interface Attachment {
  id: string;
  name: string;
  type: AttachmentType;
  content: string;
  size: number;
  status: 'processing' | 'ready' | 'error';
  preview?: string;
}

function ChatWorkspaceScreen({ models }: { models: ModelRecord[] }) {
  const ollamaModels = useMemo(() => models.filter((model) => model.source === "ollama"), [models]);
  const [messages, setMessages] = useState<{ role: "assistant" | "user", content: string }[]>([
    { role: "assistant", content: "Merhaba! Seçtiğiniz Ollama modeliyle sohbet edebilir, metin, PDF ve imaj dosyalarını bağlam olarak ekleyebilir ve üretilen artefact kayıtlarını takip edebilirsiniz." }
  ]);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    if (!selectedModelId && ollamaModels[0]?.id) {
      setSelectedModelId(ollamaModels[0].id);
    }
    if (selectedModelId && !ollamaModels.some((model) => model.id === selectedModelId)) {
      setSelectedModelId(ollamaModels[0]?.id ?? "");
    }
  }, [ollamaModels, selectedModelId]);

  const processDroppedPaths = async (paths: string[]) => {
    for (const path of paths) {
      const fileName = path.split('/').pop() || path.split('\\').pop() || 'file';
      const id = crypto.randomUUID();
      const ext = fileName.toLowerCase().split('.').pop() || '';
      const type: AttachmentType = ext === 'pdf' ? 'pdf' : 'text';
      setAttachments(prev => [...prev, {
        id,
        name: fileName,
        type,
        content: "",
        size: 0,
        status: 'processing'
      }]);

      try {
        const content = await api.readContextFile(path);
        setAttachments(prev => prev.map(a =>
          a.id === id ? { ...a, content, status: 'ready' as const, size: content.length } : a
        ));
      } catch {
        setAttachments(prev => prev.map(a =>
          a.id === id ? { ...a, status: 'error' as const } : a
        ));
      }
    }
  };

  useEffect(() => {
    let cancelled = false;
    let unlisten: (() => void) | undefined;

    try {
      getCurrentWebview().onDragDropEvent((event: any) => {
        if (event.payload.type === 'over') {
          setDragActive(true);
          return;
        }
        if (event.payload.type === 'drop') {
          setDragActive(false);
          void processDroppedPaths(event.payload.paths ?? []);
          return;
        }
        setDragActive(false);
      }).then((handler) => {
        if (cancelled) {
          handler();
          return;
        }
        unlisten = handler;
      });
    } catch {
      setDragActive(false);
    }

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);

  const clearSession = () => {
    setMessages([
      { role: "assistant", content: "Merhaba! Seçtiğiniz Ollama modeliyle sohbet edebilir, metin, PDF ve imaj dosyalarını bağlam olarak ekleyebilir ve üretilen artefact kayıtlarını takip edebilirsiniz." }
    ]);
    setAttachments([]);
    setInput("");
  };

  const handleSend = async () => {
    if (!input.trim() || isTyping) return;
    const userMsg = input;
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setInput("");
    setIsTyping(true);
    
    try {
      if (!selectedModelId) {
        throw new Error(
          "Chat için en az bir Ollama modeli içe aktarın. Model Hub > Ollama Keşfet ile yüklü modelleri ekleyebilirsiniz."
        );
      }
      
      const context = attachments
        .filter((attachment) => attachment.status === 'ready' && attachment.content)
        .map((attachment) => {
          if (attachment.type === 'image') {
            return `\n\n[İmaj: ${attachment.name}]\n[Bu bir görsel dosyadır. Vision model kullanarak analiz edilebilir.]`;
          }
          return `\n\n[Dosya: ${attachment.name}]\n${attachment.content.slice(0, 6000)}`;
        })
        .join("");
      const images = attachments
        .filter((attachment) => attachment.type === "image" && attachment.status === "ready")
        .map((attachment) => attachment.content.replace(/^data:image\/[^;]+;base64,/, ""));
      const res = await api.chat(selectedModelId, `${userMsg}${context}`, images);
      setMessages(prev => [...prev, { role: "assistant", content: res.response }]);
    } catch (e: any) {
      setMessages(prev => [...prev, { role: "assistant", content: `Hata: ${e?.message ?? String(e)}` }]);
    } finally {
      setIsTyping(false);
    }
  };

  const readImageAsBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  const handleAttachment = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    for (const file of Array.from(files)) {
      const id = crypto.randomUUID();
      
      // İmaj dosyaları
      if (file.type.startsWith('image/')) {
        setAttachments(prev => [...prev, {
          id,
          name: file.name,
          type: 'image',
          content: '',
          size: file.size,
          status: 'processing'
        }]);
        
        try {
          const base64 = await readImageAsBase64(file);
          setAttachments(prev => prev.map(a => 
            a.id === id ? { ...a, content: base64, status: 'ready' as const, preview: base64 } : a
          ));
        } catch {
          setAttachments(prev => prev.map(a => 
            a.id === id ? { ...a, status: 'error' as const } : a
          ));
        }
        continue;
      }
      
      const supportedDocuments = [".txt", ".md", ".json", ".jsonl", ".csv", ".log", ".pdf"];
      if (supportedDocuments.some((suffix) => file.name.toLowerCase().endsWith(suffix))) {
        setAttachments(prev => [...prev, {
          id,
          name: file.name,
          type: file.name.toLowerCase().endsWith(".pdf") ? 'pdf' : 'text',
          content: '',
          size: file.size,
          status: 'processing'
        }]);
        
        try {
          const extracted = await api.extractContextFile(file);
          setAttachments(prev => prev.map(a => 
            a.id === id
              ? {
                  ...a,
                  type: extracted.type === "pdf" ? "pdf" : "text",
                  content: extracted.content,
                  status: 'ready' as const,
                  size: extracted.size,
                }
              : a
          ));
        } catch {
          setAttachments(prev => prev.map(a => 
            a.id === id ? { ...a, status: 'error' as const } : a
          ));
        }
        continue;
      }
    }
  };

  const removeAttachment = (id: string) => {
    setAttachments(prev => prev.filter(a => a.id !== id));
  };

  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      // Only deactivate if leaving the drop zone entirely
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX;
      const y = e.clientY;
      if (x <= rect.left || x >= rect.right || y <= rect.top || y >= rect.bottom) {
        setDragActive(false);
      }
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleAttachment(e.dataTransfer.files);
      e.dataTransfer.clearData();
    }
  };

  return (
    <div 
      className="flex h-screen flex-col"
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
    >
      <Header title="Chat & Workspace" description="Bağlam destekli (RAG) otonom model etkileşimi ve kod alanı." />
      
      {/* Drag Overlay */}
      {dragActive && (
        <div className="fixed inset-0 z-50 bg-primary/10 backdrop-blur-sm flex items-center justify-center pointer-events-none">
          <div className="glass-panel p-12 rounded-3xl border-2 border-primary border-dashed animate-pulse">
            <Boxes className="size-16 text-primary mx-auto mb-4 animate-bounce" />
            <p className="text-2xl font-bold text-primary">Dosyaları Buraya Bırakın</p>
            <p className="text-sm text-muted-foreground mt-2">TXT, PDF, MD, İmaj dosyaları destekleniyor</p>
          </div>
        </div>
      )}
      
      <div className="flex flex-1 overflow-hidden p-6 gap-6 max-w-[1600px] mx-auto w-full">
        {/* Chat Area */}
        <div className="flex-1 flex flex-col glass-panel rounded-2xl overflow-hidden border border-white/5">
          {/* Chat Header with Session Controls */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-white/5 bg-background/30">
            <div className="flex items-center gap-2">
              <BrainCircuit className="size-4 text-primary" />
              <span className="text-sm font-medium">Chat Session</span>
            </div>
            <div className="flex gap-2">
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={clearSession}
                className="text-xs h-7"
                title="Yeni session başlat"
              >
                🔄 Yeni Session
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => {
                  if (confirm("Tüm konuşma geçmişi silinecek. Emin misiniz?")) {
                    clearSession();
                  }
                }}
                className="text-xs h-7 text-destructive hover:text-destructive"
                title="Konuşma geçmişini temizle"
              >
                🗑️ Temizle
              </Button>
            </div>
          </div>
          
          <div className="flex-1 p-6 overflow-y-auto space-y-4">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex gap-4 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                <div className={`size-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === "user" ? "bg-accent/20" : "bg-primary/20"}`}>
                  {msg.role === "user" ? <div className="size-4 rounded-full bg-accent" /> : <BrainCircuit className="size-4 text-primary" />}
                </div>
                <div className={`bg-white/5 border border-white/10 rounded-2xl p-4 text-sm text-foreground/90 max-w-[80%] ${msg.role === "user" ? "rounded-tr-sm bg-accent/10" : "rounded-tl-sm"}`}>
                  {msg.content}
                </div>
              </div>
            ))}
            {isTyping && (
              <div className="flex gap-4">
                <div className="size-8 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                  <BrainCircuit className="size-4 text-primary animate-pulse" />
                </div>
                <div className="bg-white/5 border border-white/10 rounded-2xl rounded-tl-sm p-4 text-sm text-foreground/90 flex items-center gap-1">
                  <div className="size-1.5 bg-primary/50 rounded-full animate-bounce" />
                  <div className="size-1.5 bg-primary/50 rounded-full animate-bounce [animation-delay:0.2s]" />
                  <div className="size-1.5 bg-primary/50 rounded-full animate-bounce [animation-delay:0.4s]" />
                </div>
              </div>
            )}
          </div>
          <div className="p-4 border-t border-white/5 bg-background/50">
            <div className="flex gap-3">
              <select
                value={selectedModelId}
                onChange={(event) => setSelectedModelId(event.target.value)}
                className="bg-background/80 border border-white/10 rounded-xl px-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary w-56"
              >
                {ollamaModels.length === 0 ? <option value="">Ollama modeli yok</option> : null}
                {ollamaModels.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
              <div className="flex-1 flex items-center bg-background/80 border border-white/10 rounded-xl px-3 focus-within:ring-1 focus-within:ring-primary">
                <input 
                  type="text" 
                  placeholder="Prompt veya '/' ile komut yazın..." 
                  className="flex-1 bg-transparent border-none focus:outline-none py-2 text-sm" 
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                />
                <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg hover:bg-white/10">
                  <label className="flex h-full w-full cursor-pointer items-center justify-center" title="Dosya bağlamı ekle (TXT, PDF, İmaj)">
                    <FileText className="size-4" />
                    <input
                      type="file"
                      className="hidden"
                      accept=".txt,.md,.json,.jsonl,.csv,.log,.pdf,image/*"
                      multiple
                      onChange={(event) => handleAttachment(event.target.files)}
                    />
                  </label>
                </Button>
              </div>
              <Button onClick={handleSend} disabled={isTyping || !input.trim()}>Gönder</Button>
            </div>
          </div>
        </div>

        {/* Tools & Sandbox Sidebar */}
        <div className={`w-[340px] flex flex-col gap-4`}>
          <div
            className={`glass-panel p-5 rounded-2xl flex-1 border border-white/5 ${dragActive ? "border-primary bg-primary/5" : ""}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <h3 className="font-semibold flex items-center gap-2 mb-4"><Cpu className="size-4 text-primary" /> Araçlar (Tool Calling)</h3>
            <div className="space-y-3">
              <label className="flex items-center gap-3 p-3 rounded-xl border border-white/5 bg-white/5 hover:bg-white/10 cursor-pointer transition-colors">
                <input type="checkbox" className="rounded border-white/20 bg-transparent text-primary focus:ring-primary/50" defaultChecked />
                <div className="text-sm">Web Arama (DuckDuckGo)</div>
              </label>
              <label className="flex items-center gap-3 p-3 rounded-xl border border-white/5 bg-white/5 hover:bg-white/10 cursor-pointer transition-colors">
                <input type="checkbox" className="rounded border-white/20 bg-transparent text-primary focus:ring-primary/50" defaultChecked />
                <div className="text-sm">Yerel Kod Yürütme (Sandbox)</div>
              </label>
              <label className="flex items-center gap-3 p-3 rounded-xl border border-white/5 bg-white/5 hover:bg-white/10 cursor-pointer transition-colors">
                <input type="checkbox" className="rounded border-white/20 bg-transparent text-primary focus:ring-primary/50" />
                <div className="text-sm">Dosya Sistemi Erişimi</div>
              </label>
            </div>
          </div>
          <div className="glass-panel p-5 rounded-2xl flex-1 border border-white/5">
            <h3 className="font-semibold flex items-center gap-2 mb-4">
              <Boxes className="size-4 text-primary" /> Dosyalar & Bağlam
            </h3>
            <div className={`flex flex-col h-[calc(100%-2rem)] ${attachments.length === 0 ? 'items-center justify-center' : ''}`}>
              {attachments.length === 0 ? (
                <div className="text-center text-sm text-muted-foreground border-2 border-dashed rounded-xl p-8 border-white/10">
                  <Boxes className="size-8 mb-2 opacity-50 mx-auto" />
                  <p className="font-medium">Dosya sürükle-bırak</p>
                  <p className="text-xs mt-1">veya gönder alanındaki doküman butonunu kullan</p>
                  <p className="text-xs mt-2 opacity-70">TXT, PDF, MD, İmaj</p>
                </div>
              ) : (
                <div className="w-full space-y-2 text-left overflow-y-auto">
                  {attachments.map((attachment) => (
                    <div key={attachment.id} className="rounded-xl border border-white/5 bg-white/5 p-3 group hover:bg-white/10 transition-colors">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            {attachment.type === 'image' && <span className="text-xs">🖼️</span>}
                            {attachment.type === 'pdf' && <span className="text-xs">📄</span>}
                            {attachment.type === 'text' && <span className="text-xs">📝</span>}
                            <div className="text-sm font-medium truncate">{attachment.name}</div>
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {attachment.status === 'processing' && '⏳ İşleniyor...'}
                            {attachment.status === 'ready' && `✓ Hazır (${(attachment.size / 1024).toFixed(1)} KB)`}
                            {attachment.status === 'error' && '✗ Hata'}
                          </div>
                        </div>
                        <button
                          onClick={() => removeAttachment(attachment.id)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive p-1"
                          title="Kaldır"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                      {attachment.type === 'image' && attachment.preview && (
                        <img src={attachment.preview} alt={attachment.name} className="mt-2 rounded-lg max-h-24 object-cover" />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

type FineTuneSuggestion = {
  method: string;
  framework: string;
  epochs: number;
  batchSize: number;
  learningRate: string;
  loraRank: number;
  title: string;
  reasons: string[];
  warnings: string[];
};

function buildFineTuneSuggestion(
  model: ModelRecord | undefined,
  dataset: DatasetRecord | undefined,
): FineTuneSuggestion {
  const params = Number(model?.parameter_count ?? 0);
  const quantization = String(model?.quantization ?? "").toLowerCase();
  const taskType = String(dataset?.task_type ?? "").toLowerCase();
  const rows = Number(dataset?.row_count ?? 0);
  const duplicateRatio = Number(dataset?.duplicate_ratio ?? 0);
  const reasons: string[] = [];
  const warnings: string[] = [];

  let method = "lora";
  let framework = "peft";
  let epochs = 3;
  let batchSize = 4;
  let learningRate = "2e-4";
  let loraRank = 16;

  if (model?.source === "ollama") {
    warnings.push(
      "Ollama kayıtları inference içindir. Eğitim için aynı modelin HuggingFace veya yerel ağırlık kaydı daha uygundur."
    );
  }
  if (params >= 7_000_000_000 || quantization.includes("q4") || quantization.includes("q5")) {
    method = "qlora";
    framework = "peft";
    batchSize = 1;
    learningRate = "1e-4";
    loraRank = 16;
    reasons.push("Model büyük veya quantized görünüyor; tüketici donanımı için QLoRA daha güvenli.");
  } else if (params > 0 && params <= 3_000_000_000) {
    method = "lora";
    framework = "peft";
    batchSize = 4;
    learningRate = "2e-4";
    loraRank = 32;
    reasons.push("Model küçük/orta ölçekte; LoRA iyi hız-kalite dengesi verir.");
  } else {
    reasons.push("Model boyutu bilinmiyor; güvenli başlangıç için LoRA + PEFT önerildi.");
  }

  if (taskType.includes("preference") || taskType.includes("dpo")) {
    method = "dpo";
    framework = "trl";
    learningRate = "5e-5";
    reasons.push("Veri tercihe dayalı görünüyorsa DPO/TRL daha uygun olur.");
  }
  if (rows > 0 && rows < 500) {
    epochs = 5;
    batchSize = Math.min(batchSize, 2);
    warnings.push("Veri seti küçük; overfitting riskini izleyin ve Doctor validasyonu çalıştırın.");
  } else if (rows >= 5000) {
    epochs = 2;
    reasons.push("Veri seti yeterli büyüklükte; daha az epoch genellikle daha stabil başlar.");
  }
  if (duplicateRatio > 0.1) {
    warnings.push("Tekrar oranı yüksek; eğitimden önce Model Doktoru ile tekrarları temizleyin.");
  }

  return {
    method,
    framework,
    epochs,
    batchSize,
    learningRate,
    loraRank,
    title: `${method.toUpperCase()} + ${framework.toUpperCase()} önerisi`,
    reasons: reasons.length ? reasons : ["Güvenli başlangıç profili seçildi."],
    warnings,
  };
}

function FineTuningScreen({ models, datasets }: { models: ModelRecord[], datasets: DatasetRecord[] }) {
  const queryClient = useQueryClient();
  const [modelId, setModelId] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [method, setMethod] = useState("lora");
  const [framework, setFramework] = useState("peft");
  const [epochs, setEpochs] = useState(3);
  const [batchSize, setBatchSize] = useState(4);
  const [learningRate, setLearningRate] = useState("2e-4");
  const [loraRank, setLoraRank] = useState(16);
  const [plan, setPlan] = useState<FineTunePlan | null>(null);
  const [dataSource, setDataSource] = useState<"dataset" | "documents">("dataset");
  const [documents, setDocuments] = useState<Array<{ id: string; name: string; size: number; status: string; file: File }>>([]);
  const activeModelId = modelId || models[0]?.id || "";
  const activeDatasetId = datasetId || datasets[0]?.id || "";
  const activeModel = models.find((model) => model.id === activeModelId);
  const activeDataset = datasets.find((dataset) => dataset.id === activeDatasetId);
  const tuningSuggestion = useMemo(
    () => buildFineTuneSuggestion(activeModel, activeDataset),
    [activeModel, activeDataset],
  );
  const runs = useQuery({ queryKey: ["training-runs"], queryFn: api.listTrainingRuns, refetchInterval: 3000 });
  
  const handleDocumentUpload = async (files: FileList | null) => {
    if (!files) return;
    const newDocs = Array.from(files).map(f => ({
      id: crypto.randomUUID(),
      name: f.name,
      size: f.size,
      status: 'Yüklendi',
      file: f
    }));
    setDocuments(prev => [...prev, ...newDocs]);
  };
  
  const removeDocument = (id: string) => {
    setDocuments(prev => prev.filter(d => d.id !== id));
  };
  
  const payload = () => ({
    base_model_id: activeModelId,
    dataset_id: activeDatasetId,
    method,
    framework,
    epochs,
    batch_size: batchSize,
    learning_rate: Number(learningRate),
    max_seq_length: 2048,
    lora_rank: loraRank
  });
  const planMutation = useMutation({
    mutationFn: () => api.planTrainingRun(payload()),
    onSuccess: setPlan
  });
  const createRun = useMutation({
    mutationFn: () => api.createTrainingRun(payload()),
    onSuccess: async (created) => {
      setPlan(created.plan);
      await queryClient.invalidateQueries({ queryKey: ["training-runs"] });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
      await queryClient.invalidateQueries({ queryKey: ["models"] });
    }
  });
  const attachKnowledge = useMutation({
    mutationFn: () => api.attachKnowledgePack({
      model_id: activeModelId,
      dataset_id: activeDatasetId,
      name: `${models.find((model) => model.id === activeModelId)?.name ?? "Model"} bilgi paketi`
    }),
    onSuccess: async (result) => {
      addGlobalTask({
        id: `knowledge:${result.artifact_id}`,
        title: "Bilgi Paketi Bağlandı",
        progress: 100,
        status: "done",
        message: result.message_tr
      });
      await queryClient.invalidateQueries({ queryKey: ["models"] });
    }
  });

  return (
    <div className="flex h-screen flex-col overflow-y-auto">
      <Header title="Fine-Tuning Studio" description="LoRA/QLoRA eğitim planı, kalıcı run kaydı ve job kuyruğu yönetimi." />
      <div className="p-8 max-w-[1200px] mx-auto w-full grid grid-cols-3 gap-8">
        <div className="col-span-1 space-y-6">
          <div className="glass-panel p-5 rounded-2xl border border-white/5">
            <h3 className="font-semibold mb-4">1. Kaynak Seçimi</h3>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">Temel Model</label>
                <select value={activeModelId} onChange={(event) => setModelId(event.target.value)} className="w-full bg-background/50 border border-white/10 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                  {models.length === 0 ? <option value="">Model yok</option> : null}
                  {models.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
              </div>
              
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">Veri Kaynağı</label>
                <div className="flex gap-2 mb-3">
                  <button
                    onClick={() => setDataSource("dataset")}
                    className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                      dataSource === "dataset" 
                        ? "bg-primary text-primary-foreground" 
                        : "bg-background/50 border border-white/10 hover:bg-white/5"
                    }`}
                  >
                    Mevcut Veri Seti
                  </button>
                  <button
                    onClick={() => setDataSource("documents")}
                    className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                      dataSource === "documents" 
                        ? "bg-primary text-primary-foreground" 
                        : "bg-background/50 border border-white/10 hover:bg-white/5"
                    }`}
                  >
                    Dökümanlar
                  </button>
                </div>
                
                {dataSource === "dataset" ? (
                  <select value={activeDatasetId} onChange={(event) => setDatasetId(event.target.value)} className="w-full bg-background/50 border border-white/10 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                    {datasets.length === 0 ? <option value="">Veri seti yok</option> : null}
                    {datasets.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                  </select>
                ) : (
                  <div className="space-y-2">
                    <label className="flex items-center justify-center gap-2 w-full bg-background/50 border border-dashed border-white/10 rounded-xl px-3 py-3 text-sm hover:bg-white/5 cursor-pointer transition-colors">
                      <FileText className="size-4" />
                      <span>Döküman Yükle (TXT, PDF, MD)</span>
                      <input
                        type="file"
                        className="hidden"
                        accept=".txt,.md,.pdf"
                        multiple
                        onChange={(e) => handleDocumentUpload(e.target.files)}
                      />
                    </label>
                    {documents.length > 0 && (
                      <>
                        <div className="max-h-32 overflow-y-auto space-y-1">
                          {documents.map(doc => (
                            <div key={doc.id} className="flex items-center justify-between gap-2 bg-white/5 rounded-lg px-2 py-1.5 text-xs group">
                              <span className="truncate flex-1">{doc.name}</span>
                              <button
                                onClick={() => removeDocument(doc.id)}
                                className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive"
                              >
                                ×
                              </button>
                            </div>
                          ))}
                        </div>
                        <Button 
                          size="sm" 
                          className="w-full"
                          onClick={async () => {
                            const taskId = "doc-to-dataset";
                            addGlobalTask({
                              id: taskId,
                              title: "Dökümanlardan Veri Seti Oluşturuluyor...",
                              progress: 30,
                              status: "running"
                            });
                            try {
                              // Backend'e dökümanları gönder ve veri seti oluştur
                              const files = documents.map(d => d.file);
                              const datasetName = `Döküman Veri Seti ${new Date().toLocaleDateString('tr-TR')}`;
                              
                              updateGlobalTask(taskId, {
                                progress: 50,
                                message: "Dökümanlar işleniyor..."
                              });
                              
                              const dataset = await api.createDatasetFromDocuments(
                                files,
                                datasetName,
                                undefined,
                                "instruction"
                              );
                              
                              updateGlobalTask(taskId, {
                                progress: 100,
                                status: "done",
                                message: `${documents.length} döküman işlendi. Veri seti "${dataset.name}" oluşturuldu!`
                              });
                              
                              // Veri setlerini yenile
                              await queryClient.invalidateQueries({ queryKey: ["datasets"] });
                              
                              // Yeni oluşturulan veri setini seç
                              setDatasetId(dataset.id);
                              
                              // Dataset moduna geç
                              setDataSource("dataset");
                              setDocuments([]);
                            } catch (error: any) {
                              updateGlobalTask(taskId, {
                                status: "error",
                                message: `Hata: ${error.message}`
                              });
                            }
                          }}
                        >
                          📊 Veri Seti Oluştur ({documents.length} döküman)
                        </Button>
                      </>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {documents.length === 0 
                        ? "Dökümanları yükleyin, ardından veri seti oluşturun" 
                        : `${documents.length} döküman hazır - Veri seti oluşturmak için butona tıklayın`}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="glass-panel p-5 rounded-2xl border border-white/5">
            <h3 className="font-semibold mb-4">2. Optimizasyon & Hiperparametre</h3>
            <div className="space-y-4">
              <div className="rounded-xl border border-primary/20 bg-primary/5 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-primary">{tuningSuggestion.title}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {tuningSuggestion.reasons[0]}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setMethod(tuningSuggestion.method);
                      setFramework(tuningSuggestion.framework);
                      setEpochs(tuningSuggestion.epochs);
                      setBatchSize(tuningSuggestion.batchSize);
                      setLearningRate(tuningSuggestion.learningRate);
                      setLoraRank(tuningSuggestion.loraRank);
                    }}
                  >
                    Öneriyi Uygula
                  </Button>
                </div>
                {tuningSuggestion.warnings.length ? (
                  <div className="mt-2 space-y-1 text-xs text-yellow-200">
                    {tuningSuggestion.warnings.map((warning) => (
                      <div key={warning}>• {warning}</div>
                    ))}
                  </div>
                ) : null}
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">Eğitim Yöntemi (2026)</label>
                <select value={method} onChange={(event) => setMethod(event.target.value)} className="w-full bg-background/50 border border-white/10 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                  <optgroup label="🚀 2026 Yöntemleri">
                    <option value="grpo">GRPO (Group Relative Policy Optimization)</option>
                    <option value="dapo">DAPO (Distributed Adaptive Policy Optimization)</option>
                    <option value="rlvr">RLVR (RL with Verifiable Rewards)</option>
                    <option value="sdpo">SDPO (Self-Distillation Policy Optimization)</option>
                  </optgroup>
                  <optgroup label="⚡ Verimli Yöntemler">
                    <option value="lora">LoRA (Low-Rank Adaptation)</option>
                    <option value="qlora">QLoRA (Quantized LoRA)</option>
                  </optgroup>
                  <optgroup label="🎯 Tercih Optimizasyonu">
                    <option value="dpo">DPO (Direct Preference Optimization)</option>
                    <option value="orpo">ORPO (Odds Ratio Preference)</option>
                    <option value="kto">KTO (Kahneman-Tversky)</option>
                  </optgroup>
                  <optgroup label="🔄 Pekiştirmeli Öğrenme">
                    <option value="ppo">PPO (Proximal Policy Optimization)</option>
                    <option value="rlhf">RLHF (RL from Human Feedback)</option>
                    <option value="rlaif">RLAIF (RL from AI Feedback)</option>
                  </optgroup>
                  <optgroup label="🎓 Geleneksel">
                    <option value="sft">SFT (Supervised Fine-Tuning)</option>
                    <option value="full">Full Fine-Tune</option>
                  </optgroup>
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">Framework</label>
                <select value={framework} onChange={(event) => setFramework(event.target.value)} className="w-full bg-background/50 border border-white/10 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                  <option value="trl">TRL (Transformer RL)</option>
                  <option value="transformers">Transformers (HuggingFace)</option>
                  <option value="peft">PEFT (Parameter-Efficient)</option>
                  <option value="axolotl">Axolotl</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">Epochs</label>
                  <div className="flex overflow-hidden rounded-xl border border-white/10 bg-background/50">
                    <button
                      type="button"
                      className="px-3 text-sm hover:bg-white/10"
                      onClick={() => setEpochs(Math.max(1, epochs - 1))}
                    >
                      -
                    </button>
                    <input
                      type="number"
                      value={epochs}
                      min={1}
                      max={20}
                      onChange={(event) => setEpochs(Math.max(1, Number(event.target.value) || 1))}
                      className="w-full bg-transparent px-3 py-2 text-center text-sm outline-none"
                    />
                    <button
                      type="button"
                      className="px-3 text-sm hover:bg-white/10"
                      onClick={() => setEpochs(Math.min(20, epochs + 1))}
                    >
                      +
                    </button>
                  </div>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">Batch Size</label>
                  <div className="flex overflow-hidden rounded-xl border border-white/10 bg-background/50">
                    <button
                      type="button"
                      className="px-3 text-sm hover:bg-white/10"
                      onClick={() => setBatchSize(Math.max(1, batchSize - 1))}
                    >
                      -
                    </button>
                    <input
                      type="number"
                      value={batchSize}
                      min={1}
                      max={128}
                      onChange={(event) => setBatchSize(Math.max(1, Number(event.target.value) || 1))}
                      className="w-full bg-transparent px-3 py-2 text-center text-sm outline-none"
                    />
                    <button
                      type="button"
                      className="px-3 text-sm hover:bg-white/10"
                      onClick={() => setBatchSize(Math.min(128, batchSize + 1))}
                    >
                      +
                    </button>
                  </div>
                </div>
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">Learning Rate</label>
                <input type="text" value={learningRate} onChange={(event) => setLearningRate(event.target.value)} className="w-full bg-background/50 border border-white/10 rounded-xl px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">LoRA Rank</label>
                <div className="flex overflow-hidden rounded-xl border border-white/10 bg-background/50">
                  <button
                    type="button"
                    className="px-3 text-sm hover:bg-white/10"
                    onClick={() => setLoraRank(Math.max(1, loraRank - 1))}
                  >
                    -
                  </button>
                  <input
                    type="number"
                    value={loraRank}
                    min={1}
                    max={256}
                    onChange={(event) => setLoraRank(Math.max(1, Number(event.target.value) || 1))}
                    className="w-full bg-transparent px-3 py-2 text-center text-sm outline-none"
                  />
                  <button
                    type="button"
                    className="px-3 text-sm hover:bg-white/10"
                    onClick={() => setLoraRank(Math.min(256, loraRank + 1))}
                  >
                    +
                  </button>
                </div>
              </div>
            </div>
          </div>
          
          <Button variant="secondary" className="w-full gap-2" disabled={!activeModelId || !activeDatasetId || planMutation.isPending} onClick={() => planMutation.mutate()}>
            {planMutation.isPending ? <Loader2 className="size-4 animate-spin" /> : <Cpu className="size-4" />}
            Planı Hesapla
          </Button>
          <Button variant="outline" className="w-full gap-2" disabled={!activeModelId || !activeDatasetId || attachKnowledge.isPending} onClick={() => attachKnowledge.mutate()}>
            {attachKnowledge.isPending ? <Loader2 className="size-4 animate-spin" /> : <FileText className="size-4" />}
            Bilgi Paketini Modele Bağla
          </Button>
          <Button className="w-full gap-2 font-semibold shadow-lg shadow-primary/20" size="lg" disabled={!activeModelId || !activeDatasetId || createRun.isPending || Boolean(plan && !plan.ready)} onClick={() => createRun.mutate()}>
            {createRun.isPending ? <Loader2 className="size-4 animate-spin" /> : <Cpu className="size-4" />}
            Eğitim Job'ı Oluştur
          </Button>
          <MutationError error={planMutation.error} />
          <MutationError error={attachKnowledge.error} />
          <MutationError error={createRun.error} />
        </div>

        <div className="col-span-2 flex flex-col gap-6">
          <div className="grid grid-cols-3 gap-4">
            <Metric title="Tahmini VRAM" value={plan ? `${plan.estimated_vram_gb} GB` : "Plan bekleniyor"} />
            <Metric title="Tahmini Step" value={plan ? String(plan.estimated_steps) : "Plan bekleniyor"} />
            <Metric title="Durum" value={plan ? (plan.ready ? "Hazır" : "Riskli") : "Belirsiz"} />
          </div>
          {plan ? (
            <div className="glass-panel p-6 rounded-2xl border border-white/5">
              <h3 className="font-semibold mb-4">Eğitim Planı</h3>
              {(plan.config.knowledge_packs as any[])?.length ? (
                <div className="mb-4 rounded-xl border border-primary/20 bg-primary/5 p-3 text-sm">
                  {(plan.config.knowledge_packs as any[]).length} bilgi paketi bu modele bağlı.
                </div>
              ) : null}
              <List title="Uyarılar" items={plan.warnings.length ? plan.warnings : ["Bloklayıcı uyarı yok."]} />
              <List title="Öneriler" items={plan.recommendations} />
            </div>
          ) : null}
          <div className="glass-panel p-6 rounded-2xl border border-white/5">
            <h3 className="font-semibold mb-4">Training Run Kayıtları</h3>
            <div className="space-y-3 max-h-[420px] overflow-y-auto">
              {runs.data?.length === 0 ? <EmptyState text="Henüz training run yok." /> : null}
              {runs.data?.map((run: TrainingRunRecord) => (
                <div key={run.id} className="rounded-xl border border-white/5 bg-background/60 p-4">
                  <div className="flex items-center justify-between">
                    <div className="font-medium">{run.method.toUpperCase()} · {run.framework}</div>
                    <div className="flex items-center gap-2">
                      <StatusPill status={run.status} />
                      {run.status === "queued" && (
                        <Button 
                          size="sm" 
                          variant="destructive"
                          onClick={async () => {
                            try {
                              await api.cancelTrainingRun(run.id);
                              await queryClient.invalidateQueries({ queryKey: ["training-runs"] });
                            } catch (e: any) {
                              alert(`İptal hatası: ${e.message}`);
                            }
                          }}
                        >
                          İptal
                        </Button>
                      )}
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Run: {run.id.slice(0, 8)}... · Job: {run.job_id ? run.job_id.slice(0, 8) + "..." : "yok"}
                  </div>
                  {run.status === "queued" && (
                    <div className="mt-2 text-xs text-amber-500/80">
                      ⏳ Bu eğitim job kuyruğunda bekliyor. Job worker tarafından işlenecek.
                    </div>
                  )}
                  {run.status === "running" && (
                    <div className="mt-2 text-xs text-primary/80">
                      🔄 Eğitim devam ediyor. İşlem Logları'ndan detayları görebilirsiniz.
                    </div>
                  )}
                  {run.status === "completed" && (
                    <div className="mt-2 text-xs text-green-500/80">
                      ✓ Eğitim tamamlandı. Model Hub'dan yeni modeli görebilirsiniz.
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ObservabilityScreen() {
  const { data: hardware } = useQuery({
    queryKey: ["hardware"],
    queryFn: api.systemHardware,
    refetchInterval: 2000
  });

  return (
    <div className="flex h-screen flex-col overflow-y-auto">
      <Header title="Observability Dashboard" description="Canlı sistem metrikleri, RAM izleme ve Eğitim Kaybı (Training Loss) takibi." />
      <div className="p-8 max-w-[1400px] mx-auto w-full grid grid-cols-4 gap-6">
        <div className="col-span-4 grid grid-cols-4 gap-4">
          <Metric title="İşletim Sistemi" value={hardware ? formatOSName(hardware.os, hardware.os_version) : "Yükleniyor..."} />
          <Metric title="Sistem RAM" value={hardware ? formatRAM(hardware.ram_total_gb, hardware.ram_used_gb) : "Yükleniyor..."} />
          <Metric title="RAM Tüketimi" value={hardware ? `%${hardware.ram_percent}` : "Yükleniyor..."} />
          <Metric title="CPU Tüketimi" value={hardware ? `%${hardware.cpu_percent}` : "Yükleniyor..."} />
        </div>
        <div className="col-span-2 glass-panel p-6 rounded-2xl border border-white/5 h-[400px] flex flex-col">
          <h3 className="font-semibold mb-4 text-white">Canlı İşlemci (CPU) Grafiği</h3>
          <div className="flex-1 border border-white/10 bg-background/50 rounded-xl relative overflow-hidden flex items-end">
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-4xl font-black text-primary opacity-50">
                {hardware ? `%${hardware.cpu_percent}` : "..."}
              </div>
            </div>
            <div className="w-full flex justify-between items-end px-4 gap-1 opacity-70 h-full py-4 relative z-10">
              {[40, 50, 45, 60, 55, 70, 65, 80, 75, 90, 85, 70, 65, 60, 50, 45, (hardware?.cpu_percent ?? 40)].map((h, i) => (
                <div key={i} className="w-full bg-primary/40 rounded-t-sm transition-all duration-1000" style={{ height: `${h}%` }}></div>
              ))}
            </div>
          </div>
        </div>
        <div className="col-span-2 glass-panel p-6 rounded-2xl border border-white/5 h-[400px] flex flex-col">
          <h3 className="font-semibold mb-4 text-white">Eğitim Kaybı (Training Loss)</h3>
          <div className="flex-1 border border-white/10 bg-background/50 rounded-xl relative overflow-hidden flex items-end">
            <div className="w-full h-full p-4 relative">
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full stroke-accent fill-none stroke-[2] opacity-80">
                <path d="M 0 90 Q 20 80, 40 50 T 70 30 T 100 10" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ModelsScreen({ models }: { models: ModelRecord[] }) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string>("");
  const [analysis, setAnalysis] = useState<ModelAnalysis | null>(null);
  const [folderPath, setFolderPath] = useState("");
  const [repositoryId, setRepositoryId] = useState("");
  const [dropActive, setDropActive] = useState(false);

  const importFile = useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return api.importModelFile(formData);
    },
    onSuccess: async (model) => {
      setSelectedId(model.id);
      setAnalysis(model.analysis);
      await queryClient.invalidateQueries({ queryKey: ["models"] });
    }
  });

  const scanFolder = useMutation({
    mutationFn: () => api.scanModelFolder(folderPath),
    onSuccess: async (result) => {
      const firstImported = result.imported[0];
      if (firstImported) {
        setSelectedId(firstImported.id);
        setAnalysis(firstImported.analysis);
      }
      await queryClient.invalidateQueries({ queryKey: ["models"] });
    }
  });

  const discoverOllama = useMutation({
    mutationFn: api.discoverOllama,
    onSuccess: async (result) => {
      const firstImported = result.imported[0];
      if (firstImported) {
        setSelectedId(firstImported.id);
        setAnalysis(firstImported.analysis);
      }
      await queryClient.invalidateQueries({ queryKey: ["models"] });
    }
  });

  const registerHuggingFace = useMutation({
    mutationFn: () => api.registerHuggingFace(repositoryId),
    onSuccess: async (model) => {
      setRepositoryId("");
      setSelectedId(model.id);
      setAnalysis(model.analysis);
      await queryClient.invalidateQueries({ queryKey: ["models"] });
    }
  });

  const analyze = useMutation({
    mutationFn: (modelId: string) => api.analyzeModel(modelId),
    onSuccess: async (result) => {
      setAnalysis(result);
      await queryClient.invalidateQueries({ queryKey: ["models"] });
    }
  });

  const selectedModel = models.find((model) => model.id === selectedId) ?? models[0];
  const discoveryError =
    importFile.error ?? scanFolder.error ?? discoverOllama.error ?? registerHuggingFace.error;
  const hasOllamaModels = models.some((model) => model.source === "ollama");

  useEffect(() => {
    if (!hasOllamaModels && !discoverOllama.isPending && !discoverOllama.isSuccess) {
      discoverOllama.mutate();
    }
  }, [hasOllamaModels, discoverOllama.isPending, discoverOllama.isSuccess]);

  return (
    <>
      <Header
        title="Model Keşif Merkezi"
        description="Model dosyalarını, klasörleri, Ollama kurulumunu ve HuggingFace repolarını içe aktarın."
      />
      <div className="grid grid-cols-[460px_1fr] gap-8 p-8 max-w-[1600px] mx-auto">
        <section className="space-y-6">
          <div
            className={`glass-panel rounded-2xl p-6 transition-all duration-300 ${
              dropActive ? "border-primary bg-primary/10 shadow-[0_0_30px_rgba(var(--primary),0.2)]" : ""
            }`}
            onDragOver={(event) => {
              event.preventDefault();
              setDropActive(true);
            }}
            onDragLeave={() => setDropActive(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDropActive(false);
              const file = firstSupportedModelFile(event);
              if (file) {
                importFile.mutate(file);
              }
            }}
          >
            <div className="flex items-start gap-3">
              <HardDrive className="mt-1 size-5 text-primary" />
              <div>
                <h2 className="text-base font-semibold">Yerel Model İçe Aktar</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  `.gguf`, `.safetensors` veya `.bin` dosyasını buraya bırakın ya da dosya seçin.
                </p>
              </div>
            </div>
            <label className="mt-4 block">
              <input
                className="hidden"
                type="file"
                accept=".gguf,.safetensors,.bin"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) {
                    importFile.mutate(file);
                  }
                  event.target.value = "";
                }}
              />
              <span className="inline-flex h-9 cursor-pointer items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90">
                Dosya Seç
              </span>
            </label>
          </div>

          <div className="rounded-lg border border-border bg-card p-5">
            <div className="flex items-start gap-3">
              <FolderSearch className="mt-1 size-5 text-primary" />
              <div>
                <h2 className="text-base font-semibold">Klasör Tara</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Seçilen klasörde uyumlu model dosyaları aranır ve otomatik kaydedilir.
                </p>
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <input
                className="min-w-0 flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={folderPath}
                onChange={(event) => setFolderPath(event.target.value)}
                placeholder="/Users/me/models"
              />
              <Button
                variant="secondary"
                onClick={async () => {
                  const selected = await pickFolder();
                  if (selected) {
                    setFolderPath(selected);
                  }
                }}
              >
                Seç
              </Button>
            </div>
            <Button
              className="mt-3 w-full"
              disabled={scanFolder.isPending || !folderPath.trim()}
              onClick={() => scanFolder.mutate()}
            >
              {scanFolder.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Search className="mr-2 size-4" />}
              Klasörü Tara
            </Button>
            {scanFolder.data ? <DiscoverySummary result={scanFolder.data} /> : null}
          </div>

          <div className="rounded-lg border border-border bg-card p-5">
            <div className="flex items-start gap-3">
              <Server className="mt-1 size-5 text-primary" />
              <div>
                <h2 className="text-base font-semibold">Ollama Modellerini Bul</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Yerel `ollama list` çıktısı okunur ve kurulu modeller içe aktarılır.
                </p>
              </div>
            </div>
            <Button className="mt-4 w-full" disabled={discoverOllama.isPending} onClick={() => discoverOllama.mutate()}>
              {discoverOllama.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Server className="mr-2 size-4" />}
              Ollama'yı Tara
            </Button>
            {discoverOllama.data ? <DiscoverySummary result={discoverOllama.data} /> : null}
          </div>

          <div className="rounded-lg border border-border bg-card p-5">
            <div className="flex items-start gap-3">
              <BrainCircuit className="mt-1 size-5 text-primary" />
              <div>
                <h2 className="text-base font-semibold">HuggingFace Repo Kaydet</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Repo kimliğini girin; metadata çekilir ve model kaydı oluşturulur.
                </p>
              </div>
            </div>
            <form className="mt-4 space-y-3" onSubmit={(event) => submit(event, () => registerHuggingFace.mutate())}>
              <TextInput
                label="Repository ID"
                value={repositoryId}
                onChange={setRepositoryId}
                placeholder="Qwen/Qwen2.5-7B-Instruct"
                required
              />
              <Button className="w-full" disabled={registerHuggingFace.isPending || !repositoryId.trim()}>
                {registerHuggingFace.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                Metadata ile Kaydet
              </Button>
            </form>
          </div>

          <MutationError error={discoveryError} />
        </section>

        <section className="space-y-6">
          <div className="glass-panel rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-border p-4">
              <h2 className="text-base font-semibold">Keşfedilen Modeller</h2>
              <span className="text-sm text-muted-foreground">{models.length} kayıt</span>
            </div>
            <div className="divide-y divide-border">
              {models.length === 0 ? <EmptyState text="Henüz model kaydı yok." /> : null}
              {models.map((model) => (
                <button
                  key={model.id}
                  className="grid w-full grid-cols-[1fr_auto] gap-4 p-4 text-left hover:bg-muted"
                  onClick={() => {
                    setSelectedId(model.id);
                    setAnalysis(model.analysis);
                  }}
                >
                  <div>
                    <div className="font-medium">{model.name}</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      {model.source} · {model.model_family ?? "aile Bulunamadı"} · {formatParams(model.parameter_count)}
                    </div>
                  </div>
                  <span className="text-sm text-muted-foreground">{model.quantization ?? "quantization yok"}</span>
                </button>
              ))}
            </div>
          </div>

          {selectedModel ? (
            <div className="space-y-5 rounded-lg border border-border bg-card p-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold">{selectedModel.name}</h2>
                  <p className="text-sm text-muted-foreground">{selectedModel.path ?? selectedModel.provider_id ?? "kaynak bilgisi yok"}</p>
                </div>
                <Button onClick={() => analyze.mutate(selectedModel.id)} disabled={analyze.isPending}>
                  {analyze.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <BarChart3 className="mr-2 size-4" />}
                  Analiz Et
                </Button>
              </div>
              <ModelDetails model={selectedModel} />
              <LicenseNotesEditor model={selectedModel} />
              <AnalysisCards analysis={analysis ?? selectedModel.analysis} />
              <MutationError error={analyze.error} />
            </div>
          ) : null}
        </section>
      </div>
    </>
  );
}

function DiscoverySummary({
  result
}: {
  result: { imported: ModelRecord[]; skipped: string[]; errors: string[] };
}) {
  return (
    <div className="mt-3 rounded-md border border-border bg-background p-3 text-sm text-muted-foreground">
      <div>{result.imported.length} yeni model içe aktarıldı.</div>
      {result.skipped.length > 0 ? <div>{result.skipped.length} kayıt zaten vardı.</div> : null}
      {result.errors.length > 0 ? (
        <div className="mt-2 text-destructive">{result.errors.length} hata oluştu.</div>
      ) : null}
    </div>
  );
}

function ModelDetails({ model }: { model: ModelRecord }) {
  const memory = model.analysis?.memory_requirements ?? {};
  
  return (
    <div className="grid grid-cols-3 gap-3">
      <Metric title="Parametre Sayısı" value={formatParams(model.parameter_count)} />
      <Metric title="Context Length" value={model.context_length ? String(model.context_length) : "Model verisinde mevcut değil"} />
      <Metric title="Tokenizer" value={model.tokenizer ?? "Otomatik Algılandı"} />
      <Metric title="Architecture" value={model.architecture ?? "Bilinmiyor"} />
      <Metric title="Quantization" value={model.quantization ?? "Varsayılan (FP16/Ollama)"} />
      <Metric title="RAM Tahmini" value={formatMemory(memory.tahmini_inference_ram_gb)} />
      <Metric title="VRAM Tahmini" value={formatMemory(memory.tahmini_lora_ram_gb)} />
      <Metric title="Source Type" value={model.source} />
      <Metric title="Source Path" value={model.path ?? model.provider_id ?? "Sistemde yüklü"} />
      <Metric title="Dosya Boyutu" value={model.size_bytes ? formatBytes(model.size_bytes) : "API üzerinden okunuyor"} />
      <Metric title="Oluşturma Tarihi" value={model.metadata_json?.creation_date ? new Date(model.metadata_json.creation_date as string).toLocaleDateString() : (model.metadata_json?.modified_at ? new Date(model.metadata_json.modified_at as string).toLocaleDateString() : "Tarih bilgisi yok")} />
      
      {/* Gerçek Lisans Accordion */}
      <div className="rounded-lg border border-border bg-card p-4 col-span-3">
        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Lisans Detayları (Gerçek Lisans)</div>
        {model.actual_license ? (
          <details className="text-xs text-foreground/80 cursor-pointer [&_summary::-webkit-details-marker]:hidden">
            <summary className="font-medium hover:text-white transition-colors py-1 outline-none">
              Lisans Metnini Göster / Gizle
            </summary>
            <div className="mt-2 p-3 bg-black/20 rounded-md border border-white/5 whitespace-pre-wrap max-h-40 overflow-y-auto font-mono text-[10px] leading-relaxed">
              {model.actual_license}
            </div>
          </details>
        ) : (
          <div className="text-sm font-medium">Bilinmiyor</div>
        )}
      </div>

      <div className="col-span-3">
        <Metric title="Lisans Notu" value={model.user_license_notes ?? "Not yok"} />
      </div>
    </div>
  );
}

function LicenseNotesEditor({ model }: { model: ModelRecord }) {
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState(model.user_license_notes ?? "");
  const update = useMutation({
    mutationFn: (payload: { user_license_notes: string }) => api.updateModel(model.id, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["models"] });
    }
  });

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="text-sm font-semibold">Kullanıcı Lisans Notu</h3>
      <div className="mt-3 flex gap-2">
        <input
          className="min-w-0 flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Örn: Şirket içi kullanım onaylandı."
        />
        <Button
          variant="secondary"
          onClick={() => update.mutate({ user_license_notes: notes })}
          disabled={update.isPending}
        >
          {update.isPending ? <Loader2 className="size-4 animate-spin" /> : "Kaydet"}
        </Button>
      </div>
      <MutationError error={update.error} />
    </div>
  );
}

async function pickFolder() {
  try {
    const dialog = await import("@tauri-apps/plugin-dialog");
    const selected = await dialog.open({ directory: true, multiple: false });
    return typeof selected === "string" ? selected : null;
  } catch {
    return null;
  }
}

function firstSupportedModelFile(event: DragEvent<HTMLElement>) {
  const supported = [".gguf", ".safetensors", ".bin"];
  return Array.from(event.dataTransfer.files).find((file) =>
    supported.some((suffix) => file.name.toLowerCase().endsWith(suffix))
  );
}

function DatasetsScreen({ datasets }: { datasets: DatasetRecord[] }) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [publicRepo, setPublicRepo] = useState("");
  const [publicLimit, setPublicLimit] = useState(1000);
  const [publicImportMessage, setPublicImportMessage] = useState("");
  const catalog = useQuery({ queryKey: ["public-dataset-catalog"], queryFn: api.publicDatasetCatalog });

  const upload = useMutation({
    mutationFn: () => {
      if (!file) {
        throw new Error("Dosya seçilmedi.");
      }
      const formData = new FormData();
      formData.append("file", file);
      if (name.trim()) {
        formData.append("name", name.trim());
      }
      return api.uploadDataset(formData);
    },
    onSuccess: async (dataset) => {
      setSelectedId(dataset.id);
      setFile(null);
      setName("");
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
    }
  });

  const analyze = useMutation({
    mutationFn: (datasetId: string) => api.analyzeDataset(datasetId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
    }
  });

  const importPublic = useMutation({
    mutationFn: (item?: PublicDatasetCatalogItem) => {
      const repositoryId = item?.repository_id ?? publicRepo;
      setPublicImportMessage(
        `${repositoryId} HuggingFace üzerinden örnekleniyor. Büyük veri setlerinde bu işlem 10-30 saniye sürebilir.`
      );
      return api.importPublicDataset({
        repository_id: repositoryId,
        name: item?.title,
        task_type: item?.task_type ?? "instruction",
        max_rows: item?.recommended_limit ?? publicLimit
      });
    },
    onSuccess: async (dataset) => {
      setSelectedId(dataset.id);
      setPublicImportMessage(`${dataset.name} içe aktarıldı: ${dataset.row_count} örnek.`);
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
    onError: (error: any) => {
      setPublicImportMessage(
        `İçe aktarma tamamlanamadı: ${error?.message ?? "HuggingFace bağlantısını ve dataset formatını kontrol edin."}`
      );
    },
  });

  const augment = useMutation({
    mutationFn: (datasetId: string) => api.augmentDataset(datasetId),
    onSuccess: async (dataset) => {
      setSelectedId(dataset.id);
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
    }
  });

  const selected = datasets.find((dataset) => dataset.id === selectedId) ?? datasets[0];

  return (
    <>
      <Header title="Veri Seti Stüdyosu" description="JSON, JSONL, CSV, XLSX, TXT ve Parquet veri setlerini yükleyip analiz edin." />
      <div className="grid grid-cols-[380px_1fr] gap-8 p-8 max-w-[1600px] mx-auto">
        <section className="glass-panel rounded-2xl p-6">
          <h2 className="text-base font-semibold">Veri Seti Yükle</h2>
          <form className="mt-4 space-y-3" onSubmit={(event) => submit(event, () => upload.mutate())}>
            <TextInput label="Görünen ad" value={name} onChange={setName} placeholder="Boşsa dosya adı kullanılır" />
            <label className="block text-sm">
              <span className="text-muted-foreground">Dosya</span>
              <input
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2"
                type="file"
                accept=".json,.jsonl,.csv,.xlsx,.txt,.parquet"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <Button className="w-full" disabled={upload.isPending}>
              {upload.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <FileText className="mr-2 size-4" />}
              Yükle ve Analiz Et
            </Button>
            <MutationError error={upload.error} />
          </form>
          <div className="mt-6 border-t border-white/5 pt-5">
            <h3 className="text-sm font-semibold">Hugging Face Public Veri Setleri</h3>
            <p className="mt-1 text-xs text-muted-foreground">Gerçek public veri setlerinden satır limitiyle örnek alınır; sahte kayıt üretilmez.</p>
            <div className="mt-3 space-y-2">
              {catalog.data?.map((item) => (
                <button
                  key={item.repository_id}
                  className="w-full rounded-xl border border-white/5 bg-white/5 p-3 text-left hover:bg-white/10"
                  disabled={importPublic.isPending}
                  onClick={() => importPublic.mutate(item)}
                >
                  <div className="text-sm font-medium">{item.title}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{item.repository_id} · {item.description_tr}</div>
                </button>
              ))}
            </div>
            <div className="mt-4 grid grid-cols-[1fr_90px] gap-2">
              <input
                className="rounded-xl border border-white/10 bg-background/50 px-3 py-2 text-sm"
                placeholder="HF dataset id, örn: org/dataset"
                value={publicRepo}
                onChange={(event) => setPublicRepo(event.target.value)}
              />
              <input
                className="rounded-xl border border-white/10 bg-background/50 px-3 py-2 text-sm"
                type="number"
                min={10}
                max={20000}
                value={publicLimit}
                onChange={(event) => setPublicLimit(Number(event.target.value))}
              />
            </div>
            <Button className="mt-2 w-full" variant="secondary" disabled={importPublic.isPending || !publicRepo.trim()} onClick={() => importPublic.mutate(undefined)}>
              {importPublic.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Database className="mr-2 size-4" />}
              Public Dataset İçe Aktar
            </Button>
            {publicImportMessage ? (
              <div className="mt-3 rounded-xl border border-white/10 bg-background/60 p-3 text-xs text-muted-foreground">
                {publicImportMessage}
              </div>
            ) : null}
            <MutationError error={importPublic.error} />
          </div>
        </section>

        <section className="space-y-6">
          <div className="glass-panel rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/5 p-5">
              <h2 className="text-base font-semibold">Veri Setleri</h2>
              <span className="text-sm text-muted-foreground">{datasets.length} kayıt</span>
            </div>
            <div className="divide-y divide-border">
              {datasets.length === 0 ? <EmptyState text="Henüz veri seti yüklenmedi." /> : null}
              {datasets.map((dataset) => (
                <button
                  key={dataset.id}
                  className="grid w-full grid-cols-[1fr_auto] gap-4 p-4 text-left hover:bg-muted"
                  onClick={() => setSelectedId(dataset.id)}
                >
                  <div>
                    <div className="font-medium">{dataset.name}</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      {dataset.format.toUpperCase()} · {dataset.row_count} örnek · kalite {dataset.quality_score}/100
                    </div>
                  </div>
                  <span className="text-sm text-muted-foreground">{dataset.task_type ?? "görev yok"}</span>
                </button>
              ))}
            </div>
          </div>

          {selected ? (
            <div className="space-y-4 rounded-lg border border-border bg-card p-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold">{selected.name}</h2>
                  <p className="text-sm text-muted-foreground">{selected.report.summary_tr}</p>
                </div>
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => analyze.mutate(selected.id)} disabled={analyze.isPending}>
                    Yeniden Analiz Et
                  </Button>
                  <Button variant="outline" onClick={() => augment.mutate(selected.id)} disabled={augment.isPending}>
                    Public Veriyle Çoğalt
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-4 gap-3">
                <Metric title="Örnek" value={String(selected.row_count)} />
                <Metric title="Ortalama Token" value={String(selected.average_tokens)} />
                <Metric title="Tekrar" value={`%${(selected.duplicate_ratio * 100).toFixed(1)}`} />
                <Metric title="Boş Kayıt" value={`%${(selected.empty_ratio * 100).toFixed(1)}`} />
              </div>
              
              {selected.statistics?.dominant_language ? (
                <div className="grid grid-cols-2 gap-6 rounded-lg border border-border bg-background p-4 mt-4">
                  <div>
                    <h3 className="text-sm font-semibold mb-2">Dil Dağılımı</h3>
                    <div className="text-sm space-y-1 text-muted-foreground">
                      <div className="flex justify-between"><span>Türkçe:</span> <span>%{(selected.statistics.language_distribution as any)?.Türkçe ?? 0}</span></div>
                      <div className="flex justify-between"><span>İngilizce:</span> <span>%{(selected.statistics.language_distribution as any)?.İngilizce ?? 0}</span></div>
                    </div>
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold mb-2">Kalite Dağılımı</h3>
                    <div className="text-sm space-y-1 text-muted-foreground">
                      <div className="flex justify-between"><span>Yüksek (Puan ≥ 80):</span> <span className="text-primary font-medium">%{(selected.statistics.quality_distribution as any)?.Yüksek ?? 0}</span></div>
                      <div className="flex justify-between"><span>Orta (Puan ≥ 50):</span> <span className="text-yellow-500 font-medium">%{(selected.statistics.quality_distribution as any)?.Orta ?? 0}</span></div>
                      <div className="flex justify-between"><span>Düşük (Puan &lt; 50):</span> <span className="text-destructive font-medium">%{(selected.statistics.quality_distribution as any)?.Düşük ?? 0}</span></div>
                    </div>
                  </div>
                </div>
              ) : null}
              <List title="Bulgular" items={selected.report.findings ?? []} />
              <PreviewTable rows={selected.preview} />
              <MutationError error={analyze.error} />
              <MutationError error={augment.error} />
            </div>
          ) : null}
        </section>
      </div>
    </>
  );
}

function DoctorScreen({ models, datasets }: { models: ModelRecord[]; datasets: DatasetRecord[] }) {
  const queryClient = useQueryClient();
  const [modelId, setModelId] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [diagnosis, setDiagnosis] = useState<DoctorDiagnosis | null>(null);
  const [diagnosticMode, setDiagnosticMode] = useState<"basic" | "advanced">("basic");
  const activeModelId = modelId || models[0]?.id || "";
  const activeDatasetId = datasetId || datasets[0]?.id || "";
  const doctor = useMutation({
    mutationFn: () => {
      const resolvedModelId = modelId || models[0]?.id;
      const resolvedDatasetId = datasetId || datasets[0]?.id;
      if (!resolvedModelId || !resolvedDatasetId) {
        throw new Error("Tanılama için model ve veri seti seçilmelidir.");
      }
      return api.diagnose(resolvedModelId, resolvedDatasetId);
    },
    onSuccess: setDiagnosis
  });

  return (
    <>
      <Header title="Model Doktoru (2026 AI Diagnostics)" description="Gelişmiş model tanılama, otomatik hata tespiti ve akıllı düzeltme önerileri." />
      <div className="grid grid-cols-[380px_1fr] gap-8 p-8 max-w-[1600px] mx-auto">
        <section className="glass-panel rounded-2xl p-6">
          <h2 className="text-base font-semibold mb-4">Tanılama Girdileri</h2>
          
          {/* Diagnostic Mode Selector */}
          <div className="mb-4 p-3 rounded-xl border border-white/10 bg-white/5">
            <label className="text-xs text-muted-foreground mb-2 block">Tanılama Modu (2026)</label>
            <div className="flex gap-2">
              <button
                onClick={() => setDiagnosticMode("basic")}
                className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  diagnosticMode === "basic" 
                    ? "bg-primary text-white" 
                    : "bg-white/5 text-muted-foreground hover:bg-white/10"
                }`}
              >
                Temel
              </button>
              <button
                onClick={() => setDiagnosticMode("advanced")}
                className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  diagnosticMode === "advanced" 
                    ? "bg-primary text-white" 
                    : "bg-white/5 text-muted-foreground hover:bg-white/10"
                }`}
              >
                Gelişmiş AI
              </button>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {diagnosticMode === "basic" 
                ? "Hızlı temel kontroller" 
                : "LLM-as-Debugger + Trace-Based Analysis"}
            </p>
          </div>
          
          <div className="mt-4 space-y-3">
            <Select label="Model" value={modelId} onChange={setModelId} options={models.map((model) => ({ value: model.id, label: model.name }))} />
            <Select label="Veri seti" value={datasetId} onChange={setDatasetId} options={datasets.map((dataset) => ({ value: dataset.id, label: dataset.name }))} />
            <Button className="w-full" disabled={doctor.isPending || models.length === 0 || datasets.length === 0} onClick={() => doctor.mutate()}>
              {doctor.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Stethoscope className="mr-2 size-4" />}
              {diagnosticMode === "advanced" ? "AI Tanılama Başlat" : "Tanıla"}
            </Button>
            {models.length === 0 || datasets.length === 0 ? (
              <p className="text-sm text-muted-foreground">Tanılama için en az bir model ve bir veri seti gerekir.</p>
            ) : null}
            <MutationError error={doctor.error} />
          </div>
          
          {/* 2026 Diagnostic Categories */}
          <div className="mt-6 space-y-2">
            <h3 className="text-sm font-semibold text-muted-foreground mb-3">Otomatik Test Kategorileri</h3>
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs p-2 rounded-lg bg-white/5">
                <div className="size-2 rounded-full bg-green-500"></div>
                <span>Veri Kalitesi (Data Validation)</span>
              </div>
              <div className="flex items-center gap-2 text-xs p-2 rounded-lg bg-white/5">
                <div className="size-2 rounded-full bg-blue-500"></div>
                <span>Model Uyumluluğu (Compatibility)</span>
              </div>
              <div className="flex items-center gap-2 text-xs p-2 rounded-lg bg-white/5">
                <div className="size-2 rounded-full bg-yellow-500"></div>
                <span>Performans Analizi (Performance)</span>
              </div>
              <div className="flex items-center gap-2 text-xs p-2 rounded-lg bg-white/5">
                <div className="size-2 rounded-full bg-purple-500"></div>
                <span>Güvenlik Kontrolleri (Safety)</span>
              </div>
            </div>
          </div>
        </section>

        <section className="glass-panel rounded-2xl p-6">
          {diagnosis ? (
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <RiskIcon risk={diagnosis.risk_level} />
                <div className="flex-1">
                  <div className="text-sm text-muted-foreground">Risk Seviyesi</div>
                  <div className="text-2xl font-semibold">{diagnosis.risk_level}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Güven Skoru</div>
                  <div className="text-2xl font-semibold text-right">%{diagnosis.confidence_score}</div>
                </div>
              </div>
              <p className="text-sm text-muted-foreground">{diagnosis.summary_tr}</p>
              <List title="Nedenler" items={diagnosis.reasons} />
              <List title="Önerilen Aksiyonlar" items={diagnosis.recommendations} />
              
              <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 mt-4">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2 text-primary">
                  <Boxes className="size-4" /> Hızlı Çözüm Aksiyonları (YontAI Auto-Fix 2026)
                </h3>
                <p className="text-xs text-muted-foreground mb-3">
                  Tekil aksiyonlar veri seti veya model metadata kaydını günceller. Son adımda tüm kontrolleri
                  manifest olarak bağlayıp Doctor onaylı model varyantı kaydedebilirsiniz.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" className="bg-background/50 hover:bg-background" disabled={!activeModelId} onClick={async () => {
                    const tId = "fix1";
                    addGlobalTask({ id: tId, title: "Eksik Metadata Çekiliyor...", progress: 30, status: "running" });
                    try {
                      const result = await api.doctorFix("fetch_metadata", { model_id: activeModelId });
                      updateGlobalTask(tId, { progress: 100, status: "done", message: result.message_tr });
                      queryClient.invalidateQueries({ queryKey: ["models"] });
                    } catch (error: any) {
                      updateGlobalTask(tId, { status: "error", message: `Hata: ${error.message}` });
                    }
                  }}>
                    🔍 Metadata Tamamla
                  </Button>
                  <Button variant="outline" size="sm" className="bg-background/50 hover:bg-background" disabled={!activeDatasetId} onClick={async () => {
                    const tId = "fix2";
                    addGlobalTask({ id: tId, title: "Veri Seti Temizleniyor...", progress: 40, status: "running" });
                    try {
                      const result = await api.doctorFix("remove_duplicates", { dataset_id: activeDatasetId });
                      updateGlobalTask(tId, { progress: 100, status: "done", message: result.message_tr });
                      if (result.details?.dataset_id) {
                        setDatasetId(String(result.details.dataset_id));
                      }
                      queryClient.invalidateQueries({ queryKey: ["datasets"] });
                      doctor.mutate();
                    } catch (error: any) {
                      updateGlobalTask(tId, { status: "error", message: `Hata: ${error.message}` });
                    }
                  }}>
                    🧹 Tekrarları Temizle
                  </Button>
                  <Button variant="outline" size="sm" className="bg-background/50 hover:bg-background" disabled={!activeDatasetId} onClick={async () => {
                    const tId = "fix3";
                    addGlobalTask({ id: tId, title: "Kayıtlar Analiz Ediliyor...", progress: 60, status: "running" });
                    try {
                      const result = await api.doctorFix("remove_low_quality", { dataset_id: activeDatasetId });
                      updateGlobalTask(tId, { progress: 100, status: "done", message: result.message_tr });
                      if (result.details?.dataset_id) {
                        setDatasetId(String(result.details.dataset_id));
                      }
                      queryClient.invalidateQueries({ queryKey: ["datasets"] });
                      doctor.mutate();
                    } catch (error: any) {
                      updateGlobalTask(tId, { status: "error", message: `Hata: ${error.message}` });
                    }
                  }}>
                    ⚡ Kalitesiz Kayıtları Sil
                  </Button>
                  <Button variant="outline" size="sm" className="bg-background/50 hover:bg-background" disabled={!activeModelId || !activeDatasetId} onClick={async () => {
                    const tId = "fix4";
                    addGlobalTask({ id: tId, title: "AI Debugger Çalışıyor...", progress: 50, status: "running" });
                    try {
                      const result = await api.doctorFix("ai_self_diagnosis", { model_id: activeModelId, dataset_id: activeDatasetId });
                      updateGlobalTask(tId, { progress: 100, status: "done", message: result.message_tr });
                      queryClient.invalidateQueries({ queryKey: ["models"] });
                      doctor.mutate();
                    } catch (error: any) {
                      updateGlobalTask(tId, { status: "error", message: `Hata: ${error.message}` });
                    }
                  }}>
                    🤖 AI Self-Diagnosis
                  </Button>
                  <Button variant="outline" size="sm" className="bg-background/50 hover:bg-background" disabled={!activeDatasetId} onClick={async () => {
                    const tId = "fix5";
                    addGlobalTask({ id: tId, title: "Veri Validasyonu...", progress: 45, status: "running" });
                    try {
                      const result = await api.doctorFix("validate_dataset", { dataset_id: activeDatasetId });
                      updateGlobalTask(tId, { progress: 100, status: "done", message: result.message_tr });
                      queryClient.invalidateQueries({ queryKey: ["datasets"] });
                    } catch (error: any) {
                      updateGlobalTask(tId, { status: "error", message: `Hata: ${error.message}` });
                    }
                  }}>
                    ✓ Veri Validasyonu
                  </Button>
                  <Button variant="outline" size="sm" className="bg-background/50 hover:bg-background" disabled={!activeModelId} onClick={async () => {
                    const tId = "fix6";
                    addGlobalTask({ id: tId, title: "Trace Analizi...", progress: 55, status: "running" });
                    try {
                      const result = await api.doctorFix("trace_analysis", { model_id: activeModelId, dataset_id: activeDatasetId });
                      updateGlobalTask(tId, { progress: 100, status: "done", message: result.message_tr });
                      queryClient.invalidateQueries({ queryKey: ["models"] });
                    } catch (error: any) {
                      updateGlobalTask(tId, { status: "error", message: `Hata: ${error.message}` });
                    }
                  }}>
                    📊 Trace-Based Analysis
                  </Button>
                </div>
                <div className="mt-4 rounded-xl border border-white/10 bg-background/60 p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h4 className="text-sm font-semibold">Doctor’dan Geçmiş Model Kaydı</h4>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Metadata, veri validasyonu, AI self-diagnosis ve trace analizini tek manifestte
                        toplar. Ağırlık dosyası değişmez; bilgiyi ağırlıklara işlemek için Fine-Tuning
                        Studio’da eğitim/adaptor üretimi çalıştırılır.
                      </p>
                    </div>
                    <Button
                      size="sm"
                      disabled={!activeModelId || !activeDatasetId}
                      onClick={async () => {
                        const tId = `doctor-approve:${activeModelId}:${activeDatasetId}`;
                        addGlobalTask({
                          id: tId,
                          title: "Doctor kontrolleri çalışıyor...",
                          progress: 25,
                          status: "running"
                        });
                        try {
                          const result = await api.doctorFix("doctor_approve_model", {
                            model_id: activeModelId,
                            dataset_id: activeDatasetId
                          });
                          updateGlobalTask(tId, {
                            progress: 100,
                            status: "done",
                            message: result.message_tr
                          });
                          queryClient.invalidateQueries({ queryKey: ["models"] });
                          queryClient.invalidateQueries({ queryKey: ["datasets"] });
                          doctor.mutate();
                        } catch (error: any) {
                          updateGlobalTask(tId, { status: "error", message: `Hata: ${error.message}` });
                        }
                      }}
                    >
                      Doctor Modeli Kaydet
                    </Button>
                  </div>
                </div>
              </div>

              <Metric title="Beklenen Etki" value={diagnosis.expected_impact} />
            </div>
          ) : (
            <EmptyState text="Model ve veri seti seçip tanılama başlatın." />
          )}
        </section>
      </div>
    </>
  );
}

function AnalysisCards({ analysis }: { analysis: ModelAnalysis | null }) {
  if (!analysis) {
    return <EmptyState text="Bu model için henüz analiz çalıştırılmadı." />;
  }
  return (
    <div className="mt-5 space-y-4">
      <p className="text-sm text-muted-foreground">{analysis.summary_tr}</p>
      <div className="grid grid-cols-2 gap-4">
        <List title="Güçlü Yönler" items={analysis.strengths} positive />
        <List title="Zayıf Yönler" items={analysis.weaknesses} />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Metric title="Mimari" value={String(analysis.details.mimari ?? "Bulunamadı")} />
        <Metric title="Context" value={String(analysis.details.context_length ?? "Bulunamadı")} />
        <Metric title="Inference RAM" value={String(analysis.memory_requirements.tahmini_inference_ram_gb ?? "Bulunamadı")} />
      </div>
      {analysis.details.capabilities ? (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3">Model Yetenek Profili</h3>
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(analysis.details.capabilities as Record<string, number>).map(([key, score]) => (
              <div key={key}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground">{key}</span>
                  <span className="font-medium">{score}/100</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div className="h-full bg-primary" style={{ width: `${score}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {analysis.details.metadata_coverage ? (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3">Metadata Kalite Raporu</h3>
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm text-muted-foreground">Metadata Kalitesi</span>
            <span className="text-lg font-bold">%{((analysis.details.metadata_coverage as any).quality_score ?? 0)}</span>
          </div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted-foreground">Toplanan Alanlar</span>
            <span className="text-sm font-medium">
              {((analysis.details.metadata_coverage as any).filled_count ?? 0)} / {((analysis.details.metadata_coverage as any).total_count ?? 0)}
            </span>
          </div>
          {((analysis.details.metadata_coverage as any).missing_fields?.length ?? 0) > 0 ? (
            <div className="mt-3">
              <span className="text-sm font-medium text-muted-foreground">Eksik Alanlar:</span>
              <ul className="mt-1 list-disc list-inside text-sm text-destructive">
                {((analysis.details.metadata_coverage as any).missing_fields as string[]).map(field => (
                  <li key={field}>{field}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function PreviewTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) {
    return <EmptyState text="Önizlenecek kayıt yok." />;
  }
  const columns = Object.keys(rows[0]).slice(0, 5);
  return (
    <div className="overflow-hidden rounded-md border border-border">
      <table className="w-full table-fixed text-sm">
        <thead className="bg-muted text-muted-foreground">
          <tr>{columns.map((column) => <th key={column} className="px-3 py-2 text-left font-medium">{column}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.slice(0, 8).map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column} className="truncate px-3 py-2">{String(row[column] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Metric({ title, value }: { title: string; value: string }) {
  return (
    <div className="glass-panel rounded-2xl p-5 hover:bg-white/[0.02] transition-colors">
      <div className="text-sm font-medium text-muted-foreground mb-3">{title}</div>
      <div className="break-words text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/70">{value}</div>
    </div>
  );
}

function List({ title, items, positive = false }: { title: string; items: string[]; positive?: boolean }) {
  return (
    <div className="glass-panel rounded-2xl p-5">
      <h3 className="text-sm font-semibold mb-4">{title}</h3>
      <ul className="space-y-3 text-sm text-muted-foreground">
        {items.map((item) => (
          <li key={item} className="flex gap-3 items-start">
            {positive ? <CheckCircle2 className="mt-0.5 size-4 text-primary shrink-0" /> : <AlertTriangle className="mt-0.5 size-4 text-accent shrink-0" />}
            <span className="leading-relaxed">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TextInput({
  label,
  value,
  onChange,
  placeholder,
  required
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="text-muted-foreground">{label}</span>
      <input
        className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
      />
    </label>
  );
}

function Select({
  label,
  value,
  onChange,
  options
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="block text-sm">
      <span className="text-muted-foreground">{label}</span>
      <select className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Seçin</option>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="p-5 text-sm text-muted-foreground">{text}</div>;
}

function ErrorBanner({ message }: { message: string }) {
  const isLoadFailed = message.toLowerCase().includes("load failed");
  const displayMessage = isLoadFailed
    ? "Backend bağlantısı kurulamadı. Lütfen FastAPI sunucusunun (uvicorn) 8765 portunda çalıştığından emin olun."
    : message;
  
  return (
    <div className="rounded-2xl border border-destructive/50 bg-destructive/10 p-5 text-sm text-destructive flex items-center gap-3 shadow-lg shadow-destructive/5">
      <AlertTriangle className="size-5 shrink-0" />
      <div>
        <div className="font-semibold mb-1">Bağlantı Hatası</div>
        <div>{displayMessage}</div>
      </div>
    </div>
  );
}

function MutationError({ error }: { error: unknown }) {
  if (!(error instanceof Error)) {
    return null;
  }
  return <p className="text-sm text-destructive">{error.message}</p>;
}

function RiskIcon({ risk }: { risk: string }) {
  if (risk === "Düşük") {
    return <CheckCircle2 className="size-10 text-primary" />;
  }
  return <AlertTriangle className="size-10 text-accent" />;
}

function submit(event: FormEvent<HTMLFormElement>, action: () => void) {
  event.preventDefault();
  action();
}

function formatParams(value: number | null) {
  if (!value) {
    return "parametre Bulunamadı";
  }
  if (value >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(1)}B`;
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  return String(value);
}

function formatBytes(value: number | null) {
  if (!value) {
    return "Bulunamadı";
  }
  if (value >= 1_073_741_824) {
    return `${(value / 1_073_741_824).toFixed(2)} GB`;
  }
  if (value >= 1_048_576) {
    return `${(value / 1_048_576).toFixed(1)} MB`;
  }
  return `${value} B`;
}

function formatMemory(value: unknown) {
  return typeof value === "number" ? `${value} GB` : "Bulunamadı";
}

function BenchmarkScreen({ models }: { models: ModelRecord[] }) {
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = useState("Python'da asenkron programlama nedir? Kısaca açıkla.");
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [maxTokens, setMaxTokens] = useState(128);
  const [results, setResults] = useState<BenchmarkResult[]>([]);
  const { data: hardware } = useQuery({ queryKey: ["hardware", "benchmark"], queryFn: api.systemHardware, refetchInterval: 5000 });

  const ollamaModels = models.filter(m => m.source === "ollama");
  const ramTotal = Number(hardware?.ram_total_gb ?? 0);
  const ramUsed = Number(hardware?.ram_used_gb ?? 0);
  const ramFree = Math.max(0, ramTotal - ramUsed);
  const safeModelLimit = ramTotal > 0 && ramTotal < 24 ? 1 : 2;
  const benchmarkBlocked = selectedModels.length > safeModelLimit;
  const benchmarkWarning = benchmarkBlocked
    ? `Bu sistem için güvenli eşik ${safeModelLimit} model. Aynı anda daha fazla model Ollama yüklemesi RAM baskısı yaratabilir.`
    : selectedModels.length > 1
      ? "Çoklu model benchmark sıralı çalışır; test sırasında başka ağır uygulamaları kapatın."
      : null;

  const runBenchmark = useMutation({
    mutationFn: () => {
      const modelNames = ollamaModels.filter(m => selectedModels.includes(m.id)).map(m => m.name);
      if (modelNames.length === 0) {
        throw new Error("Lütfen en az bir Ollama modeli seçin.");
      }
      if (modelNames.length > safeModelLimit) {
        throw new Error(`Bu donanımda aynı anda en fazla ${safeModelLimit} model benchmark için önerilir.`);
      }
      return api.executeBenchmark(modelNames, prompt, maxTokens);
    },
    onSuccess: async (data) => {
      setResults(data);
      await queryClient.invalidateQueries({ queryKey: ["benchmark-runs"] });
    }
  });

  return (
    <>
      <Header title="Benchmark Stüdyosu" description="Aynı promptu farklı Ollama modellerinde test edin ve karşılaştırın." />
      <div className="grid grid-cols-[380px_1fr] gap-8 p-8 max-w-[1600px] mx-auto">
        <section className="glass-panel rounded-2xl p-6">
          <h2 className="text-base font-semibold">Test Ayarları</h2>
          <div className="mt-4 space-y-4">
            <label className="block text-sm">
              <span className="text-muted-foreground">Ollama Modelleri</span>
              <div className="mt-2 space-y-2 max-h-48 overflow-y-auto">
                {ollamaModels.length === 0 ? <EmptyState text="Hiç Ollama modeli bulunamadı." /> : null}
                {ollamaModels.map(model => (
                  <label key={model.id} className="flex items-center gap-2">
                    <input 
                      type="checkbox" 
                      checked={selectedModels.includes(model.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          const next = [...selectedModels, model.id];
                          setSelectedModels(next.slice(0, Math.max(1, safeModelLimit)));
                        } else {
                          setSelectedModels(selectedModels.filter(id => id !== model.id));
                        }
                      }}
                    />
                    <span>{model.name}</span>
                  </label>
                ))}
              </div>
            </label>
            {benchmarkWarning ? <ErrorBanner message={benchmarkWarning} /> : null}
            <div className="grid grid-cols-2 gap-3 rounded-xl border border-white/5 bg-white/5 p-3 text-sm">
              <div>
                <div className="text-muted-foreground">Boş RAM</div>
                <div className="font-semibold">{ramTotal ? `${ramFree.toFixed(1)} GB / ${ramTotal.toFixed(1)} GB` : "Ölçülüyor"}</div>
              </div>
              <div>
                <div className="text-muted-foreground">Güvenli model</div>
                <div className="font-semibold">{safeModelLimit}</div>
              </div>
            </div>
            <label className="block text-sm">
              <span className="text-muted-foreground">Prompt</span>
              <textarea
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 h-24"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="text-muted-foreground">Maksimum Cevap Token</span>
              <input
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2"
                type="number"
                min={16}
                max={256}
                value={maxTokens}
                onChange={(event) => setMaxTokens(Number(event.target.value))}
              />
            </label>
            <Button className="w-full" disabled={runBenchmark.isPending || selectedModels.length === 0 || benchmarkBlocked} onClick={() => runBenchmark.mutate()}>
              {runBenchmark.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <BarChart3 className="mr-2 size-4" />}
              Testi Başlat
            </Button>
            <MutationError error={runBenchmark.error} />
          </div>
        </section>

        <section className="space-y-6">
          <div className="glass-panel rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/5 p-5">
              <h2 className="text-base font-semibold">Karşılaştırma Sonuçları</h2>
            </div>
            {results.length > 0 ? (
              <table className="w-full text-sm">
                <thead className="bg-white/5 text-muted-foreground text-left">
                  <tr>
                    <th className="px-4 py-3 font-medium">Model</th>
                    <th className="px-4 py-3 font-medium">Latency</th>
                    <th className="px-4 py-3 font-medium">Input T.</th>
                    <th className="px-4 py-3 font-medium">Output T.</th>
                    <th className="px-4 py-3 font-medium">Token/s</th>
                    <th className="px-4 py-3 font-medium">TTFT</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {results.map((r, i) => (
                    <tr key={i}>
                      <td className="px-4 py-3">{r.model}</td>
                      <td className="px-4 py-3">{r.error ? "Hata" : (r.latency_ms ? `${(r.latency_ms / 1000).toFixed(2)}s` : "-")}</td>
                      <td className="px-4 py-3">{r.input_tokens ?? "-"}</td>
                      <td className="px-4 py-3">{r.output_tokens ?? "-"}</td>
                      <td className="px-4 py-3">{r.token_per_sec ? `${r.token_per_sec.toFixed(1)}` : "-"}</td>
                      <td className="px-4 py-3">{r.ttft_ms ? `${r.ttft_ms.toFixed(0)}ms` : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <EmptyState text="Sonuçları görmek için testi başlatın." />
            )}
          </div>

          {results.filter(r => !r.error && r.response).map((r, i) => (
            <div key={i} className="glass-panel rounded-2xl p-6">
              <h3 className="font-semibold text-sm text-primary mb-3">{r.model} Cevabı</h3>
              <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">{r.response}</p>
            </div>
          ))}
        </section>
      </div>
    </>
  );
}
