module.exports = {
  content: [
    './templates/**/*.html',
    './frontend/src/controllers/*.js',
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
    require('daisyui'),
  ],
};
