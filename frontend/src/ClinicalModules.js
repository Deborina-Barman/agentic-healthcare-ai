import React from "react";
import {
  Brain,
  Droplets,
  HeartPulse,
  Pill,
  ShieldAlert,
  Stethoscope,
  Thermometer,
  Wind,
} from "lucide-react";
import { ClinicalCard } from "./DashboardComponents";

const value = (item, fallback = "Pending") => {
  if (Array.isArray(item)) return item.length ? item.join(", ") : fallback;
  return item !== undefined && item !== null && String(item).trim() !== "" ? String(item) : fallback;
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

const deniedSymptoms = (data) =>
  new Set(
    Object.entries(symptomFieldLabels)
      .filter(([field]) => data?.backend?.clinical_fields?.[field] === false || data?.clinical_fields?.[field] === false)
      .map(([, label]) => canonicalSymptom(label))
  );

const positiveSymptoms = (data) => {
  const denied = deniedSymptoms(data);
  return (data?.associated_symptoms || []).filter((symptom) => !denied.has(canonicalSymptom(symptom)));
};

const hasSymptom = (data, pattern) => {
  const text = [data?.chief_complaint, ...positiveSymptoms(data)].join(" ").toLowerCase();
  return pattern.test(text);
};

const Row = ({ label, value: rowValue, tone = "text-slate-900" }) => (
  <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-2.5 text-xs last:border-b-0">
    <span className="font-semibold text-slate-600">{label}</span>
    <span className={`text-right font-bold ${tone}`}>{rowValue}</span>
  </div>
);

export function FeverClinicalCard({ data }) {
  return (
    <ClinicalCard title="Fever Clinical Focus" icon={Thermometer} accent="rose" className="lg:col-span-4">
      <Row label="Temperature" value={value(data?.temperature)} tone={data?.temperature ? "text-rose-600" : "text-slate-500"} />
      <Row label="Duration" value={value(data?.duration)} />
      <Row label="Associated Symptoms" value={value(positiveSymptoms(data), "Pending")} />
      <Row label="Fever Alert" value={data?.red_flags?.some((flag) => /fever/i.test(flag)) ? "Active" : "Monitor"} tone="text-amber-700" />
    </ClinicalCard>
  );
}

export function CardiacRiskCard({ data }) {
  const chestPain = hasSymptom(data, /chest pain|chest pressure/);
  const sweating = hasSymptom(data, /sweating|sweat/);
  return (
    <ClinicalCard title="Cardiac Risk" icon={HeartPulse} accent="rose" className="lg:col-span-4">
      <Row label="Chest Pain" value={chestPain ? "Reported" : "Not reported"} tone={chestPain ? "text-rose-600" : "text-emerald-700"} />
      <Row label="Sweating" value={sweating ? "Reported" : "Not reported"} tone={sweating ? "text-rose-600" : "text-emerald-700"} />
      <Row label="Breathing Difficulty" value={value(data?.breathing_difficulty, "Not reported")} />
      <Row label="Escalation" value={chestPain || data?.breathing_difficulty === "Yes" ? "Prioritize review" : "Routine screen"} tone={chestPain ? "text-rose-600" : "text-slate-700"} />
    </ClinicalCard>
  );
}

export function RespiratoryRiskCard({ data }) {
  return (
    <ClinicalCard title="Respiratory Risk" icon={Wind} accent="blue" className="lg:col-span-4">
      <Row label="Breathing Difficulty" value={value(data?.breathing_difficulty, "Not reported")} tone={data?.breathing_difficulty === "Yes" ? "text-rose-600" : "text-emerald-700"} />
      <Row label="Cough" value={hasSymptom(data, /cough/) ? "Reported" : "Not reported"} />
      <Row label="Severity" value={value(data?.severity)} />
      <Row label="Respiratory Alert" value={data?.breathing_difficulty === "Yes" ? "Active" : "Screen negative"} tone={data?.breathing_difficulty === "Yes" ? "text-rose-600" : "text-emerald-700"} />
    </ClinicalCard>
  );
}

export function GastrointestinalCard({ data }) {
  return (
    <ClinicalCard title="Gastrointestinal Symptoms" icon={Stethoscope} accent="amber" className="lg:col-span-4">
      <Row label="Vomiting" value={hasSymptom(data, /vomit/) ? "Reported" : "Not reported"} tone={hasSymptom(data, /vomit/) ? "text-amber-700" : "text-slate-600"} />
      <Row label="Other GI Symptoms" value={positiveSymptoms(data).filter((item) => /nausea|diarrhea|abdominal|stomach/i.test(item)).join(", ") || "Pending"} />
      <Row label="Medication Response" value={value(data?.medication_response)} />
      <Row label="Clinical Focus" value="Fluid loss and infection screen" />
    </ClinicalCard>
  );
}

export function MedicationCard({ data }) {
  const taken = value(data?.medications_taken || data?.medications || data?.medication_taken, "Pending");
  const response = value(data?.medication_response || data?.clinical_fields?.medication_response, "Pending");
  const allergyStatus = value(data?.backend?.allergies || data?.allergies, "Awaiting response");
  const currentStatus = taken === "Pending" ? "Pending" : response === "Pending" ? "Requires response review" : "Medication recorded";

  return (
    <ClinicalCard title="Medication Review" icon={Pill} accent="violet" className="lg:col-span-4">
      <div className="overflow-hidden rounded-lg border border-slate-200">
        <Row label="Medication Taken" value={taken} tone={taken === "Pending" ? "text-amber-700" : "text-emerald-700"} />
        <Row label="Medication Response" value={response} tone={response === "Pending" ? "text-amber-700" : "text-emerald-700"} />
        <Row label="Allergy Status" value={allergyStatus} tone={allergyStatus === "Awaiting response" ? "text-amber-700" : "text-emerald-700"} />
        <Row label="Current Status" value={currentStatus} tone={currentStatus === "Medication recorded" ? "text-emerald-700" : "text-amber-700"} />
        <Row label="Next Recommended Action" value="Confirm dose, timing, and allergy status" />
      </div>
      {taken === "Pending" && <p className="mt-3 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs font-semibold text-slate-500">No medication information available yet.</p>}
    </ClinicalCard>
  );
}

export function HydrationRiskCard({ data }) {
  const dehydrationRisk = hasSymptom(data, /vomit|diarrhea/) || Number(data?.triage_score || 0) >= 4;
  return (
    <ClinicalCard title="Hydration Risk" icon={Droplets} accent="green" className="lg:col-span-4">
      <Row label="Fluid Loss Symptoms" value={hasSymptom(data, /vomit|diarrhea/) ? "Present" : "Not reported"} tone={dehydrationRisk ? "text-amber-700" : "text-emerald-700"} />
      <Row label="Fever" value={value(data?.temperature)} />
      <Row label="Risk Level" value={dehydrationRisk ? "Requires Assessment" : "Monitor"} tone={dehydrationRisk ? "text-amber-700" : "text-emerald-700"} />
      <Row label="Recommendation" value="Hydration monitoring" />
    </ClinicalCard>
  );
}

export function NeurologyRiskCard({ data }) {
  const neuroFlag = hasSymptom(data, /confusion|faint|seizure|dizziness|weakness/);
  return (
    <ClinicalCard title="Neurology Risk" icon={Brain} accent="blue" className="lg:col-span-4">
      <Row label="Neuro Symptoms" value={neuroFlag ? "Reported" : "Not reported"} tone={neuroFlag ? "text-rose-600" : "text-emerald-700"} />
      <Row label="Consciousness" value={value(data?.altered_consciousness, "Pending")} />
      <Row label="Severity" value={value(data?.severity)} />
      <Row label="Escalation" value={neuroFlag ? "Screen urgently" : "Continue monitoring"} />
    </ClinicalCard>
  );
}

export function PregnancyRiskCard({ data }) {
  return (
    <ClinicalCard title="Pregnancy Risk" icon={ShieldAlert} accent="rose" className="lg:col-span-4">
      <Row label="Pregnancy Status" value={value(data?.pregnancy_status, "Pending")} />
      <Row label="Pain or Bleeding" value={value(data?.bleeding_or_pain, "Pending")} />
      <Row label="Medication Safety" value={data?.medications_taken?.length ? "Review required" : "No medication captured"} />
      <Row label="Clinical Focus" value="Safety screening" />
    </ClinicalCard>
  );
}
