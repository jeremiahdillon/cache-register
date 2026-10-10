// Landing reel (cacheregister.dev root): play only the receipt on screen, in the shape that fits
// the viewport. One video at a time and none while the splash fills the screen; without this
// script, or with reduced motion, the <picture> stills stay. "Pause motion" holds every video still
// for the session (WCAG 2.2.2).
(() => {
  const slides = [...document.querySelectorAll(".slide")];
  if (!slides.length) return;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const portrait = matchMedia("(orientation: portrait)");
  let active = null;
  let paused = false;
  try {
    paused = sessionStorage.getItem("reel-paused") === "1";
  } catch {}

  const pips = document.createElement("div");
  pips.className = "pips";
  pips.setAttribute("aria-hidden", "true");
  pips.append(...slides.map(() => document.createElement("i")));
  document.body.append(pips);

  const buttons = [];
  for (const slide of slides) {
    const video = slide.querySelector("video");
    if (!video || reduce) continue;
    video.addEventListener("playing", () => video.classList.add("playing"));
    video.addEventListener("error", () => video.classList.remove("playing"));
    const button = document.createElement("button");
    button.type = "button";
    button.className = "motion";
    button.textContent = "Pause motion";
    button.addEventListener("click", () => {
      paused = !paused;
      try {
        sessionStorage.setItem("reel-paused", paused ? "1" : "0");
      } catch {}
      sync();
    });
    slide.querySelector(".meta a").before(button);
    buttons.push(button);
  }

  function play(slide) {
    const video = slide && slide.querySelector("video");
    if (!video || reduce || paused) return;
    const src = video.dataset[portrait.matches ? "portrait" : "landscape"];
    if (video.getAttribute("src") !== src) {
      video.classList.remove("playing");
      video.src = src;
    }
    video.play().catch(() => video.classList.remove("playing"));
  }

  function sync() {
    for (const button of buttons) button.setAttribute("aria-pressed", String(paused));
    for (const slide of slides) {
      const video = slide.querySelector("video");
      if (video && (paused || slide !== active)) {
        video.pause();
        if (paused) video.classList.remove("playing");
      }
    }
    pips.classList.toggle("on", active !== null);
    slides.forEach((slide, i) => pips.children[i].classList.toggle("on", slide === active));
    play(active);
  }

  // Watch the media box, not the slide, so "on screen" means the visual itself is mostly in view.
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const slide = entry.target.closest(".slide");
        // isIntersecting stays true below the threshold, so compare the ratio itself.
        if (entry.intersectionRatio >= 0.6) active = slide;
        else if (slide === active) active = null;
      }
      sync();
    },
    { threshold: 0.6 },
  );
  for (const slide of slides) observer.observe(slide.querySelector(".media"));
  portrait.addEventListener("change", () => play(active));
  sync();
})();
