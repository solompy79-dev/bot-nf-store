import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";
import { z } from "zod";

// ============ CART ============
export const listCart = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { data, error } = await context.supabase
      .from("cart_items")
      .select("id, product_id, quantity, created_at, products(slug, name, price, duration, color, logo_slug, image_url, initials)")
      .order("created_at", { ascending: false });
    if (error) throw error;
    return data ?? [];
  });

export const addToCart = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ productId: z.string().uuid(), quantity: z.number().int().min(1).max(20).default(1) }).parse(d))
  .handler(async ({ data, context }) => {
    const { error } = await context.supabase
      .from("cart_items")
      .upsert(
        { user_id: context.userId, product_id: data.productId, quantity: data.quantity },
        { onConflict: "user_id,product_id" },
      );
    if (error) throw error;
    return { ok: true as const };
  });

export const updateCartQty = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ id: z.string().uuid(), quantity: z.number().int().min(1).max(20) }).parse(d))
  .handler(async ({ data, context }) => {
    const { error } = await context.supabase.from("cart_items").update({ quantity: data.quantity }).eq("id", data.id);
    if (error) throw error;
    return { ok: true as const };
  });

export const removeFromCart = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ id: z.string().uuid() }).parse(d))
  .handler(async ({ data, context }) => {
    const { error } = await context.supabase.from("cart_items").delete().eq("id", data.id);
    if (error) throw error;
    return { ok: true as const };
  });

export const clearCart = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { error } = await context.supabase.from("cart_items").delete().eq("user_id", context.userId);
    if (error) throw error;
    return { ok: true as const };
  });

// ============ FAVORITES ============
export const listFavorites = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { data, error } = await context.supabase
      .from("favorites")
      .select("id, product_id, products(slug, name, price, duration, color, logo_slug, image_url, initials, tagline)")
      .order("created_at", { ascending: false });
    if (error) throw error;
    return data ?? [];
  });

export const toggleFavorite = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ productId: z.string().uuid() }).parse(d))
  .handler(async ({ data, context }) => {
    const { data: existing } = await context.supabase
      .from("favorites")
      .select("id")
      .eq("user_id", context.userId)
      .eq("product_id", data.productId)
      .maybeSingle();
    if (existing) {
      await context.supabase.from("favorites").delete().eq("id", existing.id);
      return { favorited: false };
    }
    const { error } = await context.supabase
      .from("favorites")
      .insert({ user_id: context.userId, product_id: data.productId });
    if (error) throw error;
    return { favorited: true };
  });

// ============ COUPONS ============
export const applyCoupon = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ code: z.string().trim().min(1).max(40), subtotal: z.number().nonnegative() }).parse(d))
  .handler(async ({ data, context }) => {
    const code = data.code.toUpperCase();
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { data: coupon, error } = await supabaseAdmin
      .from("coupons")
      .select("id, code, discount_type, discount_value, min_amount, max_uses, uses_count, active, expires_at")
      .eq("code", code)
      .eq("active", true)
      .maybeSingle();
    if (error) throw error;
    if (!coupon) return { ok: false as const, reason: "الكود غير صحيح" };
    if (coupon.expires_at && new Date(coupon.expires_at) < new Date())
      return { ok: false as const, reason: "الكود منتهي" };
    if (coupon.max_uses !== null && coupon.uses_count >= coupon.max_uses)
      return { ok: false as const, reason: "الكود استُخدم بالكامل" };
    if (Number(coupon.min_amount) > data.subtotal)
      return { ok: false as const, reason: `الحد الأدنى ${coupon.min_amount} ج.م` };
    const discount =
      coupon.discount_type === "percent"
        ? Math.round((data.subtotal * Number(coupon.discount_value)) / 100)
        : Math.min(Number(coupon.discount_value), data.subtotal);
    return { ok: true as const, code: coupon.code, discount, discount_type: coupon.discount_type };
  });

