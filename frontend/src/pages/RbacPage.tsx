import { useEffect, useState } from "react";
import { Chip, Paper, Stack, Typography } from "@mui/material";
import { api } from "../api/client";

type Permission = { id: string; code: string; category: string };
type Role = { id: string; name: string; slug: string; is_system: boolean };

export function RbacPage() {
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);

  useEffect(() => {
    api<{ data: Permission[] }>("/rbac/permissions").then((r) => {
      if (r.ok) setPermissions(r.data!.data);
    });
    api<{ data: Role[] }>("/rbac/roles").then((r) => {
      if (r.ok) setRoles(r.data!.data);
    });
  }, []);

  return (
    <Stack spacing={3}>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          Your roles
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {roles.map((r) => (
            <Chip key={r.id} label={r.name} color={r.is_system ? "secondary" : "primary"} />
          ))}
          {roles.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              None visible.
            </Typography>
          )}
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          Permissions ({permissions.length})
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {permissions.map((p) => (
            <Chip key={p.id} size="small" label={p.code} variant="outlined" />
          ))}
        </Stack>
      </Paper>
    </Stack>
  );
}
