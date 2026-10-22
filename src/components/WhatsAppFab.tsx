import { useLocation } from "@tanstack/react-router";
import { MessageCircle } from "lucide-react";

const WA_URL = "https://wsend.co/201101560023";
const TG_URL = "https://t.me/T8TS8";

export function WhatsAppFab() {
  const { pathname } = useLocation();
  if (pathname === "/" || pathname === "/account") {
    return <a href={WA_URL} target="_blank" rel="noreferrer" aria-label="تواصل مع الدعم على واتساب" className="store-support-fab"><MessageCircle size={22} /></a>;
  }
  return (
    <div className="fixed bottom-28 sm:bottom-24 end-3 sm:end-4 z-[60] flex flex-col items-end gap-2.5">
      <a
        href={TG_URL}
        target="_blank"
        rel="noreferrer"
        aria-label="تواصل عبر تلجرام"
        className="size-12 sm:size-14 rounded-full grid place-items-center shadow-2xl hover:scale-110 active:scale-95 transition-transform"
        style={{
          background: "#0088cc",
          boxShadow: "0 10px 30px -5px rgba(0,136,204,0.55)",
        }}
      >
        <img
          src="https://cdn.simpleicons.org/telegram/white"
          alt=""
          aria-hidden
          className="relative size-6 sm:size-7"
        />
      </a>

      <a
        href={WA_URL}
        target="_blank"
        rel="noreferrer"
        aria-label="تواصل عبر واتساب"
        className="size-12 sm:size-14 rounded-full grid place-items-center shadow-2xl hover:scale-110 active:scale-95 transition-transform"
        style={{
          background: "#25d366",
          boxShadow: "0 10px 30px -5px rgba(37,211,102,0.6)",
        }}
      >
        <span aria-hidden className="absolute rounded-full animate-ping opacity-40 pointer-events-none size-12 sm:size-14"
              style={{ background: "#25d366" }} />
        <img
          src="https://cdn.simpleicons.org/whatsapp/white"
          alt=""
          aria-hidden
          className="relative size-6 sm:size-7"
        />
      </a>
    </div>
  );
}
