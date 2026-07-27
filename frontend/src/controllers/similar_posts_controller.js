import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["container"];
  static values = { postId: String };

  connect() {
    this.abortController = null;
    this.loadSimilarPosts();
  }

  disconnect() {
    this.abortPendingRequest();
  }

  async loadSimilarPosts() {
    this.abortPendingRequest();
    const controller = new AbortController();
    this.abortController = controller;
    this.containerTarget.setAttribute('aria-busy', 'true');

    try {
      const response = await fetch(`/jobs/${this.postIdValue}/similar/`, {
        signal: controller.signal,
      });
      if (!response.ok) throw new Error('Network response was not ok');
      const data = await response.json();
      this.renderSimilarPosts(data.similar_posts);
    } catch (error) {
      if (error.name === 'AbortError') return;

      this.renderErrorState();
    } finally {
      if (this.abortController === controller) {
        this.abortController = null;
        this.containerTarget.setAttribute('aria-busy', 'false');
      }
    }
  }

  renderSimilarPosts(similarPosts) {
    if (similarPosts.length === 0) {
      this.containerTarget.replaceChildren(this.renderStatusMessage('No similar jobs found yet.'));
      return;
    }

    this.containerTarget.replaceChildren(...similarPosts.map(post => this.renderPost(post)));
  }

  renderErrorState() {
    const item = document.createElement('li');
    item.className = 'app-muted-panel space-y-2 text-sm leading-6 dynamic-copy';

    const message = document.createElement('p');
    message.textContent = 'Similar jobs are unavailable right now.';

    const retryButton = document.createElement('button');
    retryButton.type = 'button';
    retryButton.className = 'search-retry';
    retryButton.setAttribute('data-action', 'click->similar-posts#loadSimilarPosts');
    retryButton.textContent = 'Try again';

    item.append(message, retryButton);
    this.containerTarget.replaceChildren(item);
  }

  renderStatusMessage(message) {
    const item = document.createElement('li');
    item.className = 'app-muted-panel text-sm leading-6 dynamic-copy';
    item.textContent = message;

    return item;
  }

  renderPost(post) {
    const truncateDescription = (text, maxLength) => {
      if (text.length <= maxLength) return text;
      return text.substr(0, maxLength) + '...';
    };

    const item = document.createElement('li');
    item.className = 'job-card';

    const link = document.createElement('a');
    link.className = 'block p-4';
    link.href = `/jobs/${encodeURIComponent(post.id)}`;

    const company = document.createElement('p');
    company.className = 'truncate text-sm font-semibold dynamic-title';
    company.textContent = post.company?.name || 'Company';

    const description = document.createElement('p');
    description.className = 'mt-2 text-sm leading-6 dynamic-copy';
    description.textContent = truncateDescription(post.description || '', 150);

    link.append(company, description);
    item.appendChild(link);

    return item;
  }

  abortPendingRequest() {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }
}
