import type { Product } from "./products";

export const brandLogoUrl = "/images/brand/ishtiraki-plus-logo-v1.webp";

const services: Array<[string, RegExp]> = [
  ["youtube", /youtube|yotube|يوتيوب/iu],
  ["netflix", /netflix|نتفليكس/iu],
  ["spotify", /spotify|سبوتفاي/iu],
  ["shahid", /shahid|شاهد/iu],
  ["lovable", /lovable|لوفابل/iu],
  ["linkedin", /linked\s*in|لينكد/iu],
  ["expressvpn", /express\s*vpn/iu],
  ["prime", /amazon|prime\s*video/iu],
  ["crunchyroll", /crunchyroll/iu],
  ["icloud", /icloud/iu],
  ["snapchat", /snapchat/iu],
  ["discord", /discord/iu],
  ["xbox", /xbox/iu],
  ["microsoft", /microsoft|office\s*365/iu],
  ["applemusic", /apple\s*music/iu],
  ["canva", /canva/iu],
  ["chatgpt", /chatgpt|openai|gpt\s*plus/iu],
  ["watchit", /watch\s*it/iu],
  ["gemini", /gemini/iu],
  ["max", /ishtiraki\s*max|ishtraki\s*max|اشتراكي\s*ماكس/iu],
  ["adobe", /adobe/iu],
  ["disney", /disney/iu],
  ["anghami", /anghami|أنغامي|انغامي/iu],
  ["osn", /osn/iu],
];

export function withProductArtwork<T extends Product>(product: T): T {
  const identity = product.slug + " " + product.name;
  const service = services.find(([, pattern]) => pattern.test(identity))?.[0];
  return service ? { ...product, imageUrl: "/images/subscriptions/" + service + "-v1.webp" } : product;
}
