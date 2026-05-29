import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["container"];
  static values = { postId: String };

  connect() {
    this.loadSimilarPosts();
  }

  async loadSimilarPosts() {
    try {
      const response = await fetch(`/api/posts/similar/${this.postIdValue}`);
      if (!response.ok) throw new Error('Network response was not ok');
      const data = await response.json();
      this.renderSimilarPosts(data.similar_posts);
    } catch (error) {
      console.error('Error fetching similar posts:', error);
      this.renderErrorState();
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
    this.containerTarget.replaceChildren(this.renderStatusMessage('Similar jobs are unavailable right now.'));
  }

  renderStatusMessage(message) {
    const item = document.createElement('li');
    item.className = 'app-muted-panel text-sm leading-6 text-zinc-600';
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
    company.className = 'truncate text-sm font-semibold text-zinc-950';
    company.textContent = post.company?.name || 'Company';

    const description = document.createElement('p');
    description.className = 'mt-2 text-sm leading-6 text-zinc-600';
    description.textContent = truncateDescription(post.description || '', 150);

    link.append(company, description);
    item.appendChild(link);

    return item;
  }
}
