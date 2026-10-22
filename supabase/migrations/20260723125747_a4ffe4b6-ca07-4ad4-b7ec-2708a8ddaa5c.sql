
REVOKE ALL ON FUNCTION public.debit_wallet(uuid, numeric) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.credit_wallet(uuid, numeric) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.debit_wallet(uuid, numeric) TO service_role;
GRANT EXECUTE ON FUNCTION public.credit_wallet(uuid, numeric) TO service_role;
