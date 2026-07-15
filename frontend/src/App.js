import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  Bell,
  ChevronLeft,
  Download,
  FileText,
  Globe2,
  History,
  LayoutDashboard,
  Mic,
  Moon,
  NotebookPen,
  RefreshCw,
  Send,
  Settings,
  ShieldCheck,
  Trash2,
  UserRound,
  Upload,
  Volume2,
} from "lucide-react";
import jsPDF from "jspdf";
import html2canvas from "html2canvas";
import { AdaptiveClinicalDashboard } from "./AdaptiveDashboard";
import { createInitialClinicalState, formatVisitTime, syncClinicalState } from "./clinicalState";

const nowTime = () => new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const VOICE_MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm"];
const VOICE_FALLBACK_MIME_TYPE = "audio/webm";
const VOICE_CHUNK_INTERVAL_MS = 1000;
const VOICE_LANGUAGE_CODES = {
  English: "en",
  Hindi: "hi",
  Bengali: "bn",
};
const VOICE_STATUS = {
  IDLE: "idle",
  LISTENING: "listening",
  TRANSCRIBING: "transcribing",
  SPEAKING: "speaking",
};

const sessionGroup = (dateValue) => {
  const date = new Date(dateValue);
  if (Number.isNaN(date.getTime())) return "Older";
  const today = new Date();
  const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const dayDifference = Math.floor((startToday - new Date(date.getFullYear(), date.getMonth(), date.getDate())) / 86400000);
  if (dayDifference === 0) return "Today";
  if (dayDifference === 1) return "Yesterday";
  if (dayDifference <= 7) return "Previous 7 Days";
  return "Older";
};

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [data, setData] = useState(null);
  const [voiceStatus, setVoiceStatus] = useState("idle");
  const [loading, setLoading] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [showPatientModal, setShowPatientModal] = useState(true);
  const [patientDraft, setPatientDraft] = useState({
    name: "",
    age: "",
    gender: "",
    language: "Hindi",
  });
  const [history, setHistory] = useState(() => JSON.parse(localStorage.getItem("clinical_history") || "[]"));
  const [uploadingReport, setUploadingReport] = useState(false);
  const [resettingSession, setResettingSession] = useState(false);
  const [isHistoryView, setIsHistoryView] = useState(false);
  const [sessionError, setSessionError] = useState("");
  const [showAllHistory, setShowAllHistory] = useState(false);

  const chatEndRef = useRef(null);
  const reportInputRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordingStartedAtRef = useRef(null);
  const mountedRef = useRef(true);
  const savedCompletionRef = useRef(null);
  const stopRequestedRef = useRef(false);
  const voiceStatusRef = useRef(VOICE_STATUS.IDLE);
  const voiceUploadInFlightRef = useRef(false);
  const chatRequestInFlightRef = useRef(false);
  const backendSessionIsFreshRef = useRef(false);

  const isRecording = voiceStatus === VOICE_STATUS.LISTENING;
  const isTranscribing = voiceStatus === VOICE_STATUS.TRANSCRIBING;
  const voiceStatusLabel = isRecording ? "Listening" : isTranscribing ? "Processing" : voiceStatus === VOICE_STATUS.SPEAKING ? "Speaking" : "Ready";
  const visibleHistory = showAllHistory ? history : history.slice(0, 5);
  const groupedHistory = visibleHistory.reduce((groups, item) => {
    const group = sessionGroup(item.date);
    groups[group] = [...(groups[group] || []), item];
    return groups;
  }, {});
  const interactionDisabled = loading || resettingSession || isHistoryView;
  const navigationItems = [
    [LayoutDashboard, "Dashboard"],
    [History, "Conversation"],
    [UserRound, "Patient"],
    [Activity, "Timeline"],
    [FileText, "Reports"],
    [NotebookPen, "Notes"],
    [Bell, "Alerts"],
  ];
  const micButtonClass = isRecording
    ? "bg-red-500 shadow-red-200"
    : isTranscribing
      ? "bg-amber-400 shadow-amber-200"
      : "bg-indigo-600 shadow-indigo-200";

  const setVoicePhase = useCallback((nextStatus) => {
    voiceStatusRef.current = nextStatus;
    if (mountedRef.current) {
      setVoiceStatus(nextStatus);
    }
  }, []);

  const stopMediaStream = useCallback((stream = mediaStreamRef.current) => {
    stream?.getTracks().forEach((track) => track.stop());
    if (stream === mediaStreamRef.current) {
      mediaStreamRef.current = null;
    }
  }, []);

  const selectedVoiceLanguage = useMemo(() => {
    const selectedLanguage =
      patientDraft.language || data?.patient_info?.language || data?.preferred_language || data?.language || data?.patient?.language;
    return VOICE_LANGUAGE_CODES[selectedLanguage] || "";
  }, [data, patientDraft.language]);

  const activeVisitTime = useMemo(() => {
    if (history[0]?.date) return history[0].date;
    return formatVisitTime();
  }, [history]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    mountedRef.current = true;
    console.log("APP MOUNTED: mountedRef =", mountedRef.current);

    return () => {
      mountedRef.current = false;
      console.log("APP UNMOUNT CLEANUP: mountedRef =", mountedRef.current);
      stopRequestedRef.current = true;
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
      stopMediaStream();
    };
  }, [stopMediaStream]);

  useEffect(() => {
    if (data?.is_complete && savedCompletionRef.current !== data) {
      savedCompletionRef.current = data;
      const newEntry = {
        id: Date.now(),
        date: new Date().toLocaleString(),
        summary: data,
      };
      setHistory((currentHistory) => {
        const updatedHistory = [newEntry, ...currentHistory.slice(0, 9)];
        localStorage.setItem("clinical_history", JSON.stringify(updatedHistory));
        return updatedHistory;
      });
    }
  }, [data]);

  const handleSend = async () => {
    if (interactionDisabled || chatRequestInFlightRef.current) return;
    if (!input.trim()) return;
    if (!data) {
      setShowPatientModal(true);
      return;
    }

    const userMsg = input.trim();
    const userTime = nowTime();
    const lastAssistantText = messages.slice().reverse().find((message) => message.role === "assistant")?.text || "";
    chatRequestInFlightRef.current = true;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: userMsg, time: userTime }]);
    setLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_input: userMsg }),
      });

      const result = await response.json();

      if (result.status === "success") {
        const backendData = result.data;
        const assistantTime = nowTime();
        setMessages((prev) => [...prev, { role: "assistant", text: backendData.message, time: assistantTime }]);
        setData((previousState) =>
          syncClinicalState(previousState, backendData, {
            userText: userMsg,
            lastAssistantText,
            time: userTime,
          })
        );
      }
    } catch (error) {
      console.error("SevaCare Connection Error:", error);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Connection error. Please check if backend is running.", time: nowTime() },
      ]);
    } finally {
      chatRequestInFlightRef.current = false;
      setLoading(false);
    }
  };

  const handleReportUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file || !data || interactionDisabled) return;

    const uploadTime = nowTime();
    const formData = new FormData();
    formData.append("file", file);
    setUploadingReport(true);
    setMessages((prev) => [...prev, { role: "user", text: `Uploaded medical report: ${file.name}`, time: uploadTime }]);

    try {
      const response = await fetch("http://127.0.0.1:8000/upload", {
        method: "POST",
        body: formData,
      });
      const result = await response.json();

      if (result.status === "success") {
        const backendData = result.data;
        const assistantTime = nowTime();
        setMessages((prev) => [...prev, { role: "assistant", text: backendData.message || "Medical report analyzed.", time: assistantTime }]);
        setData((previousState) =>
          syncClinicalState(previousState, backendData, {
            userText: `Uploaded medical report: ${file.name}`,
            lastAssistantText: "",
            time: uploadTime,
          })
        );
      }
    } catch (error) {
      console.error("Report upload failed:", error);
      setMessages((prev) => [...prev, { role: "assistant", text: "Report upload failed. Please try again.", time: nowTime() }]);
    } finally {
      setUploadingReport(false);
      if (reportInputRef.current) reportInputRef.current.value = "";
    }
  };

  const startRecording = async () => {

    console.log("START RECORDING");
    if (interactionDisabled || voiceStatusRef.current !== VOICE_STATUS.IDLE || mediaRecorderRef.current) return;

    stopRequestedRef.current = false;
    audioChunksRef.current = [];
    setVoicePhase(VOICE_STATUS.LISTENING);

    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        throw new Error("Voice recording is not supported in this browser.");
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });
      const supportedMimeType = VOICE_MIME_TYPES.find((mimeType) => MediaRecorder.isTypeSupported(mimeType));
      const recorderOptions = supportedMimeType ? { mimeType: supportedMimeType } : undefined;
      const recorder = new MediaRecorder(stream, recorderOptions);
      console.log("RECORDER CREATED");
      console.log("VOICE MIME:", recorder.mimeType || supportedMimeType || VOICE_FALLBACK_MIME_TYPE);


      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) {
          console.log("AUDIO CHUNK", {
            size: event.data.size,
            type: event.data.type,
          });
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = (event) => {
        console.error("Voice recorder error:", event.error);
        stopMediaStream(stream);
        if (mediaRecorderRef.current === recorder) {
          mediaRecorderRef.current = null;
        }
        audioChunksRef.current = [];
        setVoicePhase(VOICE_STATUS.IDLE);
      };

      recorder.onstop = async () => {
        const audioChunks = audioChunksRef.current;
        const recordingDurationMs = recordingStartedAtRef.current ? Date.now() - recordingStartedAtRef.current : 0;

        console.log("ONSTOP FIRED");
        console.log("AUDIO CHUNKS:", audioChunks.length);
        console.log("RECORDING DURATION MS:", recordingDurationMs);

        audioChunksRef.current = [];
        recordingStartedAtRef.current = null;
        stopRequestedRef.current = false;
        stopMediaStream(stream);

        if (mediaRecorderRef.current === recorder) {
          mediaRecorderRef.current = null;
        }

        if (!audioChunks.length) {
          setVoicePhase(VOICE_STATUS.IDLE);
          return;
        }

        console.log("ONSTOP mountedRef:", mountedRef.current);
        if (!mountedRef.current) {
          console.warn("VOICE UPLOAD SKIPPED: component is unmounted");
          return;
        }

        setVoicePhase(VOICE_STATUS.TRANSCRIBING);

        const audioMimeType = recorder.mimeType || VOICE_FALLBACK_MIME_TYPE;
        const audioBlob = new Blob(audioChunks, { type: audioMimeType });
        console.log("AUDIO BLOB READY", {
          size: audioBlob.size,
          type: audioBlob.type,
        });
        console.log("CALLING sendAudioToBackend");
        await sendAudioToBackend(audioBlob);
      };

      recordingStartedAtRef.current = Date.now();
      recorder.start(VOICE_CHUNK_INTERVAL_MS);
      console.log("RECORDER STARTED", recorder.state);

      if (stopRequestedRef.current && recorder.state === "recording") {
        recorder.stop();
      }
    } catch (error) {
      console.error("Microphone error:", error);
      stopMediaStream();
      alert(error.message);
      mediaRecorderRef.current = null;
      audioChunksRef.current = [];
      recordingStartedAtRef.current = null;
      stopRequestedRef.current = false;
      setVoicePhase(VOICE_STATUS.IDLE);
    }
  };

  const stopRecording = () => {
    stopRequestedRef.current = true;
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") return;
    setVoicePhase(VOICE_STATUS.TRANSCRIBING);
    recorder.stop();
  };

  const toggleRecording = () => {
    console.log("TOGGLE", voiceStatusRef.current, mediaRecorderRef.current?.state);
    if (interactionDisabled && !isRecording) return;
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      stopRecording();
      return;
    }

    if (voiceStatusRef.current === VOICE_STATUS.LISTENING) {
      stopRequestedRef.current = true;
      setVoicePhase(VOICE_STATUS.TRANSCRIBING);
      return;
    }

    if (voiceStatusRef.current === VOICE_STATUS.IDLE) {
      startRecording();
    }
  };

  const sendAudioToBackend = async (audioBlob) => {

    console.log("UPLOADING AUDIO", audioBlob.size);
    if (voiceUploadInFlightRef.current) {
      console.warn("VOICE UPLOAD SKIPPED: upload already in flight");
      return;
    }

    voiceUploadInFlightRef.current = true;

    try {
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");
      if (selectedVoiceLanguage) {
        formData.append("language", selectedVoiceLanguage);
      }

      console.log("VOICE LANGUAGE", selectedVoiceLanguage || "auto");

      const response = await fetch("http://127.0.0.1:8000/voice", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Voice transcription failed with status ${response.status}`);
      }

     
      const result = await response.json();
      console.log("VOICE RESULT", result);
  
      if (result.transcription && mountedRef.current) {
        setInput(result.transcription.trim());
      }
    } catch (error) {
      console.error("Voice upload failed:", error);
    } finally {
      voiceUploadInFlightRef.current = false;
      setVoicePhase(VOICE_STATUS.IDLE);
    }
  };

  const exportPDF = () => {
    const element = document.getElementById("report-area");
    if (!element) return alert("No report generated yet!");

    html2canvas(element, { scale: 2 }).then((canvas) => {
      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF("p", "mm", "a4");
      const imgProps = pdf.getImageProperties(imgData);
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;
      pdf.addImage(imgData, "PNG", 0, 0, pdfWidth, pdfHeight);
      pdf.save(`Clinical_Report_${Date.now()}.pdf`);
    });
  };

  const resetBackendSession = async () => {
    const response = await fetch("http://127.0.0.1:8000/reset", {
      method: "POST",
    });
    const result = await response.json().catch(() => ({}));

    if (!response.ok || result.status !== "success") {
      throw new Error(result.message || "Could not start a fresh clinical session.");
    }

    backendSessionIsFreshRef.current = true;
  };

  const resetSession = async () => {
    if (loading || resettingSession) return;
    setResettingSession(true);
    setSessionError("");
    try {
      await resetBackendSession();
      // Do not reveal a new local intake until FastAPI has created its fresh controller.
      setMessages([]);
      setInput("");
      setData(null);
      savedCompletionRef.current = null;
      setIsHistoryView(false);
      setPatientDraft({ name: "", age: "", gender: "", language: "Hindi" });
      setShowPatientModal(true);
    } catch (err) {
      console.error("Failed to reset backend:", err);
      setSessionError(err.message || "Could not start a fresh clinical session.");
    } finally {
      setResettingSession(false);
    }
  };

  const selectHistory = (item) => {
    if (loading || resettingSession) return;
    setData(item.summary);
    setMessages([]);
    setInput("");
    setIsHistoryView(true);
    setSessionError("");
    setShowPatientModal(false);
  };

  const initializePatientSession = async (event) => {
    event.preventDefault();
    if (loading || resettingSession) return;
    setResettingSession(true);
    setSessionError("");

    try {
      // Initial page loads have no prior New Patient click, so reset here as well.
      if (!backendSessionIsFreshRef.current) {
        await resetBackendSession();
      }
      backendSessionIsFreshRef.current = false;
      savedCompletionRef.current = null;
      setIsHistoryView(false);
      setInput("");
      setMessages([]);
      // This is deliberately after /reset succeeds, keeping both session states aligned.
      setData(
        createInitialClinicalState({
          name: patientDraft.name.trim(),
          age: patientDraft.age.trim(),
          gender: patientDraft.gender,
          language: patientDraft.language.trim() || "Hindi",
          visit_time: formatVisitTime(),
        })
      );
      setShowPatientModal(false);
    } catch (err) {
      console.error("Failed to initialize patient session:", err);
      setSessionError(err.message || "Could not start a fresh clinical session.");
    } finally {
      setResettingSession(false);
    }
  };

  return (
    <div className={`${darkMode ? "dark" : ""}`}>
      <div className="min-h-screen bg-slate-50 text-slate-950">
        <header className="sticky top-0 z-30 flex h-[72px] items-center justify-between border-b border-slate-200/80 bg-white/95 px-4 shadow-sm shadow-slate-200/40 backdrop-blur-xl lg:px-7">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#5B5CEB] text-white shadow-lg shadow-indigo-200">
              <Activity size={19} />
            </div>
            <div>
              <h1 className="text-lg font-black tracking-tight">
                SevaCare <span className="text-[#5B5CEB]">AI</span>
              </h1>
              <p className="hidden text-[11px] font-medium text-slate-500 sm:block">Clinical Intake Platform</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
              <span className="hidden items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 xl:inline-flex">
              <Globe2 size={15} />
              Multilingual Voice Enabled
            </span>
            <button className="hidden items-center gap-2 rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700 transition hover:bg-emerald-100 sm:inline-flex">
              <Mic size={15} />
              Voice On
            </button>
            <button
              onClick={() => setDarkMode(!darkMode)}
              className="grid h-9 w-9 place-items-center rounded-xl border border-slate-200 text-indigo-600 transition hover:bg-indigo-50"
              title="Toggle theme"
            >
              <Moon size={17} />
            </button>
            <button
              onClick={resetSession}
              disabled={loading || resettingSession}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw size={15} />
              <span className="hidden sm:inline">New Patient</span>
            </button>
            <button
              onClick={exportPDF}
              disabled={!data}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-bold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50 sm:px-4"
            >
              <Download size={15} />
              Export SOAP PDF
            </button>
          </div>
        </header>

        <main className="grid h-[calc(100vh-72px)] grid-cols-1 overflow-hidden lg:grid-cols-[250px_minmax(360px,450px)_1fr]">
          <aside className="hidden border-r border-slate-200/80 bg-white lg:flex lg:flex-col">
            <nav className="space-y-1 px-3 py-5">
              {navigationItems.map(([Icon, label], index) => (
                <button
                  type="button"
                  key={label}
                  className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-semibold transition ${
                    index === 0 ? "border-l-2 border-[#5B5CEB] bg-indigo-50 text-[#4d4ed8]" : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"
                  }`}
                >
                  <Icon size={18} />
                  {label}
                </button>
              ))}
            </nav>

            <div className="mx-4 border-t border-slate-100" />
            <div className="flex items-center justify-between px-5 pb-3 pt-5">
              <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[0.12em] text-slate-500">
                <History size={15} />
                Recent sessions
              </div>
              <button
                onClick={() => {
                  setHistory([]);
                  localStorage.removeItem("clinical_history");
                }}
                className="text-rose-400 transition hover:text-rose-600"
                title="Clear History"
              >
                <Trash2 size={15} />
              </button>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto px-3">
              {history.length === 0 && (
                <div className="rounded-xl border border-dashed border-slate-200 p-4 text-xs text-slate-500">
                  Completed clinical intakes will appear here.
                </div>
              )}
              {["Today", "Yesterday", "Previous 7 Days", "Older"].map((group) => groupedHistory[group]?.length ? (
                <div key={group} className="space-y-2">
                  <p className="px-1 text-[10px] font-black uppercase tracking-[0.12em] text-slate-400">{group}</p>
                  {groupedHistory[group].map((item) => (
                    <button
                      key={item.id}
                      onClick={() => selectHistory(item)}
                      className={`w-full rounded-xl p-4 text-left text-xs transition hover:bg-indigo-50 ${
                        item.id === history[0]?.id ? "border-l-4 border-indigo-600 bg-indigo-50" : "bg-white"
                      }`}
                    >
                      <p className="font-bold text-slate-900">{item.date}</p>
                      <p className="mt-1 truncate font-semibold text-slate-600">
                        {item.summary?.chief_complaint || item.summary?.backend?.nlice_data?.nature || item.summary?.complaint || "Clinical Entry"}
                      </p>
                    </button>
                  ))}
                </div>
              ) : null)}
              {history.length > 5 && <button onClick={() => setShowAllHistory((visible) => !visible)} className="w-full rounded-lg px-3 py-2 text-xs font-bold text-indigo-700 transition hover:bg-indigo-50">{showAllHistory ? "Show Recent" : "View All"}</button>}
            </div>

            <div className="border-t border-slate-100 p-4">
              <div className="mb-4 rounded-xl border border-rose-100 bg-rose-50/60 p-3 text-[11px] leading-5 text-slate-600">
                <div className="mb-1 flex items-center gap-2 font-bold text-rose-700"><ShieldCheck size={14} /> Clinical guidance</div>
                SevaCare AI supports intake and does not replace professional clinical judgment.
              </div>
              <button className="flex items-center gap-2 text-xs font-semibold text-slate-500">
                <Settings size={16} />
                Settings
              </button>
            </div>
          </aside>

          <section className="flex min-h-0 flex-col border-r border-slate-200 bg-white">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-4">
              <div className="flex items-center gap-3">
                <ChevronLeft size={17} className="text-slate-500" />
                <h2 className="text-sm font-black">{isHistoryView ? "Session History" : "Live Conversation"}</h2>
                <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-bold ${isHistoryView ? "border-amber-100 bg-amber-50 text-amber-700" : "border-emerald-100 bg-emerald-50 text-emerald-700"}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${isHistoryView ? "bg-amber-500" : "bg-emerald-500"}`} />
                  {isHistoryView ? "Read-only" : "Live"}
                </span>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto bg-slate-50/60 px-5 py-5">
              {isHistoryView && (
                <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-800">
                  This completed session is a local history preview. Start a new patient session to continue the clinical conversation.
                </div>
              )}
              {messages.length === 0 && (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <div className="grid h-14 w-14 place-items-center rounded-2xl bg-indigo-50 text-indigo-600">
                    <Activity size={28} />
                  </div>
                  <p className="mt-4 max-w-xs text-sm font-semibold text-slate-700">Start a clinical intake by describing the patient's primary symptom.</p>
                </div>
              )}

              <AnimatePresence initial={false}>
                {messages.map((message, index) => (
                  <motion.div
                    key={`${message.role}-${index}-${message.text}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className={`mb-5 flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    {message.role === "assistant" && (
                      <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-indigo-100 text-indigo-600">
                        <Activity size={17} />
                      </div>
                    )}
                    <div className={`max-w-[78%] ${message.role === "user" ? "text-right" : "text-left"}`}>
                      <div
                        className={`rounded-2xl px-4 py-3 text-sm leading-5 shadow-sm ${
                          message.role === "user"
                            ? "rounded-tr-md bg-indigo-100 text-slate-900"
                            : "rounded-tl-md border border-slate-200 bg-white text-slate-900"
                        }`}
                      >
                        {message.text}
                      </div>
                      <p className="mt-1 text-xs font-medium text-slate-400">{message.time}</p>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>

              {loading && (
                <div className="flex items-center gap-2 text-xs font-semibold text-indigo-600">
                  <Activity size={14} className="animate-pulse" />
                  Analyzing clinical context...
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <div className="border-t border-slate-200 bg-white p-4">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_8px_24px_rgba(15,23,42,0.06)]">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-black text-slate-950"><Mic size={16} className="text-[#5B5CEB]" /> Voice Assistant</div>
                    <p className="mt-1 text-xs text-slate-500">Speak naturally or continue by text.</p>
                  </div>
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ${isRecording ? "bg-red-50 text-red-600" : isTranscribing ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${isRecording ? "bg-red-500 animate-pulse" : isTranscribing ? "bg-amber-500" : "bg-emerald-500"}`} />
                    {voiceStatusLabel}
                  </span>
                </div>
                <div className="mb-4 flex items-center justify-between gap-2">
                  <input ref={reportInputRef} type="file" accept="image/*,.pdf" className="hidden" onChange={handleReportUpload} />
                  <button
                    onClick={() => reportInputRef.current?.click()}
                    disabled={!data || uploadingReport || interactionDisabled}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-indigo-200 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Upload size={14} />
                    {uploadingReport ? "Analyzing..." : "Upload Report"}
                  </button>
                  <span className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700">
                    <Globe2 size={14} />
                    <span>Multilingual Voice Enabled:</span>
                    <span>English • Hindi • Bengali</span>
                  </span>
                </div>

                <div className="mb-2 flex items-center justify-center gap-3">
                  <div
                    className={`h-8 flex-1 rounded-full opacity-60 ${
                      isRecording
                        ? "bg-[repeating-linear-gradient(90deg,#ef4444_0_2px,transparent_2px_9px)]"
                        : isTranscribing
                          ? "bg-[repeating-linear-gradient(90deg,#f59e0b_0_2px,transparent_2px_9px)]"
                          : "bg-[repeating-linear-gradient(90deg,#4f46e5_0_2px,transparent_2px_9px)]"
                    }`}
                  />
                  <button
                    onClick={toggleRecording}
                    disabled={isTranscribing || interactionDisabled}
                    title={voiceStatusLabel}
                    aria-label={isRecording ? "Stop recording" : "Start voice recording"}
                    className={`grid h-[72px] w-[72px] shrink-0 place-items-center rounded-full text-white shadow-xl ring-4 ring-indigo-50 transition hover:scale-105 disabled:cursor-wait disabled:hover:scale-100 ${micButtonClass}`}
                  >
                    <Mic size={25} className={isTranscribing ? "animate-pulse" : ""} />
                  </button>
                  <div
                    className={`h-8 flex-1 rounded-full opacity-60 ${
                      isRecording
                        ? "bg-[repeating-linear-gradient(90deg,#ef4444_0_2px,transparent_2px_9px)]"
                        : isTranscribing
                          ? "bg-[repeating-linear-gradient(90deg,#f59e0b_0_2px,transparent_2px_9px)]"
                          : "bg-[repeating-linear-gradient(90deg,#4f46e5_0_2px,transparent_2px_9px)]"
                    }`}
                  />
                </div>

                <div className="mb-3 text-center text-xs font-bold text-slate-500">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 ${
                      isRecording
                        ? "bg-red-50 text-red-600"
                        : isTranscribing
                          ? "bg-amber-50 text-amber-700"
                          : "bg-indigo-50 text-indigo-700"
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        isRecording ? "bg-red-500" : isTranscribing ? "bg-amber-500" : "bg-indigo-500"
                      }`}
                    />
                    {voiceStatusLabel}
                  </span>
                </div>

                <div className="relative">
                  <Volume2 size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={(event) => event.key === "Enter" && handleSend()}
                    disabled={interactionDisabled}
                    placeholder={isHistoryView ? "History preview is read-only" : "Click the mic and speak or type your message..."}
                    className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-12 text-sm outline-none transition placeholder:text-slate-400 focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:bg-slate-100"
                  />
                  <button
                    onClick={handleSend}
                    disabled={interactionDisabled || !input.trim()}
                    className="absolute right-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-slate-900 transition hover:bg-indigo-50 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <Send size={18} />
                  </button>
                </div>
              </div>
            </div>
          </section>

          <section className="min-h-0 overflow-y-auto bg-slate-50 p-4 lg:p-5">
            <AdaptiveClinicalDashboard data={data} messages={messages} onExport={exportPDF} fallbackVisitTime={activeVisitTime} />
          </section>
        </main>

        <AnimatePresence>
          {showPatientModal && (
            <motion.div
              className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 px-4 backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <motion.form
                onSubmit={initializePatientSession}
                className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl shadow-slate-900/20"
                initial={{ opacity: 0, y: 24, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 16, scale: 0.98 }}
                transition={{ duration: 0.28, ease: "easeOut" }}
              >
                <div className="mb-6 flex items-start gap-4">
                  <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-indigo-100 text-indigo-700">
                    <UserRound size={24} />
                  </div>
                  <div>
                    <h2 className="text-xl font-black text-slate-950">Patient Intake</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-500">
                      Add patient details before starting the live clinical conversation.
                    </p>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="text-sm font-bold text-slate-700">
                    Patient Name
                    <input
                      value={patientDraft.name}
                      onChange={(event) => setPatientDraft((draft) => ({ ...draft, name: event.target.value }))}
                      placeholder="Ananya Sharma"
                      className="mt-2 h-11 w-full rounded-xl border border-slate-200 px-3 text-sm font-medium outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
                    />
                  </label>
                  <label className="text-sm font-bold text-slate-700">
                    Age
                    <input
                      value={patientDraft.age}
                      onChange={(event) => setPatientDraft((draft) => ({ ...draft, age: event.target.value }))}
                      placeholder="24"
                      inputMode="numeric"
                      className="mt-2 h-11 w-full rounded-xl border border-slate-200 px-3 text-sm font-medium outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
                    />
                  </label>
                  <label className="text-sm font-bold text-slate-700">
                    Gender
                    <select
                      value={patientDraft.gender}
                      onChange={(event) => setPatientDraft((draft) => ({ ...draft, gender: event.target.value }))}
                      className="mt-2 h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
                    >
                      <option value="">Select gender</option>
                      <option value="Female">Female</option>
                      <option value="Male">Male</option>
                      <option value="Other">Other</option>
                    </select>
                  </label>
                  <label className="text-sm font-bold text-slate-700">
                    Preferred Language
                    <select
                      value={patientDraft.language}
                      onChange={(event) => setPatientDraft((draft) => ({ ...draft, language: event.target.value }))}
                      className="mt-2 h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
                    >
                      <option value="Hindi">Hindi</option>
                      <option value="English">English</option>
                      <option value="Tamil">Tamil</option>
                      <option value="Telugu">Telugu</option>
                      <option value="Bengali">Bengali</option>
                    </select>
                  </label>
                </div>

                {sessionError && (
                  <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
                    {sessionError}
                  </div>
                )}

                <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                  <button
                    type="button"
                    onClick={() => {
                      if (data) setShowPatientModal(false);
                    }}
                    disabled={!data}
                    className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={resettingSession || loading}
                    className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {resettingSession ? "Starting session..." : "Start Clinical Session"}
                  </button>
                </div>
              </motion.form>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default App;
