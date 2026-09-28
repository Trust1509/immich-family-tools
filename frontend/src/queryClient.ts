import { QueryClient, type QueryClientConfig } from "@tanstack/react-query";

/**
 * Die EINE Quelle fuer die App-weiten React-Query-Vorgaben. `main.tsx` und
 * jeder Test, der produktionsnahes Cache-Verhalten pruefen will (insbesondere
 * `staleTime`), teilen sich diese Konstante.
 *
 * Zwei Kopien derselben Zahl waren der Fehler, nicht die Loesung (#110,
 * Nacharbeit 2, Fund 2, Blindpruefer): Die Testsuite baute bisher einen
 * eigenen Client OHNE `staleTime` — TanStacks eigener Bibliotheks-Standard
 * ist ebenfalls 0, also verhielt sich der Test-Client zufaellig genauso wie
 * ein `staleTime: 0`-Client, ohne das je zu erzwingen. Damit bewies keine
 * einzige Probe, dass GruppenWahls eigenes `staleTime: 0` (siehe dort) gegen
 * die ECHTEN 30 Sekunden aus dieser Datei etwas austraegt: Ein Mutationslauf,
 * der `staleTime: 0` entfernte, blieb unter dem alten (staleTime-losen)
 * Test-Client gruen.
 */
export const QUERY_VORGABEN: NonNullable<QueryClientConfig["defaultOptions"]>["queries"] = {
  retry: 1,
  staleTime: 30_000,
};

/** Der Produktions-Client — `main.tsx` ruft NUR das hier auf, damit es
 *  wirklich eine einzige Quelle bleibt statt einer zweiten Kopie der Zahlen. */
export function erzeugeAppQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: QUERY_VORGABEN } });
}
