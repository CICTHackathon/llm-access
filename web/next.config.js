/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The Prisma engine and bcrypt run on the server only.
  experimental: { serverComponentsExternalPackages: ["@prisma/client", "bcryptjs"] },
}

module.exports = nextConfig
