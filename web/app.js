// Set window.MANDILENS_API (see web/config.js) to talk to the AWS Lambda API.
// Empty means the local FastAPI server at /api.
const API_BASE = (window.MANDILENS_API || "").replace(/\/$/, "");
const LAMBDA = API_BASE !== "";

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

const form = document.querySelector("#grade-form");
const fileInput = document.querySelector("#file");
const fileName = document.querySelector("#file-name");
const drop = document.querySelector("#drop");
const button = document.querySelector("#grade-button");
const slip = document.querySelector("#slip-body");
const sampleRow = document.querySelector("#sample-row");
const health = document.querySelector("#health");

const SAMPLE_LABELS = {
  "morning.png": "Morning lot",
  "soft.png": "Soft focus",
  "dark.png": "Too dark",
  "marker.png": "No marker",
  "cutoff.png": "Cut-off fruit",
  "red-tray.png": "Red tray",
};

fetch(LAMBDA ? API_BASE + "/health" : "/api/health")
  .then((response) => response.json())
  .then((body) => {
    health.textContent = LAMBDA ? `AWS Lambda · MandiLens ${body.version}` : `OpenCV ${body.opencv} · MandiLens ${body.version}`;
  })
  .catch(() => {
    health.textContent = "Health check failed.";
  });

fetch(LAMBDA ? "/samples.json" : "/api/samples")
  .then((response) => response.json())
  .then((body) => {
    for (const sample of body.samples) {
      const control = document.createElement("button");
      control.type = "button";
      control.className = "ghost";
      control.textContent = SAMPLE_LABELS[sample.name] || sample.name;
      control.addEventListener("click", () => loadSample(sample.url, control.textContent));
      sampleRow.appendChild(control);
    }
  })
  .catch(() => {});

fileInput.addEventListener("change", () => {
  const file = fileInput.files && fileInput.files[0];
  fileName.textContent = file ? file.name : "JPEG or PNG, up to 8 MB. Shoot from above.";
});

["dragenter", "dragover"].forEach((name) => {
  drop.addEventListener(name, (event) => {
    event.preventDefault();
    drop.classList.add("drag");
  });
});
["dragleave", "drop"].forEach((name) => {
  drop.addEventListener(name, (event) => {
    event.preventDefault();
    drop.classList.remove("drag");
  });
});
drop.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files && event.dataTransfer.files[0];
  if (!file) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  fileName.textContent = file.name;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files && fileInput.files[0];
  if (!file) {
    renderError("Choose a photo first.");
    return;
  }
  const data = new FormData();
  data.append("file", file);
  data.append("marker_mm", document.querySelector("#marker-mm").value || "50");
  await grade(data);
});

async function loadSample(url, label) {
  fileName.textContent = label;
  const response = await fetch(url);
  const blob = await response.blob();
  const data = new FormData();
  data.append("file", new File([blob], label + ".png", { type: "image/png" }));
  data.append("marker_mm", document.querySelector("#marker-mm").value || "50");
  await grade(data);
}

