import { kindMeta } from "../../lib/kinds";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { MapPin } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { VenueCover } from "../../components/VenueCover";
import { money } from "../../lib/format";
import { Button } from "../../components/Button";
import { EmptyState, ErrorState, Skeleton } from "../../components/States";
import { PageHeader, SampleTag } from "../../components/ui";
import { api, extractErrorMessage } from "../../lib/api";
import type { Page, Specialization, VenueKind, VenueSummary } from "../../types";

const COPY: Record<VenueKind, { title: string; description: string; search: string }> = {
  HOSPITAL: { title: "Hospitals", description: "Book a consultation with a doctor and get a queue token for your visit.",
    search: "Search by hospital name or area" },
  SHOP: { title: "Shops", description: "Salons, repair desks and consultations that take appointments.",
    search: "Search by shop, service type or area" },
  HOTEL: { title: "Hotels", description: "Check room availability and reserve with the price calculated upfront.",
    search: "Search by hotel name or area" },
};

export default function VenueList({ kind }: { kind: VenueKind }) {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";
  const city = params.get("city") || "";
  const specialization = params.get("specialization") || "";
  const [draft, setDraft] = useState(q);
  const [cities, setCities] = useState<string[]>([]);
  const [specs, setSpecs] = useState<Specialization[]>([]);
  const [page, setPage] = useState<Page<VenueSummary> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const copy = COPY[kind];

  useEffect(() => {
    api.get<string[]>("/api/venues/cities", { params: { kind } }).then((r) => setCities(r.data)).catch(() => setCities([]));
    if (kind === "HOSPITAL") api.get<Specialization[]>("/api/specializations").then((r) => setSpecs(r.data)).catch(() => setSpecs([]));
  }, [kind]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (draft !== q) setParams((p) => { if (draft) p.set("q", draft); else p.delete("q"); return p; }, { replace: true });
    }, 300);
    return () => clearTimeout(t);
  }, [draft, q, setParams]);

  useEffect(() => {
    const controller = new AbortController();
    setPage(null);
    setError(null);
    api.get<Page<VenueSummary>>("/api/venues", { signal: controller.signal, params: {
      kind, q: q || undefined, city: city || undefined, specialization: specialization || undefined, limit: 12 } })
      .then((r) => setPage(r.data))
      .catch((e) => !controller.signal.aborted && setError(extractErrorMessage(e)));
    return () => controller.abort();
  }, [kind, q, city, specialization]);

  async function loadMore() {
    if (!page) return;
    setLoadingMore(true);
    try {
      const { data } = await api.get<Page<VenueSummary>>("/api/venues", { params: {
        kind, q: q || undefined, city: city || undefined, specialization: specialization || undefined,
        limit: 12, offset: page.items.length } });
      setPage({ ...data, items: [...page.items, ...data.items] });
    } catch (e) {
      setError(extractErrorMessage(e));
    } finally {
      setLoadingMore(false);
    }
  }

  const setFilter = (key: string, value: string) =>
    setParams((p) => { if (value) p.set(key, value); else p.delete(key); return p; }, { replace: true });
  const meta = kindMeta[kind];

  return (
    <AppShell>
      <PageHeader title={copy.title} description={copy.description} />
      <div className="mb-6 flex flex-col gap-3 sm:flex-row">
        <label className="sr-only" htmlFor="venue-search">{copy.search}</label>
        <input id="venue-search" type="search" className="field sm:max-w-md" placeholder={copy.search}
          value={draft} onChange={(e) => setDraft(e.target.value)} />
        <label className="sr-only" htmlFor="venue-city">City</label>
        <select id="venue-city" className="field sm:w-48" value={city} onChange={(e) => setFilter("city", e.target.value)}>
          <option value="">All cities</option>
          {cities.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      {kind === "HOSPITAL" && specs.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2" role="group" aria-label="Filter by specialization">
          {[{ slug: "", name: "All specializations" }, ...specs].map((s) => (
            <button key={s.slug} onClick={() => setFilter("specialization", s.slug)} aria-pressed={specialization === s.slug}
              className={`rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${specialization === s.slug
                ? "border-care-600 bg-care-50 text-care-600" : "border-ink-200 bg-white text-ink-600 hover:border-ink-400"}`}>
              {s.name}
            </button>
          ))}
        </div>
      )}
      {error && <ErrorState message={error} />}
      {!page && !error && (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-72 rounded-2xl" />)}</div>
      )}
      {page && page.items.length === 0 && (
        <EmptyState title={`No ${copy.title.toLowerCase()} match your search`}
          body="Try another name, clear the city filter, or check back once more places are added."
          action={(q || city || specialization) ? <Button variant="secondary" onClick={() => { setDraft(""); setParams({}); }}>Clear filters</Button> : undefined} />
      )}
      {page && page.items.length > 0 && (
        <>
          <p className="mb-3 text-sm text-ink-500">{page.total} {page.total === 1 ? meta.label.toLowerCase() : copy.title.toLowerCase()}</p>
          <ul className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {page.items.map((v) => (
              <li key={v.id}>
                <Link to={`/venues/${v.id}`} className="surface group flex h-full flex-col overflow-hidden rounded-2xl transition-shadow hover:shadow-lg focus-visible:outline-2">
                  <VenueCover name={v.name} kind={v.kind} className="h-32" />
                  <div className="flex flex-1 flex-col gap-3 p-5">
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <h2 className="text-base font-semibold leading-snug text-ink-900 group-hover:underline">{v.name}</h2>
                        {v.is_sample && <SampleTag />}
                      </div>
                      <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-500">
                        <MapPin aria-hidden className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{[v.address, v.city].filter(Boolean).join(", ")}</span>
                      </p>
                    </div>
                    {!!v.highlights?.length && (
                      <ul className="flex flex-wrap gap-1.5" aria-label={kind === "HOTEL" ? "Room types" : kind === "HOSPITAL" ? "Specializations" : "Services"}>
                        {v.highlights.map((h) => (
                          <li key={h} className={`rounded-md px-2 py-0.5 text-xs font-medium ${meta.tint} ${meta.text}`}>{h}</li>
                        ))}
                      </ul>
                    )}
                    {v.service_count === undefined ? (
                      <p className="line-clamp-2 text-sm text-ink-600">{v.description}</p>
                    ) : null}
                    <div className="mt-auto flex items-end justify-between gap-3 border-t border-ink-100 pt-3 text-sm">
                      <span className="text-ink-500">
                        {v.service_count === undefined ? (kind === "HOTEL" ? "Check rooms" : "View services") : kind === "HOTEL"
                          ? `${v.service_count} room type${v.service_count === 1 ? "" : "s"}`
                          : `${v.service_count} service${v.service_count === 1 ? "" : "s"}, ${v.provider_count} ${kind === "HOSPITAL" ? "doctor" : "staff"}${v.provider_count === 1 || kind === "SHOP" ? "" : "s"}`}
                      </span>
                      {v.starting_price != null && (
                        <span className="text-right">
                          <span className="block text-[11px] text-ink-400">{kind === "HOTEL" ? "per night from" : "from"}</span>
                          <span className="font-display font-semibold text-ink-900">{money(v.starting_price, v.currency)}</span>
                        </span>
                      )}
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          {page.items.length < page.total && (
            <div className="mt-6 flex justify-center">
              <Button variant="secondary" onClick={() => void loadMore()} loading={loadingMore}>Show more</Button>
            </div>
          )}
        </>
      )}
    </AppShell>
  );
}
