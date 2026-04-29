import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Python FastAPI로 API 요청 프록시 (개발 환경)
  async rewrites() {
    return [
      {
        source: "/api/rpa/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001/dashboard"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
