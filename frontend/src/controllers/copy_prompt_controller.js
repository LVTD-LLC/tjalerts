import { Controller } from "@hotwired/stimulus";

import { copyPrompt } from "../utils/copy_prompt.js";

export class CopyPromptController extends Controller {
  static targets = ["button", "label", "prompt", "status"];

  initialize() {
    this.copyAttempt = 0;
    this.resetTimer = null;
  }

  connect() {
    this.copyAttempt += 1;
    this.clearResetTimer();
    this.buttonTarget.disabled = false;
    this.reset();
  }

  disconnect() {
    this.copyAttempt += 1;
    this.clearResetTimer();
  }

  async copy() {
    this.clearResetTimer();
    const copyAttempt = ++this.copyAttempt;
    this.buttonTarget.disabled = true;

    try {
      await copyPrompt(navigator.clipboard, this.promptTarget.value.trim());
      if (!this.isCurrentAttempt(copyAttempt)) return;

      this.labelTarget.textContent = "Copied!";
      this.statusTarget.textContent = "AI setup prompt copied to your clipboard.";
    } catch {
      if (!this.isCurrentAttempt(copyAttempt)) return;

      this.labelTarget.textContent = "Copy failed";
      this.statusTarget.textContent = "Clipboard access failed. Check your browser permission and try again.";
    } finally {
      if (this.isCurrentAttempt(copyAttempt)) {
        this.buttonTarget.disabled = false;
        this.resetTimer = window.setTimeout(() => {
          if (this.isCurrentAttempt(copyAttempt)) this.reset();
        }, 2500);
      }
    }
  }

  isCurrentAttempt(copyAttempt) {
    return copyAttempt === this.copyAttempt && this.element.isConnected;
  }

  reset() {
    this.labelTarget.textContent = "Copy Prompt for AI";
    this.statusTarget.textContent = "";
    this.resetTimer = null;
  }

  clearResetTimer() {
    if (this.resetTimer) {
      window.clearTimeout(this.resetTimer);
      this.resetTimer = null;
    }
  }
}

export default CopyPromptController;
