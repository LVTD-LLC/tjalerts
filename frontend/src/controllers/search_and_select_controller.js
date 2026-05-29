import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["searchResults", "selectedResults", "search"];
  static values = {
    searchUrl: String,
    detailUrl: String,
    type: String
  };

  connect() {
    this.selectedItems = new window.Set();
    this.loadPreselectedItems();
  }

  async loadPreselectedItems() {
    const urlParams = new URLSearchParams(window.location.search);
    const preselectedIds = urlParams.getAll(this.typeValue);

    if (preselectedIds.length > 0) {
      preselectedIds.forEach(async (id) => {
        const response = await fetch(`${this.detailUrlValue}/${id}`);
        const details = await response.json();
        this.addItemToSelection(details.id, details.name, details.post_count);
      });
    }
  }

  async search() {
    const query = this.searchTarget.value;
    if (query.length < 2) {
      this.clearSearchResults();
      return;
    }

    const response = await fetch(`${this.searchUrlValue}?query=${encodeURIComponent(query)}`);
    const items = await response.json();

    const filteredItems = items.filter(item => !this.selectedItems.has(String(item.id)));

    if (filteredItems.length > 0) {
      this.searchResultsTarget.classList.add('border', 'border-zinc-200');
      this.searchResultsTarget.replaceChildren(...filteredItems.map(item => this.renderSearchResult(item)));
    } else {
      this.clearSearchResults();
    }
  }



  addItem(event) {
    const id = event.currentTarget.dataset.id;
    const name = event.currentTarget.dataset.name;
    const postCount = event.currentTarget.dataset.postCount;
    this.addItemToSelection(id, name, postCount);

    this.searchTarget.value = '';
    this.clearSearchResults();
  }

  addItemToSelection(id, name, postCount) {
    const itemId = String(id);

    if (!this.selectedItems.has(itemId)) {
      this.selectedItems.add(itemId);
      this.selectedResultsTarget.appendChild(this.renderSelectedItem(itemId, name, postCount));
    }
  }

  removeItem(event) {
    const itemElement = event.currentTarget.closest('div');
    const id = itemElement.dataset.id;
    this.selectedItems.delete(id);
    itemElement.remove();
  }

  clearSearchResults() {
    this.searchResultsTarget.classList.remove('border', 'border-zinc-200');
    this.searchResultsTarget.replaceChildren();
  }

  renderSearchResult(item) {
    const result = document.createElement('div');
    result.className = 'cursor-pointer rounded-md p-2 text-sm text-zinc-800 hover:bg-zinc-100';
    result.setAttribute('data-action', 'click->search-and-select#addItem');
    result.dataset.id = String(item.id);
    result.dataset.name = item.name;
    result.dataset.postCount = item.post_count || '';
    result.textContent = this.formatLabel(item.name, item.post_count);

    return result;
  }

  renderSelectedItem(id, name, postCount) {
    const item = document.createElement('div');
    item.className = 'tag';
    item.dataset.id = id;

    const label = document.createElement('span');
    label.textContent = this.formatLabel(name, postCount);

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ml-2 rounded-sm text-emerald-900 hover:bg-emerald-100';
    button.setAttribute('data-action', 'click->search-and-select#removeItem');

    const screenReaderLabel = document.createElement('span');
    screenReaderLabel.className = 'sr-only';
    screenReaderLabel.textContent = `Remove ${name}`;

    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('class', 'h-3.5 w-3.5');
    icon.setAttribute('fill', 'none');
    icon.setAttribute('viewBox', '0 0 24 24');
    icon.setAttribute('stroke', 'currentColor');
    icon.setAttribute('aria-hidden', 'true');

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');
    path.setAttribute('stroke-width', '2');
    path.setAttribute('d', 'M6 18 18 6M6 6l12 12');

    const input = document.createElement('input');
    input.type = 'checkbox';
    input.name = this.typeValue;
    input.value = id;
    input.className = 'hidden';
    input.checked = true;

    icon.appendChild(path);
    button.append(screenReaderLabel, icon);
    item.append(label, button, input);

    return item;
  }

  formatLabel(name, postCount) {
    return postCount ? `${name} (${postCount} posts)` : name;
  }
}
