import { Controller } from "@hotwired/stimulus";

const SEARCH_DELAY_MS = 250;

export default class extends Controller {
  static targets = ["searchResults", "selectedResults", "search"];
  static values = {
    searchUrl: String,
    detailUrl: String,
    type: String,
  };

  connect() {
    this.selectedItems = new window.Set();
    this.searchTimeout = null;
    this.abortController = null;
    this.activeIndex = -1;

    this.syncInputState(false);
    this.loadPreselectedItems();
  }

  disconnect() {
    this.abortPendingSearch();
    window.clearTimeout(this.searchTimeout);
  }

  async loadPreselectedItems() {
    const urlParams = new URLSearchParams(window.location.search);
    const preselectedIds = urlParams.getAll(this.typeValue);

    if (preselectedIds.length === 0) return;

    await window.Promise.all(preselectedIds.map(async (id) => {
      try {
        const response = await fetch(`${this.detailUrlValue}/${id}`);
        if (!response.ok) return;

        const details = await response.json();
        if (details && details.id) {
          this.addItemToSelection(details.id, details.name, details.post_count);
        }
      } catch (_error) {
        // Preselected chips are a convenience; the hidden form values still submit.
      }
    }));
  }

  search() {
    const query = this.searchTarget.value;
    window.clearTimeout(this.searchTimeout);

    if (query.length < 2) {
      this.clearSearchResults();
      return;
    }

    this.searchTimeout = window.setTimeout(() => this.performSearch(query), SEARCH_DELAY_MS);
  }

