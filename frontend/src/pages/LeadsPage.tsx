import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { api } from "../api/client";

type LeadSource = { id: string; name: string; channel?: string | null };
type Lead = {
  id: string;
  status: string;
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  source_id?: string | null;
  lost_reason?: string | null;
};
type Meta = { page: number; page_size: number; total: number; total_pages: number };
type FollowUp = {
  id: string;
  type: string;
  scheduled_at: string;
  completed_at?: string | null;
  outcome?: string | null;
};

const FOLLOW_UP_TYPES = ["call", "visit", "email", "whatsapp", "sms"];
const STATUS_COLORS: Record<string, "default" | "success" | "error" | "warning"> = {
  new: "default",
  converted: "success",
  lost: "error",
};

export function LeadsPage() {
  const [sources, setSources] = useState<LeadSource[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");

  const [sourceName, setSourceName] = useState("Walk-in");
  const [lead, setLead] = useState({ first_name: "", last_name: "", email: "", phone: "" });
  const [followLead, setFollowLead] = useState<Lead | null>(null);

  const loadSources = useCallback(async () => {
    const res = await api<{ data: LeadSource[] }>("/crm/lead-sources");
    if (res.ok) setSources(res.data!.data);
  }, []);

  const loadLeads = useCallback(async () => {
    const q = new URLSearchParams({ page: String(page), page_size: "10" });
    if (statusFilter) q.set("status", statusFilter);
    const res = await api<{ data: Lead[]; meta: Meta }>(`/crm/leads?${q.toString()}`);
    if (res.ok) {
      setLeads(res.data!.data);
      setMeta(res.data!.meta);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    loadSources();
  }, [loadSources]);
  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  const createSource = async () => {
    if (!sourceName.trim()) return;
    await api("/crm/lead-sources", { method: "POST", body: { name: sourceName } });
    setSourceName("");
    loadSources();
  };

  const createLead = async () => {
    await api("/crm/leads", {
      method: "POST",
      body: {
        first_name: lead.first_name || null,
        last_name: lead.last_name || null,
        email: lead.email || null,
        phone: lead.phone || null,
        source_id: sources[0]?.id ?? null,
      },
    });
    setLead({ first_name: "", last_name: "", email: "", phone: "" });
    loadLeads();
  };

  const convert = async (id: string) => {
    await api(`/crm/leads/${id}/convert`, { method: "POST", body: {} });
    loadLeads();
  };

  const markLost = async (id: string) => {
    const reason = window.prompt("Lost reason?", "Too expensive");
    if (!reason) return;
    await api(`/crm/leads/${id}/lost`, { method: "POST", body: { lost_reason: reason } });
    loadLeads();
  };

  return (
    <Stack spacing={3}>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          Lead sources
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          {sources.map((s) => (
            <Chip key={s.id} label={s.name} />
          ))}
          {sources.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              None yet.
            </Typography>
          )}
        </Stack>
        <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
          <TextField
            size="small"
            label="New source"
            value={sourceName}
            onChange={(e) => setSourceName(e.target.value)}
          />
          <Button variant="outlined" onClick={createSource}>
            Add source
          </Button>
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          Create lead
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {(["first_name", "last_name", "email", "phone"] as const).map((f) => (
            <TextField
              key={f}
              size="small"
              label={f.replace("_", " ")}
              value={lead[f]}
              onChange={(e) => setLead({ ...lead, [f]: e.target.value })}
            />
          ))}
          <Button variant="contained" onClick={createLead}>
            Add lead
          </Button>
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="subtitle1">Leads</Typography>
          <TextField
            select
            size="small"
            label="Status"
            value={statusFilter}
            onChange={(e) => {
              setPage(1);
              setStatusFilter(e.target.value);
            }}
            sx={{ minWidth: 160 }}
          >
            <MenuItem value="">All</MenuItem>
            {["new", "contacted", "trial", "follow_up", "negotiating", "converted", "lost"].map(
              (s) => (
                <MenuItem key={s} value={s}>
                  {s}
                </MenuItem>
              ),
            )}
          </TextField>
        </Stack>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {leads.map((l) => (
              <TableRow key={l.id}>
                <TableCell>{[l.first_name, l.last_name].filter(Boolean).join(" ") || "—"}</TableCell>
                <TableCell>{l.email || "—"}</TableCell>
                <TableCell>
                  <Chip size="small" label={l.status} color={STATUS_COLORS[l.status] ?? "default"} />
                </TableCell>
                <TableCell align="right">
                  <Button size="small" onClick={() => setFollowLead(l)}>
                    Follow-ups
                  </Button>
                  <Button size="small" onClick={() => convert(l.id)} disabled={l.status === "converted"}>
                    Convert
                  </Button>
                  <Button
                    size="small"
                    color="error"
                    onClick={() => markLost(l.id)}
                    disabled={l.status === "converted" || l.status === "lost"}
                  >
                    Lost
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {leads.length === 0 && (
              <TableRow>
                <TableCell colSpan={4}>
                  <Typography variant="body2" color="text.secondary">
                    No leads yet.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        {meta && (
          <Stack direction="row" spacing={2} alignItems="center" justifyContent="flex-end" sx={{ mt: 1 }}>
            <Typography variant="caption">
              Page {meta.page} / {Math.max(meta.total_pages, 1)} · {meta.total} total
            </Typography>
            <IconButton size="small" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              ‹
            </IconButton>
            <IconButton
              size="small"
              disabled={page >= meta.total_pages}
              onClick={() => setPage((p) => p + 1)}
            >
              ›
            </IconButton>
          </Stack>
        )}
      </Paper>

      {followLead && (
        <FollowUpsDialog lead={followLead} onClose={() => setFollowLead(null)} />
      )}
    </Stack>
  );
}

function FollowUpsDialog({ lead, onClose }: { lead: Lead; onClose: () => void }) {
  const [items, setItems] = useState<FollowUp[]>([]);
  const [type, setType] = useState("call");
  const [when, setWhen] = useState("");

  const load = useCallback(async () => {
    const res = await api<{ data: FollowUp[] }>(`/crm/leads/${lead.id}/follow-ups`);
    if (res.ok) setItems(res.data!.data);
  }, [lead.id]);

  useEffect(() => {
    load();
  }, [load]);

  const create = async () => {
    const scheduled = when ? new Date(when).toISOString() : new Date().toISOString();
    await api(`/crm/leads/${lead.id}/follow-ups`, {
      method: "POST",
      body: { type, scheduled_at: scheduled },
    });
    setWhen("");
    load();
  };

  const complete = async (id: string) => {
    await api(`/crm/follow-ups/${id}/complete`, {
      method: "POST",
      body: { outcome: "Done" },
    });
    load();
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Follow-ups</DialogTitle>
      <DialogContent dividers>
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <TextField select size="small" label="Type" value={type} onChange={(e) => setType(e.target.value)} sx={{ minWidth: 120 }}>
            {FOLLOW_UP_TYPES.map((t) => (
              <MenuItem key={t} value={t}>
                {t}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            size="small"
            type="datetime-local"
            label="When"
            InputLabelProps={{ shrink: true }}
            value={when}
            onChange={(e) => setWhen(e.target.value)}
          />
          <Button variant="contained" onClick={create}>
            Schedule
          </Button>
        </Stack>
        <Divider />
        <Table size="small">
          <TableBody>
            {items.map((f) => (
              <TableRow key={f.id}>
                <TableCell>{f.type}</TableCell>
                <TableCell>{new Date(f.scheduled_at).toLocaleString()}</TableCell>
                <TableCell>
                  {f.completed_at ? <Chip size="small" color="success" label="done" /> : "pending"}
                </TableCell>
                <TableCell align="right">
                  <Button size="small" disabled={!!f.completed_at} onClick={() => complete(f.id)}>
                    Complete
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {items.length === 0 && (
              <TableRow>
                <TableCell>
                  <Typography variant="body2" color="text.secondary">
                    No follow-ups.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
