import { Link } from "react-router-dom";

export default function PageNotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-slate-50">
      <div className="text-center space-y-4">
        <h1 className="text-7xl font-light text-slate-300">404</h1>
        <p className="text-slate-600">This page does not exist.</p>
        <Link to="/" className="inline-block text-sm font-medium text-teal-700 hover:underline">
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
