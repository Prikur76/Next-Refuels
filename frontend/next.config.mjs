/** @type {import('next').NextConfig} */
const backendBaseUrl =
  process.env.NEXT_INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";
const backendBaseUrlNormalized = backendBaseUrl.replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  skipTrailingSlashRedirect: true,
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  
  // ✅ Webpack-конфиг
  webpack: (config, { dev, isServer }) => {
    if (dev && !isServer && process.env.WATCHPACK_POLLING) {
      const interval = Number(process.env.WATCHPACK_POLLING) || 1000;
      config.watchOptions = {
        poll: interval,
        aggregateTimeout: 300,
      };
    }
    return config;
  }, 

  // ✅ Turbopack-конфиг
  turbopack: {},
  
  // ✅ Rewrites 
  async rewrites() {
    return [
      {
        source: "/api/v1/reports/export/csv",
        destination: "/api/reports/export/csv",
      },
      {
        source: "/api/v1/reports/export/csv/",
        destination: "/api/reports/export/csv",
      },
      {
        source: "/api/v1/reports/export/xlsx",
        destination: "/api/reports/export/xlsx",
      },
      {
        source: "/api/v1/reports/export/xlsx/",
        destination: "/api/reports/export/xlsx",
      },
      {
        source: "/accounts/login",
        destination: `${backendBaseUrlNormalized}/accounts/login/`,
      },
      {
        source: "/api/v1/:path*",
        destination: `${backendBaseUrlNormalized}/api/v1/:path*`,
      },
      {
        source: "/accounts/:path*",
        destination: `${backendBaseUrlNormalized}/accounts/:path*`,
      },
    ];
  },
};

export default nextConfig;