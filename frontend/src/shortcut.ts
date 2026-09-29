export function shortcutFromKey(event: Pick<KeyboardEvent,"key"|"altKey"|"ctrlKey"|"metaKey"|"shiftKey">): string | null {
  if(event.key==="Backspace"||event.key==="Delete")return "";
  if(!event.altKey&&!event.ctrlKey&&!event.metaKey)return null;
  if(["Alt","Control","Meta","Shift","Dead","Unidentified"].includes(event.key)||event.key.length!==1)return null;
  return [event.ctrlKey?"Ctrl":null,event.altKey?"Alt":null,event.metaKey?"Meta":null,event.shiftKey?"Shift":null,event.key.toUpperCase()].filter(Boolean).join("+");
}

export function matchesShortcut(event: KeyboardEvent, value: string): boolean {
  if(!value)return false;
  const parts=value.split("+");
  return event.key.toUpperCase()===parts.at(-1)?.toUpperCase()
    &&event.ctrlKey===parts.includes("Ctrl")
    &&event.altKey===parts.includes("Alt")
    &&event.metaKey===parts.includes("Meta")
    &&event.shiftKey===parts.includes("Shift");
}
