import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ShieldCheck, ArrowRight, Phone, RefreshCw, Bell, BellOff,
  Pencil, Trash2, Plus, Users, ShoppingBag, Search, X, Save, LogOut, Loader2, Package, Send, MessageCircle, Pin, PinOff,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { isProductPinned, nextProductOrder } from "@/lib/product-order";
import {
  adminVerifyPassword, adminListOrders, adminCreateOrder,
  adminUpdateOrder, adminDeleteOrder, adminListCustomers,
} from "@/lib/orders.functions";
import { products as staticProducts } from "@/lib/products";
import {
  adminListProducts, adminUpsertProduct, adminDeleteProduct,
} from "@/lib/products.functions";

export const Route = createFileRoute("/admin")({
  component: AdminPage,
  head: () => ({
    meta: [
      { title: "لوحة الإدارة — اشتراكي بلس" },
      { name: "description", content: "إدارة منتجات وطلبات وعملاء اشتراكي بلس وترتيب الاشتراكات في المتجر." },
      { property: "og:title", content: "لوحة الإدارة — اشتراكي بلس" },
      { property: "og:description", content: "لوحة إدارة منتجات وطلبات اشتراكي بلس." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
});

const PW_KEY = "admin_pw";

function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
      <div className="relative">
        <div className="size-12 rounded-full border-2 border-primary/20" />
        <Loader2 className="size-12 absolute inset-0 animate-spin text-primary" />
      </div>
      {label && <div className="text-sm font-bold">{label}</div>}
    </div>
  );
}

type Order = {
  id: string;
  user_id: string;
  product_slug: string;
  product_name: string;
  amount: number;
  currency: string;
  status: string;
  detected_phone: string | null;
  ai_notes: string | null;
  created_at: string;
};

function AdminPage() {
  const [pw, setPw] = useState<string | null>(() =>
    typeof window !== "undefined" ? sessionStorage.getItem(PW_KEY) : null,
  );
  const [tab, setTab] = useState<"orders" | "customers" | "products" | "broadcast">("orders");

  if (!pw) return <PasswordGate onUnlock={(p) => { sessionStorage.setItem(PW_KEY, p); setPw(p); }} />;

  return (
    <div className="min-h-screen">
      <div className="max-w-5xl mx-auto px-5 pt-8 pb-32">
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6">
          <ArrowRight className="size-4" /> الرجوع
        </Link>

        <div className="flex items-center gap-3 mb-6">
          <div className="size-12 rounded-2xl grid place-items-center text-primary-foreground"
               style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}>
            <ShieldCheck className="size-6" />
          </div>
          <div className="flex-1">
            <h1 className="text-2xl font-black">لوحة الإدارة</h1>
            <p className="text-xs text-muted-foreground">الطلبات والعملاء في مكان واحد</p>
          </div>
          <button
            onClick={() => { sessionStorage.removeItem(PW_KEY); setPw(null); }}
            className="rounded-full p-2 border border-border bg-card/50 hover:bg-card"
            title="خروج"
          >
            <LogOut className="size-4" />
          </button>
        </div>

        <div className="flex gap-2 mb-6 rounded-2xl p-1 border border-border bg-card/40 overflow-x-auto">
          <TabBtn active={tab === "orders"} onClick={() => setTab("orders")} icon={<ShoppingBag className="size-4" />}>الطلبات</TabBtn>
          <TabBtn active={tab === "products"} onClick={() => setTab("products")} icon={<Package className="size-4" />}>المنتجات</TabBtn>
          <TabBtn active={tab === "customers"} onClick={() => setTab("customers")} icon={<Users className="size-4" />}>العملاء</TabBtn>
          <TabBtn active={tab === "broadcast"} onClick={() => setTab("broadcast")} icon={<MessageCircle className="size-4" />}>بث واتساب</TabBtn>
        </div>

        {tab === "orders" ? <OrdersTab pw={pw} /> :
         tab === "products" ? <ProductsTab pw={pw} /> :
         tab === "broadcast" ? <BroadcastTab /> :
         <CustomersTab pw={pw} />}
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-bold transition ${
        active ? "text-primary-foreground shadow-md" : "text-muted-foreground hover:text-foreground"
      }`}
      style={active ? { background: "var(--gradient-hero)" } : undefined}
    >
      {icon}
      {children}
    </button>
  );
}

function PasswordGate({ onUnlock }: { onUnlock: (p: string) => void }) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await adminVerifyPassword({ data: { password: value } });
      onUnlock(value);
    } catch {
      toast.error("كلمة السر غلط");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center px-5">
      <form onSubmit={submit} className="w-full max-w-sm rounded-3xl glow-card p-8">
        <div className="size-14 rounded-2xl grid place-items-center mx-auto mb-4 text-primary-foreground"
             style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}>
          <ShieldCheck className="size-7" />
        </div>
        <h2 className="text-xl font-black text-center mb-1">لوحة الإدارة</h2>
        <p className="text-xs text-muted-foreground text-center mb-6">ادخل كلمة السر للدخول</p>
        <input
          type="password"
          inputMode="numeric"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="••••••"
          className="w-full rounded-2xl border border-border bg-background/50 px-4 py-3 text-center tabular-nums tracking-widest text-lg"
          dir="ltr"
        />
        <button
          type="submit"
          disabled={loading || !value}
          className="w-full mt-4 rounded-2xl py-3 text-sm font-black text-primary-foreground disabled:opacity-60"
          style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}
        >
          {loading ? "..." : "دخول"}
        </button>
      </form>
    </div>
  );
}

// =========================== ORDERS ===========================
function OrdersTab({ pw }: { pw: string }) {
  const qc = useQueryClient();
  const [notifyOn, setNotifyOn] = useState(false);
  const [editing, setEditing] = useState<Order | null>(null);
  const [creating, setCreating] = useState(false);
  const knownIds = useRef<Set<string>>(new Set());
  const firstLoad = useRef(true);

  const { data: orders, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin", "orders"],
    queryFn: () => adminListOrders({ data: { password: pw } }) as Promise<Order[]>,
    refetchInterval: 15000,
  });

  useEffect(() => {
    if (!orders) return;
    if (firstLoad.current) {
      orders.forEach((o) => knownIds.current.add(o.id));
      firstLoad.current = false;
      return;
    }
    const fresh = orders.filter((o) => !knownIds.current.has(o.id));
    if (fresh.length > 0) {
      fresh.forEach((o) => knownIds.current.add(o.id));
      playBeep();
      const latest = fresh[0];
      toast.success(`طلب جديد: ${latest.product_name}`, {
        description: `${latest.amount} ج.م · ${latest.detected_phone ?? ""}`,
      });
      if (notifyOn && "Notification" in window && Notification.permission === "granted") {
        new Notification("طلب جديد 🛒", {
          body: `${latest.product_name} — ${latest.amount} ج.م${latest.detected_phone ? " · " + latest.detected_phone : ""}`,
        });
      }
    }
  }, [orders, notifyOn]);

  const del = useMutation({
    mutationFn: (id: string) => adminDeleteOrder({ data: { password: pw, id } }),
    onSuccess: () => { toast.success("اتحذف"); qc.invalidateQueries({ queryKey: ["admin", "orders"] }); },
    onError: (e: Error) => toast.error(e.message),
  });

  const enableNotifications = async () => {
    if (!("Notification" in window)) return toast.error("متصفحك لا يدعم الإشعارات");
    const perm = await Notification.requestPermission();
    if (perm === "granted") { setNotifyOn(true); toast.success("تم تفعيل الإشعارات"); }
    else toast.error("مسموحش الإشعارات");
  };

  return (
    <>
      <div className="flex gap-2 mb-4">
        <button
          onClick={notifyOn ? undefined : enableNotifications}
          disabled={notifyOn}
          className="flex-1 rounded-2xl border border-border bg-card/50 p-3 flex items-center gap-2 text-right hover:bg-card disabled:opacity-70 text-xs"
        >
          {notifyOn ? <Bell className="size-4 text-green-400" /> : <BellOff className="size-4 text-muted-foreground" />}
          <span className="font-bold">{notifyOn ? "الإشعارات مفعّلة" : "فعّل الإشعارات"}</span>
        </button>
        <button
          onClick={() => refetch()}
          className="rounded-2xl p-3 border border-border bg-card/50 hover:bg-card"
          title="تحديث"
        >
          <RefreshCw className={`size-4 ${isFetching ? "animate-spin" : ""}`} />
        </button>
        <button
          onClick={() => setCreating(true)}
          className="rounded-2xl px-4 py-3 text-sm font-black text-primary-foreground flex items-center gap-2"
          style={{ background: "var(--gradient-hero)" }}
        >
          <Plus className="size-4" /> إضافة
        </button>
      </div>

      {isLoading ? (
        <Spinner label="جاري تحميل الطلبات..." />
      ) : !orders?.length ? (
        <div className="rounded-3xl glow-card p-8 text-center">
          <div className="text-5xl mb-3">📭</div>
          <div className="text-lg font-bold">لسه مفيش طلبات</div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="text-xs text-muted-foreground">إجمالي: {orders.length}</div>
          {orders.map((o) => (
            <div key={o.id} className="rounded-2xl glow-card p-4">
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="font-black break-words leading-tight" dir="auto">{o.product_name}</div>
                    <div className="font-black text-sm gradient-text tabular-nums shrink-0" dir="ltr">{o.amount} ج.م</div>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {new Date(o.created_at).toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" })}
                  </div>
                  {o.detected_phone && (
                    <div className="mt-2 flex items-center gap-2 text-sm flex-wrap">
                      <Phone className="size-3.5 text-primary" />
                      <a href={`tel:${o.detected_phone}`} className="tabular-nums font-bold" dir="ltr">{o.detected_phone}</a>
                      <a href={`https://wa.me/2${o.detected_phone.replace(/^0/, "")}`} target="_blank" rel="noreferrer"
                         className="text-[11px] px-2 py-0.5 rounded-full bg-green-500/15 text-green-300 border border-green-500/30">واتساب</a>
                    </div>
                  )}
                  <StatusBadge status={o.status} note={o.ai_notes} />
                </div>
                <div className="flex flex-col gap-1.5 shrink-0">
                  <button onClick={() => setEditing(o)} className="rounded-lg p-2 border border-border bg-card/50 hover:bg-card" title="تعديل">
                    <Pencil className="size-3.5" />
                  </button>
                  <button onClick={() => { if (confirm("تحذف الطلب دا؟")) del.mutate(o.id); }}
                          className="rounded-lg p-2 border border-red-500/30 bg-red-500/10 hover:bg-red-500/20 text-red-300" title="حذف">
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && <OrderEditor pw={pw} order={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); qc.invalidateQueries({ queryKey: ["admin", "orders"] }); }} />}
      {creating && <OrderCreator pw={pw} onClose={() => setCreating(false)} onSaved={() => { setCreating(false); qc.invalidateQueries({ queryKey: ["admin", "orders"] }); }} />}
    </>
  );
}

