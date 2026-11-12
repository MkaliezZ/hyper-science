"use strict";
(() => {
  const mount = () => {
    const header = document.getElementById("header");
    if (!header || !header.children.length || document.getElementById("research-entry")) return;
    const a = document.createElement("a");
    a.id = "research-entry"; a.href = "/research/"; a.textContent = "超维科研";
    a.className = "btn"; a.setAttribute("aria-label", "打开独立的超维科研板块");
    header.append(a);
  };
  window.addEventListener("DOMContentLoaded", () => {
    const header = document.getElementById("header");
    if (header) new MutationObserver(mount).observe(header, {childList: true, subtree: true});
    mount();
  }, {once: true});
})();
