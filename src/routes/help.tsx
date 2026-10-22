import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, MessageCircle, Mail, HelpCircle } from "lucide-react";

export const Route = createFileRoute("/help")({
  component: HelpPage,
  head: () => ({
    meta: [
      { title: "المساعدة — اشتراكي بلس" },
      { name: "description", content: "تواصل مع الدعم واطلع على الأسئلة الشائعة" },
      { property: "og:title", content: "مركز المساعدة — اشتراكي بلس" },
      { property: "og:description", content: "تواصل مع فريق دعم اشتراكي بلس عبر واتساب أو إيميل، مع إجابات للأسئلة الشائعة." },
    ],
  }),
});

function HelpPage() {
  const faqs: [string, string][] = [
    ["الاشتراكات أصلية ولا لأ؟", "كل اشتراكاتنا أصلية 100% ومباشرة من الخدمة الرسمية."],
    ["إمتى بيتم التفعيل؟", "التفعيل بيتم خلال 5 لـ 15 دقيقة كحد أقصى بعد تأكيد الدفع."],
    ["لو حصل أي مشكلة؟", "عندنا ضمان طول مدة الاشتراك، بنستبدل أو نعوّض أي مشكلة فوراً."],
    ["إيه طرق الدفع المتاحة؟", "فودافون كاش، إنستاباي، فيزا/ماستركارد، تحويل بنكي."],
  ];

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
            <HelpCircle className="size-7" />
          </div>
          <h1 className="text-3xl font-black mb-2">مركز المساعدة</h1>
          <p className="text-sm text-muted-foreground">فريق الدعم متاح 24/7</p>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-10">
          <a href="https://wa.me/" target="_blank" rel="noreferrer"
             className="rounded-2xl glow-card p-5 flex flex-col items-center text-center gap-2 hover:scale-105 transition-transform">
            <MessageCircle className="size-7 text-primary" />
            <div className="font-bold">واتساب</div>
            <div className="text-[11px] text-muted-foreground">رد فوري</div>
          </a>
          <a href="mailto:support@example.com"
             className="rounded-2xl glow-card p-5 flex flex-col items-center text-center gap-2 hover:scale-105 transition-transform">
            <Mail className="size-7 text-primary" />
            <div className="font-bold">إيميل</div>
            <div className="text-[11px] text-muted-foreground">خلال 24 ساعة</div>
          </a>
        </div>

        <div className="text-xs text-muted-foreground uppercase tracking-wider text-center mb-4">
          الأسئلة الشائعة
        </div>
        <div className="space-y-3">
          {faqs.map(([q, a]) => (
            <details key={q} className="group rounded-2xl border border-border bg-card/50 p-5 open:bg-card">
              <summary className="cursor-pointer font-bold flex items-center justify-between list-none">
                {q}
                <span className="text-primary group-open:rotate-45 transition-transform text-2xl leading-none">+</span>
              </summary>
              <p className="mt-3 text-sm text-muted-foreground">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </div>
  );
}
