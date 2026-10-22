import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/wallet")({
  beforeLoad: () => { throw redirect({ to: "/" }); },
  head: () => ({ meta: [
    { title: "الدفع المباشر — اشتراكي بلس" },
    { name: "description", content: "ادفع ثمن طلبك مباشرة في اشتراكي بلس." },
    { property: "og:title", content: "الدفع المباشر — اشتراكي بلس" },
    { property: "og:description", content: "دفع الطلبات مباشرة بدون شحن رصيد." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
    { name: "robots", content: "noindex" },
  ] }),
});
