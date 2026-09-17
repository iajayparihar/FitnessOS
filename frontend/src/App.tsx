import { useCallback, useEffect, useState } from "react";
import {
  AppBar,
  Box,
  Button,
  CircularProgress,
  Container,
  Tab,
  Tabs,
  Toolbar,
  Typography,
} from "@mui/material";
import { api } from "./api/client";
import { authMode, useAppAuth } from "./auth/auth";
import { DevLogin } from "./components/DevLogin";
import { ResponsePanel } from "./components/ResponsePanel";
import { Onboarding } from "./pages/Onboarding";
import { LeadsPage } from "./pages/LeadsPage";
import { RbacPage } from "./pages/RbacPage";

type Me = { id: string; email: string; organization_id: string | null; is_superuser: boolean };

export default function App() {
  const { isSignedIn, email, signOut } = useAppAuth();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState(0);

  const loadMe = useCallback(async () => {
    setLoading(true);
    const res = await api<{ data: Me }>("/auth/me");
    setMe(res.ok ? res.data!.data : null);
    setLoading(false);
  }, []);

  useEffect(() => {
    if (isSignedIn) loadMe();
  }, [isSignedIn, loadMe]);

  if (!isSignedIn) return <DevLogin />;

  return (
    <Box>
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar sx={{ gap: 2 }}>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            FitnessOS — Testing Console
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {email} · {authMode}
          </Typography>
          <Button size="small" onClick={() => { signOut(); setMe(null); }}>
            Sign out
          </Button>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ py: 3 }}>
        {loading ? (
          <Box sx={{ display: "grid", placeItems: "center", py: 8 }}>
            <CircularProgress />
          </Box>
        ) : me && me.organization_id === null ? (
          <Onboarding onDone={loadMe} />
        ) : (
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1.4fr 1fr" }, gap: 3 }}>
            <Box>
              <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
                <Tab label="CRM · Leads" />
                <Tab label="RBAC" />
              </Tabs>
              {tab === 0 ? <LeadsPage /> : <RbacPage />}
            </Box>
            <Box sx={{ position: "sticky", top: 16, height: "calc(100vh - 120px)" }}>
              <ResponsePanel />
            </Box>
          </Box>
        )}
      </Container>
    </Box>
  );
}
