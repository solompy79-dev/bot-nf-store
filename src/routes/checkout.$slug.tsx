import { InstantDelivery, isAdobe, isChatGpt } from "@/components/InstantDelivery";
import { createFileRoute, Link, notFound, useNavigate } from "@tanstack/react-router";
import { ArrowRight, Copy, Upload, CheckCircle2, AlertTriangle, Loader2, MessageCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { getProduct } from "@/lib/products";
import { useProduct } from "@/lib/products-hooks";
import { supabase } from "@/lib/auth-client";
import { submitOrder } from "@/lib/orders.functions";
import { toast } from "sonner";

const PHONE = "01116945570";
const PHONE_INTL = "201116945570";

export const Route = createFileRoute("/checkout/$slug")({
  component: CheckoutPage,
  head: ({ params }) => {
    const p = getProduct(params.slug);
    const title = p ? `دفع ${p.name} — اشتراكي بلس` : "دفع الاشتراك";
    return {
      meta: [
        { title },
        { name: "description", content: "ادفع ثمن طلبك مباشرة بفودافون كاش وارفع الإيصال لتأكيد الطلب." },
        { property: "og:title", content: title },
        { property: "og:description", content: "دفع مباشر لطلبات اشتراكي بلس بفودافون كاش." },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary" },
      ],
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
      <div className="text-2xl font-black">حصل خطأ</div>
    </div>
  ),
});

function CheckoutPage() {
  const { slug } = Route.useParams();
  const navigate = useNavigate();
  const product = useProduct(slug) ?? getProduct(slug);
  if (!product) throw notFound();

  const [userId, setUserId] = useState<string | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [senderPhone, setSenderPhone] = useState("");
  const [result, setResult] = useState<{ status: string; reason: string; matched: boolean } | null>(null);
  const [success, setSuccess] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUserId(data.session?.user?.id ?? null);
      setCheckingAuth(false);
    });
  }, []);

  const onPick = (f: File | null) => {
    setFile(f);
    setResult(null);
    if (!f) return setPreview(null);
    const reader = new FileReader();
    reader.onload = () => setPreview(String(reader.result));
    reader.readAsDataURL(f);
  };

  const copyPhone = () => {
    navigator.clipboard.writeText(PHONE);
    toast.success("تم نسخ الرقم");
  };

  const submit = async () => {
    if (!preview) return toast.error("ارفع صورة الإيصال الأول");
    const senderDigits = senderPhone.replace(/\D/g, "");
    if (senderDigits.length < 10) return toast.error("اكتب رقم اللي حوّلت منه");
    setSubmitting(true);
    setResult(null);
    try {
      const res = await submitOrder({ data: { slug: product.slug, imageBase64: preview, senderPhone: senderDigits } });
      setResult({ status: res.status, reason: res.reason, matched: res.matched });
      if (res.matched) {
        toast.success("تم تأكيد الطلب!");
        setSuccess(true);
      } else {
        toast.error(res.reason);
      }
    } catch (e: any) {
      const msg = e?.message ?? "حصل خطأ";
      setResult({ status: "rejected", reason: msg, matched: false });
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen">
      <div className="max-w-2xl mx-auto px-5 pt-8 pb-32">
        {success ? (
          <SuccessView product={product} />
        ) : (
        <>
        <Link to="/s/$slug" params={{ slug: product.slug }}
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6">
          <ArrowRight className="size-4" />
          الرجوع
        </Link>

        {/* Product summary */}
        <div className="rounded-3xl glow-card p-5 flex items-center gap-4 mb-6">
          <div className="size-14 rounded-2xl grid place-items-center overflow-hidden shrink-0"
               style={{ background: product.color }}>
            {product.logoSlug ? (
              <img src={`https://cdn.simpleicons.org/${product.logoSlug}/white`}
                   alt={product.name} className="w-8 h-8 object-contain" />
            ) : (
              <span className="text-white text-xl font-black">{product.initials}</span>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-black truncate">{product.name}</div>
            <div className="text-xs text-muted-foreground">لمدة {product.duration}</div>
          </div>
          <div className="text-left">
            <div className="text-2xl font-black gradient-text leading-none">{product.price}</div>
            <div className="text-[11px] text-muted-foreground">ج.م</div>
          </div>
        </div>

        {!checkingAuth && !userId ? (
          <div className="rounded-3xl glow-card p-8 text-center">
            <div className="text-lg font-bold mb-2">سجّل دخول عشان تكمل الطلب</div>
            <p className="text-sm text-muted-foreground mb-5">لازم تكون مسجّل عشان نقدر نتابع طلبك ونأكده تلقائيًا.</p>
            <button
              onClick={() => navigate({ to: "/auth" })}
              className="rounded-full px-6 py-2.5 text-sm font-bold text-primary-foreground"
              style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}>
              تسجيل دخول
            </button>
          </div>
        ) : (
          <>
            {/* Payment instructions */}
            <div className="rounded-3xl glow-card p-6 mb-6">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-3">خطوات الدفع</div>
              <ol className="space-y-4 text-sm">
                <li className="flex gap-3">
                  <span className="size-6 rounded-full bg-primary/20 text-primary grid place-items-center text-xs font-black shrink-0">1</span>
                  <div className="flex-1">
                    حوّل <span className="font-black gradient-text">{product.price} ج.م</span> على فودافون كاش رقم:
                    <button onClick={copyPhone}
                            className="mt-2 w-full flex items-center justify-between gap-2 rounded-xl border border-border bg-card/50 hover:bg-card p-3 tabular-nums"
                            dir="ltr">
                      <span className="font-black text-lg">{PHONE}</span>
                      <Copy className="size-4 text-muted-foreground" />
                    </button>
                  </div>
                </li>
                <li className="flex gap-3">
                  <span className="size-6 rounded-full bg-primary/20 text-primary grid place-items-center text-xs font-black shrink-0">2</span>
                  <div>خد سكرين شوت من رسالة تأكيد التحويل (لازم يبان فيها الرقم والمبلغ بوضوح).</div>
                </li>
                <li className="flex gap-3">
                  <span className="size-6 rounded-full bg-primary/20 text-primary grid place-items-center text-xs font-black shrink-0">3</span>
                  <div>ارفع الصورة تحت وهيتأكد الطلب <span className="font-bold">تلقائي</span> خلال ثواني.</div>
                </li>
              </ol>
            </div>

            {/* Sender phone */}
            <div className="rounded-3xl glow-card p-6 mb-4">
              <label className="block text-xs text-muted-foreground uppercase tracking-wider mb-3">
                رقم اللي حوّلت منه
              </label>
              <div className="flex items-center gap-2 rounded-2xl border border-border bg-card/50 px-3 py-2.5 focus-within:border-primary/60 transition">
                <MessageCircle className="size-4 text-muted-foreground shrink-0" />
                <input
                  type="tel"
                  inputMode="tel"
                  dir="ltr"
                  placeholder="01xxxxxxxxx"
                  value={senderPhone}
                  onChange={(e) => setSenderPhone(e.target.value)}
                  className="flex-1 bg-transparent outline-none text-base tabular-nums placeholder:text-muted-foreground/60"
                />
              </div>
            </div>

            {/* Upload */}
            <div className="rounded-3xl glow-card p-6 mb-4">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-3">صورة الإيصال</div>

              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => onPick(e.target.files?.[0] ?? null)}
              />

              {preview ? (
                <div className="relative">
                  <img src={preview} alt="الإيصال" className="w-full rounded-2xl border border-border max-h-96 object-contain bg-black/40" />
                  <button
                    onClick={() => fileRef.current?.click()}
                    className="mt-3 w-full rounded-xl border border-border bg-card/50 hover:bg-card py-2.5 text-sm font-bold">
                    اختر صورة تانية
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => fileRef.current?.click()}
                  className="w-full rounded-2xl border-2 border-dashed border-border/70 hover:border-primary/50 bg-card/30 py-10 flex flex-col items-center gap-2 transition">
                  <Upload className="size-7 text-muted-foreground" />
                  <div className="font-bold">اضغط لرفع صورة الإيصال</div>
                  <div className="text-xs text-muted-foreground">PNG · JPG</div>
                </button>
              )}
            </div>

            {result && (
              <div className={`rounded-2xl p-4 mb-4 flex gap-3 ${result.matched ? "bg-green-500/10 border border-green-500/40" : "bg-yellow-500/10 border border-yellow-500/40"}`}>
                {result.matched ? (
                  <CheckCircle2 className="size-5 text-green-400 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="size-5 text-yellow-400 shrink-0 mt-0.5" />
                )}
                <div className="text-sm">
                  <div className="font-bold mb-1">
                    {result.matched ? "تم تأكيد الطلب تلقائيًا ✅" : "الطلب قيد المراجعة"}
                  </div>
                  <div className="text-muted-foreground">{result.reason}</div>
                  <Link to="/orders" className="inline-block mt-2 text-primary underline text-xs">
                    تابع في طلباتي
                  </Link>
                </div>
              </div>
            )}

            <button
              onClick={submit}
              disabled={!preview || submitting}
              className="w-full rounded-2xl py-4 font-black text-primary-foreground shadow-lg flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}>
              {submitting ? (
                <><Loader2 className="size-5 animate-spin" /> جاري التأكيد...</>
              ) : (
                <>تأكيد الطلب</>
              )}
            </button>

            <a href="https://wsend.co/201101560023"
               target="_blank" rel="noreferrer"
               className="mt-3 w-full rounded-2xl py-3 text-sm font-bold border border-border bg-card/50 hover:bg-card flex items-center justify-center gap-2">
              <MessageCircle className="size-4" />
              محتاج مساعدة؟ كلمنا على واتساب
            </a>
          </>
        )}
        </>
        )}
      </div>
    </div>
  );
}

