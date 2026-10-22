import { DatabaseSync } from "node:sqlite";
import { randomBytes, randomUUID, scrypt as scryptCallback, timingSafeEqual, createHash } from "node:crypto";
import { promisify } from "node:util";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
const scrypt = promisify(scryptCallback);
const COOKIE = "ishtiraki_local_session";
const TTL = 7 * 24 * 60 * 60 * 1000;
const digest = value => createHash("sha256").update(value).digest("hex");

export function localAuthPlugin() {
  return {
    name: "ishtiraki-local-auth",
    apply: "serve",
    configureServer(server) {
      if (process.env.LOCAL_AUTH !== "true") return;
      const path = resolve(process.env.LOCAL_AUTH_DB || ".local/accounts.sqlite");
      mkdirSync(dirname(path), { recursive: true });
      const db = new DatabaseSync(path);
      db.exec(`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, hash TEXT NOT NULL, salt TEXT NOT NULL, full_name TEXT NOT NULL, phone TEXT NOT NULL, referral_code TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires INTEGER NOT NULL);
      `);
      const attempts = new Map();
      server.httpServer?.once("close", () => db.close());
      const profile = u => ({ id: u.id, full_name: u.full_name, phone: u.phone, avatar_url: null, wallet_balance: 0, referral_code: u.referral_code, created_at: u.created_at });
      const user = u => ({ id: u.id, email: u.email, aud: "authenticated", role: "authenticated", created_at: u.created_at, app_metadata: { provider: "local", providers: ["local"] }, user_metadata: { full_name: u.full_name, phone: u.phone } });
      const session = u => ({ user: user(u), access_token: "", refresh_token: "", token_type: "local" });
      function issue(res, id) {
        const token = randomBytes(32).toString("hex");
        db.prepare("DELETE FROM sessions WHERE expires < ?").run(Date.now());
        db.prepare("INSERT INTO sessions VALUES (?, ?, ?)").run(digest(token), id, Date.now() + TTL);
        res.setHeader("Set-Cookie", COOKIE + "=" + token + "; HttpOnly; SameSite=Strict; Path=/api/local-auth; Max-Age=" + TTL / 1000);
      }
      server.middlewares.use(async (req, res, next) => {
        if (!req.url?.startsWith("/api/local-auth/")) return next();
        const reply = (status, data) => { res.statusCode = status; res.setHeader("Content-Type", "application/json; charset=utf-8"); res.setHeader("Cache-Control", "no-store"); res.end(JSON.stringify(data)); };
        try {
          if (!["GET", "POST"].includes(req.method)) return reply(405, { message: "طريقة غير مسموحة" });
          const action = req.url.split("?")[0].slice("/api/local-auth/".length);
          if (req.method === "POST") {
            const origin = req.headers.origin;
            if (!origin || new URL(origin).host !== req.headers.host) return reply(403, { message: "طلب غير مسموح" });
            if (!req.headers["content-type"]?.startsWith("application/json")) return reply(415, { message: "صيغة غير مدعومة" });
          }
          let body = {};
          if (req.method === "POST") {
            const chunks = []; let size = 0;
            for await (const chunk of req) { size += chunk.length; if (size > 8192) return reply(413, { message: "الطلب كبير جدًا" }); chunks.push(chunk); }
            try { body = JSON.parse(Buffer.concat(chunks).toString() || "{}"); } catch { return reply(400, { message: "بيانات غير صالحة" }); }
            if (!body || typeof body !== "object" || Array.isArray(body)) return reply(400, { message: "بيانات غير صالحة" });
          }
          const raw = req.headers.cookie?.split(";").map(v => v.trim()).find(v => v.startsWith(COOKIE + "="))?.slice(COOKIE.length + 1) || "";
          const current = raw ? db.prepare("SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id WHERE sessions.token=? AND sessions.expires>?").get(digest(raw), Date.now()) : null;
          if (action === "session" && req.method === "GET") return reply(200, { session: current ? session(current) : null });
          if (action === "signout" && req.method === "POST") {
            if (raw) db.prepare("DELETE FROM sessions WHERE token=?").run(digest(raw));
            res.setHeader("Set-Cookie", COOKIE + "=; HttpOnly; SameSite=Strict; Path=/api/local-auth; Max-Age=0");
            return reply(200, { ok: true });
          }
          if (["signup", "signin"].includes(action) && req.method === "POST") {
            const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
            const password = typeof body.password === "string" ? body.password : "";
            if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254) return reply(400, { message: "اكتب إيميل صحيح" });
            if (password.length < 8 || password.length > 128) return reply(400, { message: "كلمة السر لازم تكون من 8 إلى 128 حرف" });
            const rateKey = req.socket.remoteAddress + ":" + email;
            const now = Date.now();
            if (attempts.size > 1000) for (const [key, value] of attempts) if (value.until < now) attempts.delete(key);
            const entry = attempts.get(rateKey);
            if (entry && entry.until > now && entry.count >= 10) return reply(429, { message: "محاولات كتير. جرب بعد 15 دقيقة" });
            attempts.set(rateKey, { count: entry && entry.until > now ? entry.count + 1 : 1, until: entry && entry.until > now ? entry.until : now + 900000 });
            let u = db.prepare("SELECT * FROM users WHERE email=?").get(email);
            if (action === "signup") {
              if (u) return reply(409, { message: "الإيميل مسجل محليًا بالفعل، سجّل دخولك" });
              const fullName = typeof body.full_name === "string" ? body.full_name.trim().slice(0, 120) : "";
              const phone = typeof body.phone === "string" ? body.phone.trim().slice(0, 30) : "";
              if (!fullName) return reply(400, { message: "اكتب اسمك" });
              const salt = randomBytes(16).toString("hex");
              const hash = (await scrypt(password, salt, 64)).toString("hex");
              const id = randomUUID();
              try { db.prepare("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)").run(id, email, hash, salt, fullName, phone, randomBytes(5).toString("hex").toUpperCase(), new Date().toISOString()); }
              catch (error) { if (error.code === "ERR_SQLITE_ERROR") return reply(409, { message: "الإيميل مسجل بالفعل" }); throw error; }
              u = db.prepare("SELECT * FROM users WHERE id=?").get(id);
            } else {
              const hash = await scrypt(password, u?.salt || "local-auth-dummy-salt", 64);
              if (!u || !timingSafeEqual(hash, Buffer.from(u.hash, "hex"))) return reply(401, { code: "invalid_credentials", message: "الإيميل أو كلمة السر غير صحيحين" });
            }
            attempts.delete(rateKey);
            issue(res, u.id);
            return reply(200, { session: session(u), user: user(u) });
          }
          if (!current) return reply(401, { message: "سجل دخولك الأول" });
          if (action === "profile" && req.method === "GET") return reply(200, profile(current));
          if (action === "profile" && req.method === "POST") {
            if (typeof body.full_name !== "string" || !body.full_name.trim() || body.full_name.length > 120 || typeof body.phone !== "string" || body.phone.length > 30) return reply(400, { message: "راجع بيانات الاسم والموبايل" });
            db.prepare("UPDATE users SET full_name=?, phone=? WHERE id=?").run(body.full_name.trim(), body.phone.trim(), current.id);
            return reply(200, { ok: true });
          }
          if (action === "password" && req.method === "POST") {
            if (typeof body.password !== "string" || body.password.length < 8 || body.password.length > 128) return reply(400, { message: "كلمة السر لازم تكون من 8 إلى 128 حرف" });
            if (typeof body.current_password !== "string" || body.current_password.length > 128) return reply(400, { message: "اكتب كلمة السر الحالية" });
            const oldHash = await scrypt(body.current_password, current.salt, 64);
            if (!timingSafeEqual(oldHash, Buffer.from(current.hash, "hex"))) return reply(403, { message: "كلمة السر الحالية غير صحيحة" });
            const salt = randomBytes(16).toString("hex");
            const hash = (await scrypt(body.password, salt, 64)).toString("hex");
            db.prepare("UPDATE users SET hash=?, salt=? WHERE id=?").run(hash, salt, current.id);
            db.prepare("DELETE FROM sessions WHERE user_id=?").run(current.id);
            issue(res, current.id);
            return reply(200, { user: user(current) });
          }
          return reply(404, { message: "المسار غير موجود" });
        } catch (error) { console.error("[local-auth]", error); reply(500, { message: "تعذّر تنفيذ الطلب، حاول مرة تانية" }); }
      });
    },
  };
}