async function grade(data) {
  button.disabled = true;
  slip.innerHTML = '<p class="empty">Reading the tray…</p>';
  try {
    let response;
    if (LAMBDA) {
      const payload = {
        image_base64: await fileToBase64(data.get("file")),
        marker_mm: Number(data.get("marker_mm") || 50),
      };
      response = await fetch(API_BASE + "/lots", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      response = await fetch("/api/grade", { method: "POST", body: data });
    }
    const body = await response.json();
    if (!response.ok) {
      renderError(messageOf(body));
      return;
    }
    renderLot(body);
  } catch (error) {
    renderError("The grader did not answer. Is the local server running?");
  } finally {
    button.disabled = false;
  }
}

function renderLot(lot) {
  slip.innerHTML = "";
  slip.appendChild(statusBlock(lot));
  if (lot.quality) slip.appendChild(chips(lot.quality));
  const picture = lot.rectified_jpeg || lot.preview_jpeg;
  if (picture && lot.fruits && lot.fruits.length) {
    slip.appendChild(stage(picture, lot.fruits));
    slip.appendChild(table(lot));
  }
  if (lot.status === "needs_review") slip.appendChild(reviewForm(lot));
  slip.appendChild(trace(lot.steps || []));
}

function statusBlock(lot) {
  const node = document.createElement("div");
  const destination = lot.destination || "review";
  node.className = "callout " + (lot.status === "routed" ? destination : lot.status);
  const title = document.createElement("strong");
  if (lot.status === "retake") title.textContent = "Retake";
  else if (lot.status === "needs_review") title.textContent = "Needs a person";
  else title.textContent = destinationLabel(lot.destination);
  const text = document.createElement("p");
  text.textContent = lot.reason || "";
  text.style.margin = "0";
  node.append(title, text);
  if (lot.note) {
    const note = document.createElement("p");
    note.className = "meta";
    note.textContent = lot.note;
    node.appendChild(note);
  }
  return node;
}

function chips(quality) {
  const row = document.createElement("div");
  row.className = "chips";
  const items = [
    ["Blur", quality.blur_ok, Math.round(quality.blur_score)],
    ["Exposure", quality.exposure_ok, Math.round(quality.brightness)],
    ["Glare", quality.glare_ok, (quality.glare_fraction * 100).toFixed(1) + "%"],
    ["Marker", quality.marker_found, quality.marker_found ? "in frame" : "missing"],
    ["Tray", quality.background_ok, "chroma " + Math.round(quality.tray_chroma)],
  ];
  for (const [label, ok, detail] of items) {
    const chip = document.createElement("span");
    chip.className = "chip " + (ok ? "ok" : "bad");
    chip.textContent = label + " " + detail;
    row.appendChild(chip);
  }
  return row;
}

function stage(jpeg, fruits) {
  const wrap = document.createElement("div");
  wrap.className = "stage";
  const canvas = document.createElement("canvas");
  wrap.appendChild(canvas);
  const image = new Image();
  image.onload = () => {
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(image, 0, 0);
    for (const fruit of fruits) {
      const radius = fruit.diameter_px / 2;
      ctx.beginPath();
      ctx.arc(fruit.center_x, fruit.center_y, radius, 0, Math.PI * 2);
      ctx.lineWidth = Math.max(2, image.naturalWidth / 280);
      ctx.strokeStyle = gradeColor(fruit.grade);
      ctx.stroke();
      ctx.fillStyle = gradeColor(fruit.grade);
      ctx.font = "600 18px IBM Plex Sans, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(fruit.grade, fruit.center_x, fruit.center_y + 6);
    }
  };
  image.src = "data:image/jpeg;base64," + jpeg;
  return wrap;
}

function table(lot) {
  const tableNode = document.createElement("table");
  tableNode.innerHTML = "<thead><tr><th>Fruit</th><th>mm</th><th>Ripe</th><th>Defect</th><th>Grade</th><th>Trust</th></tr></thead>";
  const body = document.createElement("tbody");
  for (const fruit of lot.fruits) {
    const row = document.createElement("tr");
    if (fruit.needs_review) row.className = "low";
    row.innerHTML = [
      fruit.fruit_id,
      fruit.diameter_mm.toFixed(1),
      fruit.ripeness,
      fruit.defect_pct.toFixed(1) + "%",
      `<span class="grade ${fruit.grade}">${fruit.grade}</span>`,
      Math.round(fruit.confidence * 100) + "%",
    ].map((cell) => `<td>${cell}</td>`).join("");
    body.appendChild(row);
  }
  tableNode.appendChild(body);
  return tableNode;
}

function reviewForm(lot) {
  const formNode = document.createElement("form");
  formNode.className = "review";
  const note = document.createElement("p");
  note.textContent = "These fruit touch the edge or sit on a grade boundary. Accept the grade or override it, then the lot can be routed.";
  formNode.appendChild(note);
  const pending = lot.fruits.filter((fruit) => lot.review_ids.includes(fruit.fruit_id));
  const picks = [];
  for (const fruit of pending) {
    const label = document.createElement("label");
    label.className = "marker-size";
    label.textContent = `Fruit ${fruit.fruit_id} `;
    const select = document.createElement("select");
    select.name = "grade-" + fruit.fruit_id;
    for (const grade of ["A", "B", "C"]) {
      const option = document.createElement("option");
      option.value = grade;
      option.textContent = grade;
      if (grade === fruit.grade) option.selected = true;
      select.appendChild(option);
    }
    label.appendChild(select);
    formNode.appendChild(label);
    picks.push({ fruit, select });
  }
  const submit = document.createElement("button");
  submit.className = "primary";
  submit.type = "submit";
  submit.textContent = "Save review and route";
  formNode.appendChild(submit);
  formNode.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    const decisions = picks.map(({ fruit, select }) => ({
      fruit_id: fruit.fruit_id,
      grade: select.value,
    }));
    try {
      const response = await fetch(`${LAMBDA ? API_BASE : "/api"}/lots/${lot.lot_id}/review`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ decisions }),
      });
      const body = await response.json();
      if (!response.ok) {
        renderError(messageOf(body));
        return;
      }
      if (!body.rectified_jpeg) body.rectified_jpeg = lot.rectified_jpeg;
      if (!body.preview_jpeg) body.preview_jpeg = lot.preview_jpeg;
      renderLot(body);
    } catch (error) {
      renderError("Review did not save.");
    }
  });
  return formNode;
}

function trace(steps) {
  const wrap = document.createElement("div");
  const title = document.createElement("h2");
  title.textContent = "What the agent did";
  title.style.marginTop = "8px";
  const list = document.createElement("ol");
  list.className = "trace";
  steps.forEach((step, index) => {
    const item = document.createElement("li");
    const badge = document.createElement("span");
    badge.className = "step-no";
    badge.textContent = String(index + 1);
    const copy = document.createElement("div");
    const tool = document.createElement("div");
    tool.className = "tool";
    tool.textContent = step.tool + (step.arguments && step.arguments.op ? " " + step.arguments.op : "");
    const because = document.createElement("p");
    because.className = "because";
    because.textContent = step.because;
    copy.append(tool, because);
    item.append(badge, copy);
    list.appendChild(item);
  });
  wrap.append(title, list);
  return wrap;
}

function renderError(text) {
  slip.innerHTML = "";
  const node = document.createElement("div");
  node.className = "callout error";
  node.textContent = text;
  slip.appendChild(node);
}

function messageOf(body) {
  if (!body) return "Something went wrong.";
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map((item) => item.msg || String(item)).join(" ");
  return "Something went wrong.";
}

function destinationLabel(destination) {
  if (destination === "mandi") return "Send to the mandi";
  if (destination === "local") return "Sell locally";
  if (destination === "processing") return "Send to processing";
  return "Routed";
}

function gradeColor(grade) {
  if (grade === "A") return "#2d6a45";
  if (grade === "B") return "#8d5b12";
  return "#c4452d";
}
