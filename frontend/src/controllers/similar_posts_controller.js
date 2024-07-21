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
    }
  }

  renderSimilarPosts(similarPosts) {
    this.containerTarget.innerHTML = similarPosts.map(post => this.renderPost(post)).join('');
  }

  renderPost(post) {
    const truncateDescription = (text, maxLength) => {
      if (text.length <= maxLength) return text;
      return text.substr(0, maxLength) + '...';
    };

    return `
      <li>
        <a class="flex flex-col px-6 py-2 bg-white rounded-md hover:bg-gray-50" href="/jobs/${post.id}">
          <div class="flex justify-between items-center py-2 w-full">
            <div class="flex-1">
              <div class="flex justify-between items-center">
                <p class="text-sm font-medium text-gray-900 truncate">
                ${post.company.name}
                </p>
              </div>
              <p class="text-xs text-gray-600">
                ${truncateDescription(post.description, 150)}
              </p>
            </div>
          </div>
        </a>
      </li>
    `;
  }
}
