// Owner-Entscheid 28.09.2026 (#99, #112): "Rueckgaengig" ist gesperrt, wenn
// `undo_data.account_id` kein lebendes Konto mehr ist — mit Grund. Der
// Server lehnt das schon ab (`errors.account_gone`); die Oberflaeche bietet
// den Knopf dann gar nicht erst an.
//
// Alle Daten erfunden; das Repo ist oeffentlich.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import SyncPanel from "./SyncPanel";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

function eintrag(id: string, accountId: string) {
  return {
    id,
    timestamp: "2026-01-01T00:00:00+00:00",
    action: "sync_names",
    details: `Eintrag ${id}`,
    status: "success" as const,
    undo_data: { account_id: accountId, person_id: "p1", previous_name: "Alt" },
  };
}

const { logMock, accountsMock } = vi.hoisted(() => ({
  logMock: vi.fn(),
  accountsMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    sync: { log: logMock, clearLog: vi.fn(), undo: vi.fn() },
    accounts: { list: accountsMock },
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
});

async function rendern() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <LanguageProvider>
        <SyncPanel />
      </LanguageProvider>
    </QueryClientProvider>
  );
  await waitFor(() => expect(screen.queryAllByRole("row").length).toBeGreaterThan(1));
}

describe("SyncPanel: Rueckgaengig-Sperre bei totem Konto", () => {
  it("sperrt Rueckgaengig, wenn das Konto nicht mehr lebt", async () => {
    logMock.mockResolvedValue([eintrag("log-1", "konto-tot")]);
    accountsMock.mockResolvedValue([{ id: "konto-lebt", name: "Lebt", color: "#111" }]);

    await rendern();

    expect(screen.queryByRole("button", { name: /Rückgängig/i })).toBeNull();
    expect(screen.getByText(/Rückgängig gesperrt/i)).toBeTruthy();
  });

  it("bietet Rueckgaengig an, wenn das Konto lebt", async () => {
    logMock.mockResolvedValue([eintrag("log-2", "konto-lebt")]);
    accountsMock.mockResolvedValue([{ id: "konto-lebt", name: "Lebt", color: "#111" }]);

    await rendern();

    expect(screen.getByRole("button", { name: /Rückgängig/i })).toBeTruthy();
    expect(screen.queryByText(/Rückgängig gesperrt/i)).toBeNull();
  });
});
