
CREATE TABLE public.free_services (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL UNIQUE,
  name text NOT NULL,
  description text,
  image_url text,
  logo_slug text,
  color text NOT NULL DEFAULT 'linear-gradient(135deg,#8b5cf6,#4c1d95)',
  initials text NOT NULL DEFAULT '',
  delivery_type text NOT NULL CHECK (delivery_type IN ('link','stock')),
  link_url text,
  active boolean NOT NULL DEFAULT true,
  sort_order int NOT NULL DEFAULT 100,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON public.free_services TO anon, authenticated;
GRANT ALL ON public.free_services TO service_role;
ALTER TABLE public.free_services ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read active free services" ON public.free_services
  FOR SELECT USING (active = true);

CREATE TABLE public.free_service_stock (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  service_id uuid NOT NULL REFERENCES public.free_services(id) ON DELETE CASCADE,
  content text NOT NULL,
  claimed_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  claimed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT ALL ON public.free_service_stock TO service_role;
ALTER TABLE public.free_service_stock ENABLE ROW LEVEL SECURITY;
CREATE INDEX free_service_stock_avail_idx
  ON public.free_service_stock (service_id) WHERE claimed_by IS NULL;

CREATE TABLE public.free_service_claims (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  service_id uuid NOT NULL REFERENCES public.free_services(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  delivered_content text NOT NULL,
  delivery_type text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (service_id, user_id)
);
GRANT SELECT ON public.free_service_claims TO authenticated;
GRANT ALL ON public.free_service_claims TO service_role;
ALTER TABLE public.free_service_claims ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users read own claims" ON public.free_service_claims
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

CREATE TRIGGER free_services_updated_at
  BEFORE UPDATE ON public.free_services
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
