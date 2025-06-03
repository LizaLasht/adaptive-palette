const initialData = JSON.parse(document.getElementById("initial-data").textContent);
window.initialPalette = initialData.palette;
window.initialId = initialData.id;

let currentPaletteId = window.initialId;

function displayPalette(palette) {
  const container = document.getElementById("palette-container");
  container.innerHTML = "";
  palette.forEach(color => {
    const div = document.createElement("div");
    div.className = "color-block";
    div.style.backgroundColor = color;

    const span = document.createElement("span");
    span.className = "color-code";
    span.textContent = color;

    div.appendChild(span);
    container.appendChild(div);
  });
}

// Отображаем начальную палитру
displayPalette(window.initialPalette);

function requestNewPalette() {
  fetch("/generate")
    .then(response => response.json())
    .then(data => {
      displayPalette(data.colors);
      currentPaletteId = data.palette_id;
      const probaText = data.proba === null || data.proba === undefined
        ? "💡 Чем больше вы оцените палитр, тем точнее мы сможем предсказывать ваши предпочтения!"
        : "Вероятность лайка: " + (data.proba * 100).toFixed(1) + "%";
      document.getElementById("proba-display").innerText = probaText;
      hideUploadedSection();
    })
    .catch(err => console.error("Ошибка генерации палитры:", err));
}

function sendFeedback(feedbackType) {
  fetch("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback: feedbackType, palette_id: currentPaletteId })
  })
    .then(res => {
      if (!res.ok) throw new Error("Server error");
      return res.json();
    })
    .then(() => {
      requestNewPalette();
      loadLikedPalettes();  
    })
    .catch(err => console.error("Ошибка отправки фидбека:", err));
}

document.getElementById("upload-form").addEventListener("submit", function (e) {
  e.preventDefault();
  const fileInput = this.querySelector("input[type=file]");
  const formData = new FormData();
  formData.append("image", fileInput.files[0]);

  fetch("/upload", {
    method: "POST",
    body: formData
  })
    .then(res => res.json())
    .then(data => {
      displayPalette(data.colors);
      currentPaletteId = data.palette_id;

      let probaText = "";
      if (data.proba === "need_feedback") {
        probaText = "💡 Чем больше вы оцените палитр, тем точнее мы сможем предсказывать ваши предпочтения!";
      } else if (typeof data.proba === "number") {
        probaText = "Вероятность лайка: " + (data.proba * 100).toFixed(1) + "%";
      }
      document.getElementById("proba-display").innerText = probaText;

      if (data.image) {
        showUploadedSection(data.image);
      }

      loadTopPalettes();
    })
    .catch(err => console.error("Ошибка загрузки изображения:", err));
});

document.getElementById("btn-reset").addEventListener("click", function () {
  const fileInput = document.getElementById("image-input");
  if (fileInput) fileInput.value = "";
  hideUploadedSection();
  document.getElementById("proba-display").innerText = "";
  requestNewPalette();
});

function loadLikedPalettes(showAll = false) {
  fetch("/liked_palettes")
    .then(res => res.json())
    .then(palettes => {
      const container = document.getElementById("liked-palettes");
      container.innerHTML = "";

      if (palettes.length === 0) {
        const msg = document.createElement("p");
        msg.innerText = "Вы еще не лайкнули ни одной палитры.";
        msg.style.fontStyle = "italic";
        container.appendChild(msg);
        return;
      }

      const visiblePalettes = showAll ? palettes : palettes.slice(0, 5);

      visiblePalettes.forEach(p => {
        const div = document.createElement("div");
        div.className = "top-palette";

        const bar = document.createElement("div");
        bar.style.display = "flex";
        p.colors.forEach(c => {
          const cdiv = document.createElement("div");
          cdiv.className = "color-square";
          cdiv.style.backgroundColor = c;

          const span = document.createElement("span");
          span.textContent = c;

          cdiv.appendChild(span);
          bar.appendChild(cdiv);
        });
        div.appendChild(bar);

        const info = document.createElement("p");
        info.textContent = `👍 ${p.likes} | 👎 ${p.dislikes}`;
        div.appendChild(info);

        if (p.image) {
          const img = document.createElement("img");
          img.src = p.image;
          img.style.maxWidth = "200px";
          img.style.marginTop = "8px";
          div.appendChild(img);
        }

        container.appendChild(div);
      });

      if (palettes.length > 5) {
        const btn = document.createElement("button");
        btn.innerText = showAll ? "Свернуть" : "Показать все";
        btn.onclick = () => loadLikedPalettes(!showAll);
        btn.style.marginTop = "10px";
        container.appendChild(btn);
      }
    })
    .catch(err => {
      console.error("Ошибка загрузки понравившихся палитр:", err);
    });
}

document.addEventListener("DOMContentLoaded", () => {
  requestNewPalette();
  loadLikedPalettes();
});

function showUploadedSection(imageUrl) {
  const section = document.getElementById("uploaded-section");
  const img = document.getElementById("uploaded-image");

  if (section && img) {
    img.src = imageUrl;
    section.style.display = "block";
    img.style.display = "block"; 
  }
}

function hideUploadedSection() {
  const section = document.getElementById("uploaded-section");
  const img = document.getElementById("uploaded-image");

  if (section && img) {
    section.style.display = "none";
    img.src = "";
  }
}
