import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this folder so a stray lockfile higher up the
  // filesystem (e.g. in the user's home directory) is never picked as the root.
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
