var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// workers/repo-proxy.ts
var ALLOWED_ORIGINS = ["*"];
var CACHE_TTL = 3600;
var repo_proxy_default = {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    let path = url.pathname;
    path = transformPath(path);
    console.log(`${request.method} ${path} from ${request.headers.get("cf-connecting-ip")}`);
    if (request.method === "OPTIONS") {
      return handleCors(request);
    }
    if (path === "/public.gpg" || path === "/keys/RPM-GPG-KEY-james-rc") {
      return serveFromR2(env, "public.gpg", {
        contentType: "application/pgp-keys",
        addHeaders: {
          "Content-Disposition": 'attachment; filename="RPM-GPG-KEY-james-rc"'
        }
      });
    }
    if (path.endsWith("repomd.xml")) {
      return serveFromR2(env, path, {
        contentType: "application/xml",
        cacheable: true
      });
    }
    if (path.includes("-primary.xml.gz") || path.includes("-filelists.xml.gz") || path.includes("-other.xml.gz") || path.includes("-comps.xml")) {
      return serveFromR2(env, path, {
        contentType: path.includes("gz") ? "application/x-gzip" : "application/xml",
        cacheable: true
      });
    }
    if (path.endsWith(".rpm")) {
      return serveFromR2(env, path, {
        contentType: "application/x-rpm",
        addHeaders: {
          "Content-Disposition": "attachment"
        }
      });
    }
    if (path.includes("modules.")) {
      return serveFromR2(env, path, {
        contentType: "application/x-yaml",
        cacheable: true
      });
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
__name(transformPath, "transformPath");
async function serveFromR2(env, path, options = {}) {
  const { contentType, cacheable = false, addHeaders = {} } = options;
  try {
    const key = path.startsWith("/") ? path.slice(1) : path;
    const object = await env.R2_BUCKET.get(key);
    if (!object) {
      return new Response("Not Found", {
        status: 404,
        headers: getCorsHeaders()
      });
    }
    const headers = new Headers();
    headers.set("Content-Type", contentType || "application/octet-stream");
    headers.set("ETag", object.httpEtag);
    headers.set("X-Content-Type-Options", "nosniff");
    headers.set("X-Frame-Options", "DENY");
    headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
    if (cacheable) {
      headers.set("Cache-Control", `public, max-age=${CACHE_TTL}`);
    } else {
      headers.set("Cache-Control", "no-store");
    }
    for (const [key2, value] of Object.entries(addHeaders)) {
      headers.set(key2, value);
    }
    for (const [key2, value] of Object.entries(getCorsHeaders())) {
      headers.set(key2, value);
    }
    return new Response(object.body, {
      headers
    });
  } catch (err) {
    console.error(`Error serving ${path}:`, err);
    return new Response("Internal Server Error", {
      status: 500,
      headers: getCorsHeaders()
    });
  }
}
__name(serveFromR2, "serveFromR2");
function getCorsHeaders() {
  return {
    "Access-Control-Allow-Origin": ALLOWED_ORIGINS.join(", "),
    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
    "Access-Control-Allow-Headers": "*"
  };
}
__name(getCorsHeaders, "getCorsHeaders");
function handleCors(request) {
  return new Response(null, {
    headers: getCorsHeaders()
  });
}
__name(handleCors, "handleCors");
export {
  repo_proxy_default as default
};
//# sourceMappingURL=repo-proxy.js.map
