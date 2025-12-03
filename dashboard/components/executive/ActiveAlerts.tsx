'use client';

import { useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Alert {
  id: number;
  symbol: string;
  type: string;
  direction: string | null;
  confidence: number;
  title: string;
  description: string;
  priority: string;
  created_at: string;
}

export function ActiveAlerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(`${API_URL}/api/alerts/active`);
        const json = await res.json();
        setAlerts(json.alerts || []);
      } catch (error) {
        console.error('Failed to fetch alerts:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="card animate-pulse">
        <div className="h-64 bg-gray-800 rounded"></div>
      </div>
    );
  }

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      high: 'border-l-red-500 bg-red-500/10',
      medium: 'border-l-yellow-500 bg-yellow-500/10',
      low: 'border-l-green-500 bg-green-500/10',
    };
    return colors[priority] || colors.medium;
  };

  const getTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      price_surge: '📈',
      price_drop: '📉',
      volume_spike: '🔥',
      health_decline: '⚠️',
      holder_exodus: '👋',
      holder_growth: '🎉',
      liquidity_warning: '💧',
    };
    return icons[type] || '🔔';
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="card h-full">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold">Active Alerts</h2>
        <span className="px-2 py-1 bg-chiliz-red/20 text-chiliz-red rounded text-sm">
          {alerts.length} active
        </span>
      </div>

      {alerts.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p className="text-4xl mb-2">✅</p>
          <p>No active alerts</p>
          <p className="text-xs text-gray-500">All systems nominal</p>
        </div>
      ) : (
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`border-l-4 rounded-r-lg p-3 ${getPriorityColor(alert.priority)}`}
            >
              <div className="flex items-start gap-2">
                <span className="text-lg">{getTypeIcon(alert.type)}</span>
                <div className="flex-1">
                  <div className="flex justify-between items-start">
                    <span className="font-medium">{alert.symbol}</span>
                    <span className="text-xs text-gray-400">{formatTime(alert.created_at)}</span>
                  </div>
                  <p className="text-sm text-gray-300 mt-1">{alert.title}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs text-gray-500">
                      Confidence: {(alert.confidence * 100).toFixed(0)}%
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      alert.priority === 'high' ? 'bg-red-500/20 text-red-400' :
                      alert.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-green-500/20 text-green-400'
                    }`}>
                      {alert.priority}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
