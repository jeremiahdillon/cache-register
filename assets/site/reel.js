// cacheregister.dev reel (root page and receipt pages): play only the slide on screen, in the shape
// that fits the viewport. While motion is on (body.in-motion), slides with a video hide their still,
// so the frame stays blank until the video's first frame is ready and the animation simply starts; a
// video starts loading as soon as its slide edges into view and plays once mostly on screen, from the
// beginning. None loads while the root's splash fills the screen.
// Static mode (body.static: reduced motion, or "Pause motion", page-wide for the session; WCAG 2.2.2)
// shows stills; a chart that exists only as video (data-still="borrowed": its still is another
// chart's) shows its video paused, with native controls. Without this script, or if a video fails,
// the stills show.
(() => {
  const slides = [...document.querySelectorAll(".slide")];
  if (!slides.length) return;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const portrait = matchMedia("(orientation: portrait)");
  const videoOf = (slide) => slide && slide.querySelector("video");
  const borrowed = (slide) => slide.dataset.still === "borrowed";
  let active = null;
  let paused = false;
  try {
    paused = sessionStorage.getItem("reel-paused") === "1";
  } catch {}
  const still = () => reduce || paused;

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
    const video = videoOf(slide);
    if (!video) continue;
    video.addEventListener("playing", () => video.classList.add("playing"));
    video.addEventListener("error", () => fail(video));
    if (reduce) continue; // nothing moves on its own, so there is nothing to pause
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
    const meta = slide.querySelector(".meta");
    meta.insertBefore(button, meta.querySelector("a"));
    buttons.push(button);
  }

  function load(slide) {
    const video = videoOf(slide);
    if (!video || video.classList.contains("failed") || (still() && !borrowed(slide))) return null;
    const src = video.dataset[portrait.matches ? "portrait" : "landscape"];
    if (video.getAttribute("src") !== src) {
      video.classList.remove("playing");
      video.preload = still() ? "metadata" : "auto";
      video.src = src;
    }
    return video;
  }

  function play(slide) {
    const video = load(slide);
    if (video && !still()) video.play().catch((err) => err.name !== "AbortError" && fail(video));
  }

  function sync() {
    document.body.classList.toggle("in-motion", !still() && buttons.length > 0);
    document.body.classList.toggle("static", still());
    for (const button of buttons) button.setAttribute("aria-pressed", String(paused));
    for (const slide of slides) {
      const video = videoOf(slide);
      if (!video) continue;
      const controls = still() && borrowed(slide); // the only way to see this chart: let the viewer play it
      video.controls = controls;
      video.tabIndex = controls ? 0 : -1;
      if (controls) video.removeAttribute("aria-hidden");
      else video.setAttribute("aria-hidden", "true");
      if (slide === active && !still()) continue;
      if (!video.paused) video.pause();
      if (still()) video.classList.remove("playing");
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
