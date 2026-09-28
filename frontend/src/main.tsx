import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { applyDocumentLang, LanguageProvider, readStoredLang } from "./i18n";
import AuthGate from "./components/AuthGate";
import { erzeugeAppQueryClient } from "./queryClient";
import "./index.css";

// Die Vorgaben (retry, staleTime) liegen in `queryClient.ts` — die einzige
// Quelle, die auch produktionsnahe Tests teilen (#110, Nacharbeit 2, Fund 2).
const queryClient = erzeugeAppQueryClient();

// Set <html lang> from the persisted/browser language before the first
// render, not after it — `index.html` ships hardcoded `lang="de"`, and
// without this line every non-German visitor's first frame (and anything
// that reads the attribute before React commits, e.g. a screen reader or
// the browser's own translate prompt) would report German regardless of the
// language the app is about to render in.
applyDocumentLang(readStoredLang());

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <LanguageProvider>
      <AuthGate>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </AuthGate>
    </LanguageProvider>
  </React.StrictMode>
);
