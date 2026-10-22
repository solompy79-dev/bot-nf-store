import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

export const Route = createFileRoute("/refund-policy")({
  head: () => ({
    meta: [
      { title: "سياسة الاسترجاع — اشتراكي بلس" },
      { name: "description", content: "سياسة الاسترجاع والاستبدال والضمان لاشتراكات اشتراكي بلس." },
      { property: "og:title", content: "سياسة الاسترجاع — اشتراكي بلس" },
      { property: "og:description", content: "شروط الضمان، الاستبدال ورد المبلغ للاشتراكات الرقمية على اشتراكي بلس." },
    ],
  }),
  component: RefundPage,
});

function RefundPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-background/70 border-b border-border">
        <div className="max-w-3xl mx-auto px-4 h-14 flex items-center gap-3">
          <Link to="/" className="p-2 rounded-lg hover:bg-card"><ArrowLeft className="size-5" /></Link>
          <h1 className="text-lg font-black">سياسة الاسترجاع</h1>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 py-8 pb-28 space-y-4 text-muted-foreground">
        <section className="glow-card rounded-2xl p-5">
          <h2 className="text-lg font-black text-foreground mb-2">الضمان</h2>
          <p>كل اشتراك مضمون طول مدته المتفق عليها. لو حصل أي مشكلة (توقّف الحساب، تغيير كلمة السر) هيتم استبداله فورًا أو رد المبلغ.</p>
        </section>
        <section className="glow-card rounded-2xl p-5">
          <h2 className="text-lg font-black text-foreground mb-2">شروط الاستبدال</h2>
          <ul className="space-y-2 list-disc list-inside">
            <li>الإبلاغ عن المشكلة خلال 24 ساعة من حدوثها</li>
            <li>عدم مشاركة الحساب مع أشخاص خارج العدد المتفق عليه</li>
            <li>عدم تغيير بيانات الحساب من قِبل المشتري</li>
          </ul>
        </section>
        <section className="glow-card rounded-2xl p-5">
          <h2 className="text-lg font-black text-foreground mb-2">استرداد المبلغ</h2>
          <p>يمكن استرداد المبلغ كامل خلال 48 ساعة من الشراء إذا لم يتم تفعيل الاشتراك. بعد التفعيل، يتم الاستبدال بمنتج آخر أو رد رصيد في المحفظة.</p>
        </section>
      </main>
    </div>
  );
}
