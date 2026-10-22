import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";
import { assertWalletActionAllowed } from "@/lib/payment-policy";

// Retain retired endpoints as explicit rejections for older browser tabs.
export const submitTopup = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(() => assertWalletActionAllowed());

export const payProductWithWallet = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(() => assertWalletActionAllowed());

export const payCartWithWallet = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(() => assertWalletActionAllowed());

export const listMyTopups = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { data, error } = await context.supabase
      .from("wallet_topups")
      .select("id, amount, status, created_at, notes")
      .order("created_at", { ascending: false })
      .limit(30);
    if (error) throw error;
    return data ?? [];
  });
