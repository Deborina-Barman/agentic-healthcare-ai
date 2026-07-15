import React from "react";

const NLICE_FIELDS = [
  { key: "nature", label: "Nature" },
  { key: "location", label: "Location" },
  { key: "intensity", label: "Intensity" },
  { key: "chronology", label: "Chronology" },
  { key: "excitation", label: "Excitation" },
];

const urgencyStyles = {
  High: "border-red-200 bg-red-50 text-red-700 shadow-red-100",
  Moderate: "border-orange-200 bg-orange-50 text-orange-700 shadow-orange-100",
  Low: "border-emerald-200 bg-emerald-50 text-emerald-700 shadow-emerald-100",
};

const pulseStyles = {
  High: "bg-red-500",
  Moderate: "bg-orange-500",
  Low: "bg-emerald-500",
};

export function UrgencyBadge({ analysis }) {
  const urgency = analysis?.urgency || analysis?.urgency_label || "Low";
  const score = analysis?.score ?? analysis?.urgency_score ?? 0;
  const reason = analysis?.reason || analysis?.triage_reasoning || "Awaiting clinical signal.";

  return (
    <section className="rounded-xl border border-white/70 bg-white/70 p-5 shadow-xl shadow-slate-200/60 backdrop-blur-xl">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            Urgency
          </p>
          <div
            className={`mt-2 inline-flex items-center gap-3 rounded-full border px-4 py-2 text-sm font-bold shadow-lg ${
              urgencyStyles[urgency] || urgencyStyles.Low
            }`}
          >
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                pulseStyles[urgency] || pulseStyles.Low
              } animate-pulse`}
            />
            {urgency}
          </div>
        </div>
        <div className="text-right">
          <p className="text-3xl font-black text-slate-900">{score}</p>
          <p className="text-xs font-medium text-slate-500">/ 10 score</p>
        </div>
      </div>
      <p className="mt-4 text-sm leading-6 text-slate-600">{reason}</p>
    </section>
  );
}

export function NLICETracker({ nliceData }) {
  const data = nliceData || {};

  return (
    <section className="rounded-xl border border-white/70 bg-white/70 p-5 shadow-xl shadow-slate-200/60 backdrop-blur-xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            Live NLICE
          </p>
          <h2 className="mt-1 text-lg font-bold text-slate-900">Symptom Tracker</h2>
        </div>
        <div className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
          Synced
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {NLICE_FIELDS.map((field) => {
          const value = data[field.key];
          const hasValue = value !== undefined && value !== null && String(value).trim() !== "";

          return (
            <div
              key={field.key}
              className="min-h-28 rounded-xl border border-slate-200/80 bg-slate-50/80 p-4 shadow-sm"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                {field.label}
              </p>
              <p
                className={`mt-3 break-words text-sm font-semibold text-slate-800 transition-all duration-500 ${
                  hasValue ? "translate-y-0 opacity-100" : "translate-y-1 opacity-50"
                }`}
              >
                {hasValue ? String(value) : "-"}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function RAGIntelligenceBox({ ragContext }) {
  return (
    <section className="rounded-xl border border-white/70 bg-white/70 p-5 shadow-xl shadow-slate-200/60 backdrop-blur-xl">
      <div className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          Intelligence Panel
        </p>
        <h2 className="mt-1 text-lg font-bold text-slate-900">Medical Hint</h2>
      </div>
      <div className="max-h-72 overflow-auto rounded-xl border border-indigo-100 bg-indigo-50/70 p-4">
        <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">
          {ragContext || "No medical protocol hints available yet."}
        </p>
      </div>
    </section>
  );
}

export function FinalSummaryView({ isOpen, summary, onClose, onDownload }) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm">
      <section className="max-h-[88vh] w-full max-w-4xl overflow-hidden rounded-xl border border-white/80 bg-white shadow-2xl shadow-slate-900/20">
        <div className="flex flex-col gap-3 border-b border-slate-200 bg-slate-50 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Final Report
            </p>
            <h2 className="mt-1 text-xl font-bold text-slate-900">SOAP Summary</h2>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onDownload}
              className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700"
            >
              Download PDF
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
            >
              Close
            </button>
          </div>
        </div>
        <div className="max-h-[68vh] overflow-auto p-6">
          <pre className="whitespace-pre-wrap font-sans text-sm leading-7 text-slate-700">
            {summary || "Summary is being prepared."}
          </pre>
        </div>
      </section>
    </div>
  );
}