function OrderEditor({ pw, order, onClose, onSaved }: { pw: string; order: Order; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(order.product_name);
  const [amount, setAmount] = useState(String(order.amount));
  const [status, setStatus] = useState(order.status);
  const [phone, setPhone] = useState(order.detected_phone ?? "");
  const [notes, setNotes] = useState(order.ai_notes ?? "");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await adminUpdateOrder({
        data: {
          password: pw, id: order.id,
          patch: {
            product_name: name,
            amount: Number(amount),
            status,
            detected_phone: phone || null,
            ai_notes: notes || null,
          },
        },
      });
      toast.success("تم الحفظ");
      onSaved();
    } catch (e) {
      toast.error((e as Error).message);
    } finally { setSaving(false); }
  };

  return (
    <Modal onClose={onClose} title="تعديل الطلب">
      <Field label="اسم المنتج"><input value={name} onChange={(e) => setName(e.target.value)} className={inp} /></Field>
      <Field label="السعر"><input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} className={inp} dir="ltr" /></Field>
      <Field label="الحالة">
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={inp}>
          <option value="pending">قيد المراجعة</option>
          <option value="pending_review">قيد المراجعة يدويًا</option>
          <option value="verified">مؤكد</option>
          <option value="rejected">مرفوض</option>
          <option value="delivered">تم التسليم</option>
        </select>
      </Field>
      <Field label="رقم العميل"><input value={phone} onChange={(e) => setPhone(e.target.value)} className={inp} dir="ltr" /></Field>
      <Field label="ملاحظات"><textarea value={notes} onChange={(e) => setNotes(e.target.value)} className={`${inp} min-h-20`} /></Field>
      <button onClick={save} disabled={saving}
              className="w-full mt-2 rounded-2xl py-3 text-sm font-black text-primary-foreground flex items-center justify-center gap-2 disabled:opacity-60"
              style={{ background: "var(--gradient-hero)" }}>
        <Save className="size-4" /> {saving ? "..." : "حفظ"}
      </button>
    </Modal>
  );
}

