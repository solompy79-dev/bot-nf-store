import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, ChevronDown } from "lucide-react";
import { useState } from "react";

export const Route = createFileRoute("/faq")({
  head: () => ({
    meta: [
      { title: "الأسئلة الشائعة — اشتراكي بلس" },
      { name: "description", content: "إجابات عن أشهر الأسئلة عن اشتراكات Netflix و Spotify و Shahid وطرق الدفع والاستبدال." },
      { property: "og:title", content: "الأسئلة الشائعة — اشتراكي بلس" },
      { property: "og:description", content: "إجابات سريعة عن التفعيل، الدفع، الضمان، والاستبدال لاشتراكات اشتراكي بلس." },
    ],
    scripts: [{
      type: "application/ld+json",
      children: JSON.stringify({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        mainEntity: items.map((it) => ({
          "@type": "Question",
          name: it.q,
          acceptedAnswer: { "@type": "Answer", text: it.a },
        })),
      }),
    }],
  }),
  component: FaqPage,
});

const items = [
  { q: "الاشتراكات أصلية؟", a: "نعم، كل اشتراكاتنا أصلية 100% من الشركات المصنعة، ومش حسابات مشتركة أو مسروقة." },
  { q: "قد إيه مدة التفعيل؟", a: "التفعيل بيتم خلال دقائق من التحقق من الدفع، وأقصى مدة 30 دقيقة." },
  { q: "طرق الدفع المتاحة؟", a: "فودافون كاش، إنستاباي، فيزا، ماستركارد، أو تحويل بنكي." },
  { q: "هل فيه ضمان؟", a: "أيوة — كل اشتراك مضمون طول مدته. لو حصلت مشكلة هنستبدله فورًا." },
  { q: "أقدر أشترك بأكتر من خدمة مرة واحدة؟", a: "طبعًا! ضيف كل الاشتراكات للسلة وادفعها دفعة واحدة." },
  { q: "فيه أكواد خصم؟", a: "أيوة، تابعنا على واتساب وسناب شات للعروض والأكواد الحصرية." },
];

function FaqPage() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-background/70 border-b border-border">
        <div className="max-w-3xl mx-auto px-4 h-14 flex items-center gap-3">
          <Link to="/" className="p-2 rounded-lg hover:bg-card"><ArrowLeft className="size-5" /></Link>
          <h1 className="text-lg font-black">الأسئلة الشائعة</h1>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 py-6 pb-28 space-y-2">
        {items.map((it, i) => (
          <div key={i} className="glow-card rounded-2xl overflow-hidden">
            <button onClick={() => setOpen(open === i ? null : i)}
                    className="w-full flex items-center justify-between p-4 text-right">
              <span className="font-bold">{it.q}</span>
              <ChevronDown className={`size-5 transition ${open === i ? "rotate-180" : ""}`} />
            </button>
            {open === i && <div className="px-4 pb-4 text-sm text-muted-foreground leading-relaxed">{it.a}</div>}
          </div>
        ))}
      </main>
    </div>
  );
}
