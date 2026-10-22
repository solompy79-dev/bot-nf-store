import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";
import { z } from "zod";
import { getProduct as getStaticProduct } from "@/lib/products";

async function fetchProduct(slug: string) {
  const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
  const { data } = await supabaseAdmin
    .from("products")
    .select("slug, name, price")
    .eq("slug", slug)
    .maybeSingle();
  if (data) return { slug: data.slug, name: data.name, price: Number(data.price) };
  const s = getStaticProduct(slug);
  return s ? { slug: s.slug, name: s.name, price: s.price } : null;
}

const MERCHANT_PHONE = "01116945570";
const MERCHANT_PHONE_ALT = "201116945570";

const SubmitInput = z.object({
  slug: z.string().min(1),
  imageBase64: z.string().min(20), // data URL: data:image/...;base64,....
  senderPhone: z.string().trim().min(6).max(20).optional(),
});

type VerifyResult = {
  matched: boolean;
  detected_amount: number | null;
  detected_phone: string | null;
  reason: string;
};

async function verifyReceiptWithAI(
  imageDataUrl: string,
  expectedAmount: number,
  expectedPhone: string,
): Promise<VerifyResult> {
  const key = process.env.LOVABLE_API_KEY;
  if (!key) {
    return { matched: false, detected_amount: null, detected_phone: null, reason: "AI service unavailable" };
  }

  const prompt = `أنت مسؤول تحقق من إيصالات تحويل فودافون كاش / انستاباي / محافظ إلكترونية مصرية.
حلّل صورة الإيصال المرفقة واستخرج:
1. رقم الهاتف المُحوَّل إليه (رقم المستلم / Recipient number).
2. المبلغ الذي تم تحويله بالجنيه المصري.

المتوقع:
- الرقم المُحوَّل إليه = ${expectedPhone} (أو ${MERCHANT_PHONE_ALT} بصيغة دولية)
- المبلغ = ${expectedAmount} جنيه مصري

أرجع JSON فقط بهذا الشكل بدون أي نص إضافي:
{"detected_amount": <number or null>, "detected_phone": "<string or null>", "matched": <true/false>, "reason": "<شرح مختصر بالعربية>"}

المطابقة تعتبر ناجحة (matched=true) فقط لو الرقم والمبلغ الاتنين مطابقين.`;

  try {
    const res = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${key}`,
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash",
        messages: [
          {
            role: "user",
            content: [
              { type: "text", text: prompt },
              { type: "image_url", image_url: { url: imageDataUrl } },
            ],
          },
        ],
        response_format: { type: "json_object" },
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      console.error("AI verify failed", res.status, errText);
      return { matched: false, detected_amount: null, detected_phone: null, reason: "تعذر التحقق تلقائيًا، سيتم المراجعة يدويًا" };
    }

    const data = await res.json();
    const text: string = data.choices?.[0]?.message?.content ?? "{}";
    const cleaned = text.replace(/^```json\s*|\s*```$/g, "").trim();
    const parsed = JSON.parse(cleaned);

    const detectedPhone = parsed.detected_phone ? String(parsed.detected_phone).replace(/\D/g, "") : null;
    const expectedDigits = expectedPhone.replace(/\D/g, "");
    const expectedIntl = MERCHANT_PHONE_ALT;
    const phoneOk = !!detectedPhone && (
      detectedPhone.endsWith(expectedDigits) ||
      detectedPhone.endsWith(expectedIntl) ||
      detectedPhone === expectedDigits ||
      detectedPhone === expectedIntl
    );

    const detectedAmount = typeof parsed.detected_amount === "number" ? parsed.detected_amount : null;
    const amountOk = detectedAmount !== null && Math.abs(detectedAmount - expectedAmount) < 0.5;

    const matched = phoneOk && amountOk;

    let reason = String(parsed.reason ?? "");
    if (!matched) {
      const issues: string[] = [];
      if (!phoneOk) issues.push(`الرقم في الإيصال ${detectedPhone ?? "غير واضح"} — المطلوب ${expectedPhone}`);
      if (!amountOk) issues.push(`المبلغ في الإيصال ${detectedAmount ?? "غير واضح"} — المطلوب ${expectedAmount} ج.م`);
      reason = issues.join(" · ") || reason || "المعلومات في الإيصال غير مطابقة";
    }

    return { matched, detected_amount: detectedAmount, detected_phone: detectedPhone, reason };
  } catch (e) {
    console.error("verifyReceiptWithAI error", e);
    return { matched: false, detected_amount: null, detected_phone: null, reason: "تعذر التحقق تلقائيًا" };
  }
}

export const submitOrder = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((data: unknown) => SubmitInput.parse(data))
  .handler(async ({ data, context }) => {
    const product = await fetchProduct(data.slug);
    if (!product) throw new Error("المنتج غير موجود");

    const { supabase, userId } = context;

    // Parse data URL
    const match = data.imageBase64.match(/^data:(image\/[a-zA-Z+.-]+);base64,(.+)$/);
    if (!match) throw new Error("صورة غير صالحة");
    const mime = match[1];
    const b64 = match[2];
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const ext = mime.split("/")[1].split("+")[0];
    const safeSlug = String(product.slug).replace(/[^a-zA-Z0-9._-]/g, "-").replace(/-+/g, "-").slice(0, 40) || "receipt";
    const path = `${userId}/${Date.now()}-${safeSlug}.${ext}`;

    const { error: upErr } = await supabase.storage
      .from("receipts")
      .upload(path, bytes, { contentType: mime, upsert: false });
    if (upErr) {
      console.error(upErr);
      throw new Error("فشل رفع الصورة");
    }

    // AI verification (silent — user sees no "AI" wording in UI)
    const verify = await verifyReceiptWithAI(data.imageBase64, product.price, MERCHANT_PHONE);

    if (!verify.matched) {
      // Remove uploaded receipt and reject without creating an order
      await supabase.storage.from("receipts").remove([path]);
      return {
        id: null as string | null,
        status: "rejected" as const,
        matched: false,
        reason: verify.reason || "تحويل خاطئ — الرقم أو المبلغ غير مطابق",
      };
    }

    const { data: inserted, error: insErr } = await supabase
      .from("orders")
      .insert({
        user_id: userId,
        product_slug: product.slug,
        product_name: product.name,
        amount: product.price,
        currency: "EGP",
        status: "verified",
        receipt_url: path,
        ai_verified: true,
        ai_notes: verify.reason,
        detected_amount: verify.detected_amount,
        detected_phone: data.senderPhone ?? verify.detected_phone,
      })
      .select("id, status, ai_notes")
      .single();

    if (insErr) {
      console.error(insErr);
      throw new Error("فشل حفظ الطلب");
    }

    return {
      id: inserted.id as string | null,
      status: "verified" as const,
      matched: true,
      reason: "تم تأكيد الطلب بنجاح ✅",
    };
  });

export const listMyOrders = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { data, error } = await context.supabase
      .from("orders")
      .select("id, product_slug, product_name, amount, currency, status, ai_notes, created_at")
      .order("created_at", { ascending: false });
    if (error) throw error;
    return data ?? [];
  });

export const claimAdminIfNone = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    // Check if any admin already exists.
    const { data: existing, error: exErr } = await supabaseAdmin
      .from("user_roles")
      .select("user_id")
      .eq("role", "admin")
      .limit(1);
    if (exErr) throw exErr;
    if (existing && existing.length > 0) {
      const { data: mine } = await supabaseAdmin
        .from("user_roles")
        .select("user_id")
        .eq("user_id", context.userId)
        .eq("role", "admin")
        .maybeSingle();
      return { isAdmin: !!mine };
    }
    const { error: insErr } = await supabaseAdmin
      .from("user_roles")
      .insert({ user_id: context.userId, role: "admin" });
    if (insErr) throw insErr;
    return { isAdmin: true };
  });

export const listAllOrders = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { data: roleRow } = await context.supabase
      .from("user_roles")
      .select("user_id")
      .eq("user_id", context.userId)
      .eq("role", "admin")
      .maybeSingle();
    if (!roleRow) throw new Error("Forbidden");
    const { data, error } = await context.supabase
      .from("orders")
      .select("id, user_id, product_slug, product_name, amount, currency, status, ai_notes, detected_phone, receipt_url, created_at")
      .order("created_at", { ascending: false })
      .limit(200);
    if (error) throw error;
    return data ?? [];
  });

// ============ Password-gated admin panel ============
const ADMIN_PASSWORD = "592026";

function checkPw(pw: unknown) {
  if (typeof pw !== "string" || pw !== ADMIN_PASSWORD) {
    throw new Error("كلمة السر غلط");
  }
}

export const adminVerifyPassword = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => z.object({ password: z.string() }).parse(d))
  .handler(async ({ data }) => {
    checkPw(data.password);
    return { ok: true as const };
  });

export const adminListOrders = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => z.object({ password: z.string() }).parse(d))
  .handler(async ({ data }) => {
    checkPw(data.password);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { data: rows, error } = await supabaseAdmin
      .from("orders")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(500);
    if (error) throw error;
    return rows ?? [];
  });

export const adminCreateOrder = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) =>
    z.object({
      password: z.string(),
      product_slug: z.string().min(1),
      product_name: z.string().min(1),
      amount: z.number().nonnegative(),
      detected_phone: z.string().optional().nullable(),
      status: z.string().default("verified"),
      user_id: z.string().uuid().optional().nullable(),
    }).parse(d),
  )
  .handler(async ({ data }) => {
    checkPw(data.password);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    // fallback user_id: first user, else zero-uuid (user_id is NOT NULL)
    let uid = data.user_id ?? null;
    if (!uid) {
      const { data: list } = await supabaseAdmin.auth.admin.listUsers({ page: 1, perPage: 1 });
      uid = list?.users?.[0]?.id ?? "00000000-0000-0000-0000-000000000000";
    }
    const { data: row, error } = await supabaseAdmin
      .from("orders")
      .insert({
        user_id: uid,
        product_slug: data.product_slug,
        product_name: data.product_name,
        amount: data.amount,
        currency: "EGP",
        status: data.status,
        detected_phone: data.detected_phone ?? null,
        ai_verified: false,
      })
      .select("*")
      .single();
    if (error) throw error;
    return row;
  });

export const adminUpdateOrder = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) =>
    z.object({
      password: z.string(),
      id: z.string().uuid(),
      patch: z.object({
        product_name: z.string().optional(),
        amount: z.number().optional(),
        status: z.string().optional(),
        detected_phone: z.string().nullable().optional(),
        ai_notes: z.string().nullable().optional(),
      }),
    }).parse(d),
  )
  .handler(async ({ data }) => {
    checkPw(data.password);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { data: row, error } = await supabaseAdmin
      .from("orders")
      .update(data.patch)
      .eq("id", data.id)
      .select("*")
      .single();
    if (error) throw error;
    return row;
  });

export const adminDeleteOrder = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => z.object({ password: z.string(), id: z.string().uuid() }).parse(d))
  .handler(async ({ data }) => {
    checkPw(data.password);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { error } = await supabaseAdmin.from("orders").delete().eq("id", data.id);
    if (error) throw error;
    return { ok: true as const };
  });

export const adminListCustomers = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => z.object({ password: z.string() }).parse(d))
  .handler(async ({ data }) => {
    checkPw(data.password);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { data: list, error } = await supabaseAdmin.auth.admin.listUsers({ page: 1, perPage: 200 });
    if (error) throw error;
    // fetch order counts per user
    const { data: orders } = await supabaseAdmin.from("orders").select("user_id, amount, status");
    const stats = new Map<string, { count: number; total: number }>();
    (orders ?? []).forEach((o) => {
      const s = stats.get(o.user_id) ?? { count: 0, total: 0 };
      s.count += 1;
      if (o.status === "verified") s.total += Number(o.amount) || 0;
      stats.set(o.user_id, s);
    });
    const { data: profiles } = await supabaseAdmin.from("profiles").select("id, wallet_balance");
    const balances = new Map<string, number>();
    (profiles ?? []).forEach((p) => balances.set(p.id, Number(p.wallet_balance) || 0));
    return (list?.users ?? []).map((u) => ({
      id: u.id,
      email: u.email ?? null,
      phone: u.phone ?? null,
      created_at: u.created_at,
      last_sign_in_at: u.last_sign_in_at ?? null,
      orders_count: stats.get(u.id)?.count ?? 0,
      total_spent: stats.get(u.id)?.total ?? 0,
      wallet_balance: balances.get(u.id) ?? 0,
    }));
  });
