ALTER FUNCTION public.has_role(uuid, public.app_role) SECURITY INVOKER;
REVOKE EXECUTE ON FUNCTION public.claim_admin_if_none() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.claim_admin_if_none() FROM anon;
REVOKE EXECUTE ON FUNCTION public.claim_admin_if_none() FROM authenticated;
GRANT EXECUTE ON FUNCTION public.claim_admin_if_none() TO service_role;