function SuccessView({ product }: { product: { name: string; duration: string; slug?: string } }) {
  const instant = isChatGpt(product.slug, product.name) || isAdobe(product.slug, product.name);
  return (
    <div className="pt-6">
      <div className="rounded-3xl glow-card p-8 text-center relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none opacity-40"
             style={{ background: "radial-gradient(circle at 50% 0%, hsl(var(--primary) / 0.35), transparent 60%)" }} />
        <div className="relative">
          <div className="mx-auto mb-5 size-24 rounded-full grid place-items-center animate-pulse-glow"
               style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}>
            <CheckCircle2 className="size-14 text-white" strokeWidth={2.5} />
          </div>
          <h1 className="text-3xl font-black mb-2 gradient-text">تم تأكيد طلبك ✅</h1>
          {!instant && (
            <p className="text-muted-foreground mb-6">
              <span className="text-foreground font-bold">{product.name}</span> ({product.duration})
            </p>
          )}

          <div className="mb-6"><InstantDelivery slug={product.slug} name={product.name} /></div>




          <div className="flex flex-col sm:flex-row gap-2">
            <Link to="/orders"
                  className="flex-1 rounded-2xl py-3 font-bold text-primary-foreground"
                  style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}>
              متابعة طلباتي
            </Link>
            <Link to="/"
                  className="flex-1 rounded-2xl py-3 font-bold border border-border bg-card/50 hover:bg-card">
              الرجوع للرئيسية
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
