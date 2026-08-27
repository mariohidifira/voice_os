import type { NextConfig } from "next";
const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  allowedDevOrigins: ["http://localhost:3100", "http://127.0.0.1:3100"],
};
export default config;
