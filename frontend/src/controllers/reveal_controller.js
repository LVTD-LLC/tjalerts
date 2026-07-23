import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["item", "button"];
  static classes = ["hidden"];

  connect() {
    this.hiddenClassName = this.hasHiddenClass ? this.hiddenClass : "hidden";
    this.syncButtonState();
  }

  toggle() {
    this.itemTargets.forEach((item) => {
      item.classList.toggle(this.hiddenClassName);
    });
    this.syncButtonState();
  }

  show() {
    this.itemTargets.forEach((item) => {
      item.classList.remove(this.hiddenClassName);
    });
    this.syncButtonState();
  }

  hide() {
    this.itemTargets.forEach((item) => {
      item.classList.add(this.hiddenClassName);
    });
    this.syncButtonState();
  }

  syncButtonState() {
    if (!this.hasButtonTarget) {
      return;
    }

    const isExpanded = this.itemTargets.some((item) => !item.classList.contains(this.hiddenClassName));
    this.buttonTargets.forEach((button) => {
      button.setAttribute("aria-expanded", String(isExpanded));
    });
  }
}
