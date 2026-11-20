try {
  var preference = localStorage.getItem('pharm_review_ui_theme');
  var theme = preference === 'light' || preference === 'dark'
    ? preference
    : window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
} catch {
  var systemDark = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = systemDark ? 'dark' : 'light';
  document.documentElement.style.colorScheme = systemDark ? 'dark' : 'light';
}
