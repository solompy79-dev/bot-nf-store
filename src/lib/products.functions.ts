import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import type { Product } from "@/lib/products";

const ADMIN_PASSWORD = "592026";

function checkPw(pw: unknown) {
  if (typeof pw !== "string" || pw !== ADMIN_PASSWORD) {
    throw new Error("كلمة السر غلط");
  }
}

type Row = {
  id: string;
  slug: string;
  name: string;
  tagline: string;
  initials: string;
  color: string;
  logo_slug: string | null;
  image_url: string | null;
  duration: string;
  price: number;
  badge: string | null;
  description: string | null;
  features: unknown;
  sort_order: number;
  active: boolean;
};

function toProduct(r: Row): Product & { id: string; active: boolean; sort_order: number } {
  return {
    id: r.id,
    slug: r.slug,
    name: r.name,
    tagline: r.tagline ?? "",
    initials: r.initials ?? "",
    color: r.color,
    logoSlug: r.logo_slug ?? undefined,
    imageUrl: r.image_url ?? undefined,
    duration: r.duration,
    price: Number(r.price),
    badge: r.badge ?? undefined,
    description: r.description ?? undefined,
    features: Array.isArray(r.features) ? (r.features as string[]) : [],
    sort_order: r.sort_order,
    active: r.active,
  };
}

export const listProducts = createServerFn({ method: "GET" }).handler(async () => {
  const { supabase } = await import("@/integrations/supabase/client");
  const { data, error } = await supabase
    .from("products")
    .select("*")
    .eq("active", true)
    .order("sort_order", { ascending: true });
  if (error) throw error;
  return (data ?? []).map(toProduct);
});

export const adminListProducts = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => z.object({ password: z.string() }).parse(d))
  .handler(async ({ data }) => {
    checkPw(data.password);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { data: rows, error } = await supabaseAdmin
      .from("products")
      .select("*")
      .order("sort_order", { ascending: true });
    if (error) throw error;
    return (rows ?? []).map(toProduct);
  });

const ProductInput = z.object({
  slug: z.string().min(1),
  name: z.string().min(1),
  tagline: z.string().default(""),
  initials: z.string().default(""),
  color: z.string().default("linear-gradient(135deg,#8b5cf6,#4c1d95)"),
  logoSlug: z.string().nullable().optional(),
  imageUrl: z.string().nullable().optional(),
  duration: z.string().default("شهر"),
  price: z.number().nonnegative(),
  badge: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  features: z.array(z.string()).default([]),
  sort_order: z.number().int().default(0),
  active: z.boolean().default(true),
});

export const adminUpsertProduct = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) =>
    z.object({ password: z.string(), id: z.string().uuid().optional(), product: ProductInput }).parse(d),
  )
  .handler(async ({ data }) => {
    checkPw(data.password);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const p = data.product;
    const payload = {
      slug: p.slug,
      name: p.name,
      tagline: p.tagline,
      initials: p.initials,
      color: p.color,
      logo_slug: p.logoSlug ?? null,
      image_url: p.imageUrl ?? null,
      duration: p.duration,
      price: p.price,
      badge: p.badge ?? null,
      description: p.description ?? null,
      features: p.features,
      sort_order: p.sort_order,
      active: p.active,
    };
    if (data.id) {
      const { data: row, error } = await supabaseAdmin
        .from("products").update(payload).eq("id", data.id).select("*").single();
      if (error) throw error;
      return toProduct(row as Row);
    }
    const { data: row, error } = await supabaseAdmin
      .from("products").insert(payload).select("*").single();
    if (error) throw error;
    return toProduct(row as Row);
  });

export const adminDeleteProduct = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => z.object({ password: z.string(), id: z.string().uuid() }).parse(d))
  .handler(async ({ data }) => {
    checkPw(data.password);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { error } = await supabaseAdmin.from("products").delete().eq("id", data.id);
    if (error) throw error;
    return { ok: true as const };
  });
