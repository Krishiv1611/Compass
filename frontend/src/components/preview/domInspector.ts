/**
 * Compass DOM Inspector for WebPreview Canvas (Interactive Click-to-Inspect).
 *
 * Injected into the preview environment or mounted in HTML to allow developers
 * to click any rendered UI component and pass its context directly to the Agent Chat.
 */

export interface InspectedElement {
  tag: string;
  id?: string;
  classes?: string;
  text?: string;
  selector: string;
}

export const DOM_INSPECTOR_SCRIPT = `
(function() {
  if (window.__COMPASS_INSPECTOR_INITIALIZED__) return;
  window.__COMPASS_INSPECTOR_INITIALIZED__ = true;

  var active = false;
  var highlightBox = null;
  var labelPill = null;
  var currentTarget = null;

  function createOverlay() {
    if (highlightBox) return;
    highlightBox = document.createElement("div");
    highlightBox.id = "__compass_highlight_box";
    highlightBox.style.cssText = "position:fixed;pointer-events:none;z-index:2147483646;border:2px solid #3b82f6;background:rgba(59,130,246,0.12);border-radius:4px;transition:all 60ms ease-out;display:none;";
    
    labelPill = document.createElement("div");
    labelPill.id = "__compass_highlight_label";
    labelPill.style.cssText = "position:absolute;top:-24px;left:0;background:#1e40af;color:#fff;font-family:ui-monospace,monospace;font-size:11px;font-weight:600;padding:2px 6px;border-radius:3px;white-space:nowrap;box-shadow:0 2px 4px rgba(0,0,0,0.2);";
    highlightBox.appendChild(labelPill);
    document.body.appendChild(highlightBox);
  }

  function getSelector(el) {
    if (!el || el === document.body || el === document.documentElement) return el.tagName.toLowerCase();
    var parts = [];
    while (el && el.nodeType === Node.ELEMENT_NODE && el !== document.body) {
      var sel = el.tagName.toLowerCase();
      if (el.id) {
        sel += "#" + el.id;
        parts.unshift(sel);
        break;
      } else {
        var cls = typeof el.className === "string" ? el.className.trim().split(/\\s+/).filter(Boolean) : [];
        if (cls.length > 0) {
          sel += "." + cls.slice(0, 2).join(".");
        }
      }
      parts.unshift(sel);
      el = el.parentElement;
    }
    return parts.join(" > ");
  }

  function handleMouseMove(e) {
    if (!active) return;
    var target = e.target;
    if (!target || target === highlightBox || target === labelPill || target === document.body || target === document.documentElement) {
      if (highlightBox) highlightBox.style.display = "none";
      currentTarget = null;
      return;
    }
    currentTarget = target;
    createOverlay();
    var rect = target.getBoundingClientRect();
    highlightBox.style.display = "block";
    highlightBox.style.top = rect.top + "px";
    highlightBox.style.left = rect.left + "px";
    highlightBox.style.width = rect.width + "px";
    highlightBox.style.height = rect.height + "px";

    var tag = target.tagName.toLowerCase();
    var cls = typeof target.className === "string" && target.className.trim() ? "." + target.className.trim().split(/\\s+/)[0] : "";
    labelPill.textContent = "<" + tag + cls + ">";
    if (rect.top < 26) {
      labelPill.style.top = "2px";
      labelPill.style.bottom = "auto";
    } else {
      labelPill.style.top = "-24px";
      labelPill.style.bottom = "auto";
    }
  }

  function handleClick(e) {
    if (!active) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    var target = currentTarget || e.target;
    if (!target) return;

    var tag = target.tagName.toLowerCase();
    var id = target.id || undefined;
    var classes = typeof target.className === "string" ? target.className.trim() : undefined;
    var text = (target.innerText || target.textContent || "").trim().slice(0, 100);
    var selector = getSelector(target);

    window.parent.postMessage({
      type: "COMPASS_ELEMENT_SELECTED",
      payload: {
        tag: tag,
        id: id,
        classes: classes,
        text: text,
        selector: selector
      }
    }, "*");
  }

  window.addEventListener("message", function(e) {
    if (!e.data || typeof e.data !== "object") return;
    if (e.data.type === "COMPASS_INSPECT_MODE") {
      active = Boolean(e.data.active);
      createOverlay();
      if (!active && highlightBox) {
        highlightBox.style.display = "none";
        currentTarget = null;
      }
      document.body.style.cursor = active ? "crosshair" : "";
    }
  });

  window.addEventListener("mousemove", handleMouseMove, true);
  window.addEventListener("click", handleClick, true);
})();
`;
