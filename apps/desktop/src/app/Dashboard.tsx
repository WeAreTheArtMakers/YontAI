import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Cpu, HardDrive, Loader2, Server, Stethoscope } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, SystemCapabilities } from "@/lib/api";

interface HealthRowProps {
  label: string;
  status: string;
  details?: string;
}

function HealthRow({ label, status, details }: HealthRowProps) {
  const isOk = status === "ok" || status === "ready" || status === "healthy";
  return (
    <div className="flex items-center gap-2 text-sm">
      {isOk ? (
        <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
      ) : (
        <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
      )}
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{status}</span>
      {details && <span className="text-xs text-muted-foreground">({details})</span>}
    </div>
  );
}

export function Dashboard() {
  const healthQuery = useQuery({
    queryKey: ["system-health"],
    queryFn: () => api.health(),
    refetchInterval: 15_000,
  });

  const capabilitiesQuery = useQuery({
    queryKey: ["system-capabilities"],
    queryFn: () => api.capabilities(),
    refetchInterval: 30_000,
  });

  const caps = capabilitiesQuery.data as SystemCapabilities | undefined;
  const health = healthQuery.data;

  const metrics: Record<string, string> = {};
  if (caps?.database) metrics["Veritabanı"] = caps.database;
  if (caps?.ollama_status) metrics["Ollama"] = caps.ollama_status;
  if (caps?.ai_runtimes?.length) metrics["AI Runtimes"] = caps.ai_runtimes.join(", ");
  if (caps?.events?.length) metrics["Events"] = caps.events.join(", ");

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border bg-card p-4 flex items-center gap-3">
          <Cpu className="w-8 h-8 text-blue-500" />
          <div>
            <div className="text-xs text-muted-foreground">System CPU</div>
            <div className="text-lg font-semibold">
              {health ? health.status : <Loader2 className="w-4 h-4 animate-spin" />}
            </div>
          </div>
        </div>

        <div className="rounded-xl border bg-card p-4 flex items-center gap-3">
          <Server className="w-8 h-8 text-purple-500" />
          <div>
            <div className="text-xs text-muted-foreground">Backend</div>
            <div className="text-lg font-semibold">
              {health?.service ?? <Loader2 className="w-4 h-4 animate-spin" />}
            </div>
          </div>
        </div>

        <div className="rounded-xl border bg-card p-4 flex items-center gap-3">
          <Stethoscope className="w-8 h-8 text-emerald-500" />
          <div>
            <div className="text-xs text-muted-foreground">API Status</div>
            <div className="text-lg font-semibold">{health?.status ?? "N/A"}</div>
          </div>
        </div>

        <div className="rounded-xl border bg-card p-4 flex items-center gap-3">
          <HardDrive className="w-8 h-8 text-amber-500" />
          <div>
            <div className="text-xs text-muted-foreground">Database</div>
            <div className="text-lg font-semibold">{caps?.database_status ?? "N/A"}</div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border bg-card p-4 space-y-3">
        <h3 className="font-semibold text-sm">System Health</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <HealthRow label="Service" status={health?.service ?? "unknown"} />
          <HealthRow
            label="Ollama"
            status={caps?.ollama_status ?? "unknown"}
            details="127.0.0.1:11434"
          />
          <HealthRow
            label="Metadata Engine"
            status={caps?.metadata_engine_status ?? "unknown"}
          />
          <HealthRow
            label="Benchmark Engine"
            status={caps?.benchmark_engine_status ?? "unknown"}
          />
          <HealthRow
            label="Job Worker"
            status={caps?.job_worker_status ?? "unknown"}
          />
        </div>
      </div>

      {caps?.events && caps.events.length > 0 && (
        <div className="rounded-xl border bg-card p-2 space-y-1">
          <h4 className="text-xs font-medium text-muted-foreground px-2">Olaylar / Events</h4>
          {caps.events.map((ev, i) => (
            <div key={i} className="text-xs px-2 py-0.5 text-muted-foreground">
              {ev}
            </div>
          ))}
        </div>
      )}

      {Object.keys(metrics).length > 0 && (
        <div className="rounded-xl border bg-card p-4 space-y-2">
          <h3 className="font-semibold text-sm">System Metrics</h3>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {Object.entries(metrics).map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="text-muted-foreground">{k}</span>
                <span className="font-medium">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => healthQuery.refetch()}
          disabled={healthQuery.isFetching}
        >
          {healthQuery.isFetching ? "Yenileniyor..." : "🔄 Sistemi Kontrol Et"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => capabilitiesQuery.refetch()}
          disabled={capabilitiesQuery.isFetching}
        >
          {capabilitiesQuery.isFetching ? "Yenileniyor..." : "📊 Yetenekleri Kontrol Et"}
        </Button>
      </div>
    </div>
  );
}