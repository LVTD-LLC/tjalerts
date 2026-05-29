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
      this.containerTarget.innerHTML = `
        <li class="app-muted-panel text-sm leading-6 text-zinc-600">
          No similar jobs found yet.
        </li>
      `;
      return;
    }

    this.containerTarget.innerHTML = similarPosts.map(post => this.renderPost(post)).join('');
  }

  renderErrorState() {
    this.containerTarget.innerHTML = `
      <li class="app-muted-panel text-sm leading-6 text-zinc-600">
        Similar jobs are unavailable right now.
      </li>
    `;
  }

  renderPost(post) {
    const truncateDescription = (text, maxLength) => {
      if (text.length <= maxLength) return text;
      return text.substr(0, maxLength) + '...';
    };

    return `
      <li class="job-card">
        <a class="block p-4" href="/jobs/${post.id}">
          <p class="truncate text-sm font-semibold text-zinc-950">${post.company.name}</p>
          <p class="mt-2 text-sm leading-6 text-zinc-600">
            ${truncateDescription(post.description, 150)}
          </p>
        </a>
      </li>
    `;
  }
}
