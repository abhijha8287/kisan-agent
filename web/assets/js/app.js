import { prepareImage } from "./image.js";
import { renderMarkdown } from "./markdown.js";
import { readEventStream } from "./stream.js";

const STEPS = [
  { name: "diagnose", label: "Read the photo" },
  { name: "understand", label: "Understand the question" },
  { name: "research", label: "Research treatment, prices and weather" },
  { name: "advise", label: "Write the plan" },
];
const TOPIC_LABELS = { treatment: "Treatment", market: "Market", weather: "Weather" };
const PREFS_KEY = "kisan-agent:prefs";

const $ = (id) => document.getElementById(id);
const els = {
  form: $("consult-form"),
  photo: $("photo"),
  dropzone: $("dropzone"),
  dropzoneEmpty: $("dropzone-empty"),
  preview: $("photo-preview"),
  photoClear: $("photo-clear"),
  question: $("question"),
  mic: $("mic"),
  location: $("location"),
  language: $("language"),
  submit: $("submit"),
  formError: $("form-error"),
  empty: $("empty-state"),
  result: $("result"),
  trace: $("trace"),
  diagnosis: $("diagnosis"),
  advice: $("advice"),
  resultError: $("result-error"),
  sources: $("sources"),
  sourcesList: $("sources-list"),
};

let languages = [];
let photoFile = null;

init();

async function init() {
  try {
    const response = await fetch("/api/meta");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    ({ languages } = await response.json());
  } catch {
    languages = [{ name: "English", native_name: "English", speech_code: "en-IN" }];
  }
  for (const lang of languages) {
    const label = lang.name === lang.native_name ? lang.name : `${lang.native_name} (${lang.name})`;
    els.language.add(new Option(label, lang.name));
  }
  restorePrefs();
  bindPhoto();
  bindSpeech();
  els.form.addEventListener("submit", onSubmit);
}

// Preferences (per browser convenience only)

function restorePrefs() {
  try {
    const prefs = JSON.parse(localStorage.getItem(PREFS_KEY) || "{}");
    if (prefs.location) els.location.value = prefs.location;
    if (languages.some((l) => l.name === prefs.language)) els.language.value = prefs.language;
  } catch {
    /* storage unavailable */
  }
}

function savePrefs() {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify({ location: els.location.value, language: els.language.value }));
  } catch {
    /* storage unavailable */
  }
}

// Photo input

function bindPhoto() {
  els.photo.addEventListener("change", () => setPhoto(els.photo.files[0] ?? null));
  els.photoClear.addEventListener("click", () => setPhoto(null));
  for (const type of ["dragenter", "dragover"]) {
    els.dropzone.addEventListener(type, () => els.dropzone.classList.add("is-dragging"));
  }
  for (const type of ["dragleave", "drop"]) {
    els.dropzone.addEventListener(type, () => els.dropzone.classList.remove("is-dragging"));
  }
}

function setPhoto(file) {
  if (file && !file.type.startsWith("image/")) {
    showFormError("Please choose an image file.");
    return;
  }
  photoFile = file;
  if (els.preview.src) URL.revokeObjectURL(els.preview.src);
  if (file) {
    els.preview.src = URL.createObjectURL(file);
  } else {
    els.preview.removeAttribute("src");
    els.photo.value = "";
  }
  els.preview.hidden = !file;
  els.dropzoneEmpty.hidden = Boolean(file);
  els.photoClear.hidden = !file;
}

// Voice input via the browser's built-in speech recognition (Chrome, Edge, Safari)

function bindSpeech() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) return;

  let recognition = null;
  els.mic.hidden = false;
  els.mic.addEventListener("click", () => {
    if (recognition) {
      recognition.stop();
      return;
    }
    const lang = languages.find((l) => l.name === els.language.value);
    recognition = new Recognition();
    recognition.lang = lang?.speech_code ?? "en-IN";
    recognition.interimResults = true;

    const base = els.question.value.trim();
    recognition.onresult = (event) => {
      const spoken = Array.from(event.results, (r) => r[0].transcript).join(" ");
      els.question.value = [base, spoken].filter(Boolean).join(" ");
    };
    recognition.onerror = (event) => {
      if (event.error !== "aborted" && event.error !== "no-speech") {
        showFormError("Could not use the microphone. Please type your question.");
      }
    };
    recognition.onend = () => {
      recognition = null;
      els.mic.setAttribute("aria-pressed", "false");
    };
    els.mic.setAttribute("aria-pressed", "true");
    recognition.start();
  });
}

// Submission

