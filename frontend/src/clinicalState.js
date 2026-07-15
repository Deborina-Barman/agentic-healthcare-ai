const emptyPatientInfo = {
  name: "",
  age: "",
  gender: "",
  language: "",
  visit_time: "",
};

export const createInitialClinicalState = (patientInfo = {}) => ({
  patient_info: {
    ...emptyPatientInfo,
    ...patientInfo,
    visit_time: patientInfo.visit_time || formatVisitTime(),
  },
  chief_complaint: "",
  associated_symptoms: [],
  negative_findings: [],
  temperature: "",
  severity: "",
  duration: "",
  breathing_difficulty: "",
  medications_taken: [],
  medication_response: "",
  red_flags: [],
  triage_level: "Low",
  triage_score: 0,
  clinical_category: "general",
  active_modules: ["GeneralSnapshotCard", "TriageAlertsCard", "ClinicalCompletenessCard", "AIClinicalSummaryCard", "MedicationCard", "LabReportAnalysisCard", "TimelineCard", "RecommendedNextStepsCard", "ActionPanel"],
  timeline: [],
  lab_report_analysis: {},
  ai_summary: "",
  backend: {},
  is_complete: false,
});

export function formatVisitTime() {
  return new Date().toLocaleString([], {
    month: "numeric",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

const hasValue = (value) => value !== undefined && value !== null && String(value).trim() !== "" && String(value).trim() !== "-";

const firstValue = (...values) => values.find(hasValue) || "";

const normalizeList = (value) => {
  if (!hasValue(value)) return [];
  if (Array.isArray(value)) return value.filter(hasValue).map((item) => String(item).trim());
  return String(value)
    .split(/,|;|\n/)
    .map((item) => item.trim())
    .filter(Boolean);
};

const mergeUnique = (...lists) => {
  const seen = new Set();
  const result = [];
  lists.flat().forEach((item) => {
    const normalized = String(item || "").trim();
    const key = normalized.toLowerCase();
    if (normalized && !seen.has(key)) {
      seen.add(key);
      result.push(normalized);
    }
  });
  return result;
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

const canonicalSymptom = (symptom) => {
  const normalized = String(symptom || "").trim().toLowerCase();
  const aliases = {
    "difficulty breathing": "breathing difficulty",
    "shortness of breath": "breathing difficulty",
    "trouble breathing": "breathing difficulty",
    "chest pressure": "chest pain",
    vomit: "vomiting",
    "persistent vomiting": "vomiting",
    "severe weakness": "weakness",
    "body ache": "body aches",
    "body pain": "body aches",
  };
  return aliases[normalized] || normalized;
};

const negativeSymptomsFromFields = (clinicalFields = {}) =>
  Object.entries(symptomFieldLabels)
    .filter(([field]) => clinicalFields?.[field] === false)
    .map(([, label]) => canonicalSymptom(label));

const filterSymptomsByPolarity = (symptoms, clinicalFields = {}, negativeFindings = []) => {
  const denied = new Set([
    ...negativeSymptomsFromFields(clinicalFields),
    ...normalizeList(negativeFindings).map(canonicalSymptom),
  ]);

  return mergeUnique(symptoms)
    .map(canonicalSymptom)
    .filter((symptom) => !denied.has(symptom));
};

const parseTemperature = (...sources) => {
  const text = sources.filter(hasValue).join(" ");
  const match = text.match(/\b(9[5-9]|10[0-9]|11[0-5])(?:\.\d+)?\s*(?:f|°f|fahrenheit)?\b/i);
  if (!match) return "";
  const value = match[0].replace(/fahrenheit/i, "").replace(/f/i, "").replace(/°/g, "").trim();
  return `${value} F`;
};

const parseSeverity = (...sources) => {
  const text = sources.filter(hasValue).join(" ");
  const explicit = text.match(/\b(10|[1-9])\s*(?:\/|out of)\s*10\b/i);
  if (explicit) return `${explicit[1]} / 10`;
  const scale = text.match(/\b(?:severity|severe|scale|rate|rating)\D{0,24}(10|[1-9])\b/i);
  if (scale) return `${scale[1]} / 10`;
  const standalone = text.trim().match(/^(10|[1-9])$/);
  if (standalone) return `${standalone[1]} / 10`;
  return "";
};

const parseDuration = (...sources) => {
  const text = sources.filter(hasValue).join(" ");
  const since = text.match(/\bsince\s+([a-z0-9 ]{3,40})/i);
  if (since) return `Since ${since[1].trim()}`;
  const duration = text.match(/\b(\d+\s*(?:hours?|days?|weeks?))\b/i);
  if (duration) return duration[1];
  return "";
};

const detectSymptoms = (text) => {
  const lower = String(text || "").toLowerCase();
  const isNegatedAt = (index) => {
    const prefix = lower.slice(Math.max(0, index - 90), index);
    return /\b(no|not|none|without|denies|deny)\b[\w\s,/-]{0,80}$/.test(prefix);
  };
  const symptomMap = [
    ["vomiting", ["vomit", "vomiting", "throwing up"]],
    ["diarrhea", ["diarrhea", "loose motion", "loose stools"]],
    ["headache", ["headache", "head ache"]],
    ["body aches", ["body ache", "body pain", "body aches", "muscle aches"]],
    ["cough", ["cough"]],
    ["chills", ["chills", "shivering"]],
    ["weakness", ["weakness", "weak"]],
    ["fatigue", ["fatigue", "tiredness", "tired"]],
    ["sore throat", ["sore throat"]],
    ["chest pain", ["chest pain", "chest pressure"]],
    ["breathing difficulty", ["shortness of breath", "difficulty breathing", "breathing difficulty"]],
    ["sweating", ["sweating", "sweat"]],
    ["dizziness", ["dizziness", "dizzy", "fainting"]],
    ["confusion", ["confusion", "confused"]],
  ];

  return symptomMap.flatMap(([label, terms]) => {
    const positive = terms.some((term) => {
      const pattern = new RegExp(`\\b${term.replace(/\s+/g, "\\s+")}\\b`, "g");
      let match;
      while ((match = pattern.exec(lower)) !== null) {
        if (!isNegatedAt(match.index)) return true;
      }
      return false;
    });
    return positive ? [label] : [];
  });
};

const detectNegativeFindings = (text, lastAssistantText = "") => {
  const lower = `${String(lastAssistantText || "")} ${String(text || "")}`.toLowerCase();
  const answer = String(text || "").toLowerCase();
  const negative = /\b(no|not|none|without|denies|deny)\b/.test(answer);
  if (!negative) return [];

  const findings = [];
  const targets = [
    ["breathing difficulty", /breath|breathing|shortness of breath/],
    ["confusion", /confusion|confused/],
    ["chest pain", /chest pain|chest pressure/],
    ["vomiting", /vomit|vomiting|throwing up/],
    ["diarrhea", /diarrhea|loose motion|loose stool/],
    ["rash", /rash/],
    ["dehydration", /dehydration|dehydrated/],
    ["weakness", /weakness|weak/],
    ["dizziness", /dizziness|dizzy|faint/],
  ];

  targets.forEach(([label, pattern]) => {
    if (pattern.test(lower)) findings.push(label);
  });

  return findings;
};

const detectComplaint = (backendPayload, userText) => {
  const nlice = backendPayload?.nlice_data || {};
  const explicit = firstValue(backendPayload?.chief_complaint, backendPayload?.complaint, nlice.nature);
  if (explicit) return explicit;
  if (String(userText || "").toLowerCase().includes("fever")) return "Fever";
  if (String(userText || "").toLowerCase().includes("chest pain")) return "Chest pain";
  if (String(userText || "").toLowerCase().includes("cough")) return "Cough";
  if (String(userText || "").toLowerCase().includes("vomit")) return "Vomiting";
  return "";
};

const detectBreathingDifficulty = (userText, lastAssistantText, previousValue) => {
  const answer = String(userText || "").trim().toLowerCase();
  const question = String(lastAssistantText || "").toLowerCase();
  const mentionsBreathing = /breath|breathing|shortness of breath/.test(`${answer} ${question}`);

  if (/breath|breathing|shortness of breath/.test(answer) && !/\b(no|not|none|without|denies)\b/.test(answer)) {
    return "Yes";
  }

  if (mentionsBreathing && /\b(no|not|none|without|denies)\b/.test(answer)) {
    return "No";
  }

  if (mentionsBreathing && /\b(yes|yeah|yep|having|difficulty)\b/.test(answer)) {
    return "Yes";
  }

  return previousValue || "";
};

const detectMedications = (...sources) => {
  const text = sources.filter(hasValue).join(" ").toLowerCase();
  const meds = [
    ["Paracetamol", ["paracetamol", "acetaminophen", "crocin", "dolo"]],
    ["Ibuprofen", ["ibuprofen", "advil"]],
    ["Aspirin", ["aspirin"]],
    ["Antibiotic", ["antibiotic"]],
  ];

  return meds
    .filter(([, terms]) => terms.some((term) => text.includes(term)))
    .map(([label]) => label);
};

const medicationResponse = (...sources) => {
  const text = sources.filter(hasValue).join(" ").toLowerCase();
  if (/\b(no|not|none|limited|little)\b.*\b(relief|improvement|help)\b/.test(text) || /no significant relief/.test(text)) {
    return "No significant relief";
  }
  if (/\b(helped|better|relief|improved)\b/.test(text)) return "Some relief";
  return "";
};

const numericTemperature = (temperature) => {
  const match = String(temperature || "").match(/\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : 0;
};

const numericSeverity = (severity) => {
  const match = String(severity || "").match(/\b(10|[1-9])\b/);
  return match ? Number(match[1]) : 0;
};

export const scoreClinicalUrgency = (state) => {
  let score = 0;
  const redFlags = [];
  const temp = numericTemperature(state.temperature);
  const severity = numericSeverity(state.severity);
  const symptoms = state.associated_symptoms.map((item) => item.toLowerCase());
  const breathing = String(state.breathing_difficulty || "").toLowerCase();
  const hasSymptom = (pattern) => symptoms.some((symptom) => pattern.test(symptom));

  if (temp >= 105) {
    score += 6;
    redFlags.push(`Very high fever: ${state.temperature}`);
  } else if (temp > 103) {
    score += 5;
    redFlags.push(`High fever: ${state.temperature}`);
  } else if (temp >= 100.4) {
    score += 2;
  }

  if (hasSymptom(/vomiting|diarrhea/)) {
    score += temp >= 103 ? 2 : 1;
    redFlags.push("Fluid loss symptom reported");
  }

  if (breathing === "yes") {
    score += 5;
    redFlags.push("Breathing difficulty reported");
  }

  if (hasSymptom(/cough|wheez|sore throat/) || breathing === "yes") {
    score += breathing === "yes" ? 2 : 1;
    redFlags.push("Respiratory symptom reported");
  }

  if (hasSymptom(/weakness|fatigue|body aches|chills|sweating/)) {
    score += 1;
    redFlags.push("Systemic symptom burden reported");
  }

  if (symptoms.length >= 3) {
    score += 1;
    redFlags.push("Multiple symptoms reported");
  }

  if (symptoms.includes("chest pain")) {
    score += symptoms.includes("sweating") || breathing === "yes" ? 5 : 4;
    redFlags.push("Chest pain reported");
  }

  if (symptoms.includes("confusion") || symptoms.includes("dizziness")) {
    score += 3;
    redFlags.push("Neurologic red flag reported");
  }

  if (severity >= 7) {
    score += 2;
    redFlags.push(`High symptom severity: ${state.severity}`);
  }

  const triageScore = Math.min(10, Math.round(score));
  const triageLevel = triageScore >= 8 ? "Urgent" : triageScore >= 6 ? "High" : triageScore >= 3 ? "Moderate" : "Low";

  return {
    triage_level: triageLevel,
    triage_score: triageScore,
    red_flags: mergeUnique(state.red_flags, redFlags),
  };
};

const addTimelineEvent = (timeline, event) => {
  if (!event?.text) return timeline;
  const key = event.key || event.text.toLowerCase();
  if (timeline.some((item) => item.key === key)) return timeline;
  return [...timeline, { ...event, key, time: event.time || new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) }];
};

const deriveTimeline = (state, previousState, userText, timestamp) => {
  let timeline = previousState.timeline || [];

  if (state.chief_complaint && state.chief_complaint !== previousState.chief_complaint) {
    timeline = addTimelineEvent(timeline, { key: "chief_complaint", time: timestamp, text: `${state.chief_complaint} reported` });
  }
  if (state.duration && state.duration !== previousState.duration) {
    timeline = addTimelineEvent(timeline, { key: "duration", time: timestamp, text: `${state.chief_complaint || "Symptom"} started ${state.duration.toLowerCase()}` });
  }
  if (state.temperature && state.temperature !== previousState.temperature) {
    timeline = addTimelineEvent(timeline, { key: "temperature", time: timestamp, text: `Temperature recorded: ${state.temperature}` });
  }
  if (state.severity && state.severity !== previousState.severity) {
    timeline = addTimelineEvent(timeline, { key: "severity", time: timestamp, text: `Severity rated: ${state.severity}` });
  }
  if (state.breathing_difficulty && state.breathing_difficulty !== previousState.breathing_difficulty) {
    timeline = addTimelineEvent(timeline, { key: "breathing", time: timestamp, text: `Breathing difficulty: ${state.breathing_difficulty}` });
  }

  state.associated_symptoms.forEach((symptom) => {
    if (!previousState.associated_symptoms.map((item) => item.toLowerCase()).includes(symptom.toLowerCase())) {
      timeline = addTimelineEvent(timeline, { key: `symptom:${symptom.toLowerCase()}`, time: timestamp, text: `${symptom} reported` });
    }
  });

  state.medications_taken.forEach((medication) => {
    if (!previousState.medications_taken.map((item) => item.toLowerCase()).includes(medication.toLowerCase())) {
      timeline = addTimelineEvent(timeline, { key: `medication:${medication.toLowerCase()}`, time: timestamp, text: `${medication} taken` });
    }
  });

  if (state.medication_response && state.medication_response !== previousState.medication_response) {
    const responseText = String(state.medication_response);
    timeline = addTimelineEvent(timeline, {
      key: `medication_response:${responseText.toLowerCase()}`,
      time: timestamp,
      text: `${responseText.charAt(0).toUpperCase()}${responseText.slice(1)} after medication`,
    });
  }

  if (String(userText || "").toLowerCase().includes("fever") && !timeline.some((item) => item.key === "chief_complaint")) {
    timeline = addTimelineEvent(timeline, { key: "chief_complaint", time: timestamp, text: "Fever reported" });
  }

  return timeline;
};

export const generateClinicalSummary = (state) => {
  const patient = state.patient_info || emptyPatientInfo;
  const demographics = [patient.age ? `${patient.age}-year-old` : "", patient.gender || "", "patient"].filter(Boolean).join(" ");
  const parts = [];
  const positives = state.associated_symptoms.filter((symptom) => symptom.toLowerCase() !== String(state.chief_complaint || "").toLowerCase());
  const negatives = state.negative_findings || [];

  if (state.chief_complaint) {
    parts.push(`${demographics} presenting with ${state.chief_complaint.toLowerCase()}${state.duration ? ` ${state.duration.toLowerCase()}` : ""}`);
  } else {
    parts.push(`${demographics} clinical intake in progress`);
  }

  if (state.temperature) {
    parts.push(`Maximum recorded temperature is ${state.temperature}.`);
  }
  if (positives.length) {
    parts.push(`Associated symptoms include ${positives.join(", ")}.`);
  }
  if (negatives.length) {
    parts.push(`Denies ${negatives.join(" and ")}.`);
  }
  if (state.triage_level && state.triage_level !== "Low" && state.red_flags.length) {
    parts.push(`Findings warrant ${state.triage_level.toLowerCase()} clinical attention due to ${state.red_flags.slice(0, 2).join(" and ").toLowerCase()}.`);
  }
  if (state.severity) {
    parts.push(`Self-rated severity is ${state.severity}.`);
  }
  if (state.breathing_difficulty) {
    parts.push(`${state.breathing_difficulty === "No" ? "No" : "Positive"} breathing difficulty reported.`);
  }
  if (state.medications_taken.length) {
    parts.push(`Patient took ${state.medications_taken.join(", ")}${state.medication_response ? ` with ${state.medication_response.toLowerCase()}` : ""}.`);
  }

  return parts.join(" ");
};

export const classifyClinicalCategory = (state) => {
  const text = [
    state.chief_complaint,
    state.associated_symptoms.join(" "),
    state.temperature,
    state.breathing_difficulty,
    state.backend?.clinical_category,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  const hasFever = text.includes("fever") || text.includes("temperature");
  const hasGI = /vomit|nausea|diarrhea|abdominal|stomach/.test(text);
  const hasCardiac = /chest pain|chest pressure|sweating/.test(text);
  const hasRespiratory = /breath|shortness of breath|cough|wheez/.test(text);
  const hasNeuro = /confusion|faint|seizure|dizziness|stroke/.test(text);
  const hasPregnancy = /pregnan|missed period|vaginal bleeding/.test(text);

  if (hasCardiac) return "cardiac";
  if (hasRespiratory) return "respiratory";
  if (hasNeuro) return "neurology";
  if (hasPregnancy) return "pregnancy";
  if (hasFever && hasGI) return "infectious_gi";
  if (hasFever) return "infectious";
  if (hasGI) return "gastrointestinal";
  return "general";
};

export const fallbackModulesForCategory = (category) => {
  const categoryModules = {
    infectious: ["FeverClinicalCard", "MedicationCard"],
    infectious_gi: ["FeverClinicalCard", "GastrointestinalCard", "HydrationRiskCard", "MedicationCard"],
    gastrointestinal: ["GastrointestinalCard", "HydrationRiskCard", "MedicationCard"],
    cardiac: ["CardiacRiskCard", "RespiratoryRiskCard", "MedicationCard"],
    respiratory: ["RespiratoryRiskCard", "CardiacRiskCard", "MedicationCard"],
    neurology: ["NeurologyRiskCard", "MedicationCard"],
    pregnancy: ["PregnancyRiskCard", "MedicationCard"],
    general: ["MedicationCard"],
  };

  return [
    "GeneralSnapshotCard",
    "TriageAlertsCard",
    "ClinicalCompletenessCard",
    "AIClinicalSummaryCard",
    ...(categoryModules[category] || categoryModules.general),
    "LabReportAnalysisCard",
    "TimelineCard",
    "RecommendedNextStepsCard",
    "ActionPanel",
  ];
};

const ensureModulesForFindings = (modules, state) => {
  const text = [
    state.chief_complaint,
    state.associated_symptoms.join(" "),
    state.temperature,
    state.breathing_difficulty,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  const additions = [];
  if (/fever|temperature/.test(text)) additions.push("FeverClinicalCard");
  if (/chest pain|chest pressure|sweating/.test(text)) additions.push("CardiacRiskCard");
  if (/cough|breath|shortness of breath|wheez/.test(text)) additions.push("RespiratoryRiskCard");
  if (/abdominal|stomach|vomit|nausea|diarrhea/.test(text)) additions.push("GastrointestinalCard", "HydrationRiskCard");
  if (/weakness|fatigue|dizziness|confusion|faint|seizure/.test(text)) additions.push("NeurologyRiskCard");

  const result = [];
  [...modules, ...additions].forEach((module) => {
    if (!result.includes(module)) result.push(module);
  });
  return result;
};

export function syncClinicalState(previousState, backendPayload = {}, context = {}) {
  const prev = previousState || createInitialClinicalState();
  const nlice = backendPayload?.nlice_data || {};
  const userText = context.userText || "";
  const lastAssistantText = context.lastAssistantText || "";
  const timestamp = context.time || new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

  const next = {
    ...prev,
    patient_info: {
      ...prev.patient_info,
      ...(backendPayload.patient_info || {}),
      name: firstValue(backendPayload.patient_name, backendPayload.patient?.name, prev.patient_info.name),
      age: firstValue(backendPayload.age, backendPayload.patient?.age, prev.patient_info.age),
      gender: firstValue(backendPayload.gender, backendPayload.patient?.gender, prev.patient_info.gender),
      language: firstValue(backendPayload.preferred_language, backendPayload.language, backendPayload.patient?.language, prev.patient_info.language),
      visit_time: firstValue(backendPayload.visit_time, backendPayload.visitTime, prev.patient_info.visit_time),
    },
    backend: backendPayload,
    is_complete: Boolean(backendPayload.is_complete),
  };

  const detectedTemperature = parseTemperature(backendPayload.temperature, nlice.excitation, userText);
  const detectedSeverity = parseSeverity(backendPayload.severity, nlice.intensity, userText);
  const detectedDuration = firstValue(backendPayload.duration, parseDuration(nlice.chronology, userText), nlice.chronology);
  const clinicalFields = backendPayload.clinical_fields || {};
  const detectedNegatives = detectNegativeFindings(userText, lastAssistantText);
  const detectedSymptoms = filterSymptomsByPolarity(
    mergeUnique(backendPayload.associated_symptoms || [], detectSymptoms(userText)),
    clinicalFields,
    detectedNegatives
  );
  const detectedMedications = mergeUnique(normalizeList(backendPayload.medications_taken), normalizeList(backendPayload.medications), detectMedications(userText, nlice.excitation));

  next.chief_complaint = firstValue(detectComplaint(backendPayload, userText), prev.chief_complaint);
  next.temperature = firstValue(detectedTemperature, prev.temperature);
  next.severity = firstValue(detectedSeverity, prev.severity);
  next.duration = firstValue(detectedDuration, prev.duration);
  next.associated_symptoms = filterSymptomsByPolarity(
    mergeUnique(prev.associated_symptoms, detectedSymptoms),
    clinicalFields,
    mergeUnique(prev.negative_findings || [], normalizeList(backendPayload.negative_findings), detectedNegatives)
  );
  next.negative_findings = mergeUnique(prev.negative_findings || [], normalizeList(backendPayload.negative_findings), detectedNegatives);
  next.breathing_difficulty = detectBreathingDifficulty(userText, lastAssistantText, firstValue(backendPayload.breathing_difficulty, backendPayload.breathingDifficulty, prev.breathing_difficulty));
  next.medications_taken = mergeUnique(prev.medications_taken, detectedMedications);
  next.clinical_fields = clinicalFields;
  next.medication_response = firstValue(backendPayload.medication_response, clinicalFields.medication_response, backendPayload.response, medicationResponse(userText, nlice.excitation), prev.medication_response);
  next.lab_report_analysis = {
    ...(prev.lab_report_analysis || {}),
    ...(backendPayload.lab_report_analysis || {}),
  };

  const urgency = scoreClinicalUrgency(next);
  next.triage_level = urgency.triage_level;
  next.triage_score = urgency.triage_score;
  next.red_flags = urgency.red_flags;
  next.clinical_category = backendPayload.clinical_category || classifyClinicalCategory(next);
  next.active_modules = ensureModulesForFindings(
    backendPayload.active_modules?.length ? backendPayload.active_modules : fallbackModulesForCategory(next.clinical_category),
    next
  );
  next.timeline = deriveTimeline(next, prev, userText, timestamp);
  next.ai_summary = generateClinicalSummary(next);
  next.clinical_analysis = {
    ...(backendPayload.clinical_analysis || {}),
    urgency: next.triage_level,
    score: next.triage_score,
    reason: next.red_flags.length ? next.red_flags.join("; ") : "No urgent red flags identified from captured intake.",
  };

  return next;
}
