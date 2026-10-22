import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { ArrowRight, MessageCircle, User, Phone, Check, Shield, Zap, Clock, Heart, ShoppingCart } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { getProduct } from "@/lib/products";
import { useProduct } from "@/lib/products-hooks";
import { supabase } from "@/lib/auth-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { addToCart, listFavorites, toggleFavorite } from "@/lib/features.functions";
import { listProducts } from "@/lib/products.functions";

export const Route = createFileRoute("/s/$slug")({
  loader: async ({ context }) => {
    await context.queryClient.ensureQueryData({ queryKey: ["products", "public"], queryFn: () => listProducts() });
  },
  component: ProductPage,
  head: ({ params }) => {
    const p = getProduct(params.slug);
    const title = p ? `${p.name} — اشتراكي بلس` : "اشتراك — اشتراكي بلس";
    const desc = p ? `أسعار اشتراك ${p.name} بجميع المدد` : "أسعار الاشتراكات";
    const scripts = p ? [{
      type: "application/ld+json",
      children: JSON.stringify({
        "@context": "https://schema.org",
        "@type": "Product",
        name: p.name,
        description: p.description ?? p.tagline ?? desc,
        image: p.imageUrl ?? undefined,
        brand: { "@type": "Brand", name: "اشتراكي بلس" },
        offers: {
          "@type": "Offer",
          price: p.price,
          priceCurrency: "EGP",
          availability: "https://schema.org/InStock",
          url: `https://ishtraki.store/s/${p.slug}`,
        },
      }),
    }] : undefined;
    return {
      meta: [
        { title },
        { name: "description", content: desc },
        { property: "og:title", content: title },
        { property: "og:description", content: desc },
        { property: "og:type", content: "product" },
        { name: "twitter:card", content: "summary" },
      ],
      ...(scripts ? { scripts } : {}),
    };
  },
  notFoundComponent: () => (
    <div className="min-h-screen grid place-items-center p-8 text-center">
      <div>
        <div className="text-2xl font-black mb-2">الاشتراك مش موجود</div>
        <Link to="/" className="text-primary underline">ارجع للرئيسية</Link>
      </div>
    </div>
  ),
  errorComponent: () => (
    <div className="min-h-screen grid place-items-center p-8 text-center">
      <div>
        <div className="text-2xl font-black mb-2">حصل خطأ</div>
        <Link to="/" className="text-primary underline">ارجع للرئيسية</Link>
      </div>
    </div>
  ),
});

