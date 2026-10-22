CREATE OR REPLACE FUNCTION public.credit_wallet(_user_id uuid, _amount numeric)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  ref_code text;
BEGIN
  ref_code := upper(substring(md5(_user_id::text || random()::text) from 1 for 8));
  INSERT INTO public.profiles (id, wallet_balance, referral_code)
  VALUES (_user_id, _amount, ref_code)
  ON CONFLICT (id) DO UPDATE
    SET wallet_balance = public.profiles.wallet_balance + EXCLUDED.wallet_balance;
END;
$$;