import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { supabase } from "@/lib/auth-client";
import { listFavorites, toggleFavorite } from "@/lib/features.functions";
import { ArrowLeft, Heart } from "lucide-react";

export const Route = createFileRoute("/favorites")({
  component: FavoritesPage,
  head: () => ({
    meta: [
      { title: "المفضلة — اشتراكي بلس" },
      { name: "description", content: "الاشتراكات اللي حفظتها في المفضلة عشان ترجعلها بسرعة." },
      { property: "og:title", content: "المفضلة — اشتراكي بلس" },
      { property: "og:description", content: "قائمة الاشتراكات المفضلة الخاصة بك." },
      { name: "robots", content: "noindex" },
    ],
  }),
});

function FavoritesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setAuthed(!!data.user);
      if (!data.user) navigate({ to: "/auth" });
    });
  }, [navigate]);

  const listFn = useServerFn(listFavorites);
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["favorites"],
    queryFn: () => listFn(),
    enabled: !!authed,
  });
  const toggleFn = useServerFn(toggleFavorite);
  const toggleMut = useMutation({
    mutationFn: (productId: string) => toggleFn({ data: { productId } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorites"] }),
  });

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-background/70 border-b border-border">
        <div className="max-w-3xl mx-auto px-4 h-14 flex items-center gap-3">
          <Link to="/" className="p-2 rounded-lg hover:bg-card"><ArrowLeft className="size-5" /></Link>
          <h1 className="text-lg font-black">المفضلة</h1>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 pb-28">
        {isLoading ? (
          <div className="text-center text-muted-foreground py-20">جاري التحميل...</div>
        ) : items.length === 0 ? (
          <div className="text-center py-20">
            <Heart className="size-16 mx-auto text-muted-foreground/50 mb-4" />
            <div className="text-lg font-bold mb-2">لا توجد منتجات مفضلة</div>
            <Link to="/" className="inline-block mt-4 px-6 py-2.5 rounded-xl font-black text-primary-foreground"
                  style={{ background: "var(--gradient-hero)" }}>تصفح المنتجات</Link>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {items.map((it) => {
              const p = it.products;
              if (!p) return null;
              return (
                <div key={it.id} className="glow-card rounded-2xl p-4 relative">
                  <button onClick={() => toggleMut.mutate(it.product_id)}
                          className="absolute top-2 start-2 p-1.5 rounded-full bg-background/70 hover:bg-destructive/20">
                    <Heart className="size-4 fill-destructive text-destructive" />
                  </button>
                  <Link to="/s/$slug" params={{ slug: p.slug }} className="block text-center">
                    <div className="size-14 rounded-xl grid place-items-center text-white font-black shrink-0 mx-auto mb-2 overflow-hidden"
                         style={{ background: p.color || "linear-gradient(135deg,#8b5cf6,#4c1d95)" }}>
                      {p.image_url ? <img src={p.image_url} alt={p.name} className="w-full h-full object-cover" /> :
                       p.logo_slug ? <img src={`https://cdn.simpleicons.org/${p.logo_slug}/white`} alt="" className="w-8 h-8" /> :
                       <span>{p.initials}</span>}
                    </div>
                    <div className="font-bold text-sm truncate">{p.name}</div>
                    <div className="text-xs text-muted-foreground truncate">{p.tagline}</div>
                    <div className="mt-2 text-sm font-black gradient-text">{p.price} <span className="text-xs">ج.م</span></div>
                  </Link>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