// ============ PROFILE ============
export const getMyProfile = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { data, error } = await context.supabase
      .from("profiles")
      .select("id, full_name, phone, avatar_url, wallet_balance, referral_code, created_at")
      .eq("id", context.userId)
      .maybeSingle();
    if (error) throw error;
    // If missing (shouldn't happen with trigger, but be defensive)
    if (!data) {
      const referralCode = Math.random().toString(36).slice(2, 10).toUpperCase();
      await context.supabase.from("profiles").insert({ id: context.userId, referral_code: referralCode });
      return { id: context.userId, full_name: null, phone: null, avatar_url: null, wallet_balance: 0, referral_code: referralCode, created_at: new Date().toISOString() };
    }
    return data;
  });

export const updateMyProfile = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) =>
    z.object({
      full_name: z.string().trim().max(120).optional().nullable(),
      phone: z.string().trim().max(30).optional().nullable(),
    }).parse(d),
  )
  .handler(async ({ data, context }) => {
    const { error } = await context.supabase
      .from("profiles")
      .update({ full_name: data.full_name ?? null, phone: data.phone ?? null })
      .eq("id", context.userId);
    if (error) throw error;
    return { ok: true as const };
  });

// ============ REVIEWS ============
export const listProductReviews = createServerFn({ method: "GET" })
  .inputValidator((d: unknown) => z.object({ productId: z.string().uuid() }).parse(d))
  .handler(async ({ data }) => {
    const { createClient } = await import("@supabase/supabase-js");
    const key = process.env.SUPABASE_PUBLISHABLE_KEY!;
    const client = createClient(process.env.SUPABASE_URL!, key, {
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
    const { data: rows, error } = await client
      .from("reviews")
      .select("id, user_id, rating, comment, created_at")
      .eq("product_id", data.productId)
      .eq("approved", true)
      .order("created_at", { ascending: false })
      .limit(50);
    if (error) throw error;
    return rows ?? [];
  });

export const submitReview = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) =>
    z.object({
      productId: z.string().uuid(),
      rating: z.number().int().min(1).max(5),
      comment: z.string().trim().max(500).optional().nullable(),
    }).parse(d),
  )
  .handler(async ({ data, context }) => {
    const { error } = await context.supabase
      .from("reviews")
      .upsert(
        { user_id: context.userId, product_id: data.productId, rating: data.rating, comment: data.comment ?? null },
        { onConflict: "user_id,product_id" },
      );
    if (error) throw error;
    return { ok: true as const };
  });

// ============ NOTIFICATIONS ============
export const listMyNotifications = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { data, error } = await context.supabase
      .from("notifications")
      .select("id, title, body, type, link, read, created_at")
      .order("created_at", { ascending: false })
      .limit(50);
    if (error) throw error;
    return data ?? [];
  });

export const markNotificationRead = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ id: z.string().uuid() }).parse(d))
  .handler(async ({ data, context }) => {
    await context.supabase.from("notifications").update({ read: true }).eq("id", data.id);
    return { ok: true as const };
  });

export const markAllNotificationsRead = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    await context.supabase.from("notifications").update({ read: true }).eq("user_id", context.userId).eq("read", false);
    return { ok: true as const };
  });

// ============ TICKETS ============
export const listMyTickets = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { data, error } = await context.supabase
      .from("tickets")
      .select("id, subject, status, priority, created_at, updated_at")
      .order("updated_at", { ascending: false });
    if (error) throw error;
    return data ?? [];
  });

export const createTicket = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) =>
    z.object({
      subject: z.string().trim().min(3).max(200),
      message: z.string().trim().min(3).max(2000),
    }).parse(d),
  )
  .handler(async ({ data, context }) => {
    const { data: ticket, error } = await context.supabase
      .from("tickets")
      .insert({ user_id: context.userId, subject: data.subject })
      .select("id")
      .single();
    if (error) throw error;
    await context.supabase
      .from("ticket_messages")
      .insert({ ticket_id: ticket.id, sender_id: context.userId, is_staff: false, message: data.message });
    return { id: ticket.id };
  });

