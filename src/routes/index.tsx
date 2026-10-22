import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArrowUpLeft, Search, ShieldCheck, Sparkles } from "lucide-react";
import { useProducts } from "@/lib/products-hooks";
import type { Product } from "@/lib/products";
import { StoreHeader, StoreBottomNav } from "@/components/StoreChrome";
import { brandLogoUrl } from "@/lib/product-artwork";

export const Route = createFileRoute("/")({
  head: () => ({ meta: [
    { title: "اشتراكي بلس | متجر الاشتراكات الرقمية" },
    { name: "description", content: "اكتشف اشتراكاتك الرقمية المفضلة بأسعار مميزة، دفع آمن ودعم عربي." },
    { property: "og:title", content: "اشتراكي بلس | متجر الاشتراكات الرقمية" },
    { property: "og:description", content: "اشتراكاتك المفضلة بأسعار مميزة ودعم عربي." },
  ] }),
  component: StorePage,
});

function ProductArt({ product }: { product: Product }) {
  const [failed, setFailed] = useState(false);
  return <div className="product-art" style={{ background: product.color }}>
    <span className="art-orbit art-orbit-one" /><span className="art-orbit art-orbit-two" />
    {product.imageUrl ? <img src={product.imageUrl} alt={product.name} loading="lazy" /> : <>
      {product.logoSlug && !failed ? <img className="brand-symbol" src={`https://cdn.simpleicons.org/${product.logoSlug}/white`} alt="" onError={() => setFailed(true)} loading="lazy" /> : <span className="brand-initials">{product.initials}</span>}
      <span className="art-product-name" dir="auto">{product.name}</span>
    </>}
    {product.badge && <span className="product-badge"><Sparkles size={9} />{product.badge}</span>}
  </div>;
}

function StorePage() {
  const products = useProducts();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [slide, setSlide] = useState(0);
  const featured = products.slice(0, 4);
  const current = featured[slide % (featured.length || 1)];
  useEffect(() => {
    const timer = window.setInterval(() => setSlide(s => s + 1), 6000);
    return () => window.clearInterval(timer);
  }, []);
  const visible = products.filter(p => `${p.name} ${p.tagline}`.toLowerCase().includes(search.toLowerCase()) && (filter === "all" || !!p.badge));
  return <div className="store-page">
    <StoreHeader />
    <main className="store-main">
      <nav className="store-top-tabs" aria-label="أقسام المتجر"><a href="#catalog" className="selected">المنتجات</a><Link to="/orders">طلباتي</Link><Link to="/faq">المساعدة</Link><Link to="/support">تواصل معنا</Link></nav>
      {current && <section className="store-spotlight branded-spotlight" aria-label="اشتراكات مميزة">
        <h1 className="sr-only">اشتراكي بلس — اشتراكاتك الرقمية المفضلة</h1>
        <img className="spotlight-product-image" src={current.imageUrl} alt={current.name} fetchPriority="high" width={960} height={540} />
        <div className="spotlight-caption"><span>{current.duration} · تفعيل سريع</span><Link to="/s/$slug" params={{ slug: current.slug }} className="blue-button">اشترك الآن · {current.price} ج.م<ArrowUpLeft size={15} /></Link></div>
        <div className="spotlight-dots">{featured.map((p, i) => <button key={p.slug} aria-label={`عرض ${p.name}`} aria-pressed={slide % featured.length === i} className={slide % featured.length === i ? "active" : ""} onClick={() => setSlide(i)} />)}</div>
      </section>}
      <section id="catalog" aria-labelledby="products-title" className="store-catalog">
        <div className="catalog-heading"><h2 id="products-title">كل المنتجات</h2><span>اشتراكات صغيرة. إمكانيات كبيرة.</span></div>
        <div className="catalog-tools"><div className="catalog-filters"><button onClick={() => setFilter("all")} className={filter === "all" ? "selected" : ""}>الكل</button><button onClick={() => setFilter("featured")} className={filter === "featured" ? "selected" : ""}>المميزة</button></div><label className="catalog-search"><Search size={15} /><input aria-label="ابحث عن اشتراك" placeholder="ابحث عن اشتراك..." value={search} onChange={e => setSearch(e.target.value)} /></label></div>
        <div className="store-product-grid">{visible.map(p => <Link to="/s/$slug" params={{ slug: p.slug }} className="store-product-card" key={p.slug}><ProductArt product={p} /><div className="product-card-copy"><span className="product-category" dir="auto">اشتراك رقمي · {p.duration}</span><h3 dir="auto">{p.name}</h3><p>{p.tagline}</p><div className="product-price-row"><strong>{p.price}<small>ج.م</small></strong><span className="duration-pill">{p.duration}</span></div></div></Link>)}</div>
        {!visible.length && <p className="catalog-empty">مفيش منتجات مطابقة لبحثك. جرّب اسم تاني.</p>}
      </section>
      <footer className="store-footer"><img className="footer-store-logo" src={brandLogoUrl} alt="اشتراكي بلس" width={180} height={60} loading="lazy" /><p>دفع آمن · دعم عربي · ضمان طوال الاشتراك</p><div><Link to="/faq">الأسئلة الشائعة</Link><Link to="/support">الدعم</Link><Link to="/refund-policy">سياسة الاسترجاع</Link></div><small>© {new Date().getFullYear()} اشتراكي بلس</small></footer>
    </main><StoreBottomNav active="store" />
  </div>;
}
