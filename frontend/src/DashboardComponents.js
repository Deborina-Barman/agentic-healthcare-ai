import React from "react";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BadgeInfo,
  Check,
  ClipboardList,
  Download,
  Droplets,
  Edit3,
  FileText,
  HeartPulse,
  Pill,
  PlusCircle,
  Share2,
  ShieldAlert,
  Stethoscope,
  Thermometer,
  Timer,
  UserRound,
} from "lucide-react";

const cardMotion = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.35, ease: "easeOut" },
};

const isPresent = (value) => {
  if (Array.isArray(value)) return value.length > 0;
  return value !== undefined && value !== null && String(value).trim() !== "" && value !== "-";
};

const clean = (value, fallback = "Awaiting intake") => {
  if (Array.isArray(value)) return value.length ? value.join(", ") : fallback;
  return isPresent(value) ? String(value) : fallback;
};

const fieldStatus = (value) =>
  isPresent(value)
    ? { label: "Captured", className: "border-emerald-200 bg-emerald-50 text-emerald-700" }
    : { label: "Pending", className: "border-amber-200 bg-amber-50 text-amber-800" };

const toList = (value) => {
  if (!isPresent(value)) return [];
  if (Array.isArray(value)) return value.filter(isPresent).map(String);
  return String(value)
    .split(/,|;|\n/)
    .map((item) => item.trim())
    .filter(Boolean);
};

const symptomFieldLabels = {
  breathing_difficulty: "breathing difficulty",
  shortness_of_breath: "breathing difficulty",
  chest_pain: "chest pain",
  vomiting: "vomiting",
  diarrhea: "diarrhea",
  rash: "rash",
  confusion: "confusion",
  cough: "cough",
  weakness: "weakness",
  chills: "chills",
  body_aches: "body aches",
  sweating: "sweating",
  dizziness: "dizziness",
  fainting: "fainting",
};

const canonicalSymptom = (symptom) =>
  String(symptom || "")
    .trim()
    .toLowerCase()
    .replace("difficulty breathing", "breathing difficulty")
    .replace("shortness of breath", "breathing difficulty")
    .replace("chest pressure", "chest pain")
    .replace("vomit", "vomiting");

const positiveSymptoms = (data) => {
  const clinicalFields = data?.clinical_fields || data?.backend?.clinical_fields || {};
  const denied = new Set(
    Object.entries(symptomFieldLabels)
      .filter(([field]) => clinicalFields?.[field] === false)
      .map(([, label]) => canonicalSymptom(label))
  );

  return toList(data?.associated_symptoms).filter((symptom) => !denied.has(canonicalSymptom(symptom)));
};

const scoreConfig = (score = 0, urgency = "") => {
  const normalized = String(urgency).toLowerCase();
  if (score >= 8 || normalized.includes("urgent") || normalized.includes("emergency")) {
    return {
      label: "Urgent",
      badge: "bg-rose-50 text-rose-700 border-rose-200",
      ring: "border-rose-300 text-rose-700",
      panel: "from-rose-50 to-white",
    };
  }
  if (score >= 6 || normalized.includes("high")) {
    return {
      label: "High",
      badge: "bg-rose-50 text-rose-700 border-rose-200",
      ring: "border-rose-300 text-rose-700",
      panel: "from-rose-50 to-white",
    };
  }
  if (score >= 3 || normalized.includes("moderate")) {
    return {
      label: "Moderate",
      badge: "bg-amber-50 text-amber-700 border-amber-200",
      ring: "border-amber-300 text-amber-700",
      panel: "from-amber-50 to-white",
    };
  }
  return {
    label: "Low",
    badge: "bg-emerald-50 text-emerald-700 border-emerald-200",
    ring: "border-emerald-300 text-emerald-700",
    panel: "from-emerald-50 to-white",
  };
};

