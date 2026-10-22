import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { supabase } from "@/lib/auth-client";
import { listCart, updateCartQty, removeFromCart, applyCoupon, submitCartOrder } from "@/lib/features.functions";
import { toast } from "sonner";
import { ArrowLeft, Minus, Plus, Trash2, Tag, ShoppingBag } from "lucide-react";

export const Route = createFileRoute("/cart")({
  component: CartPage,
  head: () => ({
    meta: [
      { title: "سلة المشتريات — اشتراكي بلس" },
      { name: "description", content: "راجع الاشتراكات في سلتك، طبّق كود الخصم وأكمل الدفع." },
      { property: "og:title", content: "سلة المشتريات — اشتراكي بلس" },
      { property: "og:description", content: "راجع الاشتراكات في سلتك وأكمل الدفع." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
      { name: "robots", content: "noindex" },
    ],
  }),
});

function CartPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setAuthed(!!data.user);
      if (!data.user) navigate({ to: "/auth" });
    });
  }, [navigate]);

  const listFn = useServerFn(listCart);
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["cart"],
    queryFn: () => listFn(),
    enabled: !!authed,
  });

  const qtyFn = useServerFn(updateCartQty);
  const rmFn = useServerFn(removeFromCart);
  const applyFn = useServerFn(applyCoupon);
  const submitFn = useServerFn(submitCartOrder);
  const qtyMut = useMutation({
    mutationFn: (v: { id: string; quantity: number }) => qtyFn({ data: v }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cart"] }),
  });
  const rmMut = useMutation({
    mutationFn: (id: string) => rmFn({ data: { id } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cart"] }),
  });

  const [couponCode, setCouponCode] = useState("");
  const [discount, setDiscount] = useState(0);
  const [appliedCode, setAppliedCode] = useState<string | null>(null);
  const [couponLoading, setCouponLoading] = useState(false);

  const subtotal = items.reduce((s, it) => s + (it.products ? Number(it.products.price) * it.quantity : 0), 0);
  const total = Math.max(0, subtotal - discount);

  const tryCoupon = async () => {
    if (!couponCode.trim()) return;
    setCouponLoading(true);
    try {
      const r = await applyFn({ data: { code: couponCode.trim(), subtotal } });
      if (r.ok) {
        setDiscount(r.discount);
        setAppliedCode(r.code);
        toast.success(`تم تطبيق الكوبون — وفّرت ${r.discount} ج.م`);
      } else {
        setDiscount(0);
        setAppliedCode(null);
        toast.error(r.reason);
      }
    } finally { setCouponLoading(false); }
  };

  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const checkout = async () => {
    if (items.length === 0) return;
    setCheckoutLoading(true);
    try {
      const r = await submitFn({ data: { couponCode: appliedCode } });
      if (r.ok) {
        toast.success("تم إنشاء الطلب — ادفع وارفع الإيصال");
        qc.invalidateQueries({ queryKey: ["cart"] });
        navigate({ to: "/orders" });
      } else {
        toast.error(r.reason);
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally { setCheckoutLoading(false); }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-background/70 border-b border-border">
        <div className="max-w-3xl mx-auto px-4 h-14 flex items-center gap-3">
          <Link to="/" aria-label="الرجوع للرئيسية" className="p-2 rounded-lg hover:bg-card"><ArrowLeft className="size-5" /></Link>
          <h1 className="text-lg font-black">سلة المشتريات</h1>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 pb-32">
        {isLoading ? (
          <div className="text-center text-muted-foreground py-20">جاري التحميل...</div>
        ) : items.length === 0 ? (
          <div className="text-center py-20">
            <ShoppingBag className="size-16 mx-auto text-muted-foreground/50 mb-4" />
            <div className="text-lg font-bold mb-2">السلة فارغة</div>
            <Link to="/" className="inline-block mt-4 px-6 py-2.5 rounded-xl font-black text-primary-foreground"
                  style={{ background: "var(--gradient-hero)" }}>تصفح الاشتراكات</Link>
          </div>
        ) : (
          <>
            <div className="space-y-3 mb-6">
              {items.map((it) => {
                const p = it.products;
                if (!p) return null;
                return (
                  <div key={it.id} className="glow-card rounded-2xl p-3 flex items-center gap-3">
                    <div className="size-14 rounded-xl grid place-items-center text-white font-black shrink-0"
                         style={{ background: p.color || "linear-gradient(135deg,#8b5cf6,#4c1d95)" }}>
                      {p.image_url ? <img src={p.image_url} alt={p.name} className="w-full h-full object-cover rounded-xl" /> :
                       p.logo_slug ? <img src={`https://cdn.simpleicons.org/${p.logo_slug}/white`} alt="" className="w-8 h-8" /> :
                       <span>{p.initials}</span>}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-bold text-sm truncate">{p.name}</div>
                      <div className="text-xs text-muted-foreground">/ {p.duration}</div>
                      <div className="text-sm font-black gradient-text mt-0.5">{Number(p.price) * it.quantity} ج.م</div>
                    </div>
                    <div className="flex items-center gap-1 border border-border rounded-lg">
                      <button onClick={() => it.quantity > 1 && qtyMut.mutate({ id: it.id, quantity: it.quantity - 1 })}
                              aria-label="تقليل الكمية"
                              className="p-1.5 hover:bg-card"><Minus className="size-3.5" /></button>
                      <span className="w-6 text-center text-sm font-bold">{it.quantity}</span>
                      <button onClick={() => qtyMut.mutate({ id: it.id, quantity: it.quantity + 1 })}
                              aria-label="زيادة الكمية"
                              className="p-1.5 hover:bg-card"><Plus className="size-3.5" /></button>
                    </div>
                    <button onClick={() => rmMut.mutate(it.id)} aria-label="حذف من السلة" className="p-2 text-destructive hover:bg-destructive/10 rounded-lg">
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                );
              })}
            </div>

            {/* Coupon */}
            <div className="glow-card rounded-2xl p-4 mb-4">
              <div className="flex items-center gap-2 text-sm font-bold mb-3"><Tag className="size-4" /> كود الخصم</div>
              <div className="flex gap-2">
                <input value={couponCode} onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                       placeholder="اكتب الكود" dir="ltr"
                       className="flex-1 px-3 py-2 rounded-xl bg-background border border-border text-right uppercase" />
                <button onClick={tryCoupon} disabled={couponLoading || !couponCode.trim()}
                        className="px-4 py-2 rounded-xl font-bold border border-border hover:bg-card disabled:opacity-50">
                  {couponLoading ? "..." : "تطبيق"}
                </button>
              </div>
              {appliedCode && <div className="text-xs text-primary mt-2">✓ الكوبون {appliedCode} مطبق</div>}
            </div>

            {/* Summary */}
            <div className="glow-card rounded-2xl p-4 space-y-2 mb-6">
              <div className="flex justify-between text-sm"><span className="text-muted-foreground">المجموع الفرعي</span><span className="font-bold">{subtotal} ج.م</span></div>
              {discount > 0 && <div className="flex justify-between text-sm text-primary"><span>الخصم</span><span className="font-bold">- {discount} ج.م</span></div>}
              <div className="flex justify-between text-lg pt-2 border-t border-border"><span className="font-bold">الإجمالي</span><span className="font-black gradient-text">{total} ج.م</span></div>
            </div>

            <button onClick={checkout} disabled={checkoutLoading}
                    className="w-full py-3.5 rounded-xl font-black text-primary-foreground text-lg disabled:opacity-50"
                    style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}>
              {checkoutLoading ? "جاري إنشاء الطلب..." : `متابعة الدفع — ${total} ج.م`}
            </button>

          </>
        )}
      </main>
    </div>
  );
}