function ProductPage() {
  const { slug } = Route.useParams();
  const navigate = useNavigate();
  const product = useProduct(slug) ?? getProduct(slug);
  if (!product) throw notFound();

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [wa, setWa] = useState("");
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setUserId(data.session?.user?.id ?? null));
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setUserId(s?.user?.id ?? null));
    return () => sub.subscription.unsubscribe();
  }, []);

  const qc = useQueryClient();
  const productId = (product as unknown as { id?: string }).id;
  const favFn = useServerFn(listFavorites);
  const toggleFavFn = useServerFn(toggleFavorite);
  const addCartFn = useServerFn(addToCart);
  const { data: favs = [] } = useQuery({
    queryKey: ["favorites"], queryFn: () => favFn(), enabled: !!userId,
  });
  const isFav = !!productId && favs.some((f) => f.product_id === productId);
  const favMut = useMutation({
    mutationFn: () => toggleFavFn({ data: { productId: productId! } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorites"] }),
  });
  const cartMut = useMutation({
    mutationFn: () => addCartFn({ data: { productId: productId! } }),
    onSuccess: () => { toast.success("أُضيف إلى السلة"); qc.invalidateQueries({ queryKey: ["cart"] }); },
    onError: (e: Error) => toast.error(e.message),
  });

  const requireAuth = () => {
    if (!userId) { toast.error("سجّل دخول الأول"); navigate({ to: "/auth" }); return false; }
    if (!productId) { toast.error("جاري تحميل المنتج..."); return false; }
    return true;
  };

  const proceed = () => {
    if (!userId) {
      toast.error("لازم تسجّل دخول الأول");
      navigate({ to: "/auth" });
      return;
    }
    if (name.trim().length < 2) {
      toast.error("اكتب اسمك");
      return;
    }
    const phoneDigits = phone.replace(/\D/g, "");
    if (phoneDigits.length < 7) {
      toast.error("اكتب رقم تليفونك");
      return;
    }
    const digits = wa.replace(/\D/g, "");
    if (digits.length < 7) {
      toast.error("اكتب رقم واتساب صحيح");
      return;
    }
    try {
      localStorage.setItem("delivery_whatsapp", digits);
      localStorage.setItem("customer_name", name.trim());
      localStorage.setItem("customer_phone", phoneDigits);
    } catch {}
    navigate({ to: "/checkout/$slug", params: { slug: product.slug } });
  };

  return (
    <div className="min-h-screen">
      <div className="max-w-2xl mx-auto px-4 sm:px-5 pt-6 sm:pt-8 pb-32">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-8"
        >
          <ArrowRight className="size-4" />
          الرجوع
        </Link>

        <div className="flex flex-col items-center text-center mb-6 sm:mb-10">
          <div className="w-full flex justify-end gap-2 mb-2">
            <button onClick={() => requireAuth() && favMut.mutate()}
                    className={`size-10 rounded-full grid place-items-center border border-border ${isFav ? "bg-destructive/15 text-destructive" : "bg-card/60 hover:bg-card"}`}
                    aria-label="مفضلة">
              <Heart className={`size-5 ${isFav ? "fill-current" : ""}`} />
            </button>
            <button onClick={() => requireAuth() && cartMut.mutate()}
                    disabled={cartMut.isPending}
                    className="size-10 rounded-full grid place-items-center border border-border bg-card/60 hover:bg-card"
                    aria-label="أضف للسلة">
              <ShoppingCart className="size-5" />
            </button>
          </div>
          <div
            className={product.imageUrl ? "product-detail-art rounded-3xl overflow-hidden mb-4" : "size-16 sm:size-20 rounded-3xl grid place-items-center shadow-2xl overflow-hidden mb-3 sm:mb-4"}
            style={{ background: product.color }}
          >
            {product.imageUrl ? (
              <img src={product.imageUrl} alt={`اشتراك ${product.name} من اشتراكي بلس`} width={960} height={540} className="w-full h-full object-contain" />
            ) : product.logoSlug ? (
              <img
                src={`https://cdn.simpleicons.org/${product.logoSlug}/white`}
                alt={`شعار ${product.name}`}
                className="w-9 h-9 sm:w-11 sm:h-11 object-contain"
              />
            ) : (
              <span className="text-white text-2xl sm:text-3xl font-black">{product.initials}</span>
            )}
          </div>
          <h1 className="text-2xl sm:text-3xl font-black mb-1">{product.name}</h1>
          <p className="text-muted-foreground text-xs sm:text-sm">{product.tagline}</p>
        </div>

        {/* Price card */}
        <div className="text-xs text-muted-foreground uppercase tracking-wider text-center mb-4">
          سعر الاشتراك
        </div>
        <div className="rounded-3xl glow-card p-6 sm:p-8 flex flex-col items-center text-center">
          {product.badge && (
            <div className="text-[11px] font-black text-primary-foreground px-3 py-1 rounded-full mb-4"
                 style={{ background: "var(--gradient-hero)" }}>
              {product.badge}
            </div>
          )}
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-5xl sm:text-6xl font-black gradient-text leading-none">{product.price}</span>
            <span className="text-sm sm:text-base text-muted-foreground font-bold">ج.م</span>
          </div>
          <div className="text-xs sm:text-sm text-muted-foreground">لمدة {product.duration}</div>
        </div>

        {/* Description */}
        {product.description && (
          <div className="mt-6 sm:mt-8 rounded-3xl glow-card p-5 sm:p-6">
            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-3">تفاصيل الاشتراك</div>
            <p className="text-sm leading-relaxed text-foreground/90">{product.description}</p>
          </div>
        )}

        {/* Features */}
        {product.features && product.features.length > 0 && (
          <div className="mt-4 rounded-3xl glow-card p-5 sm:p-6">
            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-4">اللي هتاخده</div>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {product.features.map((f) => (
                <li key={f} className="flex items-center gap-2 text-sm">
                  <span className="size-6 rounded-full bg-primary/15 text-primary grid place-items-center shrink-0">
                    <Check className="size-3.5" />
                  </span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Trust badges */}
        <div className="mt-4 grid grid-cols-3 gap-3">
          <div className="rounded-2xl glow-card p-4 text-center">
            <Zap className="size-5 text-primary mx-auto mb-1.5" />
            <div className="text-[11px] font-bold">تسليم فوري</div>
          </div>
          <div className="rounded-2xl glow-card p-4 text-center">
            <Shield className="size-5 text-primary mx-auto mb-1.5" />
            <div className="text-[11px] font-bold">ضمان الاشتراك</div>
          </div>
          <div className="rounded-2xl glow-card p-4 text-center">
            <Clock className="size-5 text-primary mx-auto mb-1.5" />
            <div className="text-[11px] font-bold">دعم 24/7</div>
          </div>
        </div>

        {/* Customer info form */}
        <div className="mt-6 sm:mt-8 rounded-3xl glow-card p-5 sm:p-6">
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-4">بياناتك</div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-bold mb-2">الاسم</label>
              <div className="flex items-center gap-2 rounded-2xl border border-border bg-card/50 px-3 py-2.5 focus-within:border-primary/60 transition">
                <User className="size-4 text-muted-foreground shrink-0" />
                <input
                  type="text"
                  placeholder="اكتب اسمك"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="flex-1 bg-transparent outline-none text-base placeholder:text-muted-foreground/60"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold mb-2">رقم التليفون</label>
              <div className="flex items-center gap-2 rounded-2xl border border-border bg-card/50 px-3 py-2.5 focus-within:border-primary/60 transition">
                <Phone className="size-4 text-muted-foreground shrink-0" />
                <input
                  type="tel"
                  inputMode="tel"
                  dir="ltr"
                  placeholder="+20 1xxxxxxxxx"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="flex-1 bg-transparent outline-none text-base tabular-nums placeholder:text-muted-foreground/60"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold mb-2">رقم واتساب الاستلام</label>
              <div className="flex items-center gap-2 rounded-2xl border border-border bg-card/50 px-3 py-2.5 focus-within:border-primary/60 transition">
                <MessageCircle className="size-4 text-muted-foreground shrink-0" />
                <input
                  type="tel"
                  inputMode="tel"
                  dir="ltr"
                  placeholder="+20 1xxxxxxxxx"
                  value={wa}
                  onChange={(e) => setWa(e.target.value)}
                  className="flex-1 bg-transparent outline-none text-base tabular-nums placeholder:text-muted-foreground/60"
                />
              </div>
              <p className="text-[11px] text-muted-foreground mt-2">
                هنبعتلك بيانات الاشتراك على الرقم ده بعد تأكيد الدفع.
              </p>
            </div>
          </div>

          <button
            onClick={proceed}
            className="mt-6 w-full rounded-2xl py-4 font-black text-primary-foreground shadow-lg flex items-center justify-center gap-2"
            style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}
          >
            {userId ? "ادفع واستلم فورًا" : "سجّل دخول للشراء"}
          </button>
          {!userId && (
            <p className="text-[11px] text-muted-foreground text-center mt-3">
              محتاج تسجّل دخول عشان تقدر تكمل الطلب
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
