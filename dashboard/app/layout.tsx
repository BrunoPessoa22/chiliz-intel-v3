import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Chiliz Marketing Intelligence v3.0',
  description: 'Executive Dashboard for Fan Token Analysis',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-chiliz-darker text-white min-h-screen`}>
        <div className="flex">
          {/* Sidebar */}
          <aside className="w-64 bg-chiliz-dark border-r border-gray-800 min-h-screen p-4 fixed">
            <div className="flex items-center gap-3 mb-8">
              <div className="w-10 h-10 bg-chiliz-red rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-xl">C</span>
              </div>
              <div>
                <h1 className="font-bold text-lg">Chiliz Intel</h1>
                <p className="text-xs text-gray-400">v3.0 Executive</p>
              </div>
            </div>

            <nav className="space-y-2">
              <a href="/" className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-gray-800 transition">
                <span>📊</span>
                <span>Dashboard</span>
              </a>
              <a href="/executive" className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-gray-800 transition">
                <span>👔</span>
                <span>Executive View</span>
              </a>
              <a href="/tokens" className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-gray-800 transition">
                <span>🪙</span>
                <span>Tokens</span>
              </a>
              <a href="/assistant" className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-gray-800 transition">
                <span>🤖</span>
                <span>AI Assistant</span>
              </a>
            </nav>

            <div className="absolute bottom-4 left-4 right-4">
              <div className="bg-gray-800/50 rounded-lg p-4">
                <p className="text-xs text-gray-400">Data Sources</p>
                <div className="mt-2 space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-500">CoinGecko Pro</span>
                    <span className="text-green-400">●</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">X Premium</span>
                    <span className="text-green-400">●</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Chiliz Chain</span>
                    <span className="text-green-400">●</span>
                  </div>
                </div>
              </div>
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex-1 ml-64 p-6">
            {children}
          </main>
        </div>
      </body>
    </html>
  )
}