export function ClinicalCard({ title, icon: Icon, accent = "indigo", action, children, className = "" }) {
  const accentMap = {
    indigo: "bg-indigo-100 text-indigo-700",
    blue: "bg-sky-100 text-sky-700",
    green: "bg-emerald-100 text-emerald-700",
    amber: "bg-amber-100 text-amber-700",
    rose: "bg-rose-100 text-rose-700",
    violet: "bg-violet-100 text-violet-700",
  };

  return (
    <motion.section
      {...cardMotion}
      className={`clinical-card rounded-2xl border border-slate-200/80 bg-white shadow-[0_4px_18px_rgba(15,23,42,0.05)] ${className}`}
    >
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div className="flex min-w-0 items-center gap-3">
          {Icon && (
            <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${accentMap[accent]}`}>
              <Icon size={17} />
            </span>
          )}
          <h2 className="truncate text-sm font-bold text-slate-950">{title}</h2>
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </motion.section>
  );
}

export function PatientInformationCard({ patient, visitTime }) {
  const fields = [
    { label: "Name", value: clean(patient?.name, "Patient pending") },
    { label: "Age", value: clean(patient?.age, "Not recorded") },
    { label: "Gender", value: clean(patient?.gender, "Not recorded") },
    { label: "Language", value: clean(patient?.language, "Hindi") },
    { label: "Visit Time", value: visitTime },
  ];

  return (
    <ClinicalCard
      title="Patient Information"
      icon={UserRound}
      action={
        <button className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-indigo-200 hover:bg-indigo-50">
          <Edit3 size={14} />
          Edit
        </button>
      }
      className="lg:col-span-12"
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {fields.map((field) => (
          <div key={field.label} className="border-slate-100 xl:border-r xl:last:border-r-0">
            <p className="text-xs font-medium text-slate-500">{field.label}</p>
            <p className="mt-1 text-sm font-bold text-slate-950">{field.value}</p>
          </div>
        ))}
      </div>
    </ClinicalCard>
  );
}

export function ClinicalSnapshotCard({ data }) {
  const nlice = data?.backend?.nlice_data || data?.nlice_data || {};
  const symptoms = positiveSymptoms(data);
  const rows = [
    { icon: Stethoscope, label: "Chief Complaint", value: clean(data?.chief_complaint || data?.complaint || nlice.nature, "Pending") },
    { icon: Timer, label: "Duration", value: clean(data?.duration || nlice.chronology, "Pending") },
    { icon: Thermometer, label: "Temperature (Max)", value: clean(data?.temperature || nlice.excitation, "Pending"), tone: "text-rose-700" },
    { icon: Activity, label: "Severity (Self Rated)", value: clean(data?.severity || nlice.intensity, "Pending") },
    { icon: HeartPulse, label: "Breathing Difficulty", value: clean(data?.breathing_difficulty || data?.breathingDifficulty, "Awaiting response") },
    { icon: BadgeInfo, label: "Other Symptoms", value: symptoms.length ? symptoms : ["Pending"], pills: true },
    { icon: Pill, label: "Medication Taken", value: clean(data?.medications_taken || data?.medications || data?.medication_taken || data?.medication, "Awaiting response") },
    { icon: ShieldAlert, label: "Medication Response", value: clean(data?.medication_response ||data?.clinical_fields?.medication_response || data?.response, "Awaiting response") },
    
  ];
  return (
    <ClinicalCard title="Clinical Snapshot" icon={ClipboardList} accent="violet" className="lg:col-span-7">
      <div className="overflow-hidden rounded-xl border border-slate-200/90">
        {rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[minmax(145px,0.85fr)_1.15fr] border-b border-slate-100 last:border-b-0">
            <div className="flex items-center gap-3 bg-slate-50/80 px-4 py-3.5 text-xs font-semibold text-slate-700">
              <row.icon size={15} className="text-indigo-500" />
              {row.label}
            </div>
            <div className={`px-4 py-3.5 text-xs font-semibold ${row.tone || "text-slate-900"}`}>
              {row.pills ? (
                <div className="flex flex-wrap gap-2">
                  {row.value.map((item, index) => (
                    <span key={`${item}-${index}`} className={item === "Pending" ? "clinical-badge rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-amber-800" : "clinical-badge rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-emerald-700"}>
                      {item}
                    </span>
                  ))}
                </div>
              ) : (
                row.value
              )}
            </div>
          </div>
        ))}
      </div>
    </ClinicalCard>
  );
}

export function ClinicalCompletenessCard({ data }) {
  const fields = [
    ["Chief complaint", data?.chief_complaint || data?.complaint],
    ["Duration", data?.duration || data?.backend?.nlice_data?.chronology],
    ["Temperature", data?.temperature || data?.clinical_fields?.temperature_max],
    ["Respiratory screen", data?.clinical_fields?.associated_respiratory_symptoms ?? data?.clinical_fields?.breathing_difficulty],
    ["Systemic symptoms", data?.clinical_fields?.associated_systemic_symptoms ?? data?.clinical_fields?.chills ?? data?.clinical_fields?.body_aches],
    ["Medication response", data?.medication_response || data?.clinical_fields?.medication_response],
    ["Hydration", data?.clinical_fields?.hydration_status || data?.clinical_fields?.urination_normal],
    ["Exposure", data?.clinical_fields?.sick_contacts ?? data?.clinical_fields?.travel_or_mosquito_exposure],
  ];
  const collected = fields.filter(([, value]) => value !== undefined && value !== null && String(value).trim() !== "").length;
  const percentage = Math.round((collected / fields.length) * 100);
  const missing = fields.filter(([, value]) => !isPresent(value)).map(([label]) => label);

  return (
    <ClinicalCard title="Clinical Completeness" icon={Check} accent="green" className="lg:col-span-4">
      <div className="flex items-center justify-between rounded-xl border border-emerald-100 bg-emerald-50/70 px-4 py-3">
        <div>
          <p className="text-2xl font-black text-emerald-700">{percentage}%</p>
          <p className="text-xs font-semibold text-slate-600">{collected} of {fields.length} fields captured</p>
        </div>
        <span className="rounded-full border border-emerald-200 bg-white px-3 py-1 text-xs font-bold text-emerald-700">
          {collected === fields.length ? "Complete" : "In progress"}
        </span>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${percentage}%` }} />
      </div>
      <div className="mt-3 grid gap-2 text-xs">
        {fields.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-3">
            <span className="text-slate-600">{label}</span>
            <span className={`clinical-badge rounded-full border px-2 py-0.5 text-[11px] font-bold ${fieldStatus(value).className}`}>
              {fieldStatus(value).label}
            </span>
          </div>
        ))}
      </div>
      {missing.length > 0 && <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-500"><span className="font-bold text-slate-700">Still needed:</span> {missing.join(", ")}</p>}
    </ClinicalCard>
  );
}