  async performSearch(query) {
    this.abortPendingSearch();
    const controller = new AbortController();
    this.abortController = controller;
    this.renderStatusMessage("Searching...");
    this.syncInputState(true, true);

    try {
      const response = await fetch(`${this.searchUrlValue}?query=${encodeURIComponent(query)}`, {
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Search failed with status ${response.status}`);
      }

      const items = await response.json();
      if (query !== this.searchTarget.value) return;

      const filteredItems = items.filter(item => !this.selectedItems.has(String(item.id)));

      this.searchResultsTarget.classList.add("filter-search-results-active");
      this.syncInputState(false, true);

      if (filteredItems.length > 0) {
        this.activeIndex = -1;
        this.searchResultsTarget.replaceChildren(...filteredItems.map((item, index) => {
          return this.renderSearchResult(item, index);
        }));
      } else {
        this.renderStatusMessage("No matches");
      }
    } catch (error) {
      if (error.name === "AbortError") return;

      this.renderSearchError();
      this.syncInputState(false, true);
    } finally {
      if (this.abortController === controller) {
        this.abortController = null;
      }
    }
  }

  retry() {
    const query = this.searchTarget.value;
    if (query.length >= 2) {
      this.performSearch(query);
    }
  }

  handleKeydown(event) {
    const options = this.options();

    if (event.key === "Escape") {
      this.clearSearchResults();
      return;
    }

    if (options.length === 0) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      this.activeIndex = Math.min(this.activeIndex + 1, options.length - 1);
      this.updateActiveOption();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      this.activeIndex = Math.max(this.activeIndex - 1, 0);
      this.updateActiveOption();
    } else if (event.key === "Enter" && this.activeIndex >= 0) {
      event.preventDefault();
      this.addItemFromElement(options[this.activeIndex]);
    }
  }

  addItem(event) {
    event.preventDefault();
    this.addItemFromElement(event.currentTarget);
  }

  addItemFromElement(element) {
    const id = element.dataset.id;
    const name = element.dataset.name;
    const postCount = element.dataset.postCount;

    this.addItemToSelection(id, name, postCount);
    this.searchTarget.value = "";
    this.clearSearchResults();
    this.searchTarget.focus();
  }

  addItemToSelection(id, name, postCount) {
    const itemId = String(id);

    if (!this.selectedItems.has(itemId)) {
      this.selectedItems.add(itemId);
      this.selectedResultsTarget.appendChild(this.renderSelectedItem(itemId, name, postCount));
    }
  }

  removeItem(event) {
    const itemElement = event.currentTarget.closest("[data-id]");
    const id = itemElement.dataset.id;
    this.selectedItems.delete(id);
    itemElement.remove();
  }

  clearSearchResults() {
    this.abortPendingSearch();
    this.activeIndex = -1;
    this.searchResultsTarget.classList.remove("filter-search-results-active");
    this.searchResultsTarget.replaceChildren();
    this.syncInputState(false);
  }

  renderSearchResult(item, index) {
    const result = document.createElement("div");
    result.id = `${this.searchResultsTarget.id || this.typeValue}-option-${item.id}`;
    result.className = "search-option";
    result.setAttribute("role", "option");
    result.setAttribute("aria-selected", "false");
    result.setAttribute("data-action", "pointerdown->search-and-select#addItem");
    result.dataset.id = String(item.id);
    result.dataset.name = item.name;
    result.dataset.postCount = item.post_count || "";
    result.dataset.index = String(index);

    const name = document.createElement("span");
    name.className = "min-w-0 truncate font-medium";
    name.textContent = item.name;

    const count = document.createElement("span");
    count.className = "search-option-count";
    count.textContent = item.post_count ? `${item.post_count} posts` : "";

    result.append(name, count);

    return result;
  }

  renderStatusMessage(message) {
    const result = document.createElement("div");
    result.className = "search-status";
    result.setAttribute("role", "status");
    result.textContent = message;

    this.searchResultsTarget.classList.add("filter-search-results-active");
    this.searchResultsTarget.replaceChildren(result);
    return result;
  }

  renderSearchError() {
    const wrapper = document.createElement("div");
    wrapper.className = "search-error";
    wrapper.setAttribute("role", "status");

    const message = document.createElement("p");
    message.textContent = "Search is unavailable right now.";

    const retryButton = document.createElement("button");
    retryButton.type = "button";
    retryButton.className = "search-retry";
    retryButton.setAttribute("data-action", "click->search-and-select#retry");
    retryButton.textContent = "Try again";

    wrapper.append(message, retryButton);
    this.searchResultsTarget.classList.add("filter-search-results-active");
    this.searchResultsTarget.replaceChildren(wrapper);
  }

  renderSelectedItem(id, name, postCount) {
    const item = document.createElement("div");
    item.className = "tag my-0 mr-0";
    item.dataset.id = id;
    item.setAttribute("role", "listitem");

    const label = document.createElement("span");
    label.textContent = this.formatLabel(name, postCount);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip-action";
    button.setAttribute("data-action", "click->search-and-select#removeItem");

    const screenReaderLabel = document.createElement("span");
    screenReaderLabel.className = "sr-only";
    screenReaderLabel.textContent = `Remove ${name}`;

    const visualLabel = document.createElement("span");
    visualLabel.setAttribute("aria-hidden", "true");
    visualLabel.textContent = "x";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = this.typeValue;
    input.value = id;
    input.className = "hidden";
    input.checked = true;

    button.append(screenReaderLabel, visualLabel);
    item.append(label, button, input);

    return item;
  }

  formatLabel(name, postCount) {
    return postCount ? `${name} (${postCount} posts)` : name;
  }

  updateActiveOption() {
    this.options().forEach((option, index) => {
      const isActive = index === this.activeIndex;
      option.setAttribute("aria-selected", String(isActive));
      option.classList.toggle("search-option-active", isActive);

      if (isActive) {
        this.searchTarget.setAttribute("aria-activedescendant", option.id);
      }
    });
  }

  options() {
    return Array.from(this.searchResultsTarget.querySelectorAll("[role='option']"));
  }

  syncInputState(isBusy, isExpanded = false) {
    this.searchTarget.setAttribute("aria-busy", String(isBusy));
    this.searchTarget.setAttribute("aria-expanded", String(isExpanded));

    if (!isExpanded) {
      this.searchTarget.removeAttribute("aria-activedescendant");
    }
  }

  abortPendingSearch() {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }
}
