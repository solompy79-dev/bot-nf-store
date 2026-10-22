GRANT EXECUTE ON FUNCTION public.has_role(uuid, public.app_role) TO authenticated;
GRANT EXECUTE ON FUNCTION public.claim_admin_if_none() TO authenticated;
GRANT EXECUTE ON FUNCTION public.credit_wallet(uuid, numeric) TO service_role;
GRANT EXECUTE ON FUNCTION public.debit_wallet(uuid, numeric) TO service_role;