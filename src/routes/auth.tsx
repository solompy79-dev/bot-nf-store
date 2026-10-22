import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/auth-client";
import { lovable } from "@/integrations/lovable";
import { toast } from "sonner";
import { brandLogoUrl } from "@/lib/product-artwork";
import { isLocalAuth } from "@/lib/local-auth";

export const Route = createFileRoute("/auth")({
  head: () => ({
    meta: [
      { title: "تسجيل الدخول — اشتراكي بلس" },
      { name: "description", content: "سجّل دخولك أو أنشئ حساب جديد على اشتراكي بلس." },
      { property: "og:title", content: "تسجيل الدخول — اشتراكي بلس" },
      { property: "og:description", content: "سجّل دخولك أو أنشئ حساب جديد على اشتراكي بلس." },
    ],
  }),
  component: AuthPage,
});

function AuthPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [authReady, setAuthReady] = useState(false);
  const [otpStep, setOtpStep] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [authError, setAuthError] = useState("");
  const [needsConfirmation, setNeedsConfirmation] = useState(false);
  const [resetMode, setResetMode] = useState(false);
  const [recoverySession, setRecoverySession] = useState(false);
  const [resetSent, setResetSent] = useState(false);

  const showAuthError = (err: unknown) => {
    const code = typeof err === "object" && err !== null && "code" in err ? String(err.code) : "";
    const message = err instanceof Error ? err.message : "حصل خطأ، حاول مرة تانية";
    const messages: Record<string, string> = {
      invalid_credentials: "الإيميل أو كلمة السر غير صحيحين. استخدم بيانات حسابك في المتجر، مش حساب Lovable.",
      email_not_confirmed: "الإيميل لسه محتاج تأكيد. تقدر تطلب كود تأكيد جديد من الزر اللي تحت.",
      over_request_rate_limit: "محاولات كتير في وقت قصير. استنى شوية وجرب تاني.",
      over_email_send_rate_limit: "وصلت لحد إرسال الرسائل. استنى شوية قبل طلب كود جديد.",
    };
    const friendly = messages[code] || (/failed to fetch|networkerror|load failed/i.test(message) ? "تعذّر الاتصال بخدمة تسجيل الدخول. راجع اتصال الإنترنت وحاول تاني." : message);
    setNeedsConfirmation(code === "email_not_confirmed");
    setAuthError(friendly);
  };

  useEffect(() => {
    setAuthReady(true);
    const params = new URLSearchParams(window.location.search);
    const recoveryLink = params.get("reset") === "1" || new URLSearchParams(window.location.hash.slice(1)).get("type") === "recovery";
    if (recoveryLink) setResetMode(true);
    const { data: listener } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "PASSWORD_RECOVERY" || (recoveryLink && session)) {
        setResetMode(true);
        setRecoverySession(true);
      }
    });
    supabase.auth.getSession().then(({ data }) => {
      if (data.session && recoveryLink) setRecoverySession(true);
      else if (data.session) navigate({ to: "/" });
    });
    return () => listener.subscription.unsubscribe();
  }, [navigate]);

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");
    setLoading(true);
    try {
      if (recoverySession) {
        const { error } = await supabase.auth.updateUser({ password });
        if (error) throw error;
        toast.success("تم تغيير كلمة السر بنجاح");
        await navigate({ to: "/" });
      } else {
        const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
          redirectTo: `${window.location.origin}/auth?reset=1`,
        });
        if (error) throw error;
        setResetSent(true);
      }
    } catch (err) { showAuthError(err); }
    finally { setLoading(false); }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");
    setNeedsConfirmation(false);
    setLoading(true);
    try {
      if (mode === "signup") {
        if (!fullName.trim()) throw new Error("اكتب اسمك");
        if ((!isLocalAuth || phone.trim()) && !/^\+?[0-9]{7,15}$/.test(phone.trim().replace(/[\s-]/g, ""))) throw new Error("رقم موبايل غير صحيح");
        const { data, error } = await supabase.auth.signUp({
          email: email.trim(),
          password,
          options: {
            emailRedirectTo: window.location.origin,
            data: { full_name: fullName.trim(), phone: phone.trim() },
          },
        });
        if (error) throw error;
        if (data.session) {
          toast.success("أهلاً بيك!");
          await navigate({ to: "/" });
          return;
        }
        toast.success("بعتنا كود التأكيد على إيميلك!");
        setOtpStep(true);
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
        if (error) throw error;
        toast.success("أهلاً بيك!");
        navigate({ to: "/" });
      }
    } catch (err) {
      showAuthError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (!/^\d{6}$/.test(otpCode.trim())) throw new Error("الكود لازم يكون 6 أرقام");
      const { data, error } = await supabase.auth.verifyOtp({
        email: email.trim(),
        token: otpCode.trim(),
        type: "signup",
      });
      if (error) throw error;
      const uid = data.user?.id;
      if (uid) {
        await supabase.from("profiles").upsert({
          id: uid,
          full_name: fullName.trim(),
          phone: phone.trim(),
        });
      }
      toast.success("تم تفعيل حسابك! أهلاً بيك");
      navigate({ to: "/" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "كود غير صحيح");
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setLoading(true);
    try {
      const { error } = await supabase.auth.resend({ type: "signup", email: email.trim() });
      if (error) throw error;
      setAuthError("");
      setNeedsConfirmation(false);
      setOtpStep(true);
      toast.success("بعتنا كود جديد!");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "فشل الإرسال");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setLoading(true);
    try {
      const result = await lovable.auth.signInWithOAuth("google", {
        redirect_uri: window.location.origin,
      });
      if (result.error) throw result.error;
      if (result.redirected) return;
      navigate({ to: "/" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "فشل تسجيل الدخول بجوجل");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center px-6 py-16 relative overflow-hidden">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-20 -left-20 size-72 rounded-full blur-3xl animate-pulse-glow"
             style={{ background: "radial-gradient(circle, oklch(0.65 0.24 295 / 0.5), transparent 70%)" }} />
        <div className="absolute bottom-0 -right-20 size-80 rounded-full blur-3xl animate-pulse-glow"
             style={{ background: "radial-gradient(circle, oklch(0.55 0.22 310 / 0.45), transparent 70%)", animationDelay: "1.5s" }} />
      </div>

      <div className="w-full max-w-md">
        <Link to="/" className="flex items-center gap-3 justify-center mb-8">
          <img src={brandLogoUrl} alt="اشتراكي بلس" width={240} height={80} className="h-20 w-auto max-w-full object-contain" />
        </Link>

        <div className="rounded-3xl p-5 sm:p-8 glow-card animate-fade-up">
          {authError && <div role="alert" className="mb-5 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm leading-relaxed">{authError}</div>}
          {needsConfirmation && <button type="button" disabled={loading} onClick={handleResendOtp} className="mb-5 w-full rounded-xl border border-primary/40 px-3 py-3 text-sm font-bold text-primary disabled:opacity-50">إرسال كود تأكيد الإيميل</button>}
          {resetMode ? (
            <>
              <h1 className="text-2xl font-black text-center mb-3">{recoverySession ? "كلمة سر جديدة" : "استعادة كلمة السر"}</h1>
              <p className="text-sm text-muted-foreground text-center mb-6">{recoverySession ? "اختار كلمة سر قوية وفريدة لحسابك." : "اكتب إيميل حسابك وهنبعتلك رابط تعيين كلمة سر جديدة."}</p>
              {resetSent ? <p role="status" className="rounded-xl bg-primary/10 p-4 text-sm leading-relaxed">لو الإيميل مسجّل عندنا، هيوصلك رابط الاستعادة. راجع الوارد والرسائل غير المرغوب فيها.</p> : <form onSubmit={handleReset} className="space-y-4">
                {recoverySession ? <input aria-label="كلمة السر الجديدة" type="password" autoComplete="new-password" required minLength={8} value={password} onChange={e => setPassword(e.target.value)} placeholder="كلمة السر الجديدة" dir="ltr" className="w-full rounded-xl bg-background/60 border border-border px-4 py-3 text-base" /> : <input aria-label="إيميل استعادة الحساب" type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" dir="ltr" className="w-full rounded-xl bg-background/60 border border-border px-4 py-3 text-base" />}
                <button type="submit" disabled={loading} className="w-full rounded-xl py-3 text-sm font-bold bg-primary text-primary-foreground disabled:opacity-50">{loading ? "جارٍ..." : recoverySession ? "حفظ كلمة السر" : "إرسال رابط الاستعادة"}</button>
              </form>}
              {!recoverySession && <button type="button" disabled={loading} onClick={() => { setResetMode(false); setResetSent(false); setAuthError(""); }} className="block mx-auto mt-5 text-sm text-primary">رجوع لتسجيل الدخول</button>}
            </>
          ) : otpStep ? (
            <>
              <h1 className="text-2xl font-black text-center mb-1">أدخل كود التأكيد</h1>
              <p className="text-sm text-muted-foreground text-center mb-6">
                بعتنا كود مكوّن من 6 أرقام على <span className="text-primary font-bold" dir="ltr">{email}</span>
              </p>
              <form onSubmit={handleVerifyOtp} className="space-y-4">
                <input
                  type="text"
                  inputMode="numeric"
                  required
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder="------"
                  maxLength={6}
                  dir="ltr"
                  className="w-full rounded-xl bg-background/60 border border-border px-4 py-4 text-center text-3xl font-black tracking-[0.6em] outline-none focus:border-primary transition"
                />
                <button
                  type="submit"
                  disabled={loading || otpCode.length !== 6}
                  className="w-full rounded-xl py-3 text-sm font-bold text-primary-foreground hover:scale-[1.02] transition disabled:opacity-50"
                  style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}>
                  {loading ? "جارٍ التأكيد..." : "تفعيل الحساب"}
                </button>
              </form>
              <div className="flex justify-between items-center mt-6 text-sm">
                <button
                  type="button"
                  onClick={handleResendOtp}
                  disabled={loading}
                  className="text-primary font-bold hover:underline disabled:opacity-50">
                  إعادة إرسال الكود
                </button>
                <button
                  type="button"
                  onClick={() => { setOtpStep(false); setOtpCode(""); }}
                  className="text-muted-foreground hover:text-foreground">
                  تعديل الإيميل
                </button>
              </div>
            </>
          ) : (
            <>
              <h1 className="text-2xl font-black text-center mb-1">
                {mode === "signin" ? "أهلاً بيك تاني" : "أنشئ حسابك"}
              </h1>
              <p className="text-sm text-muted-foreground text-center mb-6">
                {mode === "signin" ? "سجّل دخولك للوصول لاشتراكاتك" : "خطوة واحدة وتبدأ معانا"}
              </p>

              {!isLocalAuth && <button
            type="button"
            onClick={handleGoogle}
            disabled={loading}
            className="w-full rounded-xl py-3 text-sm font-bold border border-border bg-background/60 hover:bg-background transition flex items-center justify-center gap-3 disabled:opacity-50">
            <svg className="size-5" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.1c-.22-.66-.35-1.36-.35-2.1s.13-1.44.35-2.1V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.83z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"/>
            </svg>
            المتابعة بحساب Google
          </button>}

          {!isLocalAuth && <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-muted-foreground">أو</span>
            <div className="flex-1 h-px bg-border" />
          </div>}
          {isLocalAuth && <p className="mb-5 rounded-xl bg-primary/10 p-3 text-xs leading-relaxed text-muted-foreground">حساب محلي على الجهاز ده، منفصل عن الموقع المنشور. إنشاء الحساب فوري من غير كود تأكيد.</p>}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "signup" && (
              <>
                <div>
                  <label className="block text-xs font-bold mb-1.5 text-muted-foreground">الاسم بالكامل</label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="اسمك"
                    maxLength={100}
                    className="w-full rounded-xl bg-background/60 border border-border px-4 py-3 text-sm outline-none focus:border-primary transition"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1.5 text-muted-foreground">رقم الموبايل</label>
                  <input
                    type="tel"
                    required={!isLocalAuth}
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+20 1xxxxxxxxx"
                    dir="ltr"
                    maxLength={16}
                    className="w-full rounded-xl bg-background/60 border border-border px-4 py-3 text-sm outline-none focus:border-primary transition"
                  />
                </div>
              </>
            )}
            <div>
              <label className="block text-xs font-bold mb-1.5 text-muted-foreground">البريد الإلكتروني</label>
              <input
                type="email"
                required
                value={email}
                autoComplete="email"
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                dir="ltr"
                className="w-full rounded-xl bg-background/60 border border-border px-4 py-3 text-sm outline-none focus:border-primary transition"
              />
            </div>
            <div>
              <label className="block text-xs font-bold mb-1.5 text-muted-foreground">كلمة السر</label>
              <input
                type="password"
                required
                minLength={isLocalAuth ? 8 : 6}
                maxLength={128}
                value={password}
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                dir="ltr"
                className="w-full rounded-xl bg-background/60 border border-border px-4 py-3 text-sm outline-none focus:border-primary transition"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !authReady}
              className="w-full rounded-xl py-3 text-sm font-bold text-primary-foreground hover:scale-[1.02] transition disabled:opacity-50"
              style={{ background: "var(--gradient-hero)", boxShadow: "var(--shadow-glow)" }}>
              {loading ? "جارٍ..." : mode === "signin" ? "تسجيل دخول" : "إنشاء حساب"}
            </button>
          </form>

          {mode === "signin" && !isLocalAuth && <button type="button" disabled={loading} onClick={() => { setResetMode(true); setPassword(""); setAuthError(""); setNeedsConfirmation(false); }} className="block mx-auto mt-4 text-sm font-bold text-primary">نسيت كلمة السر؟</button>}

          <p className="text-center text-sm text-muted-foreground mt-6">
            {mode === "signin" ? "لسه معندكش حساب؟" : "عندك حساب بالفعل؟"}{" "}
            <button
              type="button"
              disabled={loading}
              onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setAuthError(""); setNeedsConfirmation(false); }}
              className="text-primary font-bold hover:underline">
              {mode === "signin" ? "أنشئ حساب" : "سجّل دخول"}
            </button>
          </p>
            </>
          )}
        </div>

        <Link to="/" className="block text-center mt-6 text-sm text-muted-foreground hover:text-foreground transition">
          ← رجوع للرئيسية
        </Link>
      </div>
    </div>
  );
}
