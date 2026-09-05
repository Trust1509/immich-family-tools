import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { applyDocumentLang, LanguageProvider, readStoredLang } from "./i18n";
import AuthGate from "./components/AuthGate";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
});

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
