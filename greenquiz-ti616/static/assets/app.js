(() => {
  const themeKey = "gq_theme";
  const body = document.body;
  const toggle = document.getElementById("toggleTheme");
  if (localStorage.getItem(themeKey) === "dark") {
    body.classList.add("dark");
  }
  if (toggle) {
    toggle.addEventListener("click", () => {
      body.classList.toggle("dark");
      localStorage.setItem(themeKey, body.classList.contains("dark") ? "dark" : "light");
    });
  }
})();
