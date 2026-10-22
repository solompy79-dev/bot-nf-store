import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { supabase } from "@/lib/auth-client";
import { listMyNotifications, markAllNotificationsRead, markNotificationRead } from "@/lib/features.functions";
import { ArrowLeft, Bell, CheckCheck } from "lucide-react";

export const Route = createFileRoute("/notifications")({
  component: NotificationsPage,
  head: () => ({
    meta: [
      { title: "الإشعارات — اشتراكي بلس" },
      { name: "description", content: "آخر إشعاراتك عن الطلبات، العروض والاشتراكات." },
      { property: "og:title", content: "الإشعارات — اشتراكي بلس" },
      { property: "og:description", content: "تابع آخر الإشعارات الخاصة بحسابك." },
      { name: "robots", content: "noindex" },
    ],
  }),
});

function NotificationsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setAuthed(!!data.user);
      if (!data.user) navigate({ to: "/auth" });
    });
  }, [navigate]);

  const listFn = useServerFn(listMyNotifications);
  const markAllFn = useServerFn(markAllNotificationsRead);
  const markFn = useServerFn(markNotificationRead);

  const { data: notifications = [] } = useQuery({
    queryKey: ["notifications"], queryFn: () => listFn(), enabled: !!authed,
  });
  const markAllMut = useMutation({
    mutationFn: () => markAllFn(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const markMut = useMutation({
    mutationFn: (id: string) => markFn({ data: { id } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-background/70 border-b border-border">
        <div className="max-w-3xl mx-auto px-4 h-14 flex items-center gap-3">
          <Link to="/" className="p-2 rounded-lg hover:bg-card"><ArrowLeft className="size-5" /></Link>
          <h1 className="text-lg font-black flex-1">الإشعارات</h1>
          {notifications.some((n) => !n.read) && (
            <button onClick={() => markAllMut.mutate()} className="text-xs font-bold text-primary flex items-center gap-1">
              <CheckCheck className="size-4" /> تعليم الكل
            </button>
          )}
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 py-6 pb-28 space-y-2">
        {notifications.length === 0 ? (
          <div className="text-center py-20">
            <Bell className="size-16 mx-auto text-muted-foreground/50 mb-4" />
            <div className="text-lg font-bold">لا توجد إشعارات</div>
          </div>
        ) : notifications.map((n) => (
          <button key={n.id} onClick={() => !n.read && markMut.mutate(n.id)}
                  className={`w-full text-right rounded-2xl p-4 transition ${n.read ? "bg-card/40" : "glow-card"}`}>
            <div className="flex items-start gap-3">
              {!n.read && <span className="size-2 rounded-full bg-primary mt-2 shrink-0" />}
              <div className="flex-1 min-w-0">
                <div className="font-bold text-sm mb-1">{n.title}</div>
                {n.body && <div className="text-xs text-muted-foreground">{n.body}</div>}
                <div className="text-[10px] text-muted-foreground/70 mt-2">{new Date(n.created_at).toLocaleString("ar-EG")}</div>
              </div>
            </div>
          </button>
        ))}
      </main>
    </div>
  );
}
