import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable standalone output for Docker deployment
  output: "standalone",

  // Disable X-Powered-By header for security
  poweredByHeader: false,

  // Enable React strict mode for development
  reactStrictMode: true,

  // Configure images
  images: {
    // Allow loading images from FastAPI service
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/api/**",
      },
      {
        protocol: "http",
        hostname: "fastapi-service",
        port: "8000",
        pathname: "/api/**",
      },
      {
        protocol: "https",
        hostname: "dgx-spark.netbird.cloud",
        pathname: "/**",
      },
    ],
  },

  // Configure redirects
  async redirects() {
    return [
      {
        source: "/",
        destination: "/chat",
        permanent: false,
      },
    ];
  },

  // Turbopack configuration (empty to silence warning)
  turbopack: {},

  // Webpack configuration for path aliases
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      "@": "/src",
    };
    return config;
  },
};

export default nextConfig;
