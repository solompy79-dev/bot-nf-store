REVOKE ALL ON public.profiles FROM anon;
REVOKE ALL ON public.wallet_topups FROM anon;
REVOKE ALL ON public.user_roles FROM anon;
REVOKE ALL ON public.free_service_stock FROM anon;

GRANT SELECT, INSERT, UPDATE ON public.profiles TO authenticated;
GRANT ALL ON public.profiles TO service_role;
GRANT SELECT, INSERT ON public.wallet_topups TO authenticated;
GRANT ALL ON public.wallet_topups TO service_role;
GRANT SELECT ON public.user_roles TO authenticated;
GRANT ALL ON public.user_roles TO service_role;