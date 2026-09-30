import { locale, t } from "../../i18n.ts";
export function planDayLabel(startDate:string|null|undefined,day:number,scheduledDate?:string|null):string {
  if(!startDate&&!scheduledDate)return t("Day {0}", day);
  const date=new Date(`${scheduledDate??startDate}T12:00:00Z`);
  if(!scheduledDate)date.setUTCDate(date.getUTCDate()+day-1);
  return t("Day {0} · {1}", day, new Intl.DateTimeFormat(locale(),{weekday:"long",day:"numeric",month:"long",timeZone:"UTC"}).format(date));
}
