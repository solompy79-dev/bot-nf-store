import { InstantDelivery } from "@/components/InstantDelivery";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/auth-client";
import type { User } from "@supabase/supabase-js";
import { ShoppingBag, ArrowRight, CheckCircle2, Clock, XCircle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { listMyOrders } from "@/lib/orders.functions";

export const Route = createFileRoute("/orders")({
  component: OrdersPage,
  head: () => ({
    meta: [
      { title: "طلباتي — اشتراكي بلس" },
      { name: "description", content: "تابع كل طلبات الاشتراكات الخاصة بك" },
      { property: "og:title", content: "طلباتي — اشتراكي بلس" },
      { property: "og:description", content: "تابع حالة طلبات الاشتراكات الخاصة بك في اشتراكي بلس." },
      { name: "robots", content: "noindex" },
    ],
  }),
});

function OrdersPage() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setUser(s?.user ?? null));
    return () => sub.subscription.unsubscribe();
  }, []);

  const { data: orders, isLoading: ordersLoading } = useQuery({
    queryKey: ["my-orders", user?.id],
    queryFn: () => listMyOrders(),
    enabled: !!user,
  });

  return (
    <div className="min-h-screen">
      <div className="max-w-2xl mx-auto px-5 pt-8 pb-32">
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-8">
          <ArrowRight className="size-4" />
          الرجوع
        </Link>

        <div className="text-center mb-10">
          <div className="size-16 rounded-2xl grid place-items-center mx-auto mb-4 text-primary-foreground"
               style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}>
            <ShoppingBag className="size-7" />
          </div>
          <h1 className="text-3xl font-black mb-2">طلباتي</h1>
          <p className="text-sm text-muted-foreground">كل الاشتراكات اللي طلبتها في مكان واحد</p>
        </div>

        {loading ? (
          <div className="text-center text-muted-foreground py-20">جاري التحميل...</div>
        ) : !user ? (
          <div className="rounded-3xl glow-card p-8 text-center">
            <div className="text-lg font-bold mb-2">سجّل دخول عشان تشوف طلباتك</div>
            <p className="text-sm text-muted-foreground mb-5">هتلاقي هنا كل الاشتراكات اللي طلبتها وحالة كل طلب.</p>
            <Link to="/auth"
                  className="inline-block rounded-full px-6 py-2.5 text-sm font-bold text-primary-foreground"
                  style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}>
              تسجيل دخول
            </Link>
          </div>
        ) : (
          ordersLoading ? (
            <div className="text-center text-muted-foreground py-20">جاري تحميل طلباتك...</div>
          ) : !orders || orders.length === 0 ? (
            <div className="rounded-3xl glow-card p-8 text-center">
              <div className="text-5xl mb-3">📭</div>
              <div className="text-lg font-bold mb-2">لسه مفيش طلبات</div>
              <p className="text-sm text-muted-foreground mb-5">لما تطلب أول اشتراك هيظهرلك هنا.</p>
              <Link to="/" className="inline-block rounded-full px-6 py-2.5 text-sm font-bold text-primary-foreground"
                    style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}>
                تصفح الاشتراكات
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {orders.map((o) => (
                <div key={o.id} className="rounded-2xl glow-card p-4 flex items-start gap-3">
                  <StatusIcon status={o.status} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline justify-between gap-2">
                      <div className="font-black truncate">{o.product_name}</div>
                      <div className="font-black text-sm gradient-text tabular-nums shrink-0">{o.amount} ج.م</div>
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {new Date(o.created_at).toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" })}
                    </div>
                    <StatusBadge status={o.status} note={o.ai_notes} />
                    {o.status === "verified" && <InstantDelivery slug={o.product_slug} name={o.product_name} />}
                  </div>
                </div>
              ))}
            </div>
          )
        )}
      </div>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === "verified") return <CheckCircle2 className="size-5 text-green-400 shrink-0 mt-0.5" />;
  if (status === "rejected") return <XCircle className="size-5 text-red-400 shrink-0 mt-0.5" />;
  return <Clock className="size-5 text-yellow-400 shrink-0 mt-0.5" />;
}

function StatusBadge({ status, note }: { status: string; note: string | null }) {
  const map: Record<string, { label: string; cls: string }> = {
    verified: { label: "مؤكد ✓", cls: "bg-green-500/15 text-green-300 border-green-500/30" },
    pending_review: { label: "قيد المراجعة", cls: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30" },
    pending: { label: "قيد المراجعة", cls: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30" },
    rejected: { label: "مرفوض", cls: "bg-red-500/15 text-red-300 border-red-500/30" },
  };
  const s = map[status] ?? map.pending;
  return (
    <div className="mt-2">
      <span className={`inline-block text-[11px] font-bold px-2 py-0.5 rounded-full border ${s.cls}`}>{s.label}</span>
      {note && status !== "verified" && (
        <div className="text-[11px] text-muted-foreground mt-1.5">{note}</div>
      )}
    </div>
  );
}
