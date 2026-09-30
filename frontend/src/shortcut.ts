export function shortcutFromKey(event: Pick<KeyboardEvent,"key"|"altKey"|"ctrlKey"|"metaKey"|"shiftKey">): string | null {
  if(event.key==="Backspace"||event.key==="Delete")return "";
  if(!event.altKey&&!event.ctrlKey&&!event.metaKey)return null;
  if(["Alt","Control","Meta","Shift","Dead","Unidentified"].includes(event.key)||event.key.length!==1||event.key==="+")return null;
  return [event.ctrlKey?"Ctrl":null,event.altKey?"Alt":null,event.metaKey?"Meta":null,event.shiftKey?"Shift":null,event.key.toUpperCase()].filter(Boolean).join("+");
}

export function normalizeShortcut(value:string):string|null {
  if(!value)return "";
  const parts=value.split("+");
  const key=parts.pop();
  const modifiers=parts.map(part=>part.toLowerCase());
  if(!key||key.length!==1||key==="+"||!/[\S]/u.test(key)||modifiers.length!==new Set(modifiers).size||!modifiers.every(part=>["ctrl","alt","meta","shift"].includes(part))||!["ctrl","alt","meta"].some(part=>modifiers.includes(part)))return null;
  return [["ctrl","Ctrl"],["alt","Alt"],["meta","Meta"],["shift","Shift"]].filter(([name])=>modifiers.includes(name)).map(([,label])=>label).concat(key.toUpperCase()).join("+");
}

export function shortcutsConflict(first:string,second:string):boolean {
  const normalized=normalizeShortcut(first);
  return Boolean(normalized&&normalized===normalizeShortcut(second));
}

export function matchesShortcut(event: KeyboardEvent, value: string): boolean {
  const normalized=normalizeShortcut(value);
  return Boolean(normalized&&normalized===shortcutFromKey(event));
}
