export type Product = {
  slug: string;
  name: string;
  tagline: string;
  initials: string;
  color: string;
  logoSlug?: string;
  imageUrl?: string;
  duration: string;
  price: number;
  badge?: string;
  description?: string;
  features?: string[];
};

export const products: Product[] = [
  { slug: "netflix", name: "Netflix Premium", tagline: "4K UHD · شاشتين", initials: "N",
    color: "linear-gradient(135deg,#e50914,#831010)", logoSlug: "netflix",
    duration: "شهر", price: 150, badge: "الأكثر طلباً",
    description: "اشتراك Netflix Premium أصلي بجودة 4K UHD وHDR على كل الأجهزة.",
    features: ["جودة 4K UHD + HDR", "تشغيل على شاشتين", "تحميل الأفلام أوفلاين", "كل الأفلام والمسلسلات"] },
  { slug: "spotify", name: "Spotify Premium", tagline: "بدون إعلانات · تحميل", initials: "S",
    color: "linear-gradient(135deg,#1db954,#0a5c2a)", logoSlug: "spotify",
    duration: "شهر", price: 90,
    description: "استمع لأي أغنية بدون إعلانات وحمّلها للسماع أوفلاين.",
    features: ["بدون إعلانات نهائي", "تحميل للسماع أوفلاين", "جودة صوت عالية", "تخطي غير محدود"] },
  { slug: "shahid", name: "Shahid VIP", tagline: "مسلسلات ورمضان", initials: "ش",
    color: "linear-gradient(135deg,#7b2cbf,#3c096c)",
    duration: "شهر", price: 120,
    description: "أقوى مسلسلات ومسرحيات MBC ومسلسلات رمضان أول بأول.",
    features: ["كل مسلسلات MBC", "مسلسلات رمضان حصرية", "بدون إعلانات", "جودة HD"] },
  { slug: "disney-plus", name: "Disney+", tagline: "أفلام Marvel و Star Wars", initials: "D",
    color: "linear-gradient(135deg,#0e63be,#0a2472)", logoSlug: "disneyplus",
    duration: "شهر", price: 130,
    description: "عالم Disney وMarvel وStar Wars وNational Geographic في مكان واحد.",
    features: ["أفلام Marvel كاملة", "Star Wars الأصلي", "كرتون Disney وPixar", "جودة 4K"] },
  { slug: "youtube", name: "YouTube Premium", tagline: "بدون إعلانات + Music", initials: "Y",
    color: "linear-gradient(135deg,#ff0000,#7a0000)", logoSlug: "youtube",
    duration: "شهر", price: 100,
    description: "يوتيوب بدون إعلانات + YouTube Music + تشغيل في الخلفية.",
    features: ["بدون إعلانات", "YouTube Music", "تشغيل في الخلفية", "تحميل الفيديوهات"] },
  { slug: "chatgpt", name: "ChatGPT Plus", tagline: "GPT-4 · وصول أسرع", initials: "AI",
    color: "linear-gradient(135deg,#10a37f,#064e3b)", logoSlug: "openai",
    duration: "شهر", price: 480, badge: "جديد",
    description: "وصول لأقوى موديلات GPT-4 وأدوات ChatGPT المتقدمة.",
    features: ["GPT-4 و GPT-4o", "وصول أسرع دايمًا", "أولوية في الميزات الجديدة", "أدوات متقدمة"] },
  { slug: "anghami", name: "Anghami Plus", tagline: "موسيقى عربية بجودة عالية", initials: "A",
    color: "linear-gradient(135deg,#8a2be2,#4b0082)", logoSlug: "anghami",
    duration: "شهر", price: 70,
    description: "أكبر مكتبة موسيقى عربية بدون إعلانات وبجودة عالية.",
    features: ["موسيقى عربية كاملة", "بدون إعلانات", "تحميل أوفلاين", "جودة صوت عالية"] },
  { slug: "osn", name: "OSN+", tagline: "أحدث الأفلام والمسلسلات", initials: "O",
    color: "linear-gradient(135deg,#f59e0b,#78350f)",
    duration: "شهر", price: 140,
    description: "أحدث أفلام هوليوود ومسلسلات HBO حصريًا على OSN+.",
    features: ["أفلام هوليوود جديدة", "مسلسلات HBO", "ترجمة عربية", "جودة 4K"] },
];

export function getProduct(slug: string) {
  return products.find((p) => p.slug === slug);
}
