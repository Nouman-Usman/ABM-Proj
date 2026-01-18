import { useEffect, useMemo, useState } from "react";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getApiUrl, getWsUrl } from "@/config/settings";
import { authConfig } from "@/config";
import { useNavigate } from "react-router-dom";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";

type Metrics = {
  cpu_percent: number | null;
  memory: {
    total: number;
    available: number;
    percent: number;
    used: number;
    free: number;
  } | null;
  disk: {
    total: number;
    used: number;
    free: number;
    percent: number;
  } | null;
  gpu: unknown;
  error?: string;
};

// (no helper needed: chart shows percentages only)

export default function AdminPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  const [history, setHistory] = useState<
    { time: string; cpu: number; mem: number; disk: number }[]
  >([]);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const navigate = useNavigate();

  const token = useMemo(
    () =>
      typeof window !== "undefined"
        ? localStorage.getItem(authConfig.TOKEN_KEY)
        : null,
    []
  );

  // Centralized fetch so we can call it from refresh button or initial load
  const fetchMetrics = async () => {
    if (!token) return;
    try {
      const res = await fetch(getApiUrl("/admin/resources"), {
        headers: { Authorization: `Bearer ${token}` },
        credentials: "include",
      });
      if (res.ok) {
        const data = (await res.json()) as Metrics;
        setMetrics(data);
        setLastUpdate(new Date().toLocaleTimeString("en-US"));
      } else if (res.status === 403) {
        setError("Only admins are allowed to access");
      } else if (res.status === 401) {
        setError("Please log in again");
      } else {
        setError("Failed to load system data");
      }
    } catch {
      setError("Connection error with server");
    }
  };
  // Verify admin role before loading content
  useEffect(() => {
    let cancelled = false;
    const checkRole = async () => {
      try {
        if (!token) {
          setIsAdmin(false);
          setError("Not logged in");
          setLoading(false);
          return;
        }
        const res = await fetch(getApiUrl("/auth/me"), {
          headers: { Authorization: `Bearer ${token}` },
          credentials: "include",
        });
        if (!res.ok) {
          setIsAdmin(false);
          setError(
            res.status === 401
              ? "Access denied"
              : "Failed to authenticate user"
          );
          setLoading(false);
          return;
        }
        const me = await res.json();
        if (!cancelled) {
          const admin = me?.role_id === 0;
          setIsAdmin(admin);
          if (!admin) {
            setError("You don't have permission to access this page");
          }
        }
      } catch {
        setIsAdmin(false);
        setError("Connection error with server");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    checkRole();
    return () => {
      cancelled = true;
    };
  }, [token]);

  // Initial fetch of metrics
  useEffect(() => {
    if (isAdmin) fetchMetrics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  // Live updates via WebSocket
  const wsUrl = useMemo(() => getWsUrl("/admin/ws/resources"), []);
  const { data: wsData, isConnected } = useWebSocket(isAdmin ? wsUrl : null, {
    authToken: token,
    maxReconnectAttempts: 10,
  });

  useEffect(() => {
    if (wsData && typeof wsData === "object") {
      const m = wsData as Metrics;
      setMetrics(m);
      // Append to history
      const point = {
        time: new Date().toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
        cpu: Number(m.cpu_percent || 0),
        mem: Number(m.memory?.percent || 0),
        disk: Number(m.disk?.percent || 0),
      };
      setHistory((prev) => [...prev, point].slice(-60));
      setLastUpdate(new Date().toLocaleTimeString("en-US"));
    }
  }, [wsData]);

  // Seed first point from initial HTTP fetch if not yet seeded
  useEffect(() => {
    if (!metrics) return;
    setHistory((prev) => {
      if (prev.length > 0) return prev;
      const point = {
        time: new Date().toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
        cpu: Number(metrics.cpu_percent || 0),
        mem: Number(metrics.memory?.percent || 0),
        disk: Number(metrics.disk?.percent || 0),
      };
      return [point];
    });
  }, [metrics]);

  if (loading) {
    return (
      <div className="p-6">
        <p>Loading...</p>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="p-6">
        <Card className="max-w-xl">
          <CardHeader>
            <CardTitle>Access Denied</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-4">
              {error || "You don't have permission to access the admin page."}
            </p>
            <Button onClick={() => navigate("/home")}>Back to Home</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">System Control Panel</h2>
        <div className="flex items-center gap-3">
          <div className="text-sm text-gray-500">
            WebSocket:{" "}
            {isConnected ? (
              <span className="text-green-600">Connected</span>
            ) : (
              <span className="text-red-600">Disconnected</span>
            )}
          </div>
          <Button variant="ghost" onClick={() => fetchMetrics()}>
            Refresh
          </Button>
        </div>
      </div>

      {/* Top quick stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-muted-foreground">CPU</div>
              <div className="text-2xl font-bold">
                {metrics?.cpu_percent ?? 0}%
              </div>
            </div>
            <div className="w-24 h-6 bg-gray-200 rounded overflow-hidden">
              <div
                className="h-full bg-blue-500"
                style={{ width: `${metrics?.cpu_percent ?? 0}%` }}
              />
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-muted-foreground">RAM</div>
              <div className="text-2xl font-bold">
                {metrics?.memory?.percent ?? 0}%
              </div>
            </div>
            <div className="w-24 h-6 bg-gray-200 rounded overflow-hidden">
              <div
                className="h-full bg-green-500"
                style={{ width: `${metrics?.memory?.percent ?? 0}%` }}
              />
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-muted-foreground">Disk</div>
              <div className="text-2xl font-bold">
                {metrics?.disk?.percent ?? 0}%
              </div>
            </div>
            <div className="w-24 h-6 bg-gray-200 rounded overflow-hidden">
              <div
                className="h-full bg-amber-500"
                style={{ width: `${metrics?.disk?.percent ?? 0}%` }}
              />
            </div>
          </div>
        </Card>
      </div>

      {/* chart */}
      <Card>
        <CardHeader>
          <CardTitle>Performance Over Time</CardTitle>
          <div className="text-sm text-gray-500">
            {lastUpdate ? `Last Update: ${lastUpdate}` : "No data available"}
          </div>
        </CardHeader>
        <CardContent className="px-2 sm:px-4">
          <ResponsiveContainer width="100%" height={380}>
            <LineChart data={history} margin={{ left: 12, right: 12 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} unit="%" />
              <Tooltip
                formatter={(value) => [`${Number(value).toFixed(1)}%`, ""]}
                contentStyle={{
                  backgroundColor: "rgba(255,255,255,0.95)",
                  border: "1px solid #e5e7eb",
                  borderRadius: 8,
                }}
              />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              <Line
                type="monotone"
                dataKey="cpu"
                name="CPU %"
                stroke="#3B82F6"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="mem"
                name="RAM %"
                stroke="#10B981"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="disk"
                name="Disk %"
                stroke="#F59E0B"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* no separate detail cards: metrics are shown in the combined chart above */}

      {metrics?.error && (
        <Card className="border-red-300">
          <CardHeader>
            <CardTitle className="text-red-600">Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            <p>{metrics.error}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
