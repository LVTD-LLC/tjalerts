import { Controller } from "@hotwired/stimulus";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export default class extends Controller {
  static targets = ["button", "menu", "panel"];

  connect() {
    this.previouslyFocusedElement = null;
    this.pendingFocusFrame = null;
    this.close();
  }

  disconnect() {
    this.cancelPendingFocus();
    this.restorePageState();
  }

  open() {
    if (this.isOpen()) return;

    this.previouslyFocusedElement = document.activeElement;
    this.menuTarget.classList.remove("hidden");
    this.menuTarget.setAttribute("aria-hidden", "false");
    this.buttonTarget.setAttribute("aria-expanded", "true");
    document.body.classList.add("overflow-hidden");

    this.pendingFocusFrame = requestAnimationFrame(() => {
      this.pendingFocusFrame = null;
      if (!this.isOpen()) return;

      const firstFocusable = this.focusableElements()[0];
      (firstFocusable || this.panelTarget).focus();
    });
  }

  close() {
    if (!this.hasMenuTarget) return;

    this.cancelPendingFocus();
    this.menuTarget.classList.add("hidden");
    this.menuTarget.setAttribute("aria-hidden", "true");

    if (this.hasButtonTarget) {
      this.buttonTarget.setAttribute("aria-expanded", "false");
    }

    this.restorePageState();

    if (this.previouslyFocusedElement?.focus) {
      this.previouslyFocusedElement.focus();
    }
  }

  handleKeydown(event) {
    if (!this.isOpen()) return;

    if (event.key === "Escape") {
      event.preventDefault();
      this.close();
      return;
    }

    if (event.key !== "Tab") return;

    const focusable = this.focusableElements();
    if (focusable.length === 0) {
      event.preventDefault();
      this.panelTarget.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  isOpen() {
    return this.hasMenuTarget && !this.menuTarget.classList.contains("hidden");
  }

  focusableElements() {
    if (!this.hasPanelTarget) return [];

    return Array.from(this.panelTarget.querySelectorAll(FOCUSABLE_SELECTOR)).filter((element) => {
      return element.offsetParent !== null || element === document.activeElement;
    });
  }

  restorePageState() {
    document.body.classList.remove("overflow-hidden");
  }

  cancelPendingFocus() {
    if (this.pendingFocusFrame) {
      cancelAnimationFrame(this.pendingFocusFrame);
      this.pendingFocusFrame = null;
    }
  }
}
