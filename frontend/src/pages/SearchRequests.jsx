import React from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useInfiniteQuery } from "@tanstack/react-query";
import { ListChecks, PlusCircle, Search, FlaskConical } from "lucide-react";
import { api, qs } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import RequestListItem from "@/components/RequestListItem";
import { ErrorBlock, LoadingBlock } from "@/components/PageState";
import { useAuth } from "@/lib/AuthContext";
import { useDebounced } from "@/lib/useDebounced";

const STATUS_OPTIONS = [
  "All", "New", "Searching", "Formula found", "No formula found", "Draft created",
  "Pending pharmacist approval", "Requires correction", "Approved", "Rejected", "Error",
];
const PAGE = 30;

export default function SearchRequests() {
  const { canPrepare } = useAuth();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = React.useState(params.get("q") || "");
  const status = params.get("status") || "All";
  const q = useDebounced(query.trim());

  const { data, isLoading, error, refetch, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ["requests", q, status],
    queryFn: ({ pageParam }) =>
      api.get(`/api/requests${qs({ q, status: status === "All" ? "" : status, limit: PAGE, offset: pageParam })}`),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, p) => n + p.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
  });
  const items = data?.pages.flatMap((p) => p.items) || [];
  const total = data?.pages[0]?.total ?? 0;

  const setStatus = (value) => {
    const next = new URLSearchParams(params);
    if (value === "All") next.delete("status");
    else next.set("status", value);
    setParams(next, { replace: true });
  };

  return (
    <div className="p-4 sm:p-6 md:p-10 max-w-6xl mx-auto">
      <div className="flex items-center justify-between gap-4 mb-5 sm:mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-teal-50 flex items-center justify-center">
            <ListChecks className="w-5 h-5 text-teal-600" />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-semibold text-slate-900">Search Requests</h1>
            <p className="text-sm text-slate-500">{total} request{total === 1 ? "" : "s"}</p>
          </div>
        </div>
        {canPrepare && (
          <Link to="/new-search">
            <Button className="bg-teal-600 hover:bg-teal-700 h-10">
              <PlusCircle className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">New Search</span>
            </Button>
          </Link>
        )}
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            type="search"
            placeholder="Ingredient, dosage form or request number…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9 h-11 text-base"
          />
        </div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-full sm:w-60 h-11">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((s) => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        {isLoading ? (
          <LoadingBlock />
        ) : error ? (
          <ErrorBlock error={error} onRetry={refetch} />
        ) : items.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
              <FlaskConical className="w-6 h-6 text-slate-400" />
            </div>
            <p className="text-slate-600 font-medium">{q || status !== "All" ? "No matching requests" : "No requests yet"}</p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((req) => (
              <RequestListItem key={req.id} req={req} />
            ))}
          </ul>
        )}
      </div>
      {hasNextPage && (
        <div className="mt-4 flex justify-center">
          <Button variant="outline" onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
            {isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        </div>
      )}
    </div>
  );
}
