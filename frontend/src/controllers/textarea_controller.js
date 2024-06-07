import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  connect() {
    this.updateTextAreaContent();
  }

  updateTextAreaContent() {
    const textAreas = document.querySelectorAll("textarea");

    textAreas.forEach((textArea) => {
      // Store the value attribute content
      const valueContent = textArea.getAttribute("value");
      if (valueContent) {
        // Remove the value attribute
        textArea.removeAttribute("value");

        // Move the value attribute content to the textarea tag content
        textArea.innerHTML = valueContent;
      }
    });
  }
}
