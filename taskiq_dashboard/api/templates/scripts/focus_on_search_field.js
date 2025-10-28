if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey) {
  const el = document.activeElement;
  const typing = el && (el.isContentEditable || ["INPUT","TEXTAREA","SELECT"].includes(el.tagName));
  if (typing) return;
  event.preventDefault();
  const input = document.querySelector("input[name=q]");
  if (input) {
    input.focus({ preventScroll: true });
    const end = input.value.length;
    if (typeof input.setSelectionRange === "function") {
      input.setSelectionRange(end, end); // курсор в конец, без выделения
    } else {
      // запасной вариант на всякий случай
      input.value = input.value;
    }
  }
}
