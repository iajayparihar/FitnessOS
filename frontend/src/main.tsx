import React from "react";
import ReactDOM from "react-dom/client";
import { CssBaseline, ThemeProvider } from "@mui/material";
import App from "./App";
import { AppAuthProvider } from "./auth/auth";
import { theme } from "./theme";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppAuthProvider>
        <App />
      </AppAuthProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
