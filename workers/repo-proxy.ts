/**
 * Cloudflare Worker for RPM Repository Proxy
 * 
 * Handles dnf/yum metadata requests with:
 * - Custom headers (security, caching)
 * - Request logging
 * - Version-aware path routing
 * - GPG key serving
 */

const R2_BUCKET = "repo-james-rc";
const ALLOWED_ORIGINS = ["*"];
const CACHE_TTL = 3600;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Log request (consider sending to analytics/Logflare)
    console.log(`${request.method} ${path} from ${request.headers.get("cf-connecting-ip")}`);

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return handleCors(request);
    }

    // Route: Serve GPG public key
    if (path === "/public.gpg" || path === "/keys/RPM-GPG-KEY-james-rc") {
      return serveFromR2(env, "public.gpg", {
        contentType: "application/pgp-keys",
        addHeaders: {
          "Content-Disposition": "attachment; filename=\"RPM-GPG-KEY-james-rc\"",
        },
      });
    }

    // Route: Serve repomd.xml (metadata)
    if (path.endsWith("repomd.xml")) {
      return serveFromR2(env, path, {
        contentType: "application/xml",
        cacheable: true,
      });
    }

    // Route: Serve primary/comps/filelists XML
    if (path.includes("-primary.xml.gz") || 
        path.includes("-filelists.xml.gz") || 
        path.includes("-comps.xml")) {
      return serveFromR2(env, path, {
        contentType: path.includes("gz") ? "application/x-gzip" : "application/xml",
        cacheable: true,
      });
    }

    // Route: Serve RPM packages
    if (path.endsWith(".rpm")) {
      return serveFromR2(env, path, {
        contentType: "application/x-rpm",
        addHeaders: {
          "Content-Disposition": "attachment",
        },
      });
    }

    // Route: Serve module metadata
    if (path.includes("modules.")) {
      return serveFromR2(env, path, {
        contentType: "application/x-yaml",
        cacheable: true,
      });
    }

    // Route: Handle $releasever/$basearch path rewriting
    // Convert paths like /repo/fedora-40/x86_64/ to /repo/fedora-40-x86_64/
    const transformedPath = transformPath(path);
    if (transformedPath !== path) {
      return serveFromR2(env, transformedPath, { cacheable: true });
    }

    // Default: try serving directly
    return serveFromR2(env, path, { cacheable: true });
  },
};

function transformPath(path) {
  // /repo/fedora-40/x86_64/ -> /repo/fedora-40-x86_64/
  const match = path.match(/^\/repo\/([^\/]+)\/([^\/]+)\/(.*)$/);
  if (match) {
    return `/repo/${match[1]}-${match[2]}/${match[3]}`;
  }
  return path;
}

async function serveFromR2(env, path, options = {}) {
  const { contentType, cacheable = false, addHeaders = {} } = options;

  try {
    const object = await env.R2_BUCKET.get(path);

    if (!object) {
      return new Response("Not Found", {
        status: 404,
        headers: getCorsHeaders(),
      });
    }

    const headers = new Headers();
    headers.set("Content-Type", contentType || "application/octet-stream");
    headers.set("ETag", object.httpEtag);

    // Security headers
    headers.set("X-Content-Type-Options", "nosniff");
    headers.set("X-Frame-Options", "DENY");
    headers.set("Referrer-Policy", "strict-origin-when-cross-origin");

    // Cache headers
    if (cacheable) {
      headers.set("Cache-Control", `public, max-age=${CACHE_TTL}`);
    } else {
      headers.set("Cache-Control", "no-store");
    }

    // Custom headers
    for (const [key, value] of Object.entries(addHeaders)) {
      headers.set(key, value);
    }

    // CORS headers
    for (const [key, value] of getCorsHeaders()) {
      headers.set(key, value);
    }

    return new Response(object.body, {
      headers,
    });
  } catch (err) {
    console.error(`Error serving ${path}:`, err);
    return new Response("Internal Server Error", {
      status: 500,
      headers: getCorsHeaders(),
    });
  }
}

function getCorsHeaders() {
  return {
    "Access-Control-Allow-Origin": ALLOWED_ORIGINS.join(", "),
    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
    "Access-Control-Allow-Headers": "*",
  };
}

function handleCors(request) {
  return new Response(null, {
    headers: getCorsHeaders(),
  });
}
