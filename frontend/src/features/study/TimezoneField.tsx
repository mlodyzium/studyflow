const popular = [
  ["Europe/Warsaw", "Warszawa (Polska)"],
  ["Europe/London", "Londyn"],
  ["Europe/Berlin", "Berlin"],
  ["Europe/Paris", "Paryż"],
  ["Europe/Kyiv", "Kijów"],
  ["America/New_York", "Nowy Jork"],
  ["America/Los_Angeles", "Los Angeles"],
  ["Asia/Tokyo", "Tokio"],
  ["UTC", "UTC"],
] as const;

export function TimezoneField({value}:{value:string}){
  const all=typeof Intl.supportedValuesOf==="function"?Intl.supportedValuesOf("timeZone"):popular.map(([zone])=>zone);
  const popularNames=new Set<string>(popular.map(([zone])=>zone));
  const remaining=[...new Set([value,...all])].filter(zone=>!popularNames.has(zone)).sort((a,b)=>a.localeCompare(b,"pl"));
  return <label>Strefa czasowa<select name="timezone" defaultValue={value} required><optgroup label="Najczęściej używane">{popular.map(([zone,label])=><option value={zone} key={zone}>{label} · {zone}</option>)}</optgroup><optgroup label="Pozostałe strefy">{remaining.map(zone=><option value={zone} key={zone}>{zone.replaceAll("_"," ")}</option>)}</optgroup></select><small className="field-hint">Wybierz strefę, w której zapisujesz naukę i terminy.</small></label>;
}
