/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  images: {
    domains: ['s2.coinmarketcap.com'],
  },
}

module.exports = nextConfig
