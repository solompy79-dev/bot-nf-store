import { supabase as cloudClient } from "@/integrations/supabase/client";
import { isLocalAuth, localAuth } from "./local-auth";
// Only the explicitly enabled local development server uses local accounts.
export const supabase = new Proxy(cloudClient, {
  get(target, key) {
    if (isLocalAuth && key === "auth") return localAuth;
    return Reflect.get(target, key);
  },
});
