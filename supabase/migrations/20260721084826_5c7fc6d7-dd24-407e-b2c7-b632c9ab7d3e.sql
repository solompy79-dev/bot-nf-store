-- Restrict coupon reads: remove broad authenticated SELECT; keep admin manage.
DROP POLICY IF EXISTS "authenticated read active coupons" ON public.coupons;

-- Lock down privilege-escalation function: only service_role may execute.
REVOKE EXECUTE ON FUNCTION public.claim_admin_if_none() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.claim_admin_if_none() FROM anon;
REVOKE EXECUTE ON FUNCTION public.claim_admin_if_none() FROM authenticated;
GRANT EXECUTE ON FUNCTION public.claim_admin_if_none() TO service_role;