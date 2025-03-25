/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  
  // Static export configuration for Next.js 13+
  output: 'export',
  
  // Required for static export with images
  images: {
    unoptimized: true,
  },
  
  /*
  // API proxy configuration (will work during development but not in static export)
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://mm2xymkp2i.eu-west-2.awsapprunner.com/api/v1';
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/:path*`,
      },
    ];
  }
  */
  // Environment variable configuration
  env: {
    // Store full URLs for API endpoints, but only hostnames for WebSockets
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://e39gefrnpq.eu-west-2.awsapprunner.com',
    // Store only the hostname without protocol for WebSocket connections
    NEXT_PUBLIC_WS_HOST: process.env.NEXT_PUBLIC_WS_HOST || 'e39gefrnpq.eu-west-2.awsapprunner.com',
    // WebSocket Gateway URL
    NEXT_PUBLIC_WS_GATEWAY: process.env.NEXT_PUBLIC_WS_GATEWAY || 'wss://5nu02h2v13.execute-api.eu-west-2.amazonaws.com/production'

  }
}

module.exports = nextConfig;
