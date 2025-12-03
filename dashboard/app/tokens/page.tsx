'use client';

import { useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Token {
  symbol: string;
  name: string;
  team: string;
  price: number;
  price_change_1h: number | null;
  price_change_24h: number | null;
  price_change_7d: number | null;
  volume_24h: number;
  market_cap: number;
  total_holders: number | null;
  holder_change_24h: number | null;
  liquidity_1pct: number;
  spread_bps: number | null;
  health_score: number | null;
  health_grade: string | null;
  active_exchanges: number;
}

export default function TokensPage() {
  const [tokens, setTokens] = useState<Token[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<keyof Token>('volume_24h');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    async function fetchTokens() {
      try {
        const res = await fetch(`${API_URL}/api/tokens`);
        const data = await res.json();
        setTokens(data);
      } catch (error) {
        console.error('Failed to fetch tokens:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchTokens();
    const interval = setInterval(fetchTokens, 30000);
    return () => clearInterval(interval);
  }, []);

  const sortedTokens = [...tokens].sort((a, b) => {
    const aVal = a[sortBy] ?? 0;
    const bVal = b[sortBy] ?? 0;
    const multiplier = sortOrder === 'desc' ? -1 : 1;
    return (Number(aVal) - Number(bVal)) * multiplier;
  });

  const handleSort = (column: keyof Token) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('desc');
    }
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

  const getGradeColor = (grade: string | null) => {
    const colors: Record<string, string> = {
      A: 'bg-green-500/20 text-green-400',
      B: 'bg-lime-500/20 text-lime-400',
      C: 'bg-yellow-500/20 text-yellow-400',
      D: 'bg-orange-500/20 text-orange-400',
      F: 'bg-red-500/20 text-red-400',
    };
    return colors[grade || ''] || 'bg-gray-500/20 text-gray-400';
  };

  const ChangeCell = ({ value }: { value: number | null }) => {
    if (value === null) return <span className="text-gray-500">-</span>;
    const color = value >= 0 ? 'text-green-400' : 'text-red-400';
    return <span className={color}>{value >= 0 ? '+' : ''}{value.toFixed(2)}%</span>;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-chiliz-red"></div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Fan Tokens</h1>
        <p className="text-gray-400">Complete list of all tracked fan tokens with metrics</p>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-800/50">
              <tr className="text-left text-gray-400 text-sm">
                <th className="px-4 py-3 font-medium">Token</th>
                <th
                  className="px-4 py-3 font-medium cursor-pointer hover:text-white"
                  onClick={() => handleSort('price')}
                >
                  Price {sortBy === 'price' && (sortOrder === 'desc' ? '↓' : '↑')}
                </th>
                <th className="px-4 py-3 font-medium">1h</th>
                <th
                  className="px-4 py-3 font-medium cursor-pointer hover:text-white"
                  onClick={() => handleSort('price_change_24h')}
                >
                  24h {sortBy === 'price_change_24h' && (sortOrder === 'desc' ? '↓' : '↑')}
                </th>
                <th className="px-4 py-3 font-medium">7d</th>
                <th
                  className="px-4 py-3 font-medium cursor-pointer hover:text-white"
                  onClick={() => handleSort('volume_24h')}
                >
                  Volume {sortBy === 'volume_24h' && (sortOrder === 'desc' ? '↓' : '↑')}
                </th>
                <th
                  className="px-4 py-3 font-medium cursor-pointer hover:text-white"
                  onClick={() => handleSort('total_holders')}
                >
                  Holders {sortBy === 'total_holders' && (sortOrder === 'desc' ? '↓' : '↑')}
                </th>
                <th className="px-4 py-3 font-medium">Liquidity</th>
                <th className="px-4 py-3 font-medium">Spread</th>
                <th
                  className="px-4 py-3 font-medium cursor-pointer hover:text-white"
                  onClick={() => handleSort('health_score')}
                >
                  Health {sortBy === 'health_score' && (sortOrder === 'desc' ? '↓' : '↑')}
                </th>
                <th className="px-4 py-3 font-medium">Exchanges</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {sortedTokens.map((token) => (
                <tr key={token.symbol} className="hover:bg-gray-800/50 transition">
                  <td className="px-4 py-4">
                    <div>
                      <span className="font-bold">{token.symbol}</span>
                      <p className="text-xs text-gray-400">{token.team}</p>
                    </div>
                  </td>
                  <td className="px-4 py-4 font-medium">{formatPrice(token.price)}</td>
                  <td className="px-4 py-4"><ChangeCell value={token.price_change_1h} /></td>
                  <td className="px-4 py-4"><ChangeCell value={token.price_change_24h} /></td>
                  <td className="px-4 py-4"><ChangeCell value={token.price_change_7d} /></td>
                  <td className="px-4 py-4">{formatVolume(token.volume_24h)}</td>
                  <td className="px-4 py-4">
                    {token.total_holders ? (
                      <div>
                        <span>{token.total_holders.toLocaleString()}</span>
                        {token.holder_change_24h !== null && (
                          <span className={`text-xs ml-1 ${token.holder_change_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            ({token.holder_change_24h >= 0 ? '+' : ''}{token.holder_change_24h})
                          </span>
                        )}
                      </div>
                    ) : '-'}
                  </td>
                  <td className="px-4 py-4">{formatVolume(token.liquidity_1pct)}</td>
                  <td className="px-4 py-4">
                    {token.spread_bps !== null ? `${token.spread_bps.toFixed(0)} bps` : '-'}
                  </td>
                  <td className="px-4 py-4">
                    {token.health_grade && (
                      <span className={`px-2 py-1 rounded text-sm font-medium ${getGradeColor(token.health_grade)}`}>
                        {token.health_grade} ({token.health_score})
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-4 text-center">{token.active_exchanges}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
