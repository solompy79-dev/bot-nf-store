
CREATE TABLE public.products (
  id uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  slug text NOT NULL UNIQUE,
  name text NOT NULL,
  tagline text NOT NULL DEFAULT '',
  initials text NOT NULL DEFAULT '',
  color text NOT NULL DEFAULT 'linear-gradient(135deg,#8b5cf6,#4c1d95)',
  logo_slug text,
  duration text NOT NULL DEFAULT 'شهر',
  price numeric NOT NULL DEFAULT 0,
  badge text,
  description text,
  features jsonb NOT NULL DEFAULT '[]'::jsonb,
  sort_order integer NOT NULL DEFAULT 0,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

GRANT SELECT ON public.products TO anon, authenticated;
GRANT ALL ON public.products TO service_role;

ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anyone reads active products"
  ON public.products FOR SELECT
  USING (active = true);

CREATE TRIGGER update_products_updated_at
  BEFORE UPDATE ON public.products
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

INSERT INTO public.products (slug, name, tagline, initials, color, logo_slug, duration, price, badge, description, features, sort_order) VALUES
('netflix', 'Netflix Premium', '4K UHD · شاشتين', 'N', 'linear-gradient(135deg,#e50914,#831010)', 'netflix', 'شهر', 150, 'الأكثر طلباً',
  'اشتراك Netflix Premium أصلي بجودة 4K UHD وHDR على كل الأجهزة.',
  '["جودة 4K UHD + HDR","تشغيل على شاشتين","تحميل الأفلام أوفلاين","كل الأفلام والمسلسلات"]'::jsonb, 1),
('spotify', 'Spotify Premium', 'بدون إعلانات · تحميل', 'S', 'linear-gradient(135deg,#1db954,#0a5c2a)', 'spotify', 'شهر', 90, NULL,
  'استمع لأي أغنية بدون إعلانات وحمّلها للسماع أوفلاين.',
  '["بدون إعلانات نهائي","تحميل للسماع أوفلاين","جودة صوت عالية","تخطي غير محدود"]'::jsonb, 2),
('shahid', 'Shahid VIP', 'مسلسلات ورمضان', 'ش', 'linear-gradient(135deg,#7b2cbf,#3c096c)', NULL, 'شهر', 120, NULL,
  'أقوى مسلسلات ومسرحيات MBC ومسلسلات رمضان أول بأول.',
  '["كل مسلسلات MBC","مسلسلات رمضان حصرية","بدون إعلانات","جودة HD"]'::jsonb, 3),
('disney-plus', 'Disney+', 'أفلام Marvel و Star Wars', 'D', 'linear-gradient(135deg,#0e63be,#0a2472)', 'disneyplus', 'شهر', 130, NULL,
  'عالم Disney وMarvel وStar Wars وNational Geographic في مكان واحد.',
  '["أفلام Marvel كاملة","Star Wars الأصلي","كرتون Disney وPixar","جودة 4K"]'::jsonb, 4),
('youtube', 'YouTube Premium', 'بدون إعلانات + Music', 'Y', 'linear-gradient(135deg,#ff0000,#7a0000)', 'youtube', 'شهر', 100, NULL,
  'يوتيوب بدون إعلانات + YouTube Music + تشغيل في الخلفية.',
  '["بدون إعلانات","YouTube Music","تشغيل في الخلفية","تحميل الفيديوهات"]'::jsonb, 5),
('chatgpt', 'ChatGPT Plus', 'GPT-4 · وصول أسرع', 'AI', 'linear-gradient(135deg,#10a37f,#064e3b)', 'openai', 'شهر', 480, 'جديد',
  'وصول لأقوى موديلات GPT-4 وأدوات ChatGPT المتقدمة.',
  '["GPT-4 و GPT-4o","وصول أسرع دايمًا","أولوية في الميزات الجديدة","أدوات متقدمة"]'::jsonb, 6),
('anghami', 'Anghami Plus', 'موسيقى عربية بجودة عالية', 'A', 'linear-gradient(135deg,#8a2be2,#4b0082)', 'anghami', 'شهر', 70, NULL,
  'أكبر مكتبة موسيقى عربية بدون إعلانات وبجودة عالية.',
  '["موسيقى عربية كاملة","بدون إعلانات","تحميل أوفلاين","جودة صوت عالية"]'::jsonb, 7),
('osn', 'OSN+', 'أحدث الأفلام والمسلسلات', 'O', 'linear-gradient(135deg,#f59e0b,#78350f)', NULL, 'شهر', 140, NULL,
  'أحدث أفلام هوليوود ومسلسلات HBO حصريًا على OSN+.',
  '["أفلام هوليوود جديدة","مسلسلات HBO","ترجمة عربية","جودة 4K"]'::jsonb, 8);
