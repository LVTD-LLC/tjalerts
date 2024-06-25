import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    static targets = ["item", "query"];

    connect() {
      this.search(this.queryTarget);
    }

    search() {
      const query = this.queryTarget.value.toLowerCase();
      console.log(`searching: ${query}`);
      this.itemTargets.forEach(item => {
        const label = item.closest('label').textContent.trim().toLowerCase();
        item.closest('div').style.display = label.includes(query) ? "" : "none";
      });
    }
}
