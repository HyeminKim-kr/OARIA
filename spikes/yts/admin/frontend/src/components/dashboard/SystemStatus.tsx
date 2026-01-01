"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  Play,
  Loader2,
  Database,
  Server,
  HardDrive,
  Boxes,
  Flower2,
  Cog,
  Cpu,
} from "lucide-react";
import { systemApi, SystemHealth, ServiceStatus } from "@/lib/api";

const serviceIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  PostgreSQL: Database,
  Redis: Server,
  Weaviate: Boxes,
  MinIO: HardDrive,
  "Celery (Flower)": Flower2,
  "Celery (Backfill)": Cog,
  "Celery (Embed)": Cpu,
};

function StatusBadge({ status }: { status: "healthy" | "unhealthy" | "unknown" }) {
  if (status === "healthy") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-700">
        <CheckCircle2 className="h-3 w-3" />
        OK
      </span>
    );
  }
  if (status === "unhealthy") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-700">
        <XCircle className="h-3 w-3" />
        Error
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">
      <AlertCircle className="h-3 w-3" />
      Unknown
    </span>
  );
}

function ServiceCard({ service }: { service: ServiceStatus }) {
  const Icon = serviceIcons[service.name] || Server;
  const bgClass = service.status === "healthy"
    ? "bg-green-50 text-green-600"
    : service.status === "unhealthy"
      ? "bg-red-50 text-red-600"
      : "bg-gray-50 text-gray-600";

  return (
    <div className="flex items-center justify-between rounded-lg border bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <div className={"rounded-lg p-2 " + bgClass}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="font-medium text-gray-900">{service.name}</p>
          {service.latency !== undefined && (
            <p className="text-xs text-gray-500">{service.latency}ms</p>
          )}
          {service.message && (
            <p className="text-xs text-red-500">{service.message}</p>
          )}
        </div>
      </div>
      <StatusBadge status={service.status} />
    </div>
  );
}

export function SystemStatus() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [triggering, setTriggering] = useState<"embed" | "reembed" | null>(null);
  const [triggerMessage, setTriggerMessage] = useState<string | null>(null);

  const fetchHealth = async () => {
    try {
      const data = await systemApi.getHealth();
      setHealth(data);
    } catch (error) {
      console.error("Failed to fetch system health:", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchHealth();
  };

  const handleTriggerEmbed = async () => {
    setTriggering("embed");
    setTriggerMessage(null);
    try {
      const result = await systemApi.triggerEmbedding(100);
      setTriggerMessage(result.success ? (result.message || "Triggered") : (result.message || "Failed"));
    } catch {
      setTriggerMessage("Error");
    } finally {
      setTriggering(null);
    }
  };

  const handleTriggerReembed = async () => {
    setTriggering("reembed");
    setTriggerMessage(null);
    try {
      const result = await systemApi.triggerReembedding();
      setTriggerMessage(result.success ? (result.message || "Triggered") : (result.message || "Failed"));
    } catch {
      setTriggerMessage("Error");
    } finally {
      setTriggering(null);
    }
  };

  if (loading) {
    return (
      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </div>
    );
  }

  const overallStatus = health?.status || "unknown";
  const statusColorMap: Record<string, string> = {
    healthy: "bg-green-500",
    degraded: "bg-yellow-500",
    unhealthy: "bg-red-500",
    unknown: "bg-gray-500",
  };
  const statusColor = statusColorMap[overallStatus] || "bg-gray-500";
  const refreshClass = refreshing ? "h-4 w-4 animate-spin" : "h-4 w-4";

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-900">System Status</h2>
          <span className={"inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium text-white " + statusColor}>
            {overallStatus === "healthy" && "All OK"}
            {overallStatus === "degraded" && "Partial"}
            {overallStatus === "unhealthy" && "Outage"}
            {overallStatus === "unknown" && "Unknown"}
          </span>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 disabled:opacity-50"
          title="Refresh"
        >
          <RefreshCw className={refreshClass} />
        </button>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {health?.services.map((service) => (
          <ServiceCard key={service.name} service={service} />
        ))}
      </div>

      <div className="border-t pt-4">
        <h3 className="mb-3 text-sm font-medium text-gray-700">Manual Actions</h3>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleTriggerEmbed}
            disabled={triggering !== null}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {triggering === "embed" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Embed (100)
          </button>
          <button
            onClick={handleTriggerReembed}
            disabled={triggering !== null}
            className="inline-flex items-center gap-2 rounded-lg bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-700 disabled:opacity-50"
          >
            {triggering === "reembed" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Retry Failed
          </button>
        </div>
        {triggerMessage && (
          <p className="mt-2 text-sm text-gray-600">{triggerMessage}</p>
        )}
      </div>

      {health?.timestamp && (
        <p className="mt-4 text-right text-xs text-gray-400">
          Last: {new Date(health.timestamp).toLocaleString()}
        </p>
      )}
    </div>
  );
}
