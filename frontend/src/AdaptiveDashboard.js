import React from "react";
import { motion } from "framer-motion";
import { PatientInformationCard } from "./DashboardComponents";
import { MODULE_COMPONENTS, resolveActiveModules } from "./dashboardConfig";

export function AdaptiveClinicalDashboard({ data, messages, onExport, fallbackVisitTime }) {
  const clinicalData = data || {};
  const visitTime =
    clinicalData?.patient_info?.visit_time ||
    clinicalData?.visit_time ||
    clinicalData?.visitTime ||
    fallbackVisitTime ||
    new Date().toLocaleString([], {
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

  const activeModules = resolveActiveModules(clinicalData);

  return (
    <motion.div
      id="report-area"
      className="grid grid-cols-1 gap-4 lg:grid-cols-12"
      initial="initial"
      animate="animate"
      transition={{ staggerChildren: 0.04 }}
    >
      <PatientInformationCard patient={patient} visitTime={visitTime} />

      {activeModules.map((moduleName) => {
        const Component = MODULE_COMPONENTS[moduleName];
        return (
          <Component
            key={moduleName}
            data={clinicalData}
            analysis={clinicalData?.clinical_analysis}
            messages={messages}
            onExport={onExport}
            canExport={Boolean(data)}
          />
        );
      })}

      <div className="lg:col-span-12 text-center text-xs text-slate-500">
        SevaCare AI is not a substitute for professional medical advice.
      </div>
    </motion.div>
  );
}
