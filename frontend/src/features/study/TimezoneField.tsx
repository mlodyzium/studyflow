import { t } from "../../i18n";
const popular = [
  ["Europe/Warsaw", t("Warsaw (Poland)")],
  ["Europe/London", t("London")],
  ["Europe/Berlin", "Berlin"],
  ["Europe/Paris", t("Paris")],
  ["Europe/Kyiv", t("Kyiv")],
  ["America/New_York", t("New York")],
  ["America/Los_Angeles", "Los Angeles"],
  ["Asia/Tokyo", t("Tokyo")],
  ["UTC", "UTC"],
] as const;

export function TimezoneField({value}:{value:string}){
  const all=typeof Intl.supportedValuesOf==="function"?Intl.supportedValuesOf("timeZone"):popular.map(([zone])=>zone);
  const popularNames=new Set<string>(popular.map(([zone])=>zone));
  const remaining=[...new Set([value,...all])].filter(zone=>!popularNames.has(zone)).sort((a,b)=>a.localeCompare(b,"pl"));
  return <label>{t("Time zone")}<select name="timezone" defaultValue={value} required><optgroup label={t("Most used")}>{popular.map(([zone,label])=><option value={zone} key={zone}>{label} · {zone}</option>)}</optgroup><optgroup label={t("Other zones")}>{remaining.map(zone=><option value={zone} key={zone}>{zone.replaceAll("_"," ")}</option>)}</optgroup></select><small className="field-hint">{t("Choose the time zone where you record your studies and deadlines.")}</small></label>;
}