async function onSubmit(event) {
  event.preventDefault();
  hideFormError();

  const question = els.question.value.trim();
  if (question.length < 3) {
    showFormError("Please describe the problem in a few words.");
    els.question.focus();
    return;
  }

  const body = new FormData();
  body.set("question", question);
  body.set("language", els.language.value);
  body.set("location", els.location.value.trim());
  savePrefs();

  setBusy(true);
  try {
    if (photoFile) body.set("image", await prepareImage(photoFile));
    resetResult(Boolean(photoFile));

    const response = await fetch("/api/consult", { method: "POST", body });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(formatApiError(detail) || `Request failed (${response.status})`);
    }
    await readEventStream(response, handleEvent);
  } catch (error) {
    showResultError(error.message || "Something went wrong. Please try again.");
  } finally {
    els.advice.classList.remove("is-streaming");
    setBusy(false);
  }
}

function formatApiError(detail) {
  if (typeof detail.detail === "string") return detail.detail;
  if (Array.isArray(detail.detail)) return detail.detail.map((d) => d.msg).join(". ");
  return "";
}

// Rendering of agent events

let adviceText = "";
let sourceIds = new Set();

function resetResult(hasPhoto) {
  adviceText = "";
  sourceIds = new Set();
  els.empty.hidden = true;
  els.result.hidden = false;
  els.diagnosis.hidden = true;
  els.sources.hidden = true;
  els.resultError.hidden = true;
  els.advice.innerHTML = "";
  els.sourcesList.innerHTML = "";
  els.trace.innerHTML = "";
  for (const step of STEPS) {
    const li = document.createElement("li");
    li.className = "trace__step";
    li.dataset.step = step.name;
    li.dataset.status = step.name === "diagnose" && !hasPhoto ? "skipped" : "pending";
    li.innerHTML = `
      <span class="trace__dot"></span>
      <span><span class="trace__label"></span> <span class="trace__model"></span></span>
      <span class="trace__time"></span>
      <span class="trace__detail"></span>`;
    li.querySelector(".trace__label").textContent = step.label;
    els.trace.append(li);
  }
}

function handleEvent(type, data) {
  switch (type) {
    case "step":
      return updateStep(data);
    case "diagnosis":
      return showDiagnosis(data);
    case "sources":
      return showSources(data.sources);
    case "token":
      adviceText += data.text;
      els.advice.classList.add("is-streaming");
      els.advice.innerHTML = renderMarkdown(adviceText, sourceIds);
      return;
    case "error":
      return showResultError(data.message);
  }
}

function updateStep({ name, status, model, detail, elapsed_ms }) {
  const li = els.trace.querySelector(`[data-step="${name}"]`);
  if (!li) return;
  li.dataset.status = status;
  if (model) li.querySelector(".trace__model").textContent = model;
  li.querySelector(".trace__detail").textContent = detail ?? "";
  li.querySelector(".trace__time").textContent = elapsed_ms != null ? `${(elapsed_ms / 1000).toFixed(1)}s` : "";
}

function showDiagnosis(d) {
  els.diagnosis.replaceChildren();
  const condition = document.createElement("div");
  condition.className = "diagnosis__condition";
  condition.textContent = d.is_plant ? [d.crop, d.condition].filter(Boolean).join(": ") : "This does not look like a plant photo";
  const meta = document.createElement("div");
  meta.className = "muted";
  meta.textContent = `Confidence: ${d.confidence}`;
  els.diagnosis.append(condition, meta);
  if (d.symptoms?.length) {
    const symptoms = document.createElement("div");
    symptoms.textContent = `Seen in photo: ${d.symptoms.join("; ")}`;
    els.diagnosis.append(symptoms);
  }
  els.diagnosis.hidden = false;
}

function showSources(sources) {
  sourceIds = new Set(sources.map((s) => s.id));
  els.sourcesList.replaceChildren(
    ...sources.map((s) => {
      const li = document.createElement("li");
      li.id = `source-${s.id}`;
      li.value = s.id;
      const link = document.createElement("a");
      link.href = s.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = s.title;
      const topic = document.createElement("span");
      topic.className = "sources__topic";
      topic.textContent = TOPIC_LABELS[s.topic] ?? s.topic;
      li.append(link, topic);
      return li;
    }),
  );
  els.sources.hidden = sources.length === 0;
}

// UI state helpers

function setBusy(busy) {
  els.submit.disabled = busy;
  els.submit.textContent = busy ? "Working…" : "Get advice";
}

function showFormError(message) {
  els.formError.textContent = message;
  els.formError.hidden = false;
}

function hideFormError() {
  els.formError.hidden = true;
}

function showResultError(message) {
  els.empty.hidden = true;
  els.result.hidden = false;
  els.resultError.textContent = message;
  els.resultError.hidden = false;
}
