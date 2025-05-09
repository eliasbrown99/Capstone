/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack(config) {
    config.resolve.extensions.push('.jsx');
    return config;
  }
}

module.exports = nextConfig