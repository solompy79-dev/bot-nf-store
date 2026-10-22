GRANT SELECT ON public.user_roles TO authenticated;
REVOKE ALL ON public.free_service_stock FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.free_service_stock TO authenticated;
GRANT ALL ON public.free_service_stock TO service_role;

CREATE POLICY "admins manage free service stock"
ON public.free_service_stock
FOR ALL
TO authenticated
USING (public.has_role(auth.uid(), 'admin'))
WITH CHECK (public.has_role(auth.uid(), 'admin'));