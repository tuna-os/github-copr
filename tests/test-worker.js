import worker from "./workers/repo-proxy.ts";

const env = {
  R2_BUCKET: {
    get: async (key) => {
      console.log(`R2 get called with key: ${key}`);
      return {
        httpEtag: '"123"',
        body: 'body'
      };
    }
  }
};

const request = {
  url: "https://repo.tunaos.org/repo/fedora-43/x86_64/repodata/repomd.xml",
  method: "GET",
  headers: new Map([["cf-connecting-ip", "127.0.0.1"]])
};

worker.fetch(request, env, {}).then(res => {
  console.log("Response status:", res.status);
});
