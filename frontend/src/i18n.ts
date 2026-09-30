import polish from "./locales/pl.json" with { type: "json" };

export type Language = "en" | "pl";
const translations: Record<string, string> = polish;

export function getLanguage(): Language {
  if (typeof localStorage === "undefined") return "en";
  return localStorage.getItem("studyflow_language") === "pl" ? "pl" : "en";
}

export function locale(): string {
  return getLanguage() === "pl" ? "pl-PL" : "en-GB";
}

export function aiLanguage(): string {
  return getLanguage() === "pl" ? "Polish" : "English";
}

export function t(message: string, ...values: unknown[]): string {
  const template = getLanguage() === "pl" ? translations[message] ?? message : message;
  return template.replace(/\{(\d+)\}/g, (match, index) => index in values ? String(values[Number(index)]) : match);
}

export function setLanguage(language: Language, reload = true): void {
  const previous = getLanguage();
  localStorage.setItem("studyflow_language", language);
  document.documentElement.lang = language;
  // Reload also updates module-level labels and browser speech recognition.
  if (previous !== language && reload) window.location.reload();
}

if (typeof document !== "undefined") document.documentElement.lang = getLanguage();
