import type { Session, User, AuthChangeEvent } from "@supabase/supabase-js";
export const isLocalAuth = import.meta.env.DEV && import.meta.env.VITE_LOCAL_AUTH === "true";

export async function localRequest<T = unknown>(action: string, body?: unknown): Promise<T> {
  const response = await fetch("/api/local-auth/" + action, { method: body === undefined ? "GET" : "POST", credentials: "same-origin", headers: body === undefined ? {} : { "Content-Type": "application/json" }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  const data = await response.json();
  if (!response.ok) throw Object.assign(new Error(data.message || "تعذّر الاتصال بالخادم المحلي"), { code: data.code });
  return data as T;
}

const listeners = new Set<(event: AuthChangeEvent, session: Session | null) => void>();
function notify(event: AuthChangeEvent, session: Session | null) { listeners.forEach(fn => fn(event, session)); }
const failure = (error: unknown) => ({ data: { session: null, user: null }, error: error instanceof Error ? error : new Error("تعذّر تسجيل الدخول") });
async function authenticate(action: string, body: unknown) {
  try { const data = await localRequest<{ session: Session; user: User }>(action, body); notify("SIGNED_IN", data.session); return { data, error: null }; }
  catch (error) { return failure(error); }
}
export const localAuth = {
  async getSession() {
    if (typeof window === "undefined") return { data: { session: null }, error: null };
    try { return { data: await localRequest<{ session: Session | null }>("session"), error: null }; }
    catch (error) { return { data: { session: null }, error }; }
  },
  async getUser() { const { data, error } = await localAuth.getSession(); return { data: { user: data.session?.user ?? null }, error }; },
  signInWithPassword: (data: { email: string; password: string }) => authenticate("signin", data),
  signUp: (data: { email: string; password: string; options?: { data?: Record<string, unknown> } }) => authenticate("signup", { email: data.email, password: data.password, ...data.options?.data }),
  async signOut() { try { await localRequest("signout", {}); notify("SIGNED_OUT", null); return { error: null }; } catch(error) { return { error }; } },
  async updateUser(data: { password: string; current_password?: string }) {
    try { return { data: await localRequest("password", data), error: null }; } catch (error) { return failure(error); }
  },
  onAuthStateChange(callback: (event: AuthChangeEvent, session: Session | null) => void) {
    listeners.add(callback);
    void localAuth.getSession().then(({ data }) => { if (listeners.has(callback)) callback("INITIAL_SESSION", data.session); });
    return { data: { subscription: { unsubscribe: () => listeners.delete(callback) } } };
  },
};
