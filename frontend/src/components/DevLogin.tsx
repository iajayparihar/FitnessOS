import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useAppAuth } from "../auth/auth";

export function DevLogin() {
  const { devLogin } = useAppAuth();
  const [email, setEmail] = useState("owner@example.com");
  const [firstName, setFirstName] = useState("Test");
  const [lastName, setLastName] = useState("Owner");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError(null);
    setBusy(true);
    try {
      await devLogin(email, firstName, lastName);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
      <Card sx={{ width: 380 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            FitnessOS — Dev Login
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            No Clerk key configured, so this mints a local dev token. Same email = same
            user each time.
          </Typography>
          <Stack spacing={2}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              label="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              size="small"
            />
            <Stack direction="row" spacing={1}>
              <TextField
                label="First name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                size="small"
                fullWidth
              />
              <TextField
                label="Last name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                size="small"
                fullWidth
              />
            </Stack>
            <Button variant="contained" onClick={submit} disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
