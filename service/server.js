// Bear-Net Soundboard service
// Stores call soundboard clips, enforces limits, and gates everything behind
// a valid Stoat session token (verified against the instance API).

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const express = require("express");
const multer = require("multer");

const PORT = parseInt(process.env.PORT ?? "8600", 10);
const API_URL = process.env.API_URL ?? "http://api:14702";
const ADMIN_USER_ID = process.env.ADMIN_USER_ID ?? "";
const DATA_DIR = process.env.DATA_DIR ?? "/data";
const BUILTIN_DIR = process.env.BUILTIN_DIR ?? "/app/builtin";
const MAX_SECONDS = 10;
const MAX_UPLOAD_BYTES = 2 * 1024 * 1024;
const MAX_UPLOADS = 42;

fs.mkdirSync(path.join(DATA_DIR, "files"), { recursive: true });
const META_PATH = path.join(DATA_DIR, "sounds.json");

function loadMeta() {
  try {
    return JSON.parse(fs.readFileSync(META_PATH, "utf8"));
  } catch {
    return [];
  }
}
function saveMeta(meta) {
  fs.writeFileSync(META_PATH, JSON.stringify(meta, null, 2));
}

// ---- auth: verify session token against the Stoat API, cache 5 minutes ----
const tokenCache = new Map();
async function verifyToken(token) {
  if (!token) return null;
  const hit = tokenCache.get(token);
  if (hit && Date.now() - hit.ts < 5 * 60 * 1000) return hit.user;
  try {
    const res = await fetch(`${API_URL}/users/@me`, {
      headers: { "x-session-token": token },
    });
    if (!res.ok) return null;
    const user = await res.json();
    tokenCache.set(token, { user, ts: Date.now() });
    return user;
  } catch {
    return null;
  }
}

const app = express();

// Accept paths both with and without the /soundboard prefix, so the service
// works whether or not the reverse proxy strips it.
app.use((req, _res, next) => {
  if (req.url.startsWith("/soundboard/"))
    req.url = req.url.slice("/soundboard".length);
  next();
});

app.use(async (req, res, next) => {
  const user = await verifyToken(req.header("x-session-token"));
  if (!user) return res.status(401).json({ error: "Not signed in to Stoat" });
  req.user = user;
  next();
});

function listBuiltin() {
  try {
    return fs
      .readdirSync(BUILTIN_DIR)
      .filter((f) => f.endsWith(".ogg"))
      .map((f) => ({
        id: `b_${f.replace(/\.ogg$/, "")}`,
        label: f.replace(/\.ogg$/, "").replace(/_/g, " "),
        builtin: true,
        canDelete: false,
      }));
  } catch {
    return [];
  }
}

app.get("/list", (req, res) => {
  const uploads = loadMeta().map((s) => ({
    id: s.id,
    label: s.label,
    builtin: false,
    canDelete: s.owner === req.user._id || req.user._id === ADMIN_USER_ID,
  }));
  res.json([...listBuiltin(), ...uploads]);
});

app.get("/files/:id", (req, res) => {
  const id = req.params.id;
  if (/^b_[a-z0-9_]+$/i.test(id)) {
    const file = path.join(BUILTIN_DIR, `${id.slice(2)}.ogg`);
    if (fs.existsSync(file)) return res.type("audio/ogg").sendFile(file);
  }
  const meta = loadMeta().find((s) => s.id === id);
  if (meta) {
    const file = path.join(DATA_DIR, "files", meta.file);
    if (fs.existsSync(file)) return res.type("audio/ogg").sendFile(file);
  }
  res.status(404).json({ error: "No such sound" });
});

const upload = multer({
  dest: path.join(DATA_DIR, "tmp"),
  limits: { fileSize: MAX_UPLOAD_BYTES, files: 1 },
});

app.post("/upload", upload.single("file"), (req, res) => {
  const tmp = req.file?.path;
  const cleanup = () => {
    try {
      if (tmp) fs.unlinkSync(tmp);
    } catch {}
  };
  try {
    if (!tmp) return res.status(400).json({ error: "No file received" });
    if (loadMeta().length >= MAX_UPLOADS) {
      cleanup();
      return res.status(400).json({ error: "The board is full (42 uploads)" });
    }

    let duration;
    try {
      duration = parseFloat(
        execFileSync(
          "ffprobe",
          ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", tmp],
          { timeout: 10000 },
        )
          .toString()
          .trim(),
      );
    } catch {
      cleanup();
      return res.status(400).json({ error: "Not a playable audio file" });
    }
    if (!Number.isFinite(duration) || duration <= 0) {
      cleanup();
      return res.status(400).json({ error: "Not a playable audio file" });
    }
    if (duration > MAX_SECONDS + 0.05) {
      cleanup();
      return res
        .status(400)
        .json({ error: `Too long: ${duration.toFixed(1)}s (max ${MAX_SECONDS}s)` });
    }

    const id = crypto.randomBytes(8).toString("hex");
    const outFile = `${id}.ogg`;
    try {
      execFileSync(
        "ffmpeg",
        ["-y", "-loglevel", "error", "-i", tmp, "-vn", "-ac", "1",
         "-c:a", "libvorbis", "-q:a", "4",
         path.join(DATA_DIR, "files", outFile)],
        { timeout: 30000 },
      );
    } catch {
      cleanup();
      return res.status(400).json({ error: "Could not convert that file" });
    }
    cleanup();

    const rawLabel = (req.file.originalname ?? "sound")
      .replace(/\.[^.]+$/, "")
      .replace(/[^\w\- ]+/g, "")
      .trim()
      .slice(0, 20) || "sound";

    const meta = loadMeta();
    meta.push({
      id,
      label: rawLabel,
      owner: req.user._id,
      ownerName: req.user.username ?? "",
      file: outFile,
      uploadedAt: new Date().toISOString(),
    });
    saveMeta(meta);
    res.json({ id, label: rawLabel });
  } catch (err) {
    cleanup();
    res.status(500).json({ error: "Upload failed" });
  }
});

app.delete("/sounds/:id", (req, res) => {
  const meta = loadMeta();
  const idx = meta.findIndex((s) => s.id === req.params.id);
  if (idx === -1) return res.status(404).json({ error: "No such sound" });
  const sound = meta[idx];
  if (sound.owner !== req.user._id && req.user._id !== ADMIN_USER_ID)
    return res.status(403).json({ error: "You can only delete your own sounds" });
  try {
    fs.unlinkSync(path.join(DATA_DIR, "files", sound.file));
  } catch {}
  meta.splice(idx, 1);
  saveMeta(meta);
  res.json({ ok: true });
});

// multer errors (e.g. file too large) fall through here
app.use((err, _req, res, _next) => {
  if (err?.code === "LIMIT_FILE_SIZE")
    return res.status(400).json({ error: "File too large (max 2 MB)" });
  res.status(500).json({ error: "Something went wrong" });
});

app.listen(PORT, () => console.log(`soundboard listening on :${PORT}`));
