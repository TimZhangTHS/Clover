const words = [
  "stand out.",
  "tell your story.",
  "get admitted.",
  "do it right."
];

const typingTarget = document.getElementById("typing-text");

let wordIndex = 0;
let charIndex = 0;
let deleting = false;

function tick() {
  if (!typingTarget) {
    return;
  }

  const currentWord = words[wordIndex];

  if (deleting) {
    charIndex -= 1;
  } else {
    charIndex += 1;
  }

  typingTarget.textContent = currentWord.slice(0, charIndex);

  let delay = deleting ? 55 : 95;

  if (!deleting && charIndex === currentWord.length) {
    delay = 1200;
    deleting = true;
  } else if (deleting && charIndex === 0) {
    deleting = false;
    wordIndex = (wordIndex + 1) % words.length;
    delay = 350;
  }

  setTimeout(tick, delay);
}

tick();

const logoMarquee = document.getElementById("logo-marquee");
const logoFolder = "acceptance-logos";
const imagePattern = /\.(png|jpe?g|webp|gif|svg)$/i;

function getGitHubRepoFromPage() {
  if (!window.location.hostname.endsWith("github.io")) {
    return null;
  }

  const owner = window.location.hostname.split(".")[0];
  const repo = window.location.pathname.split("/").filter(Boolean)[0];

  if (!owner || !repo) {
    return null;
  }

  return { owner, repo };
}

function createLogoImage(src) {
  const image = document.createElement("img");
  image.src = src;
  image.alt = "Accepted school logo";
  image.className = "logo-item";
  image.loading = "lazy";
  return image;
}

function renderLogoMarquee(logoUrls) {
  if (!logoMarquee) {
    return;
  }

  if (!logoUrls.length) {
    logoMarquee.innerHTML = "<p class=\"logo-empty\">Acceptance logos will appear here.</p>";
    return;
  }

  const uniqueUrls = Array.from(new Set(logoUrls));
  const track = document.createElement("div");
  track.className = "logo-track";

  uniqueUrls.forEach((url) => {
    track.appendChild(createLogoImage(url));
  });

  const seconds = Math.max(16, uniqueUrls.length * 2.2);
  track.style.setProperty("--logo-duration", `${seconds}s`);
  logoMarquee.replaceChildren(track);
}

async function fetchLogosFromGitHubFolder() {
  const repoInfo = getGitHubRepoFromPage();
  if (!repoInfo) {
    return [];
  }

  const url = `https://api.github.com/repos/${repoInfo.owner}/${repoInfo.repo}/contents/${logoFolder}`;
  const response = await fetch(url);
  if (!response.ok) {
    return [];
  }

  const files = await response.json();
  if (!Array.isArray(files)) {
    return [];
  }

  return files
    .filter((file) => file && imagePattern.test(file.name || ""))
    .map((file) => file.download_url)
    .filter(Boolean);
}

async function fetchLogosFromDirectoryListing() {
  const response = await fetch(`./${logoFolder}/`);
  if (!response.ok) {
    return [];
  }

  const html = await response.text();
  const doc = new DOMParser().parseFromString(html, "text/html");
  const links = Array.from(doc.querySelectorAll("a"));

  return links
    .map((link) => link.getAttribute("href") || "")
    .map((href) => href.split("/").pop() || "")
    .filter((name) => imagePattern.test(name))
    .map((name) => `./${logoFolder}/${name}`);
}

async function loadAcceptanceLogos() {
  try {
    const githubLogos = await fetchLogosFromGitHubFolder();
    if (githubLogos.length) {
      renderLogoMarquee(githubLogos);
      return;
    }

    const localLogos = await fetchLogosFromDirectoryListing();
    renderLogoMarquee(localLogos);
  } catch (error) {
    renderLogoMarquee([]);
  }
}

loadAcceptanceLogos();
