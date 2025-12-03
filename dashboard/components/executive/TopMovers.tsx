'use client';

import { useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Token {
  symbol: string;
  name: string;
  team: string;
  price: number;
  price_change_24h: number;
  volume_24h: number;
  health_score: number;
  health_grade: string;
}

export function TopMovers() {
  const [tokens, setTokens] = useState<Token[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(`${API_URL}/api/tokens`);
        const json = await res.json();
        setTokens(json);
      } catch (error) {
        console.error('Failed to fetch tokens:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="card animate-pulse">
        <div className="h-48 bg-gray-800 rounded"></div>
      </div>
    );
  }

  const sorted = [...tokens].sort((a, b) =>
    Math.abs(b.price_change_24h || 0) - Math.abs(a.price_change_24h || 0)
  );
  const topMovers = sorted.slice(0, 6);

  const getGradeBg = (grade: string) => {
    const colors: Record<string, string> = {
      A: 'bg-green-500/20',
      B: 'bg-lime-500/20',
      C: 'bg-yellow-500/20',
      D: 'bg-orange-500/20',
      F: 'bg-red-500/20',
    };
    return colors[grade] || 'bg-gray-500/20';
  };

  const getGradeText = (grade: string) => {
    const colors: Record<string, string> = {
      A: 'text-green-400',
      B: 'text-lime-400',
      C: 'text-yellow-400',
      D: 'text-orange-400',
      F: 'text-red-400',
    };
    return colors[grade] || 'text-gray-400';
  };

  const formatPrice = (price: number) => {
    if (price >= 1) return `$${price.toFixed(2)}`;
    return `$${price.toFixed(4)}`;
  };

  const formatVolume = (vol: number) => {
    if (vol >= 1_000_000) return `$${(vol / 1_000_000).toFixed(2)}M`;
    if (vol >= 1_000) return `$${(vol / 1_000).toFixed(1)}K`;
    return `$${vol.toFixed(0)}`;
  };

  return (
    <div className="card">
      <h2 className="text-xl font-bold mb-4">Top Movers (24h)</h2>
      <p className="text-gray-400 text-sm mb-4">Largest price movements in the last 24 hours</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {topMovers.map((token) => (
          <div
            key={token.symbol}
            className="bg-gray-800/50 rounded-lg p-4 hover:bg-gray-800 transition cursor-pointer border border-gray-700/50"
          >
            <div className="flex justify-between items-start mb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xl font-bold">{token.symbol}</span>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${getGradeBg(token.health_grade)} ${getGradeText(token.health_grade)}`}>
                    {token.health_grade}
                  </span>
                </div>
                <p className="text-sm text-gray-400">{token.team}</p>
              </div>
              <span className={`text-lg font-bold ${(token.price_change_24h || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {(token.price_change_24h || 0) >= 0 ? '+' : ''}{(token.price_change_24h || 0).toFixed(2)}%
              </span>
            </div>

            <div className="flex justify-between text-sm">
              <div>
                <p className="text-gray-400">Price</p>
                <p className="font-medium">{formatPrice(token.price || 0)}</p>
              </div>
              <div className="text-right">
                <p className="text-gray-400">Volume</p>
                <p className="font-medium">{formatVolume(token.volume_24h || 0)}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
