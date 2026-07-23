module.exports = {
  content: [
    './templates/**/*.html',
    './frontend/src/controllers/*.js',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['InterVariable', 'Inter', 'sans-serif'],
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
  ],
};
