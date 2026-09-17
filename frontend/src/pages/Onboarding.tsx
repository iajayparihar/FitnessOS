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
import { api } from "../api/client";

export function Onboarding({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("Acme Gym");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError(null);
    setBusy(true);
    const res = await api("/auth/onboarding", {
      method: "POST",
      body: { organization: { name } },
    });
    setBusy(false);
    if (res.ok) onDone();
    else setError(JSON.stringify(res.error));
  };

  return (
    <Box sx={{ display: "grid", placeItems: "center", mt: 8 }}>
      <Card sx={{ width: 420 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Create your organization
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            You're signed in but not part of an organization yet. Creating one makes you
            its owner (full RBAC permissions).
          </Typography>
          <Stack spacing={2}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              label="Organization name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              size="small"
            />
            <Button variant="contained" onClick={submit} disabled={busy}>
              {busy ? "Creating…" : "Create organization"}
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
