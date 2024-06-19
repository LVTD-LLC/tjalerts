import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["item", "selected"];

  connect() {
    this.selectedTechnologies = {};
    this.findSelectedTechnologies();
    this.renderSelectedTechnologies();
  }

  select(event) {
    const checkbox = event.currentTarget;
    const label = this.element.querySelector(`label[for="${checkbox.id}"]`);
    if (checkbox.checked) {
      this.selectedTechnologies[checkbox.id] = label.innerText.trim();
      label.classList.add('hidden');
    }
    this.renderSelectedTechnologies();
  }

  remove(event) {
    const button = event.currentTarget;
    const data_id = button.dataset.id;
    const label = this.element.querySelector(`label[for="${data_id}"]`);
    const checkbox = this.element.querySelector(`input#${data_id}`);

    delete this.selectedTechnologies[data_id];
    label.classList.remove('hidden');
    checkbox.checked = false;

    this.renderSelectedTechnologies();
  }

  findSelectedTechnologies() {
    this.itemTargets.forEach((item) => {
      const label = this.element.querySelector(`label[for="${item.id}"]`);
      if (item.checked) {
        this.selectedTechnologies[item.id] = label.innerText.trim();
        label.classList.add('hidden');
      }
    });
  }

  renderSelectedTechnologies() {
    this.selectedTarget.innerHTML = '';
    Object.entries(this.selectedTechnologies).forEach(([id, name]) => {
      this.selectedTarget.innerHTML += `
        <div class="flex justify-between items-center py-1" data-select-technology-target="selected-item">
          <p>${name}</p>
          <button type="button" data-action="click->select-technology#remove" data-id="${id}" class="p-1 rounded-full hover:bg-red-100">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 text-red-600">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      `;
    });
  }
}
