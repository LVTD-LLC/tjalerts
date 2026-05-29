import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    static targets = [ "button", "loader" ];

    load() {
      this.loaderTarget.classList.remove('hidden');
      this.loaderTarget.classList.add('block');
      this.buttonTarget.setAttribute('aria-busy', 'true');
      this.buttonTarget.disabled = true;
      document.form.submit();
    }
}
