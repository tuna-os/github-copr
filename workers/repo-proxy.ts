/**
 * Cloudflare Worker for RPM Repository Proxy
 * 
 * Handles dnf/yum metadata requests with:
 * - Custom headers (security, caching)
 * - Request logging
 * - Version-aware path routing
 * - GPG key serving
 */

const ALLOWED_ORIGINS = ["*"];
const CACHE_TTL = 3600;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = decodePathname(url.pathname);
    if (path === null) {
      return new Response("Bad Request", {
        status: 400,
        headers: getCorsHeaders(),
      });
    }
    let routedPath = path;

    // Route: Handle $releasever/$basearch path rewriting
    // Convert paths like /repo/fedora-40/x86_64/ to /repo/fedora-40-x86_64/
    routedPath = transformPath(routedPath);

    // Log request (consider sending to analytics/Logflare)
    console.log(`${request.method} ${routedPath} from ${request.headers.get("cf-connecting-ip")}`);

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return handleCors(request);
    }

    // Route: Serve GPG public key or Release.gpg signature
    if (routedPath === "/public.gpg" || routedPath === "/keys/RPM-GPG-KEY-james-rc" || routedPath.endsWith("/Release.gpg")) {
      return serveFromR2(env, routedPath === "/public.gpg" || routedPath === "/keys/RPM-GPG-KEY-james-rc" ? "public.gpg" : routedPath, {
        contentType: "application/pgp-keys",
        addHeaders: {
          "Content-Disposition": "attachment; filename=\"RPM-GPG-KEY-james-rc\"",
        },
      });
    }
 
    // Route: Serve Debian/Ubuntu APT Release metadata files (InRelease, Release)
    if (routedPath.endsWith("/InRelease") || routedPath.endsWith("/Release")) {
      return serveFromR2(env, routedPath, {
        contentType: "text/plain",
        cacheable: true,
      });
    }

    // Route: Serve Debian/Ubuntu APT Packages indices and metadata
    if (routedPath.endsWith("/Packages") || routedPath.endsWith("/Packages.gz") || routedPath.endsWith("/Sources.gz")) {
      return serveFromR2(env, routedPath, {
        contentType: routedPath.endsWith(".gz") ? "application/x-gzip" : "text/plain",
        cacheable: true,
      });
    }

    // Route: Serve Debian packages
    if (routedPath.endsWith(".deb")) {
      return serveFromR2(env, routedPath, {
        contentType: "application/x-debian-package",
        addHeaders: {
          "Content-Disposition": "attachment",
        },
      });
    }

    // Route: Serve repomd.xml (metadata)
    if (routedPath.endsWith("repomd.xml")) {
      return serveFromR2(env, routedPath, {
        contentType: "application/xml",
        cacheable: true,
      });
    }

    // Route: Serve primary/comps/filelists XML
    if (routedPath.includes("-primary.xml.gz") ||
        routedPath.includes("-filelists.xml.gz") ||
        routedPath.includes("-other.xml.gz") ||
        routedPath.includes("-comps.xml")) {
      return serveFromR2(env, routedPath, {
        contentType: routedPath.includes("gz") ? "application/x-gzip" : "application/xml",
        cacheable: true,
      });
    }

    // Route: Serve RPM packages
    if (routedPath.endsWith(".rpm")) {
      return serveFromR2(env, routedPath, {
        contentType: "application/x-rpm",
        addHeaders: {
          "Content-Disposition": "attachment",
        },
      });
    }

    // Route: Serve module metadata
    if (routedPath.includes("modules.")) {
      return serveFromR2(env, routedPath, {
        contentType: "application/x-yaml",
        cacheable: true,
      });
    }

    // Default: try serving directly
    return serveFromR2(env, routedPath, { cacheable: true });
  },
};

function decodePathname(path) {
  try {
    // Decode one URL segment at a time so an encoded slash cannot change the
    // releasever/basearch route before transformPath runs. It is still part of
    // the final R2 key, where `%2F` and `/` identify the same object path.
    return path.split("/").map((segment) => decodeURIComponent(segment)).join("/");
  } catch {
    // A malformed escape is a client error, not an R2 miss or worker failure.
    return null;
  }
}

function transformPath(path) {
  // /repo/fedora-40/x86_64/ -> /repo/fedora-40-x86_64/
  // Only rewrite when the second segment is a known CPU architecture
  // (avoids mangling paths that already have arch baked in, e.g. /repo/10-stream-x86_64/)
  const ARCH_RE = /^(x86_64|x86_64_v[23]|aarch64|i686|ppc64le|s390x|armhfp)$/;
  const match = path.match(/^\/repo\/([^\/]+)\/([^\/]+)\/(.*)$/);
  if (match && ARCH_RE.test(match[2])) {
    return `/repo/${match[1]}-${match[2]}/${match[3]}`;
  }
  return path;
}

async function serveFromR2(env, path, options = {}) {
  const { contentType, cacheable = false, addHeaders = {} } = options;

  try {
    // Strip leading slash — R2 keys don't start with /
    const key = path.startsWith("/") ? path.slice(1) : path;
    const object = await env.R2_BUCKET.get(key);

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
    for (const [key, value] of Object.entries(getCorsHeaders())) {
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
