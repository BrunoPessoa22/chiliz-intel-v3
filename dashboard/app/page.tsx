'use client';

import { useEffect, useState } from 'react';
import { HealthMatrix } from '@/components/executive/HealthMatrix';
import { PortfolioOverview } from '@/components/executive/PortfolioOverview';
import { TopMovers } from '@/components/executive/TopMovers';
import { ActiveAlerts } from '@/components/executive/ActiveAlerts';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function Dashboard() {
  const [overview, setOverview] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(`${API_URL}/api/executive/overview`);
        const data = await res.json();
        setOverview(data);
      } catch (error) {
        console.error('Failed to fetch overview:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-chiliz-red"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Executive Dashboard</h1>
          <p className="text-gray-400">Real-time fan token portfolio intelligence</p>
        </div>
        <div className="text-right text-sm text-gray-400">
          <p>Last updated: {new Date().toLocaleTimeString()}</p>
          <p className="text-xs">Auto-refresh: 30s</p>
        </div>
      </div>

      {/* Portfolio Overview Cards */}
      <PortfolioOverview data={overview} />

      {/* Health Matrix & Alerts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <HealthMatrix />
        </div>
        <div>
          <ActiveAlerts />
        </div>
      </div>

      {/* Top Movers */}
      <TopMovers />
    </div>
  );
}
