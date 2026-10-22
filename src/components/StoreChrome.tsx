import { Link } from "@tanstack/react-router";
import { Bell, Bot, ShoppingBag, ShoppingCart, Store, UserRound } from "lucide-react";
import { isLocalAuth } from "@/lib/local-auth";
import { brandLogoUrl } from "@/lib/product-artwork";

export function StoreHeader({ page = "المتجر" }: { page?: string }) {
  return <header className="store-header"><div className="store-header-inner">
    <Link to="/" className="store-brand" aria-label="اشتراكي بلس — الرئيسية"><span><img src={brandLogoUrl} alt="اشتراكي بلس" width={150} height={50} className="store-logo" /><small>{page}{isLocalAuth ? " · حسابات محلية" : ""}</small></span></Link>
    <div className="store-header-actions"><span className="language-pill">عربي</span><Link to="/cart" className="header-pill" aria-label="سلة المشتريات"><ShoppingCart size={16} /><span>السلة</span></Link><Link to="/notifications" className="notification-button" aria-label="الإشعارات"><Bell size={16} /></Link></div>
  </div></header>;
}

export function StoreBottomNav({ active }: { active: "store" | "account" }) {
  const items = [
    { id: "store", to: "/", label: "المتجر", Icon: Store },
    { id: "orders", to: "/orders", label: "طلباتي", Icon: ShoppingBag },
    { id: "cart", to: "/cart", label: "السلة", Icon: ShoppingCart },
    { id: "account", to: "/account", label: "حسابي", Icon: UserRound },
  ] as const;
  return <nav className="store-bottom-nav" aria-label="التنقل الرئيسي">{items.map(({ id, to, label, Icon }) => <Link key={id} to={to} className={active === id ? "is-active" : ""} aria-current={active === id ? "page" : undefined}><Icon size={22} /><span>{label}</span></Link>)}</nav>;
}
