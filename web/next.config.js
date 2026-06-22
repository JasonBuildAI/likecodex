/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8080/:path*',
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