export const getTicket = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ id: z.string().uuid() }).parse(d))
  .handler(async ({ data, context }) => {
    const [ticketRes, msgRes] = await Promise.all([
      context.supabase.from("tickets").select("*").eq("id", data.id).maybeSingle(),
      context.supabase.from("ticket_messages").select("*").eq("ticket_id", data.id).order("created_at"),
    ]);
    if (ticketRes.error) throw ticketRes.error;
    return { ticket: ticketRes.data, messages: msgRes.data ?? [] };
  });

export const replyTicket = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ ticketId: z.string().uuid(), message: z.string().trim().min(1).max(2000) }).parse(d))
  .handler(async ({ data, context }) => {
    const { error } = await context.supabase
      .from("ticket_messages")
      .insert({ ticket_id: data.ticketId, sender_id: context.userId, is_staff: false, message: data.message });
    if (error) throw error;
    await context.supabase.from("tickets").update({ status: "open", updated_at: new Date().toISOString() }).eq("id", data.ticketId);
    return { ok: true as const };
  });

// ============ CHECKOUT (from cart with coupon) ============
export const submitCartOrder = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) =>
    z.object({
      couponCode: z.string().trim().max(40).optional().nullable(),
      deliveryPhone: z.string().trim().max(30).optional().nullable(),
      senderPhone: z.string().trim().max(30).optional().nullable(),
      imageBase64: z.string().min(20).optional().nullable(),
    }).parse(d),
  )
  .handler(async ({ data, context }) => {
    const { data: items, error: cartErr } = await context.supabase
      .from("cart_items")
      .select("id, product_id, quantity, products(id, slug, name, price)")
      .eq("user_id", context.userId);
    if (cartErr) throw cartErr;
    if (!items || items.length === 0) return { ok: false as const, reason: "السلة فارغة" };

    type CartRow = { id: string; product_id: string; quantity: number; products: { id: string; slug: string; name: string; price: number } | null };
    const rows = items as unknown as CartRow[];
    const subtotal = rows.reduce((sum, it) => sum + (it.products ? Number(it.products.price) * it.quantity : 0), 0);

    let discount = 0;
    let appliedCode: string | null = null;
    if (data.couponCode) {
      const code = data.couponCode.toUpperCase();
      const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
      const { data: coupon } = await supabaseAdmin
        .from("coupons")
        .select("id, code, discount_type, discount_value, min_amount, max_uses, uses_count, active, expires_at")
        .eq("code", code)
        .eq("active", true)
        .maybeSingle();
      if (coupon && Number(coupon.min_amount) <= subtotal && (!coupon.expires_at || new Date(coupon.expires_at) > new Date())) {
        discount = coupon.discount_type === "percent"
          ? Math.round((subtotal * Number(coupon.discount_value)) / 100)
          : Math.min(Number(coupon.discount_value), subtotal);
        appliedCode = coupon.code;
      }
    }

    const total = Math.max(0, subtotal - discount);

    // Create one order per cart item (keeps existing schema simple)
    const inserts = rows
      .filter((it) => it.products)
      .map((it) => ({
        user_id: context.userId,
        product_slug: it.products!.slug,
        product_name: `${it.products!.name}${it.quantity > 1 ? ` × ${it.quantity}` : ""}`,
        amount: Number(it.products!.price) * it.quantity,
        currency: "EGP",
        status: "pending" as const,
        coupon_code: appliedCode,
        discount_amount: 0,
        delivery_phone: data.deliveryPhone ?? null,
        sender_phone: data.senderPhone ?? null,
      }));
    if (inserts.length > 0 && discount > 0) {
      // Attribute discount proportionally to first order
      inserts[0].discount_amount = discount;
      inserts[0].amount = Math.max(0, inserts[0].amount - discount);
    }

    const { data: created, error: insErr } = await context.supabase.from("orders").insert(inserts).select("id");
    if (insErr) throw insErr;

    // Clear cart
    await context.supabase.from("cart_items").delete().eq("user_id", context.userId);

    return { ok: true as const, orderIds: (created ?? []).map((r) => r.id), total, subtotal, discount };
  });
