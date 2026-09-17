import { useEffect, useRef, useState } from "react";
import { Box, Chip, Paper, Stack, Typography } from "@mui/material";
import { onApiResult, type ApiLogEntry } from "../api/client";

export function ResponsePanel() {
  const [entries, setEntries] = useState<ApiLogEntry[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    return onApiResult((entry) => setEntries((prev) => [...prev.slice(-30), entry]));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  return (
    <Paper variant="outlined" sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Typography variant="subtitle2" sx={{ p: 1.5, borderBottom: "1px solid #eee" }}>
        API responses
      </Typography>
      <Box sx={{ flex: 1, overflow: "auto", p: 1.5, fontFamily: "monospace", fontSize: 12 }}>
        {entries.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            Interactions with the backend appear here.
          </Typography>
        )}
        <Stack spacing={1.5}>
          {entries.map((e, i) => (
            <Box key={i}>
              <Stack direction="row" spacing={1} alignItems="center">
                <Chip
                  size="small"
                  label={e.status || "ERR"}
                  color={e.ok ? "success" : "error"}
                />
                <Typography variant="caption" sx={{ fontFamily: "monospace" }}>
                  {e.method} {e.path}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {e.at}
                </Typography>
              </Stack>
              <Box
                component="pre"
                sx={{ m: 0, mt: 0.5, whiteSpace: "pre-wrap", wordBreak: "break-word" }}
              >
                {JSON.stringify(e.body, null, 2)}
              </Box>
            </Box>
          ))}
          <div ref={endRef} />
        </Stack>
      </Box>
    </Paper>
  );
}
