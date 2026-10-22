import { createFileRoute } from "@tanstack/react-router";
import { createClient } from "@supabase/supabase-js";

export const Route = createFileRoute("/sitemap.xml")({
  server: {
    handlers: {
      GET: async () => {
        const base = "https://ishtraki.store";
        const staticPaths = ["/", "/about", "/faq", "/refund-policy", "/help"];

        let slugs: string[] = [];
        try {
          const key = process.env.SUPABASE_PUBLISHABLE_KEY!;
          const sb = createClient(process.env.SUPABASE_URL!, key, {
            auth: { persistSession: false, autoRefreshToken: false },
            global: {
              fetch: (input, init) => {
                const h = new Headers(init?.headers);
                if (key.startsWith("sb_") && h.get("Authorization") === `Bearer ${key}`) h.delete("Authorization");
                h.set("apikey", key);
                return fetch(input, { ...init, headers: h });
              },
            },
          });
          const { data } = await sb.from("products").select("slug").eq("active", true);
          slugs = (data ?? []).map((r: { slug: string }) => r.slug);
        } catch {}

        const urls = [
          ...staticPaths.map((p) => `${base}${p}`),
          ...slugs.map((s) => `${base}/s/${s}`),
        ];
        const now = new Date().toISOString();
        const body = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls
          .map((u) => `  <url><loc>${u}</loc><lastmod>${now}</lastmod></url>`)
          .join("\n")}\n</urlset>`;
        return new Response(body, {
          headers: { "Content-Type": "application/xml; charset=utf-8", "Cache-Control": "public, max-age=3600" },
        });
      },
    },
  },
});
