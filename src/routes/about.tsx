import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

export const Route = createFileRoute("/about")({
  head: () => ({
    meta: [
      { title: "من نحن — اشتراكي بلس" },
      { name: "description", content: "تعرّف على اشتراكي بلس — منصة مصرية لبيع اشتراكات الستريمنج الأصلية بأسعار مميزة." },
      { property: "og:title", content: "من نحن — اشتراكي بلس" },
      { property: "og:description", content: "منصة مصرية لبيع اشتراكات الستريمنج الأصلية بأسعار مميزة وتفعيل فوري." },
    ],
  }),
  component: AboutPage,
});

function AboutPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-background/70 border-b border-border">
        <div className="max-w-3xl mx-auto px-4 h-14 flex items-center gap-3">
          <Link to="/" className="p-2 rounded-lg hover:bg-card"><ArrowLeft className="size-5" /></Link>
          <div className="text-lg font-black">من نحن</div>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 py-8 pb-28">
        <h1 className="text-3xl font-black mb-4 gradient-text">اشتراكي بلس</h1>
        <p className="text-muted-foreground leading-relaxed mb-6">
          اشتراكي بلس منصة مصرية متخصصة في بيع اشتراكات الترفيه الرقمي الأصلية بأسعار تنافسية للجميع.
          بنقدم لعملائنا كل خدمات الستريمنج من Netflix و Spotify و Shahid و Disney+ و YouTube Premium وأكتر.
        </p>
        <h2 className="text-xl font-black mt-8 mb-3">ليه اشتراكي بلس؟</h2>
        <ul className="space-y-2 text-muted-foreground">
          <li>✓ اشتراكات أصلية 100% — مش مسروقة ولا معدّلة</li>
          <li>✓ تفعيل فوري خلال دقايق من الدفع</li>
          <li>✓ ضمان كامل طول مدة الاشتراك</li>
          <li>✓ دعم فني عربي على مدار الساعة</li>
          <li>✓ طرق دفع مرنة: فودافون كاش، إنستاباي، فيزا</li>
        </ul>
        <h2 className="text-xl font-black mt-8 mb-3">تواصل معانا</h2>
        <p className="text-muted-foreground">واتساب: <span dir="ltr">01101560023</span></p>
      </main>
    </div>
  );
}
