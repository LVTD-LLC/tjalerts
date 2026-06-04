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
        if (details && details.id) {
          this.addItemToSelection(details.id, details.name, details.post_count);
        }
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
      this.searchResultsTarget.classList.add('border', 'border-zinc-200');
      this.searchResultsTarget.replaceChildren(this.renderEmptyResult());
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
    const itemElement = event.currentTarget.closest('[data-id]');
    const id = itemElement.dataset.id;
    this.selectedItems.delete(id);
    itemElement.remove();
  }

  clearSearchResults() {
    this.searchResultsTarget.classList.remove('border', 'border-zinc-200');
    this.searchResultsTarget.replaceChildren();
  }

  renderSearchResult(item) {
    const result = document.createElement('button');
    result.type = 'button';
    result.className = 'flex w-full items-center justify-between gap-3 rounded-md p-2 text-left text-sm text-zinc-800 hover:bg-zinc-100';
    result.setAttribute('data-action', 'click->search-and-select#addItem');
    result.dataset.id = String(item.id);
    result.dataset.name = item.name;
    result.dataset.postCount = item.post_count || '';

    const name = document.createElement('span');
    name.className = 'min-w-0 truncate font-medium';
    name.textContent = item.name;

    const count = document.createElement('span');
    count.className = 'tabular shrink-0 text-xs text-zinc-500';
    count.textContent = item.post_count ? `${item.post_count} posts` : '';

    result.append(name, count);

    return result;
  }

  renderEmptyResult() {
    const result = document.createElement('div');
    result.className = 'p-2 text-sm text-zinc-500';
    result.textContent = 'No matches';

    return result;
  }

  renderSelectedItem(id, name, postCount) {
    const item = document.createElement('div');
    item.className = 'tag my-0 mr-0';
    item.dataset.id = id;

    const label = document.createElement('span');
    label.textContent = this.formatLabel(name, postCount);

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ml-1 rounded-sm px-1 text-emerald-900 hover:bg-emerald-100';
    button.setAttribute('data-action', 'click->search-and-select#removeItem');

    const screenReaderLabel = document.createElement('span');
    screenReaderLabel.className = 'sr-only';
    screenReaderLabel.textContent = `Remove ${name}`;

    const visualLabel = document.createElement('span');
    visualLabel.setAttribute('aria-hidden', 'true');
    visualLabel.textContent = 'x';

    const input = document.createElement('input');
    input.type = 'checkbox';
    input.name = this.typeValue;
    input.value = id;
    input.className = 'hidden';
    input.checked = true;

    button.append(screenReaderLabel, visualLabel);
    item.append(label, button, input);

    return item;
  }

  formatLabel(name, postCount) {
    return postCount ? `${name} (${postCount} posts)` : name;
  }
}
