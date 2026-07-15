import {
  ActionPanel,
  AIClinicalSummaryCard,
  ClinicalCompletenessCard,
  ClinicalSnapshotCard,
  LabReportAnalysisCard,
  RecommendedNextStepsCard,
  TimelineCard,
  TriageAlertsCard,
} from "./DashboardComponents";
import {
  CardiacRiskCard,
  FeverClinicalCard,
  GastrointestinalCard,
  HydrationRiskCard,
  MedicationCard,
  NeurologyRiskCard,
  PregnancyRiskCard,
  RespiratoryRiskCard,
} from "./ClinicalModules";

export const CATEGORY_MODULES = {
  general: ["GeneralSnapshotCard", "TriageAlertsCard", "ClinicalCompletenessCard", "AIClinicalSummaryCard", "MedicationCard", "LabReportAnalysisCard", "TimelineCard", "RecommendedNextStepsCard", "ActionPanel"],
  infectious: ["GeneralSnapshotCard", "TriageAlertsCard", "ClinicalCompletenessCard", "AIClinicalSummaryCard", "FeverClinicalCard", "MedicationCard", "LabReportAnalysisCard", "TimelineCard", "RecommendedNextStepsCard", "ActionPanel"],
  infectious_gi: ["GeneralSnapshotCard", "TriageAlertsCard", "ClinicalCompletenessCard", "AIClinicalSummaryCard", "FeverClinicalCard", "GastrointestinalCard", "HydrationRiskCard", "MedicationCard", "LabReportAnalysisCard", "TimelineCard", "RecommendedNextStepsCard", "ActionPanel"],
  gastrointestinal: ["GeneralSnapshotCard", "TriageAlertsCard", "ClinicalCompletenessCard", "AIClinicalSummaryCard", "GastrointestinalCard", "HydrationRiskCard", "MedicationCard", "LabReportAnalysisCard", "TimelineCard", "RecommendedNextStepsCard", "ActionPanel"],
  cardiac: ["GeneralSnapshotCard", "TriageAlertsCard", "ClinicalCompletenessCard", "AIClinicalSummaryCard", "CardiacRiskCard", "RespiratoryRiskCard", "MedicationCard", "LabReportAnalysisCard", "TimelineCard", "RecommendedNextStepsCard", "ActionPanel"],
  respiratory: ["GeneralSnapshotCard", "TriageAlertsCard", "ClinicalCompletenessCard", "AIClinicalSummaryCard", "RespiratoryRiskCard", "CardiacRiskCard", "MedicationCard", "LabReportAnalysisCard", "TimelineCard", "RecommendedNextStepsCard", "ActionPanel"],
  neurology: ["GeneralSnapshotCard", "TriageAlertsCard", "ClinicalCompletenessCard", "AIClinicalSummaryCard", "NeurologyRiskCard", "MedicationCard", "LabReportAnalysisCard", "TimelineCard", "RecommendedNextStepsCard", "ActionPanel"],
  pregnancy: ["GeneralSnapshotCard", "TriageAlertsCard", "ClinicalCompletenessCard", "AIClinicalSummaryCard", "PregnancyRiskCard", "MedicationCard", "LabReportAnalysisCard", "TimelineCard", "RecommendedNextStepsCard", "ActionPanel"],
};

export const MODULE_COMPONENTS = {
  GeneralSnapshotCard: ClinicalSnapshotCard,
  TriageAlertsCard,
  ClinicalCompletenessCard,
  AIClinicalSummaryCard,
  LabReportAnalysisCard,
  FeverClinicalCard,
  CardiacRiskCard,
  RespiratoryRiskCard,
  GastrointestinalCard,
  MedicationCard,
  HydrationRiskCard,
  NeurologyRiskCard,
  PregnancyRiskCard,
  TimelineCard,
  RecommendedNextStepsCard,
  ActionPanel,
};

export const resolveActiveModules = (clinicalData) => {
  const category = clinicalData?.clinical_category || "general";
  const requested = clinicalData?.active_modules?.length ? clinicalData.active_modules : CATEGORY_MODULES[category] || CATEGORY_MODULES.general;
  const deduped = [];

  requested.forEach((moduleName) => {
    if (MODULE_COMPONENTS[moduleName] && !deduped.includes(moduleName)) {
      deduped.push(moduleName);
    }
  });

  return deduped.length ? deduped : CATEGORY_MODULES.general;
};
