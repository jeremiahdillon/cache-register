// Landing reel (cacheregister.dev root): play only the receipt on screen, in the shape that fits
// the viewport. While motion is on, slides with a video hide their still (body.in-motion), so the frame
// stays blank until the video's first frame is ready and the animation simply starts; a video starts
// loading as soon as its slide edges into view and plays once mostly on screen, from the beginning.
// None loads while the splash fills the screen. Without this script, with reduced motion, after
// "Pause motion" (page-wide, for the session; WCAG 2.2.2) or if a video fails, the stills show.
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

  function fail(video) {
    video.classList.remove("playing");
    video.classList.add("failed"); // brings its still back
  }

  const buttons = [];
  for (const slide of slides) {
    const video = slide.querySelector("video");
    if (!video || reduce) continue;
    video.addEventListener("playing", () => video.classList.add("playing"));
    video.addEventListener("error", () => fail(video));
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

  function load(slide) {
    const video = slide && slide.querySelector("video");
    if (!video || reduce || paused || video.classList.contains("failed")) return null;
    const src = video.dataset[portrait.matches ? "portrait" : "landscape"];
    if (video.getAttribute("src") !== src) {
      video.classList.remove("playing");
      video.preload = "auto";
      video.src = src;
    }
    return video;
  }

  function play(slide) {
    const video = load(slide);
    if (video) video.play().catch((err) => err.name !== "AbortError" && fail(video));
  }

  function sync() {
    document.body.classList.toggle("in-motion", buttons.length > 0 && !paused);
    for (const button of buttons) button.setAttribute("aria-pressed", String(paused));
    for (const slide of slides) {
      const video = slide.querySelector("video");
      if (!video || (slide === active && !paused)) continue;
      if (!video.paused) video.pause();
      if (paused) video.classList.remove("playing");
      else if (video.currentTime) video.currentTime = 0; // back to frame one: replays from the start
    }
    pips.classList.toggle("on", active !== null);
    slides.forEach((slide, i) => pips.children[i].classList.toggle("on", slide === active));
    play(active);
  }

  // Watch the media box, not the slide: any overlap starts loading, 60% in view makes it active.
  // (isIntersecting stays true below a threshold, so compare the ratio itself.)
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const slide = entry.target.closest(".slide");
        if (entry.intersectionRatio > 0) load(slide);
        if (entry.intersectionRatio >= 0.6) active = slide;
        else if (slide === active) active = null;
      }
      sync();
    },
    { threshold: [0, 0.6] },
  );
  for (const slide of slides) observer.observe(slide.querySelector(".media"));
  portrait.addEventListener("change", () => play(active));
  sync();
})();
