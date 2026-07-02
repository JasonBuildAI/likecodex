/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // ── Build optimization ─────────────────────────────────────────────
  swcMinify: true,                    // SWC-based minification (faster than Terser)
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production' ? { exclude: ['error', 'warn'] } : false,
  },

  // ── Output ─────────────────────────────────────────────────────────
  output: 'standalone',               // Self-contained deployment package

  // ── Security headers ───────────────────────────────────────────────
  poweredByHeader: false,             // Remove X-Powered-By header

  // ── Module transpilation ───────────────────────────────────────────
  transpilePackages: [],

  // ── Image optimization ─────────────────────────────────────────────
  images: {
    // Use raw images without optimization for local IDE environment
    unoptimized: true,
  },

  async rewrites() {
    return [
      // IDE-specific API routes go directly to Python engine
      {
        source: '/api/ide/:path*',
        destination: 'http://127.0.0.1:9090/api/ide/:path*',
      },
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:9090/:path*',
      },
      // Workspace API goes directly to Python engine
      {
        source: '/workspace/:path*',
        destination: 'http://127.0.0.1:9090/workspace/:path*',
      },
      // Inline edit API goes directly to Python engine
      {
        source: '/inline-edit',
        destination: 'http://127.0.0.1:9090/inline-edit',
      },
    ];
  },
};

module.exports = nextConfig;
