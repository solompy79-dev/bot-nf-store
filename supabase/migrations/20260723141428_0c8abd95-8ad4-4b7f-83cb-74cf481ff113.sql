
-- Credit previously-rejected topups that were actually paid, and mark them verified
DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN SELECT id, user_id, amount FROM public.wallet_topups WHERE status = 'rejected' LOOP
    INSERT INTO public.profiles (id, wallet_balance)
    VALUES (r.user_id, r.amount)
    ON CONFLICT (id) DO UPDATE SET wallet_balance = COALESCE(public.profiles.wallet_balance, 0) + r.amount;

    UPDATE public.wallet_topups SET status = 'verified' WHERE id = r.id;
  END LOOP;
END $$;
