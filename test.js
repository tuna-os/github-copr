// Mock Worker logic
const ALLOWED_ORIGINS = ["*"];
const CACHE_TTL = 3600;

const worker = {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    console.log(`[req] ${request.method} ${path}`);

    if (request.method === "OPTIONS") {
      return handleCors(request);
    }

    if (path === "/public.gpg" || path === "/keys/RPM-GPG-KEY-james-rc") {
      return serveFromR2(env, "public.gpg", {
        contentType: "application/pgp-keys",
      });
    }

    if (path.endsWith("repomd.xml")) {
      return serveFromR2(env, path, {
        contentType: "application/xml",
        cacheable: true,
      });
    }

    const transformedPath = transformPath(path);
    if (transformedPath !== path) {
      return serveFromR2(env, transformedPath, { cacheable: true });
    }

    return serveFromR2(env, path, { cacheable: true });
  }
};

function transformPath(path) {
  const match = path.match(/^\/repo\/([^\/]+)\/([^\/]+)\/(.*)$/);
  if (match) {
    return `/repo/${match[1]}-${match[2]}/${match[3]}`;
  }
  return path;
}

async function serveFromR2(env, path, options = {}) {
  console.log(`[R2] fetching key: ${path.startsWith("/") ? path.slice(1) : path}`);
  return { status: 200 };
}

function handleCors(request) { return { status: 200 }; }

// Test
const env = {};
const req = {
  url: "https://example.com/repo/fedora-43/x86_64/repodata/repomd.xml",
  method: "GET"
};

worker.fetch(req, env, {}).then(() => console.log("Done."));
