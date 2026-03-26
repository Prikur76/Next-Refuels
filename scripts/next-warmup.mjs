import process from "process";

function getArg(name) {
  const index = process.argv.indexOf(name);
  if (index === -1) return undefined;
  const value = process.argv[index + 1];
  return value;
}

function parsePathsFromArgs() {
  const idx = process.argv.indexOf("--paths");
  if (idx === -1) return [];

  // If user passed a single comma/space-separated string as the first value,
  // we support it. Otherwise we treat all subsequent non-flag tokens as paths.
  const tokens = process.argv.slice(idx + 1).filter((t) => !t.startsWith("--"));
  if (tokens.length === 0) return [];

  const joined = tokens.join(" ");
  if (joined.includes(",") || joined.includes(" ")) {
    return joined
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  return tokens;
}

async function fetchWithTimeout(url, timeoutMs) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      method: "GET",
      redirect: "follow",
      signal: controller.signal,
    });
    return { ok: res.ok, status: res.status };
  } finally {
    clearTimeout(timeoutId);
  }
}

async function warmup(baseUrl, paths, opts) {
  const retries = opts.retries ?? 6;
  const timeoutMs = opts.timeoutMs ?? 10000;
  const sleepMs = opts.sleepMs ?? 1500;

  const uniqPaths = Array.from(new Set(paths));
  for (const p of uniqPaths) {
    const url = `${baseUrl.replace(/\/+$/, "")}${p.startsWith("/") ? "" : "/"}${p}`;
    let lastError = null;
    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        const result = await fetchWithTimeout(url, timeoutMs);
        // Warmup: нам не важен body, важен факт успешного ответа.
        if (result.status >= 200 && result.status < 400) break;
      } catch (e) {
        lastError = e;
      }
      await new Promise((r) => setTimeout(r, sleepMs));
      if (attempt === retries) {
        console.log(
          `[warmup] FAILED ${url} after ${retries} attempts: ${String(
            lastError?.message ?? "unknown"
          )}`
        );
      }
    }
  }
}

const baseUrl = getArg("--base");
const paths = parsePathsFromArgs();

if (!baseUrl || paths.length === 0) {
  console.log(
    "Usage: node next-warmup.mjs --base <url> --paths / /login /fuel/add /fuel/reports"
  );
  process.exit(1);
}

warmup(baseUrl, paths, { retries: 8, timeoutMs: 10000, sleepMs: 1200 }).then(
  () => {
    console.log("[warmup] done");
  }
);