function OrderCreator({ pw, onClose, onSaved }: { pw: string; onClose: () => void; onSaved: () => void }) {
  const { data: prodList } = useQuery({
    queryKey: ["admin", "products", "picker"],
    queryFn: () => adminListProducts({ data: { password: pw } }),
  });
  const products = prodList && prodList.length ? prodList : staticProducts;
  const [slug, setSlug] = useState(products[0]?.slug ?? "");
  const [name, setName] = useState(products[0]?.name ?? "");
  const [amount, setAmount] = useState(String(products[0]?.price ?? 0));
  const [phone, setPhone] = useState("");
  const [status, setStatus] = useState("verified");
  const [saving, setSaving] = useState(false);

  const pickProduct = (s: string) => {
    setSlug(s);
    const p = products.find((x) => x.slug === s);
    if (p) { setName(p.name); setAmount(String(p.price)); }
  };

  const save = async () => {
    setSaving(true);
    try {
      await adminCreateOrder({
        data: {
          password: pw,
          product_slug: slug,
          product_name: name,
          amount: Number(amount),
          detected_phone: phone || null,
          status,
        },
      });
      toast.success("تم الإضافة");
      onSaved();
    } catch (e) {
      toast.error((e as Error).message);
    } finally { setSaving(false); }
  };

  return (
    <Modal onClose={onClose} title="إضافة طلب">
      <Field label="المنتج">
        <select value={slug} onChange={(e) => pickProduct(e.target.value)} className={inp}>
          {products.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
        </select>
      </Field>
      <Field label="اسم المنتج"><input value={name} onChange={(e) => setName(e.target.value)} className={inp} /></Field>
      <Field label="السعر"><input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} className={inp} dir="ltr" /></Field>
      <Field label="رقم العميل"><input value={phone} onChange={(e) => setPhone(e.target.value)} className={inp} dir="ltr" placeholder="01xxxxxxxxx" /></Field>
      <Field label="الحالة">
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={inp}>
          <option value="pending">قيد المراجعة</option>
          <option value="verified">مؤكد</option>
          <option value="delivered">تم التسليم</option>
          <option value="rejected">مرفوض</option>
        </select>
      </Field>
      <button onClick={save} disabled={saving}
              className="w-full mt-2 rounded-2xl py-3 text-sm font-black text-primary-foreground flex items-center justify-center gap-2 disabled:opacity-60"
              style={{ background: "var(--gradient-hero)" }}>
        {saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
        {saving ? "جاري الإضافة..." : "إضافة"}
      </button>
    </Modal>
  );
}

// =========================== CUSTOMERS ===========================
type Customer = {
  id: string; email: string | null; phone: string | null;
  created_at: string; last_sign_in_at: string | null;
  orders_count: number; total_spent: number; wallet_balance: number;
};

function CustomersTab({ pw }: { pw: string }) {
  const [q, setQ] = useState("");
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin", "customers"],
    queryFn: () => adminListCustomers({ data: { password: pw } }) as Promise<Customer[]>,
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    const s = q.trim().toLowerCase();
    if (!s) return data;
    return data.filter((c) => (c.email ?? "").toLowerCase().includes(s) || (c.phone ?? "").includes(s));
  }, [data, q]);

  return (
    <>
      <div className="flex gap-2 mb-4">
        <div className="flex-1 relative">
          <Search className="size-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ابحث بالإيميل أو الرقم"
                 className="w-full rounded-2xl border border-border bg-card/50 px-4 py-3 pr-10 text-sm" />
        </div>
        <button onClick={() => refetch()} className="rounded-2xl p-3 border border-border bg-card/50 hover:bg-card">
          <RefreshCw className={`size-4 ${isFetching ? "animate-spin" : ""}`} />
        </button>
      </div>

      {isLoading ? (
        <Spinner label="جاري تحميل العملاء..." />
      ) : !filtered.length ? (
        <div className="rounded-3xl glow-card p-8 text-center">
          <div className="text-5xl mb-3">👥</div>
          <div className="text-lg font-bold">مفيش عملاء</div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="text-xs text-muted-foreground">إجمالي: {filtered.length}</div>
          {filtered.map((c) => (
            <div key={c.id} className="rounded-2xl glow-card p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="font-black truncate">{c.email ?? c.phone ?? "بدون بيانات"}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    اشترك {new Date(c.created_at).toLocaleDateString("ar-EG")}
                    {c.last_sign_in_at && <> · آخر دخول {new Date(c.last_sign_in_at).toLocaleDateString("ar-EG")}</>}
                  </div>
                  <div className="mt-2 flex items-center gap-2 flex-wrap text-xs">
                    <span className="rounded-full px-2 py-0.5 bg-primary/15 text-primary border border-primary/30 font-bold">
                      {c.orders_count} طلب
                    </span>
                    <span className="rounded-full px-2 py-0.5 bg-green-500/15 text-green-300 border border-green-500/30 font-bold tabular-nums">
                      {c.total_spent} ج.م
                    </span>
                    <span className="rounded-full px-2 py-0.5 bg-purple-500/15 text-purple-300 border border-purple-500/30 font-bold tabular-nums">
                      رصيد: {c.wallet_balance} ج.م
                    </span>
                    {c.phone && (
                      <a href={`https://wa.me/2${c.phone.replace(/^0/, "").replace(/^\+?20/, "")}`}
                         target="_blank" rel="noreferrer"
                         className="tabular-nums font-bold text-green-300" dir="ltr">
                        {c.phone}
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

// =========================== SHARED ===========================
const inp = "w-full rounded-xl border border-border bg-background/50 px-3 py-2.5 text-sm";

// =========================== PRODUCTS ===========================
type AdminProduct = {
  id: string;
  slug: string;
  name: string;
  tagline: string;
  initials: string;
  color: string;
  logoSlug?: string;
  imageUrl?: string;
  duration: string;
  price: number;
  badge?: string;
  description?: string;
  features: string[];
  sort_order: number;
  active: boolean;
};

function ProductsTab({ pw }: { pw: string }) {
  const qc = useQueryClient();
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin", "products"],
    queryFn: () => adminListProducts({ data: { password: pw } }) as Promise<AdminProduct[]>,
  });
  const [editing, setEditing] = useState<AdminProduct | null>(null);
  const [creating, setCreating] = useState(false);

  const pin = useMutation({
    mutationFn: (product: AdminProduct) => adminUpsertProduct({
      data: {
        password: pw,
        id: product.id,
        product: {
          ...product,
          sort_order: nextProductOrder((data ?? []).map((item) => item.sort_order), !isProductPinned(product.sort_order)),
        },
      },
    }),
    onSuccess: (_, product) => {
      toast.success(isProductPinned(product.sort_order) ? "تم إلغاء تثبيت المنتج" : "تم تثبيت المنتج في أول المتجر");
      qc.invalidateQueries({ queryKey: ["admin", "products"] });
      qc.invalidateQueries({ queryKey: ["products", "public"] });
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const del = useMutation({
    mutationFn: (id: string) => adminDeleteProduct({ data: { password: pw, id } }),
    onSuccess: () => {
      toast.success("تم الحذف");
      qc.invalidateQueries({ queryKey: ["admin", "products"] });
      qc.invalidateQueries({ queryKey: ["products", "public"] });
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const onSaved = () => {
    setEditing(null); setCreating(false);
    qc.invalidateQueries({ queryKey: ["admin", "products"] });
    qc.invalidateQueries({ queryKey: ["products", "public"] });
  };

  return (
    <>
      <div className="flex gap-2 mb-4">
        <button onClick={() => refetch()} className="rounded-2xl p-3 border border-border bg-card/50 hover:bg-card">
          <RefreshCw className={`size-4 ${isFetching ? "animate-spin" : ""}`} />
        </button>
        <button onClick={() => setCreating(true)}
                className="flex-1 rounded-2xl px-4 py-3 text-sm font-black text-primary-foreground flex items-center justify-center gap-2"
                style={{ background: "var(--gradient-hero)" }}>
          <Plus className="size-4" /> إضافة منتج
        </button>
      </div>

      {isLoading ? (
        <Spinner label="جاري تحميل المنتجات..." />
      ) : !data?.length ? (
        <div className="rounded-3xl glow-card p-8 text-center">
          <div className="text-5xl mb-3">📦</div>
          <div className="text-lg font-bold">مفيش منتجات</div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="text-xs text-muted-foreground">إجمالي: {data.length}</div>
          {data.map((p) => (
            <div key={p.id} className="rounded-2xl glow-card p-4">
              <div className="flex items-start gap-3">
                <div className="size-12 rounded-2xl grid place-items-center text-white font-black shrink-0 overflow-hidden"
                     style={{ background: p.color }}>
                  {p.logoSlug
                    ? <img src={`https://cdn.simpleicons.org/${p.logoSlug}/white`} alt="" className="w-6 h-6 object-contain" />
                    : <span className="text-sm">{p.initials}</span>}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="font-black break-words leading-tight" dir="auto">{p.name}</div>
                    <div className="font-black text-sm gradient-text tabular-nums shrink-0" dir="ltr">{p.price} ج.م</div>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1 flex items-center gap-2 flex-wrap">
                    <span dir="ltr" className="tabular-nums">/{p.slug}</span>
                    <span>·</span>
                    <span>لمدة {p.duration}</span>
                    {isProductPinned(p.sort_order) && (
                      <span className="inline-flex items-center gap-1 text-primary font-bold">
                        <Pin className="size-3" /> مثبت
                      </span>
                    )}
                    {!p.active && (
                      <span className="rounded-full px-2 py-0.5 bg-red-500/15 text-red-300 border border-red-500/30 font-bold text-[10px]">
                        متوقف
                      </span>
                    )}
                    {p.badge && (
                      <span className="rounded-full px-2 py-0.5 bg-primary/15 text-primary border border-primary/30 font-bold text-[10px]">
                        {p.badge}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex flex-col gap-1.5 shrink-0">
                  <Button
                    variant={isProductPinned(p.sort_order) ? "secondary" : "outline"}
                    size="icon"
                    className="size-8"
                    disabled={pin.isPending}
                    onClick={() => pin.mutate(p)}
                    title={isProductPinned(p.sort_order) ? "إلغاء تثبيت المنتج" : "تثبيت في أول المتجر"}
                    aria-label={isProductPinned(p.sort_order) ? `إلغاء تثبيت ${p.name}` : `تثبيت ${p.name} في أول المتجر`}
                    aria-pressed={isProductPinned(p.sort_order)}
                  >
                    {pin.isPending && pin.variables?.id === p.id ? <Loader2 className="animate-spin" /> :
                      isProductPinned(p.sort_order) ? <PinOff /> : <Pin />}
                  </Button>
                  <button onClick={() => setEditing(p)} className="rounded-lg p-2 border border-border bg-card/50 hover:bg-card" title="تعديل">
                    <Pencil className="size-3.5" />
                  </button>
                  <button onClick={() => { if (confirm(`تحذف "${p.name}"؟`)) del.mutate(p.id); }}
                          className="rounded-lg p-2 border border-red-500/30 bg-red-500/10 hover:bg-red-500/20 text-red-300" title="حذف">
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && <ProductEditor pw={pw} product={editing} onClose={() => setEditing(null)} onSaved={onSaved} />}
      {creating && <ProductEditor pw={pw} product={null} onClose={() => setCreating(false)} onSaved={onSaved} />}
    </>
  );
}

function ProductEditor({ pw, product, onClose, onSaved }: {
  pw: string; product: AdminProduct | null; onClose: () => void; onSaved: () => void;
}) {
  const isNew = !product;
  const [slug, setSlug] = useState(product?.slug ?? "");
  const [name, setName] = useState(product?.name ?? "");
  const [tagline, setTagline] = useState(product?.tagline ?? "");
  const [initials, setInitials] = useState(product?.initials ?? "");
  const [color, setColor] = useState(product?.color ?? "linear-gradient(135deg,#8b5cf6,#4c1d95)");
  const [logoSlug, setLogoSlug] = useState(product?.logoSlug ?? "");
  const [imageUrl, setImageUrl] = useState(product?.imageUrl ?? "");
  const [duration, setDuration] = useState(product?.duration ?? "شهر");
  const [price, setPrice] = useState(String(product?.price ?? 0));
  const [badge, setBadge] = useState(product?.badge ?? "");
  const [description, setDescription] = useState(product?.description ?? "");
  const [features, setFeatures] = useState((product?.features ?? []).join("\n"));
  const [sortOrder, setSortOrder] = useState(String(product?.sort_order ?? 100));
  const [active, setActive] = useState(product?.active ?? true);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await adminUpsertProduct({
        data: {
          password: pw,
          id: product?.id,
          product: {
            slug: slug.trim(),
            name: name.trim(),
            tagline: tagline.trim(),
            initials: initials.trim(),
            color: color.trim(),
            logoSlug: logoSlug.trim() || null,
            imageUrl: imageUrl.trim() || null,
            duration: duration.trim(),
            price: Number(price) || 0,
            badge: badge.trim() || null,
            description: description.trim() || null,
            features: features.split("\n").map((s) => s.trim()).filter(Boolean),
            sort_order: Number(sortOrder) || 0,
            active,
          },
        },
      });
      toast.success(isNew ? "تم إضافة المنتج" : "تم الحفظ");
      onSaved();
    } catch (e) {
      toast.error((e as Error).message);
    } finally { setSaving(false); }
  };

  return (
    <Modal onClose={onClose} title={isNew ? "إضافة منتج" : "تعديل المنتج"}>
      <Field label="الاسم"><input value={name} onChange={(e) => setName(e.target.value)} className={inp} placeholder="Netflix Premium" /></Field>
      <Field label="Slug (بالإنجليزي)"><input value={slug} onChange={(e) => setSlug(e.target.value)} className={inp} dir="ltr" placeholder="netflix" disabled={!isNew} /></Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="السعر (ج.م)"><input type="number" value={price} onChange={(e) => setPrice(e.target.value)} className={inp} dir="ltr" /></Field>
        <Field label="المدة"><input value={duration} onChange={(e) => setDuration(e.target.value)} className={inp} placeholder="شهر" /></Field>
      </div>
      <Field label="وصف قصير (تحت الاسم)"><input value={tagline} onChange={(e) => setTagline(e.target.value)} className={inp} placeholder="4K UHD · شاشتين" /></Field>
      <Field label="شارة (اختياري)"><input value={badge} onChange={(e) => setBadge(e.target.value)} className={inp} placeholder="الأكثر طلباً" /></Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="أول حرف/حروف"><input value={initials} onChange={(e) => setInitials(e.target.value)} className={inp} placeholder="N" /></Field>
        <Field label="ترتيب العرض"><input type="number" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} className={inp} dir="ltr" /></Field>
      </div>
      <Field label="Logo slug (simpleicons.org)"><input value={logoSlug} onChange={(e) => setLogoSlug(e.target.value)} className={inp} dir="ltr" placeholder="netflix" /></Field>
      <Field label="رابط صورة المنتج (اختياري — بيحل محل اللون واللوجو)">
        <input value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} className={inp} dir="ltr" placeholder="https://..." />
        {imageUrl.trim() && (
          <div className="mt-2 rounded-xl overflow-hidden border border-border/50 aspect-video bg-card/50">
            <img src={imageUrl.trim()} alt="preview" className="w-full h-full object-cover" />
          </div>
        )}
      </Field>
      <Field label="لون الخلفية (CSS gradient)"><input value={color} onChange={(e) => setColor(e.target.value)} className={inp} dir="ltr" /></Field>
      <Field label="الوصف الكامل"><textarea value={description} onChange={(e) => setDescription(e.target.value)} className={`${inp} min-h-20`} /></Field>
      <Field label="المميزات (كل مميزة في سطر)"><textarea value={features} onChange={(e) => setFeatures(e.target.value)} className={`${inp} min-h-24`} /></Field>
      <label className="flex items-center gap-2 mb-3 text-sm cursor-pointer">
        <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="size-4" />
        <span className="font-bold">ظاهر في المتجر</span>
      </label>
      <button onClick={save} disabled={saving || !slug || !name}
              className="w-full mt-2 rounded-2xl py-3 text-sm font-black text-primary-foreground flex items-center justify-center gap-2 disabled:opacity-60"
              style={{ background: "var(--gradient-hero)" }}>
        {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
        {saving ? "جاري الحفظ..." : (isNew ? "إضافة" : "حفظ")}
      </button>
    </Modal>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block mb-3">
      <div className="text-xs font-bold text-muted-foreground mb-1.5">{label}</div>
      {children}
    </label>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm grid place-items-center p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
           className="w-full max-w-md rounded-3xl glow-card p-6 max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-black">{title}</h3>
          <button onClick={onClose} className="rounded-full p-1.5 hover:bg-card"><X className="size-4" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function StatusBadge({ status, note }: { status: string; note: string | null }) {
  const map: Record<string, { label: string; cls: string }> = {
    verified: { label: "مؤكد ✓", cls: "bg-green-500/15 text-green-300 border-green-500/30" },
    delivered: { label: "تم التسليم", cls: "bg-blue-500/15 text-blue-300 border-blue-500/30" },
    pending_review: { label: "قيد المراجعة", cls: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30" },
    pending: { label: "قيد المراجعة", cls: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30" },
    rejected: { label: "مرفوض", cls: "bg-red-500/15 text-red-300 border-red-500/30" },
  };
  const s = map[status] ?? { label: status, cls: "bg-muted/30 text-muted-foreground border-border" };
  return (
    <div className="mt-2">
      <span className={`inline-block text-[11px] font-bold px-2 py-0.5 rounded-full border ${s.cls}`}>{s.label}</span>
      {note && <div className="text-[11px] text-muted-foreground mt-1.5">{note}</div>}
    </div>
  );
}

let audioCtx: AudioContext | null = null;
function playBeep() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const ctx = audioCtx;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "sine"; o.frequency.value = 880; g.gain.value = 0.0001;
    o.connect(g).connect(ctx.destination);
    const now = ctx.currentTime;
    g.gain.exponentialRampToValueAtTime(0.2, now + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, now + 0.4);
    o.start(now); o.stop(now + 0.42);
  } catch {}
}

// =========================== WHATSAPP BROADCAST ===========================
const BC_KEY = "bc_state_v1";

function normalizePhone(raw: string): string | null {
  const digits = raw.replace(/[^\d]/g, "");
  if (!digits) return null;
  // Egypt local 01xxxxxxxxx -> 201xxxxxxxxx
  if (digits.startsWith("01") && digits.length === 11) return "2" + digits;
  if (digits.startsWith("2") && digits.length === 12) return digits;
  if (digits.length >= 10) return digits;
  return null;
}

function parseNumbers(text: string): string[] {
  const parts = text.split(/[\s,;\n]+/).map((s) => s.trim()).filter(Boolean);
  const out: string[] = [];
  const seen = new Set<string>();
  for (const p of parts) {
    const n = normalizePhone(p);
    if (n && !seen.has(n)) { seen.add(n); out.push(n); }
  }
  return out;
}

type BCState = { numbers: string[]; message: string; index: number; sent: string[] };

function BroadcastTab() {
  const [rawNumbers, setRawNumbers] = useState("");
  const [message, setMessage] = useState("");
  const [state, setState] = useState<BCState | null>(() => {
    if (typeof window === "undefined") return null;
    try { const s = localStorage.getItem(BC_KEY); return s ? JSON.parse(s) : null; } catch { return null; }
  });

  useEffect(() => {
    if (state) localStorage.setItem(BC_KEY, JSON.stringify(state));
    else localStorage.removeItem(BC_KEY);
  }, [state]);

  const parsed = useMemo(() => parseNumbers(rawNumbers), [rawNumbers]);

  const start = () => {
    if (!parsed.length) { toast.error("مفيش أرقام صحيحة"); return; }
    if (!message.trim()) { toast.error("اكتب الرسالة"); return; }
    setState({ numbers: parsed, message: message.trim(), index: 0, sent: [] });
  };

  const openCurrent = () => {
    if (!state) return;
    const phone = state.numbers[state.index];
    const url = `https://wa.me/${phone}?text=${encodeURIComponent(state.message)}`;
    window.open(url, "_blank", "noopener");
  };

  const markSentAndNext = () => {
    if (!state) return;
    const phone = state.numbers[state.index];
    const nextIndex = state.index + 1;
    const nextSent = [...state.sent, phone];
    if (nextIndex >= state.numbers.length) {
      toast.success(`تم! ابعتّ لـ ${nextSent.length} رقم`);
      setState({ ...state, index: nextIndex, sent: nextSent });
      return;
    }
    const nextState = { ...state, index: nextIndex, sent: nextSent };
    setState(nextState);
    // auto-open next
    const url = `https://wa.me/${nextState.numbers[nextIndex]}?text=${encodeURIComponent(nextState.message)}`;
    setTimeout(() => window.open(url, "_blank", "noopener"), 100);
  };

  const skip = () => {
    if (!state) return;
    const nextIndex = state.index + 1;
    if (nextIndex >= state.numbers.length) {
      toast.info("انتهى الطابور");
      setState({ ...state, index: nextIndex });
      return;
    }
    setState({ ...state, index: nextIndex });
  };

  const reset = () => setState(null);

  const done = state && state.index >= state.numbers.length;

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-border bg-card/50 p-5">
        <div className="flex items-center gap-2 mb-3">
          <MessageCircle className="size-5 text-primary" />
          <h3 className="font-black">بث واتساب</h3>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          الأداة بتفتح شات واتساب لكل رقم بالرسالة جاهزة. اضغط <b>Send</b> في واتساب، ارجع لهنا واضغط <b>تم — التالي</b> عشان يفتح الرقم اللي بعده تلقائياً.
        </p>
      </div>

      {!state ? (
        <>
          <div className="rounded-2xl border border-border bg-card/50 p-5">
            <label className="text-xs font-bold text-muted-foreground mb-2 block">
              الأرقام (سطر لكل رقم أو مفصولة بفواصل)
            </label>
            <textarea
              value={rawNumbers}
              onChange={(e) => setRawNumbers(e.target.value)}
              rows={8}
              dir="ltr"
              placeholder="01234567890&#10;01098765432&#10;..."
              className="w-full rounded-xl border border-border bg-background/50 px-4 py-3 text-sm font-mono"
            />
            <div className="mt-2 text-xs text-muted-foreground">
              اتعرف على <b className="text-foreground">{parsed.length}</b> رقم صحيح
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-card/50 p-5">
            <label className="text-xs font-bold text-muted-foreground mb-2 block">
              الرسالة
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={6}
              placeholder="اكتب الرسالة هنا... ممكن تحط لينك صورة أو فيديو جوّه النص."
              className="w-full rounded-xl border border-border bg-background/50 px-4 py-3 text-sm"
            />
            <div className="mt-2 text-xs text-muted-foreground">
              {message.length} حرف
            </div>
          </div>

          <button
            onClick={start}
            disabled={!parsed.length || !message.trim()}
            className="w-full rounded-2xl py-3.5 text-sm font-black text-primary-foreground disabled:opacity-50"
            style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}
          >
            <Send className="size-4 inline ms-2" />
            ابدأ البث ({parsed.length} رقم)
          </button>
        </>
      ) : (
        <div className="space-y-4">
          <div className="rounded-2xl border border-border bg-card/50 p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-bold text-muted-foreground">التقدم</div>
              <div className="text-xs tabular-nums">
                <span className="text-primary font-black">{Math.min(state.index, state.numbers.length)}</span>
                <span className="text-muted-foreground"> / {state.numbers.length}</span>
              </div>
            </div>
            <div className="h-2 rounded-full bg-background/50 overflow-hidden">
              <div
                className="h-full transition-all"
                style={{
                  width: `${(Math.min(state.index, state.numbers.length) / state.numbers.length) * 100}%`,
                  background: "var(--gradient-hero)",
                }}
              />
            </div>
          </div>

          {done ? (
            <div className="rounded-2xl border border-primary/40 bg-primary/5 p-6 text-center">
              <div className="text-lg font-black text-primary mb-1">✓ تم البث</div>
              <div className="text-xs text-muted-foreground mb-4">
                اتبعت لـ {state.sent.length} رقم من أصل {state.numbers.length}
              </div>
              <button
                onClick={reset}
                className="rounded-xl border border-border px-5 py-2 text-sm font-bold hover:bg-card"
              >
                بث جديد
              </button>
            </div>
          ) : (
            <div className="rounded-2xl border border-border bg-card/50 p-5">
              <div className="text-xs text-muted-foreground mb-2">الرقم الحالي</div>
              <div dir="ltr" className="text-2xl font-black tabular-nums mb-4">
                +{state.numbers[state.index]}
              </div>

              <div className="rounded-xl bg-background/50 border border-border p-3 mb-4 text-xs whitespace-pre-wrap max-h-32 overflow-auto">
                {state.message}
              </div>

              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={openCurrent}
                  className="rounded-xl py-3 text-sm font-black text-primary-foreground"
                  style={{ background: "#25d366" }}
                >
                  <MessageCircle className="size-4 inline ms-1" />
                  فتح واتساب
                </button>
                <button
                  onClick={markSentAndNext}
                  className="rounded-xl py-3 text-sm font-black text-primary-foreground"
                  style={{ background: "var(--gradient-hero)" }}
                >
                  تم — التالي ←
                </button>
              </div>

              <div className="flex justify-between mt-3">
                <button onClick={skip} className="text-xs text-muted-foreground hover:text-foreground">
                  تخطي هذا الرقم
                </button>
                <button onClick={reset} className="text-xs text-red-400 hover:text-red-300">
                  إلغاء البث
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
