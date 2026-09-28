// Nacharbeit 1 (Fremd- und Gegenpruefer, #99/#112): Ein geloeschtes Konto
// veraendert die Albumliste (Markierung, gesperrtes Umbenennen) und das
// Sync-Log (gesperrtes Rueckgaengig) — beide muessen nach dem Loeschen
// erneut geladen werden, nicht erst nach ihrer eigenen `staleTime`.
//
// Alle Daten erfunden; das Repo ist oeffentlich.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import AccountManager from "./AccountManager";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

const { listMock, removeMock, statusMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  removeMock: vi.fn(),
  statusMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    accounts: {
      list: listMock,
      remove: removeMock,
      status: statusMock,
      add: vi.fn(),
      update: vi.fn(),
    },
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  listMock.mockResolvedValue([
    { id: "k1", name: "Oma Resi", immich_url: "http://x.invalid", color: "#111", user_id: "u" },
  ]);
  removeMock.mockResolvedValue(undefined);
  // Nie aufloesend: der Verbindungsstatus ist fuer diesen Test irrelevant,
  // eine haengende Promise haelt ihn aus dem Weg.
  statusMock.mockReturnValue(new Promise(() => {}));
  window.confirm = () => true;
});

it("invalidiert managed-albums und sync-log, nachdem ein Konto geloescht wurde", async () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(["managed-albums"], [{ id: "a", owner_account_id: "k1" }]);
  qc.setQueryData(["sync-log"], []);

  render(
    <QueryClientProvider client={qc}>
      <LanguageProvider>
        <AccountManager />
      </LanguageProvider>
    </QueryClientProvider>
  );
  await waitFor(() => expect(screen.getAllByText("Oma Resi").length).toBeGreaterThan(0));

  const knoepfe = screen.getAllByRole("button");
  const loeschen = knoepfe.find((b) =>
    /entfernen|remove|l[öo]sch/i.test(
      (b.getAttribute("title") ?? "") + (b.getAttribute("aria-label") ?? "") + b.textContent
    )
  );
  expect(loeschen).toBeTruthy();
  fireEvent.click(loeschen!);

  await waitFor(() => expect(removeMock).toHaveBeenCalledWith("k1"));
  await waitFor(() => {
    expect(qc.getQueryState(["managed-albums"])?.isInvalidated).toBe(true);
    expect(qc.getQueryState(["sync-log"])?.isInvalidated).toBe(true);
  });
});
