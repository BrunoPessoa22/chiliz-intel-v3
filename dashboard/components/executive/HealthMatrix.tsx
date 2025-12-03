'use client';

import { useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface TokenHealth {
  symbol: string;
  team: string;
  league: string;
  health_score: number;
  price_change_24h: number;
  volume_24h: number;
}

interface HealthMatrixData {
  matrix: {
    A: TokenHealth[];
    B: TokenHealth[];
    C: TokenHealth[];
    D: TokenHealth[];
    F: TokenHealth[];
  };
}

export function HealthMatrix() {
  const [data, setData] = useState<HealthMatrixData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(`${API_URL}/api/executive/health-matrix`);
        const json = await res.json();
        setData(json);
      } catch (error) {
        console.error('Failed to fetch health matrix:', error);
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

  if (!data) return null;

  const gradeColors: Record<string, string> = {
    A: 'bg-green-500/20 border-green-500/50',
    B: 'bg-lime-500/20 border-lime-500/50',
    C: 'bg-yellow-500/20 border-yellow-500/50',
    D: 'bg-orange-500/20 border-orange-500/50',
    F: 'bg-red-500/20 border-red-500/50',
  };

  const gradeTextColors: Record<string, string> = {
    A: 'text-green-400',
    B: 'text-lime-400',
    C: 'text-yellow-400',
    D: 'text-orange-400',
    F: 'text-red-400',
  };

  const formatVolume = (vol: number) => {
    if (vol >= 1_000_000) return `$${(vol / 1_000_000).toFixed(1)}M`;
    if (vol >= 1_000) return `$${(vol / 1_000).toFixed(0)}K`;
    return `$${vol.toFixed(0)}`;
  };

  return (
    <div className="card">
      <h2 className="text-xl font-bold mb-4">Health Matrix</h2>
      <p className="text-gray-400 text-sm mb-4">Token health grades across the portfolio</p>

      <div className="space-y-4">
        {(['A', 'B', 'C', 'D', 'F'] as const).map((grade) => {
          const tokens = data.matrix[grade];
          if (tokens.length === 0) return null;

          return (
            <div key={grade} className={`p-4 rounded-lg border ${gradeColors[grade]}`}>
              <div className="flex items-center gap-2 mb-3">
                <span className={`text-2xl font-bold ${gradeTextColors[grade]}`}>
                  Grade {grade}
                </span>
                <span className="text-gray-400 text-sm">
                  ({tokens.length} token{tokens.length !== 1 ? 's' : ''})
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {tokens.map((token) => (
                  <div
                    key={token.symbol}
                    className="bg-black/30 rounded-lg p-3 hover:bg-black/50 transition cursor-pointer"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="font-bold">{token.symbol}</p>
                        <p className="text-xs text-gray-400 truncate max-w-[100px]">{token.team}</p>
                      </div>
                      <span className={`text-sm font-medium ${gradeTextColors[grade]}`}>
                        {token.health_score}
                      </span>
                    </div>
                    <div className="mt-2 flex justify-between text-xs">
                      <span className={token.price_change_24h >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {token.price_change_24h >= 0 ? '+' : ''}{token.price_change_24h.toFixed(1)}%
                      </span>
                      <span className="text-gray-500">{formatVolume(token.volume_24h)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
