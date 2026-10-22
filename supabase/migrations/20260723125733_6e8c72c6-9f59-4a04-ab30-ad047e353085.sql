
CREATE TABLE public.wallet_topups (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  amount numeric(10,2) NOT NULL CHECK (amount > 0),
  sender_phone text,
  receipt_url text,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','verified','rejected')),
  notes text,
  detected_amount numeric(10,2),
  detected_phone text,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT ON public.wallet_topups TO authenticated;
GRANT ALL ON public.wallet_topups TO service_role;
ALTER TABLE public.wallet_topups ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users read own topups" ON public.wallet_topups FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "users insert own topups" ON public.wallet_topups FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

-- Atomic wallet debit helper (checks + decrements balance in one shot)
CREATE OR REPLACE FUNCTION public.debit_wallet(_user_id uuid, _amount numeric)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  updated int;
BEGIN
  UPDATE public.profiles
     SET wallet_balance = wallet_balance - _amount
   WHERE id = _user_id AND wallet_balance >= _amount;
  GET DIAGNOSTICS updated = ROW_COUNT;
  RETURN updated > 0;
END;
$$;

CREATE OR REPLACE FUNCTION public.credit_wallet(_user_id uuid, _amount numeric)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  UPDATE public.profiles SET wallet_balance = wallet_balance + _amount WHERE id = _user_id;
$$;
