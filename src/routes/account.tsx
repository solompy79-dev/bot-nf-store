import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { supabase } from "@/lib/auth-client";
import type { User } from "@supabase/supabase-js";
import { getMyProfile, updateMyProfile } from "@/lib/features.functions";
import { toast } from "sonner";
import { Copy, LogOut, Wallet, Gift, Lock, Eye, ChevronLeft, CircleHelp, ShieldCheck, Headphones, UserRound } from "lucide-react";
import { StoreHeader, StoreBottomNav } from "@/components/StoreChrome";
import { isLocalAuth, localRequest, localAuth } from "@/lib/local-auth";

export const Route = createFileRoute("/account")({
  component: AccountPage,
  head: () => ({
    meta: [
      { title: "حسابي — اشتراكي بلس" },
      { name: "description", content: "بيانات حسابك، الرصيد، كود الإحالة وإعدادات كلمة السر على اشتراكي بلس." },
      { property: "og:title", content: "حسابي — اشتراكي بلس" },
      { property: "og:description", content: "أدر بياناتك ورصيدك وكود الإحالة الخاص بك." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
      { name: "robots", content: "noindex" },
    ],
  }),
});

function AccountPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const qc = useQueryClient();
  const [hideBalance, setHideBalance] = useState(false);
  useEffect(() => { setHideBalance(localStorage.getItem("hide-balance") === "true"); }, []);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user ?? null);
      setLoading(false);
      if (!data.user) navigate({ to: "/auth" });
    });
  }, [navigate]);

  const getProfile = useServerFn(getMyProfile);
  const { data: profile, isLoading } = useQuery({
    queryKey: ["me", "profile"],
    queryFn: () => isLocalAuth ? localRequest<Awaited<ReturnType<typeof getProfile>>>("profile") : getProfile(),
    enabled: !!user,
  });

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  useEffect(() => {
    if (profile) {
      setName(profile.full_name ?? "");
      setPhone(profile.phone ?? "");
    }
  }, [profile]);

  const updateFn = useServerFn(updateMyProfile);
  const saveMut = useMutation({
    mutationFn: (v: { full_name: string; phone: string }) => isLocalAuth ? localRequest<{ ok: true }>("profile", v) : updateFn({ data: v }),
    onSuccess: () => {
      toast.success("تم حفظ بياناتك");
      qc.invalidateQueries({ queryKey: ["me", "profile"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const [pwCur, setPwCur] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwLoading, setPwLoading] = useState(false);
  const changePassword = async () => {
    if (pwNew.length < 6) return toast.error("كلمة السر الجديدة قصيرة (6 حروف على الأقل)");
    setPwLoading(true);
    const { error } = isLocalAuth ? await localAuth.updateUser({ password: pwNew, current_password: pwCur }) : await supabase.auth.updateUser({ password: pwNew });
    setPwLoading(false);
    if (error) toast.error(error.message);
    else {
      toast.success("تم تغيير كلمة السر");
      setPwCur(""); setPwNew("");
    }
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    navigate({ to: "/" });
  };

  const copyReferral = async () => {
    if (!profile?.referral_code) return;
    const url = `${window.location.origin}/auth?ref=${profile.referral_code}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("تم نسخ رابط الإحالة");
    } catch { toast.error("تعذّر النسخ، حاول مرة تانية"); }
  };

  if (loading || isLoading) {
    return <div className="min-h-screen grid place-items-center text-muted-foreground">جاري التحميل...</div>;
  }

  return (
    <div className="store-page account-page">
      <StoreHeader page="حسابي" />

      <main className="account-main">
        {isLocalAuth && <p className="rounded-xl border border-border bg-card p-3 text-xs text-muted-foreground leading-relaxed">حسابك محفوظ على الجهاز ده. الطلبات والمدفوعات في الموقع المنشور منفصلة عن الحساب المحلي.</p>}
        <section className="account-identity">
          <div className="account-avatar"><UserRound size={28} /></div>
          <div><span className="eyebrow">أهلًا بيك في اشتراكي بلس</span><h1>{name || user?.email?.split("@")[0] || "حسابي"}</h1><p dir="ltr">{user?.email}</p></div>
        </section>
        {/* Wallet + Referral summary */}
        <div className="account-summary">
          <div className="glow-card rounded-2xl p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2"><Wallet className="size-4" /> الرصيد</div>
              <div className="text-2xl font-black">{hideBalance ? "••••" : Number(profile?.wallet_balance ?? 0).toFixed(0)} <span className="text-sm">ج.م</span></div>
            </div>
          </div>
          <div className="glow-card rounded-2xl p-4">
            <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2"><Gift className="size-4" /> كود الإحالة</div>
            <button onClick={copyReferral} disabled={!profile?.referral_code} className="flex items-center gap-2 font-black text-lg text-primary hover:opacity-80 disabled:opacity-50">
              {profile?.referral_code ?? "—"}
              <Copy className="size-4 text-muted-foreground" />
            </button>
          </div>
        </div>

        <section className="account-panel"><span className="eyebrow">التفضيلات</span><div className="account-preference"><span><Eye size={18} />إخفاء الرصيد</span><button className="store-switch" role="switch" aria-checked={hideBalance} aria-label="إخفاء الرصيد" onClick={() => { const next = !hideBalance; setHideBalance(next); localStorage.setItem("hide-balance", String(next)); }}><span /></button></div></section>
        <section className="account-panel"><span className="eyebrow">المساعدة والدعم</span><div className="account-support-links">{[
          { to: "/faq", title: "الأسئلة الشائعة", Icon: CircleHelp },
          { to: "/refund-policy", title: "الضمان وسياسة الاسترجاع", Icon: ShieldCheck },
          { to: "/support", title: "تواصل مع الدعم", Icon: Headphones },
        ].map(({ to, title, Icon }) => <Link key={to} to={to}><span className="support-icon"><Icon size={17} /></span><span>{title}</span><ChevronLeft size={16} /></Link>)}</div></section>

        {/* Profile edit */}
        <section className="glow-card rounded-2xl p-5">
          <h2 className="font-black text-lg mb-4">بياناتي</h2>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">الاسم</label>
              <input value={name} onChange={(e) => setName(e.target.value)}
                     className="w-full px-4 py-2.5 rounded-xl bg-background border border-border" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">رقم الموبايل</label>
              <input value={phone} onChange={(e) => setPhone(e.target.value)} dir="ltr"
                     className="w-full px-4 py-2.5 rounded-xl bg-background border border-border text-right" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">الإيميل</label>
              <input value={user?.email ?? ""} readOnly dir="ltr"
                     className="w-full px-4 py-2.5 rounded-xl bg-card border border-border text-muted-foreground text-right" />
            </div>
            <button onClick={() => saveMut.mutate({ full_name: name, phone })} disabled={saveMut.isPending}
                    className="w-full py-2.5 rounded-xl font-black text-primary-foreground disabled:opacity-50"
                    style={{ background: "var(--gradient-hero)" }}>
              {saveMut.isPending ? "جاري الحفظ..." : "حفظ التغييرات"}
            </button>
          </div>
        </section>

        {/* Change password */}
        <section className="glow-card rounded-2xl p-5">
          <h2 className="font-black text-lg mb-4 flex items-center gap-2"><Lock className="size-5" /> تغيير كلمة السر</h2>
          <div className="space-y-3">
            {isLocalAuth && <input aria-label="كلمة السر الحالية" value={pwCur} onChange={e => setPwCur(e.target.value)} type="password" autoComplete="current-password" placeholder="كلمة السر الحالية" dir="ltr" className="w-full px-4 py-2.5 rounded-xl bg-background border border-border text-right" />}
            <input value={pwNew} onChange={(e) => setPwNew(e.target.value)} type="password" placeholder="كلمة السر الجديدة" dir="ltr"
                   className="w-full px-4 py-2.5 rounded-xl bg-background border border-border text-right" />
            <button onClick={changePassword} disabled={pwLoading || !pwNew}
                    className="w-full py-2.5 rounded-xl font-black border border-border hover:bg-card disabled:opacity-50">
              {pwLoading ? "..." : "تغيير كلمة السر"}
            </button>
          </div>
        </section>

        {/* Sign out */}
        <button onClick={signOut}
                className="w-full py-3 rounded-xl font-black text-destructive border border-destructive/40 hover:bg-destructive/10 flex items-center justify-center gap-2">
          <LogOut className="size-4" /> تسجيل خروج
        </button>
      </main>
      <StoreBottomNav active="account" />
    </div>
  );
}
