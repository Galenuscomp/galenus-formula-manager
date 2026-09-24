import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { PlusCircle, ListChecks, FlaskConical, ShieldCheck, Beaker, FileSearch, Library } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import RequestListItem from "@/components/RequestListItem";
import { ErrorBlock, LoadingBlock } from "@/components/PageState";
import { useAuth } from "@/lib/AuthContext";

export default function Home() {
  const { canPrepare, isPharmacist } = useAuth();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.get("/api/dashboard"),
  });

  const stats = [
    { label: "Total requests", value: data?.total_requests, icon: FileSearch },
    { label: "In progress", value: data?.in_progress, icon: Beaker },
    { label: "Pending approval", value: data?.pending_approval, icon: ShieldCheck, highlight: isPharmacist },
    { label: "Approved formulas", value: data?.approved_formulas, icon: Library },
  ];

  return (
    <div className="p-4 sm:p-6 md:p-10 max-w-6xl mx-auto">
      <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-teal-600 to-teal-700 p-6 sm:p-8 md:p-10 text-white">
        <div className="absolute -right-8 -top-8 w-40 h-40 rounded-full bg-white/10" />
        <div className="absolute right-16 bottom-0 w-24 h-24 rounded-full bg-white/5" />
        <div className="relative">
          <div className="flex items-center gap-2 text-teal-100 text-sm font-medium mb-3">
            <FlaskConical className="w-4 h-4" />
            Internal compounding workflow
          </div>
          <h1 className="text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight max-w-xl">
            Master Formula Manager
          </h1>
          <p className="mt-3 text-teal-50/90 max-w-lg leading-relaxed text-sm sm:text-base">
            Search compounding master formulas, store originals, build local drafts, and route them for responsible
            pharmacist approval.
          </p>
          <div className="mt-6 grid grid-cols-1 sm:flex sm:flex-wrap gap-3">
            {canPrepare && (
              <Link to="/new-search">
                <Button className="w-full sm:w-auto bg-white text-teal-700 hover:bg-teal-50 font-medium h-11">
                  <PlusCircle className="w-4 h-4 mr-2" />
                  New Formula Search
                </Button>
              </Link>
            )}
            <Link to="/requests" className="hidden sm:block">
              <Button variant="outline" className="bg-transparent border-white/40 text-white hover:bg-white/10 hover:text-white h-11">
                <ListChecks className="w-4 h-4 mr-2" />
                View Requests
              </Button>
            </Link>
            <Link to="/approved-library" className="hidden sm:block">
              <Button variant="outline" className="bg-transparent border-white/40 text-white hover:bg-white/10 hover:text-white h-11">
                <Library className="w-4 h-4 mr-2" />
                Open Approved Library
              </Button>
            </Link>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mt-4 sm:mt-6">
        {stats.map((stat) => {
          const Icon = stat.icon;
          const content = (
            <div className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5 flex items-center gap-3 sm:gap-4 h-full">
              <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-lg bg-teal-50 flex items-center justify-center shrink-0">
                <Icon className="w-5 h-5 text-teal-600" />
              </div>
              <div className="min-w-0">
                <p className="text-xl sm:text-2xl font-semibold text-slate-900">{stat.value ?? "–"}</p>
                <p className="text-xs sm:text-sm text-slate-500 leading-tight">{stat.label}</p>
              </div>
            </div>
          );
          return stat.highlight ? (
            <Link key={stat.label} to="/requests?status=Pending%20pharmacist%20approval">{content}</Link>
          ) : (
            <div key={stat.label}>{content}</div>
          );
        })}
      </div>

      <div className="mt-6 sm:mt-8">
        <div className="flex items-center justify-between mb-3 sm:mb-4">
          <h2 className="text-lg font-semibold text-slate-900">Recent searches</h2>
          <Link to="/requests" className="text-sm font-medium text-teal-700 hover:text-teal-800">
            View all →
          </Link>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
          {isLoading ? (
            <LoadingBlock />
          ) : error ? (
            <ErrorBlock error={error} onRetry={refetch} />
          ) : data.recent_requests.length === 0 ? (
            <div className="p-10 text-center">
              <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
                <FlaskConical className="w-6 h-6 text-slate-400" />
              </div>
              <p className="text-slate-600 font-medium">No searches yet</p>
              <p className="text-sm text-slate-400 mt-1">Start by submitting a new formula search request.</p>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.recent_requests.map((req) => (
                <RequestListItem key={req.id} req={req} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
