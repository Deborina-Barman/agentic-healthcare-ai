import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  FinalSummaryView,
  NLICETracker,
  RAGIntelligenceBox,
  UrgencyBadge,
} from "./DashboardComponents";

const API_BASE_URL = "http://localhost:8000";

const initialUnifiedResponse = {
  message: "Tell me what symptom or concern brought you in today.",
  nlice_data: {
    nature: "",
    location: "",
    intensity: "",
    chronology: "",
    excitation: "",
  },
  clinical_analysis: {
    urgency: "Low",
    score: 0,
    reason: "Awaiting clinical signal.",
  },
  rag_context: "",
  is_complete: false,
  step: "intake",
  summary: "",
};

function normalizePacket(json) {
  return json?.data || json || initialUnifiedResponse;
}

function App() {
  const [unifiedResponse, setUnifiedResponse] = useState(initialUnifiedResponse);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: initialUnifiedResponse.message,
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [summary, setSummary] = useState("");
  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  const isComplete = Boolean(unifiedResponse?.is_complete);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (isComplete) {
      fetchSummary();
    }
  }, [isComplete]);

  const statusLabel = useMemo(() => {
    if (isLoading) return "Processing";
    if (isComplete) return "Complete";
    return unifiedResponse?.step || "intake";
  }, [isLoading, isComplete, unifiedResponse?.step]);

  async function requestJson(path, options = {}) {
    const response = await fetch(`${API_BASE_URL}${path}`, options);
    const json = await response.json().catch(() => ({}));

    if (!response.ok || json.status === "error") {
      throw new Error(json.message || json.detail || "Backend request failed.");
    }

    return normalizePacket(json);
  }

  function absorbPacket(packet) {
    setUnifiedResponse((current) => ({
      ...current,
      ...packet,
      nlice_data: {
        ...current.nlice_data,
        ...(packet.nlice_data || {}),
      },
      clinical_analysis: {
        ...current.clinical_analysis,
        ...(packet.clinical_analysis || {}),
      },
    }));

    if (packet.message) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: packet.message,
        },
      ]);
    }

    if (packet.summary) {
      setSummary(packet.summary);
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    const userInput = input.trim();
    if (!userInput || isLoading) return;

    setInput("");
    setError("");
    setIsLoading(true);
    setMessages((current) => [...current, { role: "user", content: userInput }]);

    try {
      const packet = await requestJson("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_input: userInput,
          session_id: "default",
        }),
      });
      absorbPacket(packet);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  async function uploadImage(event) {
    const file = event.target.files?.[0];
    if (!file || isLoading) return;

    const formData = new FormData();
    formData.append("file", file);

    setError("");
    setIsLoading(true);
    setMessages((current) => [
      ...current,
      { role: "user", content: `Uploaded image: ${file.name}` },
    ]);

    try {
      const packet = await requestJson("/upload", {
        method: "POST",
        body: formData,
      });
      absorbPacket(packet);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function fetchSummary() {
    setError("");

    try {
      const packet = await requestJson("/summary");
      setSummary(packet.summary || "");
      setUnifiedResponse((current) => ({
        ...current,
        ...packet,
        summary: packet.summary || current.summary,
      }));
      setSummaryOpen(true);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function resetSession() {
    setError("");
    setIsLoading(true);

    try {
      const packet = await requestJson("/reset", { method: "POST" });
      setUnifiedResponse({ ...initialUnifiedResponse, ...packet });
      setMessages([
        {
          role: "assistant",
          content: packet.message || initialUnifiedResponse.message,
        },
      ]);
      setSummary("");
      setSummaryOpen(false);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  function downloadPdf() {
    window.print();
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-100 via-indigo-50 to-cyan-50 p-4 text-slate-900 sm:p-6 lg:p-8">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-7xl flex-col gap-5 lg:flex-row">
        <section className="flex w-full flex-col rounded-xl border border-white/70 bg-white/55 shadow-2xl shadow-slate-300/50 backdrop-blur-2xl lg:w-[40%]">
          <header className="border-b border-white/70 p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">
                  Clinical Intelligence
                </p>
                <h1 className="mt-2 text-2xl font-black text-slate-950">
                  Intake Console
                </h1>
              </div>
              <span className="rounded-full border border-indigo-100 bg-white/70 px-3 py-1 text-xs font-bold capitalize text-indigo-700">
                {statusLabel}
              </span>
            </div>
          </header>

          <div className="flex-1 space-y-4 overflow-y-auto p-5">
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[86%] rounded-xl px-4 py-3 text-sm leading-6 shadow-sm ${
                    message.role === "user"
                      ? "bg-indigo-600 text-white shadow-indigo-200"
                      : "border border-white/80 bg-white/80 text-slate-700"
                  }`}
                >
                  {message.content}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="rounded-xl border border-white/80 bg-white/80 px-4 py-3 text-sm text-slate-500 shadow-sm">
                  Analyzing clinical signal...
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {error && (
            <div className="mx-5 mb-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={sendMessage} className="border-t border-white/70 p-5">
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Type a symptom or answer..."
                className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white/80 px-4 py-3 text-sm outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
              >
                Send
              </button>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={uploadImage}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="rounded-xl border border-slate-200 bg-white/80 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-white"
              >
                Upload Image
              </button>
              <button
                type="button"
                onClick={fetchSummary}
                className="rounded-xl border border-indigo-100 bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-700 transition hover:bg-indigo-100"
              >
                Summary
              </button>
              <button
                type="button"
                onClick={resetSession}
                className="rounded-xl border border-slate-200 bg-white/80 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-white"
              >
                Reset
              </button>
            </div>
          </form>
        </section>

        <section className="flex w-full flex-col gap-5 lg:w-[60%]">
          <UrgencyBadge analysis={unifiedResponse.clinical_analysis} />
          <NLICETracker nliceData={unifiedResponse.nlice_data} />
          <RAGIntelligenceBox ragContext={unifiedResponse.rag_context} />

          <section className="rounded-xl border border-white/70 bg-white/70 p-5 shadow-xl shadow-slate-200/60 backdrop-blur-xl">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Session State
                </p>
                <h2 className="mt-1 text-lg font-bold text-slate-900">
                  {isComplete ? "Ready for clinician review" : "Collecting intake data"}
                </h2>
              </div>
              <button
                type="button"
                onClick={fetchSummary}
                disabled={!isComplete && !summary}
                className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-slate-300 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
              >
                Open Report
              </button>
            </div>
          </section>
        </section>
      </div>

      <FinalSummaryView
        isOpen={summaryOpen}
        summary={summary || unifiedResponse.summary}
        onClose={() => setSummaryOpen(false)}
        onDownload={downloadPdf}
      />
    </main>
  );
}

export default App;
