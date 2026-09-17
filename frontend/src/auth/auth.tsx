import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  ClerkProvider,
  SignedIn,
  SignedOut,
  SignIn,
  UserButton,
  useAuth as useClerkAuth,
  useUser,
} from "@clerk/clerk-react";
import { api, setTokenGetter } from "../api/client";

const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
const CLERK_TEMPLATE = import.meta.env.VITE_CLERK_JWT_TEMPLATE;
export const authMode: "clerk" | "dev" = CLERK_KEY ? "clerk" : "dev";

type AuthContextValue = {
  mode: "clerk" | "dev";
  isSignedIn: boolean;
  email: string | null;
  devLogin: (email: string, firstName?: string, lastName?: string) => Promise<void>;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAppAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAppAuth must be used within AppAuthProvider");
  return ctx;
}

// --- dev mode ------------------------------------------------------------------

function DevAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("dev_token"),
  );
  const [email, setEmail] = useState<string | null>(() =>
    localStorage.getItem("dev_email"),
  );

  useEffect(() => {
    setTokenGetter(async () => token);
  }, [token]);

  const devLogin = async (mail: string, firstName?: string, lastName?: string) => {
    const res = await api<{ data: { access_token: string } }>("/auth/dev/login", {
      method: "POST",
      body: { email: mail, first_name: firstName, last_name: lastName },
    });
    if (!res.ok) throw new Error("Dev login failed (is DEV_AUTH_ENABLED set?)");
    const t = res.data!.data.access_token;
    localStorage.setItem("dev_token", t);
    localStorage.setItem("dev_email", mail);
    setToken(t);
    setEmail(mail);
  };

  const signOut = () => {
    localStorage.removeItem("dev_token");
    localStorage.removeItem("dev_email");
    setToken(null);
    setEmail(null);
  };

  return (
    <AuthContext.Provider
      value={{ mode: "dev", isSignedIn: !!token, email, devLogin, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// --- clerk mode ----------------------------------------------------------------

function ClerkBridge({ children }: { children: ReactNode }) {
  const { getToken, isSignedIn, signOut } = useClerkAuth();
  const { user } = useUser();

  useEffect(() => {
    setTokenGetter(async () =>
      isSignedIn
        ? await getToken(CLERK_TEMPLATE ? { template: CLERK_TEMPLATE } : undefined)
        : null,
    );
  }, [isSignedIn, getToken]);

  return (
    <AuthContext.Provider
      value={{
        mode: "clerk",
        isSignedIn: !!isSignedIn,
        email: user?.primaryEmailAddress?.emailAddress ?? null,
        devLogin: async () => {},
        signOut: () => signOut(),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function ClerkUserButton() {
  return <UserButton />;
}

export function AppAuthProvider({ children }: { children: ReactNode }) {
  if (authMode === "clerk") {
    return (
      <ClerkProvider publishableKey={CLERK_KEY!}>
        <SignedOut>
          <div style={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
            <SignIn routing="hash" />
          </div>
        </SignedOut>
        <SignedIn>
          <ClerkBridge>{children}</ClerkBridge>
        </SignedIn>
      </ClerkProvider>
    );
  }
  return <DevAuthProvider>{children}</DevAuthProvider>;
}
