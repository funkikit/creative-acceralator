/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // typedRoutes は実験的機能で型エラーを引き起こすため無効化
    // typedRoutes: true
  }
};

export default nextConfig;
