import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { supabase } from "@/lib/auth-client";
import { listMyTickets, createTicket, getTicket, replyTicket } from "@/lib/features.functions";
import { toast } from "sonner";
import { ArrowLeft, Plus, Send, MessageCircle } from "lucide-react";

export const Route = createFileRoute("/support")({
  component: SupportPage,
  head: () => ({
    meta: [
      { title: "الدعم الفني — اشتراكي بلس" },
      { name: "description", content: "تواصل مع فريق الدعم الفني لاشتراكي بلس لحل مشاكلك والاستفسار عن خدماتنا وتذاكر الدعم." },
      { property: "og:title", content: "الدعم الفني — اشتراكي بلس" },
      { property: "og:description", content: "افتح تذكرة دعم فني وتابع ردود فريق اشتراكي بلس." },
      { name: "robots", content: "noindex" },
    ],
  }),
});

function SupportPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setAuthed(!!data.user);
      if (!data.user) navigate({ to: "/auth" });
    });
  }, [navigate]);

  const listFn = useServerFn(listMyTickets);
  const createFn = useServerFn(createTicket);
  const getFn = useServerFn(getTicket);
  const replyFn = useServerFn(replyTicket);

  const { data: tickets = [] } = useQuery({
    queryKey: ["tickets"], queryFn: () => listFn(), enabled: !!authed,
  });
  const { data: detail } = useQuery({
    queryKey: ["ticket", openId],
    queryFn: () => getFn({ data: { id: openId! } }),
    enabled: !!openId,
  });

  const createMut = useMutation({
    mutationFn: () => createFn({ data: { subject, message } }),
    onSuccess: (r) => {
      toast.success("تم إنشاء التذكرة");
      qc.invalidateQueries({ queryKey: ["tickets"] });
      setCreating(false); setSubject(""); setMessage("");
      setOpenId(r.id);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const [reply, setReply] = useState("");
  const replyMut = useMutation({
    mutationFn: () => replyFn({ data: { ticketId: openId!, message: reply } }),
    onSuccess: () => {
      setReply("");
      qc.invalidateQueries({ queryKey: ["ticket", openId] });
      qc.invalidateQueries({ queryKey: ["tickets"] });
    },
  });

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-background/70 border-b border-border">
        <div className="max-w-3xl mx-auto px-4 h-14 flex items-center gap-3">
          {openId ? (
            <button onClick={() => setOpenId(null)} aria-label="الرجوع" className="p-2 rounded-lg hover:bg-card"><ArrowLeft className="size-5" /></button>
          ) : (
            <Link to="/" aria-label="الرجوع للرئيسية" className="p-2 rounded-lg hover:bg-card"><ArrowLeft className="size-5" /></Link>
          )}
          <h1 className="text-lg font-black flex-1">{openId ? (detail?.ticket?.subject ?? "تذكرة") : "الدعم الفني"}</h1>
          {!openId && !creating && (
            <button onClick={() => setCreating(true)}
                    className="px-3 py-1.5 rounded-lg text-sm font-black text-primary-foreground flex items-center gap-1"
                    style={{ background: "var(--gradient-hero)" }}>
              <Plus className="size-4" /> جديد
            </button>
          )}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 pb-32">
        {creating ? (
          <div className="glow-card rounded-2xl p-5 space-y-3">
            <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="عنوان المشكلة"
                   className="w-full px-4 py-2.5 rounded-xl bg-background border border-border" />
            <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={5} placeholder="اشرح المشكلة بالتفصيل"
                      className="w-full px-4 py-2.5 rounded-xl bg-background border border-border" />
            <div className="flex gap-2">
              <button onClick={() => setCreating(false)} className="flex-1 py-2.5 rounded-xl font-bold border border-border">إلغاء</button>
              <button onClick={() => createMut.mutate()} disabled={createMut.isPending || subject.length < 3 || message.length < 3}
                      className="flex-1 py-2.5 rounded-xl font-black text-primary-foreground disabled:opacity-50"
                      style={{ background: "var(--gradient-hero)" }}>
                {createMut.isPending ? "..." : "إرسال"}
              </button>
            </div>
          </div>
        ) : openId && detail ? (
          <div className="space-y-3">
            <div className="space-y-2 mb-4">
              {detail.messages.map((m) => (
                <div key={m.id} className={`rounded-2xl p-3 max-w-[85%] ${m.is_staff ? "bg-card mr-auto" : "text-primary-foreground ml-auto"}`}
                     style={!m.is_staff ? { background: "var(--gradient-hero)" } : {}}>
                  <div className="text-xs opacity-70 mb-1">{m.is_staff ? "الدعم" : "أنت"}</div>
                  <div className="text-sm whitespace-pre-wrap">{m.message}</div>
                </div>
              ))}
            </div>
            <div className="fixed bottom-24 inset-x-0 px-4">
              <div className="max-w-3xl mx-auto flex gap-2 glow-card rounded-2xl p-2">
                <input value={reply} onChange={(e) => setReply(e.target.value)}
                       placeholder="اكتب ردك..."
                       className="flex-1 px-3 py-2 rounded-xl bg-background border border-border" />
                <button onClick={() => reply.trim() && replyMut.mutate()} disabled={replyMut.isPending || !reply.trim()}
                        aria-label="إرسال الرد"
                        className="px-4 rounded-xl text-primary-foreground disabled:opacity-50"
                        style={{ background: "var(--gradient-hero)" }}>
                  <Send className="size-4" />
                </button>
              </div>
            </div>
          </div>
        ) : tickets.length === 0 ? (
          <div className="text-center py-20">
            <MessageCircle className="size-16 mx-auto text-muted-foreground/50 mb-4" />
            <div className="text-lg font-bold mb-2">لا توجد تذاكر</div>
            <button onClick={() => setCreating(true)}
                    className="mt-4 px-6 py-2.5 rounded-xl font-black text-primary-foreground"
                    style={{ background: "var(--gradient-hero)" }}>
              فتح تذكرة جديدة
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {tickets.map((t) => (
              <button key={t.id} onClick={() => setOpenId(t.id)}
                      className="w-full text-right glow-card rounded-2xl p-4 hover:bg-card/60 transition">
                <div className="flex items-center justify-between mb-1">
                  <div className="font-bold truncate">{t.subject}</div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                    t.status === "open" ? "bg-primary/20 text-primary" :
                    t.status === "closed" ? "bg-muted text-muted-foreground" : "bg-yellow-500/20 text-yellow-500"
                  }`}>
                    {t.status === "open" ? "مفتوحة" : t.status === "closed" ? "مغلقة" : "قيد المعالجة"}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground">{new Date(t.updated_at).toLocaleString("ar-EG")}</div>
              </button>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
