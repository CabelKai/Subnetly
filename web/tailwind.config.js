/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./ipam/templates/**/*.html",
    "./ipam/**/*.py",
  ],
  safelist: [
    // Arbitrary-value classes inside Django `{% if %}` wrappers aren't always
    // picked up by Tailwind's content extractor. Pin them explicitly.
    "md:pl-[calc(18rem+1.5rem)]",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
