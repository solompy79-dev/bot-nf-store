import { ExternalLink, AlertTriangle } from "lucide-react";

const CHATGPT_LINK = "https://chatgpt.com/?promo_campaign=plus-1-month-free#pricing/";
const ADOBE_LINK =
  "https://commerce.adobe.com/store/checkout?items%5B0%5D%5Bid%5D=D0440AB0F2F7F2F2CB39657F45BC5D56&items%5B0%5D%5Bq%5D=1&rrItems%5B0%5D%5Bid%5D=D0440AB0F2F7F2F2CB39657F45BC5D56&cli=creative&co=US&lang=en&sdid=WT7FHSB9&mv=affiliate&ss=commitment";

export function isChatGpt(slug?: string | null, name?: string | null) {
  const s = `${slug ?? ""} ${name ?? ""}`.toLowerCase();
  return s.includes("chatgpt");
}

export function isAdobe(slug?: string | null, name?: string | null) {
  const s = `${slug ?? ""} ${name ?? ""}`.toLowerCase();
  return s.includes("adobe");
}

function DeliveryCard({
  title,
  step,
  link,
  warning,
}: {
  title: string;
  step: string;
  link: string;
  warning: string;
}) {
  return (
    <div className="mt-3 rounded-2xl border border-primary/40 bg-primary/10 p-4 text-right text-sm space-y-3">
      <div className="font-black">{title}</div>
      <div>{step}</div>
      <a
        href={link}
        target="_blank"
        rel="noopener noreferrer"
        dir="ltr"
        className="flex items-center justify-center gap-2 rounded-xl py-3 font-bold text-primary-foreground break-all"
        style={{ background: "var(--gradient-hero)" }}
      >
        <ExternalLink className="size-4 shrink-0" /> فتح رابط التفعيل
      </a>
      <div dir="ltr" className="text-xs text-muted-foreground break-all select-all">
        {link}
      </div>
      <div className="flex gap-2 text-xs text-muted-foreground">
        <AlertTriangle className="size-4 text-primary shrink-0" />
        <span>{warning}</span>
      </div>
    </div>
  );
}

export function InstantDelivery({ slug, name }: { slug?: string | null; name?: string | null }) {
  if (isChatGpt(slug, name)) {
    return (
      <DeliveryCard
        title="ChatGPT Plus اشتراك شهري"
        step="✅ ادخل الرابط واختر ChatGPT Plus:"
        link={CHATGPT_LINK}
        warning="استخدم بطاقة خالية من الرصيد حتى لا يتم الخصم لتجديد الاشتراك وتأكد من إلغاء التجديد التلقائي."
      />
    );
  }
  if (isAdobe(slug, name)) {
    return (
      <DeliveryCard
        title="Adobe Creative Cloud اشتراك شهري"
        step="✅ ادخل الرابط وأكمل تفعيل اشتراك Adobe Creative Cloud:"
        link={ADOBE_LINK}
        warning="استخدم بطاقة خالية من الرصيد حتى لا يتم الخصم لتجديد الاشتراك وتأكد من إلغاء التجديد التلقائي."
      />
    );
  }
  return null;
}