export function LabReportAnalysisCard({ data }) {
  const report = data?.lab_report_analysis || data?.backend?.lab_report_analysis || {};
  const rows = [
    ["Hemoglobin", report.hemoglobin],
    ["WBC", report.wbc],
    ["Platelets", report.platelets],
    ["Glucose", report.glucose],
    ["Creatinine", report.creatinine],
    ["BP", report.bp],
  ].filter(([, value]) => isPresent(value));

  return (
    <ClinicalCard title="Lab Report Analysis" icon={FileText} accent="blue" className="lg:col-span-4">
      {rows.length ? (
        <div className="overflow-hidden rounded-lg border border-slate-200">
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-center justify-between gap-3 border-b border-slate-100 px-3 py-2.5 text-xs last:border-b-0">
              <span className="font-semibold text-slate-600">{label}</span>
              <span className="font-bold text-slate-950">{value}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-xs font-semibold text-slate-500">
          <p className="font-bold text-slate-700">No medical report uploaded yet.</p>
          <p className="mt-1 leading-5">Upload a prescription or lab report to automatically extract medications and clinical values.</p>
        </div>
      )}
    </ClinicalCard>
  );
}

export function TriageAlertsCard({ analysis, data }) {
  const score = Number(data?.triage_score ?? analysis?.score ?? analysis?.urgency_score ?? 0);
  const displayScore = score <= 10 ? score * 10 : score;
  const config = scoreConfig(score, data?.triage_level || analysis?.urgency || analysis?.label);
  const redFlags = Array.from(new Set([
    ...(data?.red_flags || []),
    ...positiveSymptoms(data).map((symptom) => `${symptom} present`),
    analysis?.reason || analysis?.reasoning || analysis?.triage_reasoning || null,
  ].filter(Boolean).map((alert) => String(alert).trim())));
  const symptoms = positiveSymptoms(data).map((item) => item.toLowerCase());
  const hasSymptom = (pattern) => symptoms.some((symptom) => pattern.test(symptom));

  const risks = [
    ["High Fever", data?.temperature ? (Number(String(data.temperature).match(/\d+(?:\.\d+)?/)?.[0] || 0) >= 103 ? "Yes" : "Monitor") : "Monitor"],
    ["Breathing Difficulty", clean(data?.breathing_difficulty || data?.breathingDifficulty, "No")],
    ["Chest Pain", hasSymptom(/chest pain|chest pressure/) ? "Yes" : "No"],
    ["Weakness/Fatigue", hasSymptom(/weakness|fatigue/) ? "Present" : "No"],
    ["Severe Dehydration Risk", score >= 6 || hasSymptom(/vomit|diarrhea/) ? "Requires Assessment" : "Monitor"],
    ["Altered Consciousness", clean(data?.altered_consciousness, "No")],
  ];

  return (
    <ClinicalCard title="Triage & Alerts" icon={AlertTriangle} accent="rose" className="lg:col-span-5">
      <div className={`grid grid-cols-2 gap-4 rounded-xl border border-slate-100 bg-gradient-to-br ${config.panel} p-4`}>
        <div className="flex flex-col items-center justify-center border-r border-slate-200">
          <span className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-bold ${config.badge}`}>
            <AlertTriangle size={15} />
            {config.label}
          </span>
          <p className="mt-3 text-xs font-medium text-slate-500">Urgency Level</p>
        </div>
        <div className="flex flex-col items-center justify-center">
          <div className={`grid h-20 w-20 place-items-center rounded-full border-4 ${config.ring}`}>
            <div className="text-center">
              <p className="text-2xl font-black">{score}</p>
              <p className="text-[10px] font-bold">/10</p>
            </div>
          </div>
          <p className="mt-2 text-xs font-medium text-slate-500">Triage Score ({displayScore}/100)</p>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-rose-100 bg-rose-50/70 p-4">
        <p className="mb-3 flex items-center gap-2 text-sm font-bold text-slate-900">
          <ShieldAlert size={16} className="text-rose-500" />
          Clinical Alerts
        </p>
        <ul className="space-y-2 text-xs text-slate-700">
          {(redFlags.length ? redFlags : ["No red flag alert recorded yet"]).slice(0, 4).map((alert, index) => (
            <li key={`${alert}-${index}`} className="flex gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-rose-500" />
              <span>{alert}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
        <p className="mb-3 text-sm font-bold text-slate-900">Vital Risk Indicators</p>
        <div className="space-y-2">
          {risks.map(([label, value]) => (
            <div key={label} className="flex items-center justify-between gap-3 text-xs">
              <span className="text-slate-700">{label}</span>
              <span className={String(value).toLowerCase().includes("yes") || String(value).toLowerCase().includes("requires") ? "font-bold text-rose-600" : String(value).toLowerCase().includes("monitor") ? "font-bold text-amber-700" : "font-bold text-emerald-700"}>
                {value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </ClinicalCard>
  );
}

export function AIClinicalSummaryCard({ data }) {
  const nlice = data?.backend?.nlice_data || data?.nlice_data || {};
  const complaint = clean(data?.chief_complaint || data?.complaint || nlice.nature, "Patient intake in progress");
  const clinicalFields = data?.clinical_fields || data?.backend?.clinical_fields || {};
  const findings = [
    ["Duration", clean(data?.duration || nlice.chronology, "Pending")],
    ["Maximum temperature", clean(data?.temperature || nlice.excitation, "Pending")],
    ["Medication", clean(data?.medications_taken || data?.medications || data?.medication_taken || data?.medication, "Awaiting response")],
    ["Medication response", clean(data?.medication_response || clinicalFields?.medication_response, "Awaiting response")],
    ["Breathing difficulty", clean(data?.breathing_difficulty || data?.breathingDifficulty, "Awaiting response")],
    ["Hydration", clean(clinicalFields?.hydration_status || clinicalFields?.urination_normal, "Pending")],
    ["Recent travel", clean(clinicalFields?.travel_or_mosquito_exposure, "Pending")],
  ];
  const assessment = clean(data?.clinical_analysis?.reason || data?.clinical_analysis?.reasoning, "Continue intake to strengthen the doctor handoff.");
  const recommendation = clean(data?.recommendation || data?.clinical_analysis?.recommendation, "Monitor symptoms and seek medical attention if they worsen.");

  return (
    <ClinicalCard title="AI Clinical Summary" icon={FileText} accent="blue" className="lg:col-span-7">
      <div className="grid gap-3 text-xs leading-5 text-slate-700">
        <section><p className="mb-1 font-bold uppercase tracking-[0.11em] text-slate-500">Chief complaint</p><p className="font-semibold text-slate-950">{complaint}</p></section>
        <section><p className="mb-2 font-bold uppercase tracking-[0.11em] text-slate-500">Clinical findings</p><ul className="grid gap-1.5 rounded-xl border border-slate-100 bg-slate-50/70 p-3">{findings.map(([label, finding]) => <li key={label} className="flex items-baseline justify-between gap-3"><span className="text-slate-600">{label}</span><span className="text-right font-semibold text-slate-950">{finding}</span></li>)}</ul></section>
        <section className="rounded-xl border border-indigo-100 bg-indigo-50/65 p-3"><p className="mb-1 font-bold uppercase tracking-[0.11em] text-indigo-700">Assessment</p><p>{assessment}</p></section>
        <section className="rounded-xl border border-emerald-100 bg-emerald-50/65 p-3"><p className="mb-1 font-bold uppercase tracking-[0.11em] text-emerald-700">Recommendation</p><p>{recommendation}</p></section>
      </div>
    </ClinicalCard>
  );
}

export function TimelineCard({ messages, data }) {
  const denied = new Set(
    Object.entries(symptomFieldLabels)
      .filter(([field]) => (data?.clinical_fields || data?.backend?.clinical_fields || {})?.[field] === false)
      .map(([, label]) => canonicalSymptom(label))
  );
  const timeline = data?.timeline?.length
    ? data.timeline
        .filter((item) => {
          const text = String(item?.text || "").toLowerCase();
          return ![...denied].some((symptom) => text.includes(`${symptom} reported`) || text.includes(`${symptom} present`));
        })
        .map((item, index) => ({ ...item, id: item.key || `${item.text}-${index}`, role: "clinical" }))
        .reverse()
    : messages.slice(-6).map((message, index) => ({
        time: message.time || "Now",
        text: message.text,
        role: message.role,
        id: `${message.role}-${index}-${message.text}`,
      })).reverse();
  const timelineIcon = (text = "") => {
    const event = String(text).toLowerCase();
    if (/temperature|fever/.test(event)) return Thermometer;
    if (/medication|tablet|paracetamol|dose/.test(event)) return Pill;
    if (/hydration|water|fluid/.test(event)) return Droplets;
    if (/high fever|urgent|red flag|alert/.test(event)) return AlertTriangle;
    return ClipboardList;
  };

  return (
    <ClinicalCard title="Timeline" icon={Timer} accent="blue" className="lg:col-span-4">
      <div className="space-y-3">
        {timeline.length ? timeline.map((item) => {
          const EventIcon = timelineIcon(item.text);
          return (
          <div key={item.id} className="grid grid-cols-[64px_1fr] gap-3 text-xs">
            <span className="font-semibold text-slate-600">{item.time}</span>
            <div className="relative border-l border-indigo-100 pl-4 text-slate-700">
              <span className={`absolute -left-3 top-0 grid h-6 w-6 place-items-center rounded-full border-2 border-white ${item.role === "user" ? "bg-indigo-100 text-indigo-700" : "bg-sky-100 text-sky-700"}`}><EventIcon size={12} /></span>
              <p className="line-clamp-2">{item.text}</p>
            </div>
          </div>
          );
        }) : <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-xs font-semibold text-slate-500">No clinical events recorded yet.</div>}
      </div>
    </ClinicalCard>
  );
}

export function RecommendedNextStepsCard({ data }) {
  const score = Number(data?.triage_score ?? data?.clinical_analysis?.score ?? 0);
  const dynamicRecommendations = Array.isArray(data?.recommendations) ? data.recommendations : [];
  const steps = dynamicRecommendations.length
    ? dynamicRecommendations.map((text) => ({ icon: Check, text }))
    : [
        { icon: Droplets, text: "Rest and maintain hydration" },
        { icon: Pill, text: clean(data?.medications_taken || data?.medication_taken, "Continue medication only as clinically advised") },
        { icon: Thermometer, text: "Monitor temperature and symptom progression" },
        { icon: HeartPulse, text: score >= 4 ? "Escalate if symptoms worsen or red flags appear" : "Consult a doctor if symptoms worsen or persist" },
      ];

  return (
    <ClinicalCard title="Recommended Next Steps" icon={PlusCircle} accent="green" className="lg:col-span-4">
      <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.11em] text-slate-500">AI-generated recommendations</p>
      <div className="overflow-hidden rounded-lg border border-slate-200">
        {steps.map((step) => (
          <div key={step.text} className="flex items-start gap-3 border-b border-slate-100 px-3 py-3 text-xs text-slate-700 last:border-b-0">
            <Check size={15} className="mt-0.5 shrink-0 text-emerald-600" />
            <span>{step.text}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-700">
        This is AI-assisted guidance. Use clinical judgment.
      </div>
    </ClinicalCard>
  );
}

export function ActionPanel({ onExport, canExport }) {
  const actions = [
    { label: "Export SOAP PDF", icon: Download, tone: "border-blue-100 bg-blue-50 text-blue-700", onClick: onExport, disabled: !canExport },
    { label: "Share with Doctor", icon: Share2, tone: "border-violet-100 bg-violet-50 text-violet-700" },
    { label: "Add Notes", icon: Edit3, tone: "border-amber-100 bg-amber-50 text-amber-700" },
  ];

  return (
    <ClinicalCard title="Actions" icon={ClipboardList} accent="violet" className="lg:col-span-4">
      <div className="space-y-3">
        {actions.map((action) => (
          <button
            key={action.label}
            onClick={action.onClick}
            disabled={action.disabled}
            className={`flex w-full items-center justify-between rounded-lg border px-3 py-3 text-xs font-bold transition hover:-translate-y-0.5 hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-50 ${action.tone}`}
          >
            <span className="flex items-center gap-3">
              <action.icon size={16} />
              {action.label}
            </span>
            <ArrowRight size={15} />
          </button>
        ))}
      </div>
    </ClinicalCard>
  );
}

export function ClinicalIntelligenceDashboard({ data, messages, onExport, fallbackVisitTime }) {
  const clinicalData = data || {};
  const visitTime = clinicalData?.patient_info?.visit_time || clinicalData?.visit_time || clinicalData?.visitTime || fallbackVisitTime || new Date().toLocaleString([], {
    month: "numeric",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });

  const patient = {
    name: clinicalData?.patient_info?.name || clinicalData?.patient_name || clinicalData?.patient?.name,
    age: clinicalData?.patient_info?.age || clinicalData?.age || clinicalData?.patient?.age,
    gender: clinicalData?.patient_info?.gender || clinicalData?.gender || clinicalData?.patient?.gender,
    language: clinicalData?.patient_info?.language || clinicalData?.preferred_language || clinicalData?.language || clinicalData?.patient?.language,
  };

  return (
    <motion.div
      id="report-area"
      className="grid grid-cols-1 gap-4 lg:grid-cols-12"
      initial="initial"
      animate="animate"
      transition={{ staggerChildren: 0.04 }}
    >
      <PatientInformationCard patient={patient} visitTime={visitTime} />
      <ClinicalSnapshotCard data={clinicalData} />
      <TriageAlertsCard analysis={clinicalData?.clinical_analysis} data={clinicalData} />
      <AIClinicalSummaryCard data={clinicalData} />
      <TimelineCard messages={messages} data={clinicalData} />
      <RecommendedNextStepsCard data={clinicalData} />
      <ActionPanel onExport={onExport} canExport={Boolean(data)} />
      <div className="lg:col-span-12 text-center text-xs text-slate-500">
        SevaCare AI is not a substitute for professional medical advice.
      </div>
    </motion.div>
  );
}
