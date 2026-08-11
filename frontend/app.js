const state = {
  images: [],
  cameraStream: null,
  focusKeywords: [],
  lastDownloadUrl: "",
  history: [],
  historyPage: 0,
  historyStoryIndex: 0,
  activeHistoryEntry: null,
  previewExpanded: false,
};

const HISTORY_STORAGE_KEY = "ax-rnd-vmd-result-history-v1";
const HISTORY_ASSET_DB_NAME = "ax-rnd-vmd-history-assets-v1";
const HISTORY_ASSET_STORE_NAME = "images";
const PREVIEW_COLLAPSED_COUNT = 4;
const HISTORY_PAGE_SIZE = 5;
// 업로드 전 리사이즈 목표치: Vercel Function 요청 바디 4.5MB 제한을 안전하게 피하기 위한 값.
// 백엔드가 NIM 호출 전 1280px/180KB로 한 번 더 줄이기 때문에 이보다 훨씬 높은 화질이라 정확도 손실은 없음.
const UPLOAD_MAX_DIMENSION = 1920;
const UPLOAD_TARGET_BYTES = 700000;
const EXCEL_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
const PDF_MIME_TYPE = "application/pdf";
let historyAssetDbPromise = null;
let lastExcelBlobUrl = "";
let lastPdfBlobUrl = "";
// initApp()가 다시 호출될 때(탭 재진입, React StrictMode의 이중 effect 등) 이전에 붙인
// 리스너를 확실히 떼어내기 위한 AbortController. 매번 새로 만들어 이전 것은 abort합니다.
let appAbortController = null;

// DOM 요소 참조는 React가 "앱(분석)" 뷰를 마운트할 때마다 새로 만들어지므로,
// 모듈 최초 로드 시 한 번만 querySelector하면 탭을 전환했다 돌아왔을 때 안 붙습니다.
// let로 선언해두고 initApp()에서 매번 다시 조회합니다.
let imageInput;
let cameraFallbackInput;
let startCameraBtn;
let cameraPanel;
let cameraPreview;
let capturePhotoBtn;
let stopCameraBtn;
let previewGrid;
let analyzeBtn;
let batchBtn;
let progressText;
let downloadLink;
let pdfDownloadLink;
let jsonPath;
let keywordInput;
let addKeywordBtn;
let keywordChips;
let historyGrid;
let historyEmpty;
let historyCount;
let historyPagination;
let historyPrevBtn;
let historyNextBtn;
let historyPageLabel;
let historyModal;
let clearHistoryBtn;
let closeHistoryBtn;
let historyPdfDownloadLink;
let historyStorySection;
let historyStoryProgress;
let historyStoryViewport;
let historyStoryPrevBtn;
let historyStoryNextBtn;
let historyPhotoList;
let historyPhotoListCount;

function normalizeHistoryEntries(entries) {
  const normalized = [];
  const batchGroups = new Map();
  entries.forEach((entry) => {
    if (entry.kind !== "batch" || !entry.downloadUrl) {
      normalized.push(entry);
      return;
    }
    let group = batchGroups.get(entry.downloadUrl);
    if (!group) {
      group = {
        ...entry,
        kind: "batch-group",
        imageCount: 0,
        imageNames: [],
        items: [],
        thumbnails: [],
      };
      batchGroups.set(entry.downloadUrl, group);
      normalized.push(group);
    }
    group.imageCount += 1;
    group.imageNames.push(entry.imageName || "image");
    group.items.push({
      imageName: entry.imageName || "image",
      result: entry.result || {},
      jsonPath: entry.jsonPath || "",
      status: entry.status || "success",
      error: entry.error || "",
      thumbnail: entry.thumbnail || "",
    });
    if (entry.thumbnail) {
      group.thumbnails.push(entry.thumbnail);
    }
    if (new Date(entry.createdAt || 0) > new Date(group.createdAt || 0)) {
      group.createdAt = entry.createdAt;
    }
  });
  return normalized.sort((left, right) => new Date(right.createdAt || 0) - new Date(left.createdAt || 0));
}

function loadHistory() {
  try {
    const saved = JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY) || "[]");
    return Array.isArray(saved) ? normalizeHistoryEntries(saved) : [];
  } catch (error) {
    return [];
  }
}

function persistHistory() {
  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(state.history.slice(0, 30)));
  } catch (error) {
    setProgress("결과는 표시했지만 저장 공간이 부족해 이력에 저장하지 못했습니다.");
  }
}

function openHistoryAssetDb() {
  if (!window.indexedDB) {
    return Promise.resolve(null);
  }
  if (!historyAssetDbPromise) {
    historyAssetDbPromise = new Promise((resolve) => {
      const request = window.indexedDB.open(HISTORY_ASSET_DB_NAME, 1);
      request.onupgradeneeded = () => {
        request.result.createObjectStore(HISTORY_ASSET_STORE_NAME, { keyPath: "id" });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => resolve(null);
    });
  }
  return historyAssetDbPromise;
}

async function saveHistoryAssets(entryId, images) {
  const db = await openHistoryAssetDb();
  if (!db || !entryId || !images.some(Boolean)) {
    return false;
  }
  return new Promise((resolve) => {
    const transaction = db.transaction(HISTORY_ASSET_STORE_NAME, "readwrite");
    transaction.objectStore(HISTORY_ASSET_STORE_NAME).put({ id: entryId, images });
    transaction.oncomplete = () => resolve(true);
    transaction.onerror = () => resolve(false);
  });
}

async function loadHistoryAssets(entryId) {
  const db = await openHistoryAssetDb();
  if (!db || !entryId) {
    return [];
  }
  return new Promise((resolve) => {
    const request = db.transaction(HISTORY_ASSET_STORE_NAME, "readonly")
      .objectStore(HISTORY_ASSET_STORE_NAME)
      .get(entryId);
    request.onsuccess = () => resolve(request.result?.images || []);
    request.onerror = () => resolve([]);
  });
}

function applyHistoryAssets(entry, images) {
  if (!Array.isArray(images) || !images.some(Boolean)) {
    return;
  }
  entry.originalImages = images;
  if (Array.isArray(entry.items)) {
    entry.items = entry.items.map((item, index) => ({
      ...item,
      originalImage: images[index] || "",
    }));
  }
}

async function clearHistoryAssets() {
  const db = await openHistoryAssetDb();
  if (!db) {
    return;
  }
  await new Promise((resolve) => {
    const transaction = db.transaction(HISTORY_ASSET_STORE_NAME, "readwrite");
    transaction.objectStore(HISTORY_ASSET_STORE_NAME).clear();
    transaction.oncomplete = resolve;
    transaction.onerror = resolve;
  });
}

function makeHistoryId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function makeThumbnail(image) {
  if (!image?.dataUrl) {
    return Promise.resolve("");
  }
  return new Promise((resolve) => {
    const source = new Image();
    source.onload = () => {
      const maxSize = 360;
      const scale = Math.min(1, maxSize / Math.max(source.naturalWidth, source.naturalHeight));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(source.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(source.naturalHeight * scale));
      const context = canvas.getContext("2d");
      if (!context) {
        resolve("");
        return;
      }
      context.drawImage(source, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL("image/jpeg", 0.72));
    };
    source.onerror = () => resolve("");
    source.src = image.dataUrl;
  });
}

function formatHistoryDate(value) {
  try {
    return new Intl.DateTimeFormat("ko-KR", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch (error) {
    return "저장된 결과";
  }
}

function historyTitle(entry) {
  if (entry.kind === "batch-group") {
    return `Batch analysis · ${entry.imageCount || 0} images`;
  }
  if (entry.kind === "batch") {
    return `일괄 분석 · ${entry.imageName || "이미지"}`;
  }
  return `VMD 분석 · ${entry.imageCount || 1}장`;
}

function addHistoryEntries(entries) {
  state.history = [...entries, ...state.history]
    .sort((left, right) => new Date(right.createdAt || 0) - new Date(left.createdAt || 0))
    .slice(0, 30);
  state.historyPage = 0;
  persistHistory();
  renderHistory();
}

async function saveSingleHistory(payload) {
  const originalImages = state.images.map((image) => image.dataUrl || "");
  const thumbnails = await Promise.all(state.images.map((image) => makeThumbnail(image)));
  const entry = {
    id: makeHistoryId(),
    kind: "group",
    createdAt: new Date().toISOString(),
    imageCount: state.images.length,
    imageNames: state.images.map((image) => image.name),
    result: payload.result,
    jsonPath: payload.jsonPath || "",
    downloadUrl: payload.downloadUrl || "",
    pdfDownloadUrl: payload.pdfDownloadUrl || "",
    thumbnails,
  };
  entry.thumbnail = entry.thumbnails[0] || "";
  await saveHistoryAssets(entry.id, originalImages);
  addHistoryEntries([entry]);
}

async function saveBatchHistory(payload) {
  const results = Array.isArray(payload.results) ? payload.results : [];
  const entries = await Promise.all(results.map(async (item) => {
    const sourceImage = state.images.find((image) => image.name === item.imageName);
    const thumbnail = await makeThumbnail(sourceImage);
    return {
      id: makeHistoryId(),
      kind: "batch",
      createdAt: new Date().toISOString(),
      imageCount: 1,
      imageName: item.imageName || "image",
      result: item.result || {},
      jsonPath: item.jsonPath || "",
      downloadUrl: payload.downloadUrl || "",
      pdfDownloadUrl: payload.pdfDownloadUrl || "",
      status: item.status || "success",
      error: item.error || "",
      thumbnail,
      thumbnails: thumbnail ? [thumbnail] : [],
    };
  }));
  if (entries.length) {
    addHistoryEntries(entries);
  }
}


function setProgress(message) {
  progressText.textContent = message;
}

function setBusy(isBusy) {
  analyzeBtn.disabled = isBusy;
  batchBtn.disabled = isBusy;
}

function selectedZone() {
  return document.querySelector('input[name="zone"]:checked')?.value || "VP";
}

function selectedCriteria() {
  return Array.from(document.querySelectorAll(".criteria-grid input:checked")).map((item) => item.value);
}

function renderFocusKeywords() {
  keywordChips.innerHTML = "";
  state.focusKeywords.forEach((keyword, index) => {
    const chip = document.createElement("span");
    chip.className = "keyword-chip";
    const text = document.createElement("span");
    text.textContent = keyword;
    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.ariaLabel = `${keyword} 삭제`;
    removeButton.textContent = "×";
    removeButton.addEventListener("click", () => {
      state.focusKeywords.splice(index, 1);
      renderFocusKeywords();
    });
    chip.append(text, removeButton);
    keywordChips.appendChild(chip);
  });
}

function addFocusKeyword() {
  const keyword = keywordInput.value.trim();
  if (!keyword || state.focusKeywords.includes(keyword)) {
    keywordInput.value = "";
    return;
  }
  state.focusKeywords.push(keyword);
  keywordInput.value = "";
  renderFocusKeywords();
}

function optionsPayload() {
  return {
    zoneMode: selectedZone(),
    storeType: document.getElementById("storeType").value,
    tone: document.getElementById("tone").value,
    criteria: selectedCriteria(),
    focusKeywords: state.focusKeywords,
    extraCriteria: document.getElementById("extraCriteria").value.trim(),
    temperature: 0.2,
    maxTokens: 2200,
  };
}

function dataUrlByteLength(dataUrl) {
  const base64 = dataUrl.split(",")[1] || "";
  return Math.floor((base64.length * 3) / 4);
}

function resizeImageDataUrl(dataUrl, maxDimension, targetBytes) {
  return new Promise((resolve) => {
    if (dataUrlByteLength(dataUrl) <= targetBytes) {
      resolve(dataUrl);
      return;
    }
    const source = new Image();
    source.onload = () => {
      const scale = Math.min(1, maxDimension / Math.max(source.naturalWidth, source.naturalHeight));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(source.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(source.naturalHeight * scale));
      const context = canvas.getContext("2d");
      if (!context) {
        resolve(dataUrl);
        return;
      }
      context.drawImage(source, 0, 0, canvas.width, canvas.height);
      let output = dataUrl;
      for (const quality of [0.85, 0.75, 0.65, 0.5, 0.35]) {
        output = canvas.toDataURL("image/jpeg", quality);
        if (dataUrlByteLength(output) <= targetBytes) {
          break;
        }
      }
      resolve(output);
    };
    source.onerror = () => resolve(dataUrl);
    source.src = dataUrl;
  });
}

function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = async () => {
      const dataUrl = await resizeImageDataUrl(reader.result, UPLOAD_MAX_DIMENSION, UPLOAD_TARGET_BYTES);
      resolve({ name: file.name, type: file.type, dataUrl });
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function addFiles(files) {
  const next = await Promise.all(Array.from(files).filter((file) => file.type.startsWith("image/")).map(readFile));
  state.images.push(...next);
  renderPreviews();
}

function cameraFileName() {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `camera-${stamp}.jpg`;
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    cameraFallbackInput.click();
    return;
  }
  try {
    stopCamera();
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" } },
      audio: false,
    });
    state.cameraStream = stream;
    cameraPreview.srcObject = stream;
    cameraPanel.classList.remove("hidden");
    await cameraPreview.play();
  } catch (error) {
    setProgress(`카메라를 열 수 없습니다: ${error.message}`);
  }
}

function stopCamera() {
  if (state.cameraStream) {
    state.cameraStream.getTracks().forEach((track) => track.stop());
  }
  state.cameraStream = null;
  cameraPreview.srcObject = null;
  cameraPanel.classList.add("hidden");
}

async function capturePhoto() {
  if (!state.cameraStream) {
    return;
  }
  const width = cameraPreview.videoWidth || 1280;
  const height = cameraPreview.videoHeight || 720;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }
  context.drawImage(cameraPreview, 0, 0, width, height);
  const dataUrl = await resizeImageDataUrl(
    canvas.toDataURL("image/jpeg", 0.92),
    UPLOAD_MAX_DIMENSION,
    UPLOAD_TARGET_BYTES
  );
  state.images.push({
    name: cameraFileName(),
    type: "image/jpeg",
    dataUrl,
  });
  renderPreviews();
}

function renderPreviews() {
  previewGrid.innerHTML = "";
  if (state.images.length <= PREVIEW_COLLAPSED_COUNT) {
    state.previewExpanded = false;
  }

  const isCollapsed = state.images.length > PREVIEW_COLLAPSED_COUNT && !state.previewExpanded;
  const visibleImages = isCollapsed ? state.images.slice(0, PREVIEW_COLLAPSED_COUNT) : state.images;

  visibleImages.forEach((image) => {
    const index = state.images.indexOf(image);
    const card = document.createElement("div");
    card.className = "preview-card";
    card.innerHTML = `
      <img src="${image.dataUrl}" alt="${image.name}" />
      <button type="button" aria-label="${image.name} 삭제">×</button>
    `;
    card.querySelector("button").addEventListener("click", () => {
      state.images.splice(index, 1);
      renderPreviews();
    });
    previewGrid.appendChild(card);
  });

  if (state.images.length > PREVIEW_COLLAPSED_COUNT) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "preview-toggle";
    toggle.setAttribute("aria-expanded", String(state.previewExpanded));
    toggle.setAttribute("aria-controls", "previewGrid");
    toggle.textContent = state.previewExpanded
      ? "접기"
      : `+${state.images.length - PREVIEW_COLLAPSED_COUNT}장`;
    toggle.addEventListener("click", () => {
      state.previewExpanded = !state.previewExpanded;
      renderPreviews();
    });
    previewGrid.appendChild(toggle);
  }
}

function renderList(elementId, items) {
  const node = typeof elementId === "string" ? document.getElementById(elementId) : elementId;
  node.innerHTML = "";
  if (!items || items.length === 0) {
    const li = document.createElement("li");
    li.textContent = "감지된 항목이 없습니다.";
    node.appendChild(li);
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    node.appendChild(li);
  });
}

function renderScoreBars(scores = {}, elementId = "scoreBars") {
  const labels = {
    layout: "구성/레이아웃",
    presentation_mood: "연출/분위기",
    brand_fit: "브랜드 적합성",
    color_harmony: "색상 조화",
    cleanliness: "청결/정돈",
    customer_attention: "시선 유도",
    season_concept_fit: "시즌 컨셉",
  };
  const root = typeof elementId === "string" ? document.getElementById(elementId) : elementId;
  root.innerHTML = "";
  Object.entries(labels).forEach(([key, label]) => {
    const score = Number(scores[key] || 0);
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `
      <span>${label}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${Math.max(0, Math.min(100, score))}%"></span></span>
      <strong>${score}</strong>
    `;
    root.appendChild(row);
  });
}

function renderObstacles(items = [], elementId = "obstacles") {
  const root = typeof elementId === "string" ? document.getElementById(elementId) : elementId;
  root.innerHTML = "";
  if (!items.length) {
    root.innerHTML = '<span class="pill">감지된 방해물이 없습니다.</span>';
    return;
  }
  items.forEach((item) => {
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = `${item.object || "object"} · ${item.location || "location"} · ${item.reason || ""}`;
    root.appendChild(pill);
  });
}

function renderCriteriaEvaluations(result = {}, elementId = "scoreBars") {
  const root = typeof elementId === "string" ? document.getElementById(elementId) : elementId;
  const evaluations = Array.isArray(result.criteria_evaluations)
    ? result.criteria_evaluations.filter((item) => item && item.criterion)
    : [];

  if (!evaluations.length) {
    renderScoreBars(result.scores || {}, elementId);
    return;
  }

  root.innerHTML = "";
  const list = document.createElement("div");
  list.className = "criteria-result-list";

  evaluations.forEach((item) => {
    const row = document.createElement("article");
    row.className = "criteria-result-item";

    const heading = document.createElement("div");
    heading.className = "criteria-result-head";
    const title = document.createElement("h4");
    title.className = "criteria-result-title";
    title.textContent = item.criterion;
    const score = document.createElement("strong");
    score.className = "criteria-result-score";
    score.textContent = `${item.score ?? "--"}점`;
    heading.append(title, score);

    const fields = document.createElement("div");
    fields.className = "criteria-result-grid";
    [
      ["근거", item.evidence],
      ["문제점", item.issue],
      ["개선안", item.suggestion],
    ].forEach(([label, value]) => {
      const field = document.createElement("div");
      field.className = "criteria-result-field";
      const fieldLabel = document.createElement("strong");
      fieldLabel.textContent = label;
      const fieldText = document.createElement("p");
      fieldText.textContent = value || "내용 없음";
      field.append(fieldLabel, fieldText);
      fields.appendChild(field);
    });

    row.append(heading, fields);
    list.appendChild(row);
  });
  root.appendChild(list);
}

function renderHistory() {
  historyCount.textContent = String(state.history.length);
  historyGrid.innerHTML = "";
  historyEmpty.classList.toggle("hidden", state.history.length > 0);
  state.history.forEach((entry) => {
    const result = entry.result || {};
    const card = document.createElement("button");
    card.type = "button";
    card.className = "history-card";
    card.addEventListener("click", () => openHistoryDetail(entry));

    if (entry.thumbnail) {
      const image = document.createElement("img");
      image.src = entry.thumbnail;
      image.alt = entry.imageName || "분석 이미지";
      image.className = "history-card-image";
      card.appendChild(image);
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "history-card-image history-card-placeholder";
      placeholder.textContent = "VMD";
      card.appendChild(placeholder);
    }

    const content = document.createElement("div");
    content.className = "history-card-content";
    const heading = document.createElement("div");
    heading.className = "history-card-heading";
    const title = document.createElement("strong");
    title.textContent = historyTitle(entry);
    const date = document.createElement("time");
    date.textContent = formatHistoryDate(entry.createdAt);
    heading.append(title, date);

    const metrics = document.createElement("div");
    metrics.className = "history-card-metrics";
    const score = document.createElement("strong");
    score.textContent = `${result.total_score ?? "--"}점`;
    const grade = document.createElement("span");
    grade.textContent = result.grade || entry.status || "평가 보류";
    const zone = document.createElement("span");
    zone.textContent = result.user_selected_zone || "VP";
    metrics.append(score, grade, zone);

    const summary = document.createElement("p");
    summary.textContent = result.final_summary || entry.error || "상세 결과를 확인하세요.";
    content.append(heading, metrics, summary);
    card.appendChild(content);
    historyGrid.appendChild(card);
  });
}

function closeHistoryDetail() {
  historyModal.classList.add("hidden");
  document.body.classList.remove("modal-open");
}

function historyText(value, fallback = "No data") {
  if (Array.isArray(value)) {
    return value.filter(Boolean).join("\n");
  }
  return value === undefined || value === null || value === "" ? fallback : String(value);
}

function createStoryBlock(title) {
  const block = document.createElement("section");
  block.className = "detail-block wide";
  const heading = document.createElement("h3");
  heading.textContent = title;
  block.appendChild(heading);
  return block;
}

function createStoryListBlock(title, items) {
  const block = createStoryBlock(title);
  const list = document.createElement("ul");
  renderList(list, Array.isArray(items) ? items : []);
  block.appendChild(list);
  return block;
}

function createStorySlide(title) {
  const slide = document.createElement("section");
  slide.className = "history-story-slide";
  slide.dataset.title = title;
  return slide;
}

function createStoryMetric(className, label, value, detail) {
  const card = document.createElement("article");
  card.className = className;
  const labelNode = document.createElement("p");
  labelNode.textContent = label;
  const valueNode = document.createElement("strong");
  valueNode.textContent = value;
  const detailNode = document.createElement("span");
  detailNode.textContent = detail;
  card.append(labelNode, valueNode, detailNode);
  return card;
}

function historyCarouselItems(entry) {
  if (Array.isArray(entry.items) && entry.items.length) {
    return entry.items;
  }
  if (Array.isArray(entry.thumbnails) && entry.thumbnails.length) {
    return entry.thumbnails.map((thumbnail, index) => ({
      thumbnail,
      originalImage: entry.originalImages?.[index] || "",
      imageName: entry.imageNames?.[index],
      result: entry.result || {},
    }));
  }
  return [{
    thumbnail: entry.thumbnail || "",
    originalImage: entry.originalImages?.[0] || "",
    imageName: entry.imageName,
    result: entry.result || {},
  }];
}

function renderHistoryPhotoList(entry, selectedIndex = 0) {
  const items = historyCarouselItems(entry);
  historyPhotoList.innerHTML = "";
  historyPhotoListCount.textContent = `${items.length}`;
  items.forEach((item, index) => {
    const result = item.result || entry.result || {};
    const button = document.createElement("button");
    button.type = "button";
    button.className = "history-photo-list-item";
    button.classList.toggle("active", index === selectedIndex);
    button.addEventListener("click", () => {
      renderHistoryStory(entry, index);
    });

    if (item.thumbnail) {
      const image = document.createElement("img");
      image.className = "history-photo-list-thumb";
      image.src = item.thumbnail;
      image.alt = item.imageName || `Image ${index + 1}`;
      button.appendChild(image);
    } else {
      const placeholder = document.createElement("span");
      placeholder.className = "history-photo-list-thumb history-card-placeholder";
      placeholder.textContent = `${index + 1}`;
      button.appendChild(placeholder);
    }

    const content = document.createElement("span");
    content.className = "history-photo-list-content";
    const name = document.createElement("strong");
    name.textContent = item.imageName || `Image ${index + 1}`;
    const meta = document.createElement("span");
    meta.textContent = `${result.total_score ?? "--"} · ${result.user_selected_zone || "VP"}`;
    content.append(name, meta);
    button.appendChild(content);
    historyPhotoList.appendChild(button);
  });
}

function renderHistoryStory(entry, startImageIndex = 0) {
  const carouselItems = historyCarouselItems(entry);
  let imageIndex = Math.max(0, Math.min(startImageIndex, carouselItems.length - 1));
  const activeItem = carouselItems[imageIndex] || {};
  const result = activeItem.result || entry.result || {};
  const photo = result.photo_quality || {};
  const mannequin = result.mannequin || {};
  historyStoryViewport.innerHTML = "";
  renderHistoryPhotoList(entry, imageIndex);

  const overview = createStorySlide("\uc885\ud569 \uacb0\uacfc");
  const overviewLayout = document.createElement("div");
  overviewLayout.className = "history-overview-layout";

  const imageBlock = createStoryBlock("\ubd84\uc11d \uc774\ubbf8\uc9c0");
  imageBlock.classList.remove("wide");
  const imageStage = document.createElement("div");
  imageStage.className = "history-story-image-stage";
  const image = document.createElement("img");
  image.className = "history-story-image";
  image.alt = activeItem.imageName || entry.imageName || entry.imageNames?.join(", ") || "Analysis image";
  const imagePlaceholder = document.createElement("p");
  imagePlaceholder.className = "body-text";
  imagePlaceholder.textContent = "\uc0ac\uc9c4 \ubbf8\ub9ac\ubcf4\uae30 \uc5c6\uc74c";
  const imageCount = document.createElement("span");
  imageCount.className = "history-story-image-count muted";
  const imagePrev = document.createElement("button");
  imagePrev.type = "button";
  imagePrev.className = "icon-button history-story-image-prev";
  imagePrev.setAttribute("aria-label", "Previous image");
  imagePrev.title = "Previous image";
  imagePrev.textContent = "←";
  const imageNext = document.createElement("button");
  imageNext.type = "button";
  imageNext.className = "icon-button history-story-image-next";
  imageNext.setAttribute("aria-label", "Next image");
  imageNext.title = "Next image";
  imageNext.textContent = "→";

  const updateStoryImage = () => {
    const currentItem = carouselItems[imageIndex] || {};
    const sourceImage = currentItem.originalImage || currentItem.thumbnail;
    const hasImage = Boolean(sourceImage);
    image.classList.toggle("hidden", !hasImage);
    imagePlaceholder.classList.toggle("hidden", hasImage);
    imagePrev.classList.toggle("hidden", carouselItems.length < 2);
    imageNext.classList.toggle("hidden", carouselItems.length < 2);
    imageCount.classList.toggle("hidden", carouselItems.length < 2);
    if (hasImage) {
      image.src = sourceImage;
      imageCount.textContent = `${imageIndex + 1} / ${carouselItems.length}`;
    }
  };
  imagePrev.addEventListener("click", (event) => {
    event.stopPropagation();
    renderHistoryStory(entry, (imageIndex - 1 + carouselItems.length) % carouselItems.length);
  });
  imageNext.addEventListener("click", (event) => {
    event.stopPropagation();
    renderHistoryStory(entry, (imageIndex + 1) % carouselItems.length);
  });
  imageStage.append(image, imagePlaceholder, imagePrev, imageNext, imageCount);
  imageBlock.appendChild(imageStage);
  updateStoryImage();

  const metrics = document.createElement("div");
  metrics.className = "history-overview-metrics";
  metrics.append(
    createStoryMetric("score-card", "Total Score", String(result.total_score ?? "--"), result.grade || "--"),
    createStoryMetric("metric-card", "Zone", `${result.user_selected_zone || "VP"} / ${result.ai_detected_zone || "UNKNOWN"}`, `confidence ${Math.round((result.zone_confidence || 0) * 100)}%`),
    createStoryMetric("metric-card", "Photo Quality", String(photo.score ?? "--"), photo.needs_retake ? "retake recommended" : "ready to use"),
    createStoryMetric("metric-card", "Mannequin", mannequin.exists ? "Detected" : "Not detected", mannequin.type || "type --"),
  );
  overviewLayout.append(imageBlock, metrics);
  overview.appendChild(overviewLayout);
  historyStoryViewport.appendChild(overview);

  const criteriaSlide = createStorySlide("\ud56d\ubaa9\ubcc4 \ud3c9\uac00");
  const criteriaBlock = createStoryBlock("\ud56d\ubaa9\ubcc4 \ud3c9\uac00");
  const criteriaRoot = document.createElement("div");
  criteriaRoot.className = "score-bars";
  renderCriteriaEvaluations(result, criteriaRoot);
  criteriaBlock.appendChild(criteriaRoot);
  criteriaSlide.appendChild(criteriaBlock);
  historyStoryViewport.appendChild(criteriaSlide);

  const photoSlide = createStorySlide("\uc0ac\uc9c4 \ud488\uc9c8");
  const photoLayout = document.createElement("div");
  photoLayout.className = "detail-layout";
  const photoBlock = createStoryBlock("\uc0ac\uc9c4 \ud488\uc9c8");
  const photoText = document.createElement("p");
  photoText.className = "body-text";
  photoText.textContent = historyText(photo.comment);
  photoBlock.appendChild(photoText);
  const mannequinBlock = createStoryBlock("\ub9c8\ub124\ud0b9");
  const mannequinText = document.createElement("p");
  mannequinText.className = "body-text";
  mannequinText.textContent = historyText(mannequin.comment, mannequin.exists ? mannequin.type || "Detected" : "Not detected");
  mannequinBlock.appendChild(mannequinText);
  photoLayout.append(photoBlock, mannequinBlock);
  photoSlide.appendChild(photoLayout);
  historyStoryViewport.appendChild(photoSlide);

  historyStoryViewport.appendChild(createStoryListBlock("\uc798\ub41c \uc810", result.positive_points));
  historyStoryViewport.lastElementChild.dataset.title = "\uc798\ub41c \uc810";
  historyStoryViewport.appendChild(createStoryListBlock("\ubb38\uc81c\uc810", result.critical_issues || result.detected_issues));
  historyStoryViewport.lastElementChild.dataset.title = "\ubb38\uc81c\uc810";
  historyStoryViewport.appendChild(createStoryListBlock("\uac1c\uc120 \uc81c\uc548", result.improvement_suggestions || result.improvement_actions));
  historyStoryViewport.lastElementChild.dataset.title = "\uac1c\uc120 \uc81c\uc548";

  const summarySlide = createStorySlide("\ucd5c\uc885 \uc694\uc57d");
  const summaryBlock = createStoryBlock("\ucd5c\uc885 \uc694\uc57d");
  const summaryText = document.createElement("p");
  summaryText.className = "body-text";
  summaryText.textContent = historyText(result.final_summary || result.overall_improvement_summary);
  summaryBlock.appendChild(summaryText);
  summarySlide.appendChild(summaryBlock);
  historyStoryViewport.appendChild(summarySlide);

  const obstaclesSlide = createStorySlide("\ubc29\ud574 \uc694\uc18c");
  const obstaclesBlock = createStoryBlock("\ubc29\ud574 \uc694\uc18c");
  const obstaclesRoot = document.createElement("div");
  obstaclesRoot.className = "pill-list";
  renderObstacles(Array.isArray(result.obstacles) ? result.obstacles : [], obstaclesRoot);
  obstaclesBlock.appendChild(obstaclesRoot);
  obstaclesSlide.appendChild(obstaclesBlock);
  historyStoryViewport.appendChild(obstaclesSlide);

  state.historyStoryIndex = 0;
  showHistoryStory(0);
}

function showHistoryStory(index) {
  const slides = Array.from(historyStoryViewport.children);
  if (!slides.length) {
    return;
  }
  state.historyStoryIndex = Math.max(0, Math.min(index, slides.length - 1));
  slides.forEach((slide, slideIndex) => slide.classList.toggle("hidden", slideIndex !== state.historyStoryIndex));
  const activeSlide = slides[state.historyStoryIndex];
  historyStorySection.textContent = activeSlide.dataset.title || "Result";
  historyStoryProgress.textContent = `${state.historyStoryIndex + 1} / ${slides.length}`;
  historyStoryPrevBtn.disabled = state.historyStoryIndex === 0;
  historyStoryNextBtn.disabled = state.historyStoryIndex === slides.length - 1;
}

async function openHistoryDetail(entry) {
  state.activeHistoryEntry = entry;
  document.getElementById("historyDetailTitle").textContent = historyTitle(entry);
  document.getElementById("historyDetailMeta").textContent = `${formatHistoryDate(entry.createdAt)} 쨌 ${entry.imageNames?.join(", ") || entry.imageName || "Saved result"}`;
  renderHistoryStory(entry);

  const detailDownloadLink = document.getElementById("historyDownloadLink");
  detailDownloadLink.classList.toggle("hidden", !entry.downloadUrl);
  if (entry.downloadUrl) {
    detailDownloadLink.href = entry.downloadUrl;
  }
  historyPdfDownloadLink.classList.toggle("hidden", !entry.pdfDownloadUrl);
  if (entry.pdfDownloadUrl) {
    historyPdfDownloadLink.href = entry.pdfDownloadUrl;
  }
  document.getElementById("historyJsonPath").textContent = entry.jsonPath ? `JSON: ${entry.jsonPath}` : "";
  historyModal.classList.remove("hidden");
  document.body.classList.add("modal-open");

  const originalImages = await loadHistoryAssets(entry.id);
  if (originalImages.length && state.activeHistoryEntry === entry) {
    applyHistoryAssets(entry, originalImages);
    renderHistoryStory(entry);
  }
}

function setupTabs(signal) {
  // data-tab-target이 있는 버튼만 대상으로 합니다. App.jsx 상단의 "홈페이지/앱(분석)" 전환
  // 버튼도 같은 .tab-button 클래스를 쓰지만 data-tab-target이 없어서 자연히 제외됩니다.
  document.querySelectorAll("[data-tab-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.dataset.tabTarget;
      document.querySelectorAll("[data-tab-target]").forEach((item) => item.classList.toggle("active", item === button));
      document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("hidden", panel.id !== targetId));
    }, { signal });
  });
}

function base64ToBlob(base64, mimeType) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mimeType });
}

function setDownloadLinkFromBase64(linkEl, base64, mimeType, fileName, prevBlobUrl) {
  if (!base64) {
    return prevBlobUrl;
  }
  if (prevBlobUrl) {
    URL.revokeObjectURL(prevBlobUrl);
  }
  const url = URL.createObjectURL(base64ToBlob(base64, mimeType));
  linkEl.href = url;
  linkEl.setAttribute("download", fileName || "download");
  linkEl.classList.remove("hidden");
  return url;
}

function applyDownloadLinks(payload) {
  if (payload.excelBase64) {
    lastExcelBlobUrl = setDownloadLinkFromBase64(downloadLink, payload.excelBase64, EXCEL_MIME_TYPE, payload.excelFileName, lastExcelBlobUrl);
  } else {
    const downloadUrl = payload.downloadUrl || (payload.excelPath ? `/api/download?file=${encodeURIComponent(payload.excelPath)}` : "");
    if (downloadUrl) {
      downloadLink.href = downloadUrl;
      downloadLink.classList.remove("hidden");
    }
  }
  if (payload.pdfBase64) {
    lastPdfBlobUrl = setDownloadLinkFromBase64(pdfDownloadLink, payload.pdfBase64, PDF_MIME_TYPE, payload.pdfFileName, lastPdfBlobUrl);
  } else {
    const pdfUrl = payload.pdfDownloadUrl || (payload.pdfPath ? `/api/download?file=${encodeURIComponent(payload.pdfPath)}` : "");
    pdfDownloadLink.classList.toggle("hidden", !pdfUrl);
    if (pdfUrl) {
      pdfDownloadLink.href = pdfUrl;
    }
  }
}

function renderResult(result, payload) {
  state.lastResult = result;
  state.lastPayload = payload;
  document.getElementById("totalScore").textContent = result.total_score ?? "--";
  document.getElementById("grade").textContent = result.grade || "평가 보류";
  document.getElementById("zoneResult").textContent = `${result.user_selected_zone || "VP"} → ${result.ai_detected_zone || "UNKNOWN"}`;
  document.getElementById("zoneConfidence").textContent = `confidence ${Math.round((result.zone_confidence || 0) * 100)}%`;

  const photo = result.photo_quality || {};
  document.getElementById("photoScore").textContent = photo.score ?? "--";
  document.getElementById("retakeFlag").textContent = photo.needs_retake ? "재촬영 권장" : "촬영 사용 가능";
  document.getElementById("photoComment").textContent = photo.comment || "사진 품질 코멘트가 없습니다.";

  const mannequin = result.mannequin || {};
  document.getElementById("mannequinFlag").textContent = mannequin.exists ? "있음" : "없음";
  document.getElementById("mannequinType").textContent = mannequin.type || "type --";
  document.getElementById("mannequinComment").textContent = mannequin.exists
    ? mannequin.comment || "마네킹 판정 근거가 없습니다."
    : "사진에서 마네킹이 감지되지 않았습니다.";

  renderCriteriaEvaluations(result);
  renderList("positivePoints", result.positive_points || []);
  renderList("criticalIssues", result.critical_issues || []);
  renderList("improvements", result.improvement_suggestions || []);
  renderObstacles(result.obstacles || []);

  document.getElementById("finalSummary").textContent = result.final_summary || "최종 요약이 없습니다.";

  applyDownloadLinks(payload);
  jsonPath.textContent = payload.jsonPath ? `JSON: ${payload.jsonPath}` : "";
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

async function analyze() {
  if (!state.images.length) {
    setProgress("분석할 사진을 먼저 추가하세요.");
    return;
  }
  setBusy(true);
  downloadLink.classList.add("hidden");
  pdfDownloadLink.classList.add("hidden");
  jsonPath.textContent = "";
  try {
    setProgress("이미지를 준비하고 NVIDIA NIM으로 분석 요청을 보내는 중입니다.");
    const payload = await postJson("/api/analyze", { images: state.images, options: optionsPayload() });
    renderResult(payload.result, payload);
    await saveSingleHistory(payload);
    setProgress(`분석 완료 · ${payload.elapsedSeconds}s`);
  } catch (error) {
    setProgress(`분석 실패: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

async function batchAnalyze() {
  if (!state.images.length) {
    setProgress("엑셀로 정리할 사진을 먼저 추가하세요.");
    return;
  }
  setBusy(true);
  downloadLink.classList.add("hidden");
  pdfDownloadLink.classList.add("hidden");
  jsonPath.textContent = "";
  try {
    setProgress("이미지별 일괄 분석을 시작합니다. 사진 수에 따라 시간이 걸릴 수 있습니다.");
    const payload = await postJson("/api/batch-analyze", { images: state.images, options: optionsPayload() });
    if (payload.results?.length) {
      renderResult(payload.results[0].result, { jsonPath: payload.results[0].jsonPath });
    }
    await saveBatchHistory(payload);
    applyDownloadLinks(payload);
    setProgress(`Excel·PDF 생성 완료 · ${payload.count}개 이미지 · ${payload.elapsedSeconds}s`);
  } catch (error) {
    setProgress(`Excel·PDF 생성 실패: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

// "앱(분석)" 뷰가 마운트될 때마다(최초 진입 + 다른 탭에서 돌아올 때) App.jsx가 호출합니다.
// React가 매번 새 DOM 노드를 만들기 때문에, 요소 조회와 이벤트 바인딩을 여기서 다시 합니다.
export function initApp() {
  appAbortController?.abort();
  appAbortController = new AbortController();
  const { signal } = appAbortController;

  imageInput = document.getElementById("imageInput");
  cameraFallbackInput = document.getElementById("cameraFallbackInput");
  startCameraBtn = document.getElementById("startCameraBtn");
  cameraPanel = document.getElementById("cameraPanel");
  cameraPreview = document.getElementById("cameraPreview");
  capturePhotoBtn = document.getElementById("capturePhotoBtn");
  stopCameraBtn = document.getElementById("stopCameraBtn");
  previewGrid = document.getElementById("previewGrid");
  analyzeBtn = document.getElementById("analyzeBtn");
  batchBtn = document.getElementById("batchBtn");
  progressText = document.getElementById("progressText");
  downloadLink = document.getElementById("downloadLink");
  pdfDownloadLink = document.getElementById("pdfDownloadLink");
  jsonPath = document.getElementById("jsonPath");
  keywordInput = document.getElementById("keywordInput");
  addKeywordBtn = document.getElementById("addKeywordBtn");
  keywordChips = document.getElementById("keywordChips");
  historyGrid = document.getElementById("historyGrid");
  historyEmpty = document.getElementById("historyEmpty");
  historyCount = document.getElementById("historyCount");
  historyPagination = document.getElementById("historyPagination");
  historyPrevBtn = document.getElementById("historyPrevBtn");
  historyNextBtn = document.getElementById("historyNextBtn");
  historyPageLabel = document.getElementById("historyPageLabel");
  historyModal = document.getElementById("historyModal");
  clearHistoryBtn = document.getElementById("clearHistoryBtn");
  closeHistoryBtn = document.getElementById("closeHistoryBtn");
  historyPdfDownloadLink = document.getElementById("historyPdfDownloadLink");
  historyStorySection = document.getElementById("historyStorySection");
  historyStoryProgress = document.getElementById("historyStoryProgress");
  historyStoryViewport = document.getElementById("historyStoryViewport");
  historyStoryPrevBtn = document.getElementById("historyStoryPrevBtn");
  historyStoryNextBtn = document.getElementById("historyStoryNextBtn");
  historyPhotoList = document.getElementById("historyPhotoList");
  historyPhotoListCount = document.getElementById("historyPhotoListCount");

  imageInput.addEventListener("change", async (event) => {
    await addFiles(event.target.files);
    event.target.value = "";
  }, { signal });
  cameraFallbackInput.addEventListener("change", async (event) => {
    await addFiles(event.target.files);
    event.target.value = "";
  }, { signal });
  analyzeBtn.addEventListener("click", analyze, { signal });
  batchBtn.addEventListener("click", batchAnalyze, { signal });
  startCameraBtn.addEventListener("click", startCamera, { signal });
  capturePhotoBtn.addEventListener("click", capturePhoto, { signal });
  stopCameraBtn.addEventListener("click", stopCamera, { signal });
  addKeywordBtn.addEventListener("click", addFocusKeyword, { signal });
  keywordInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addFocusKeyword();
    }
  }, { signal });

  const dropzone = document.querySelector(".dropzone");
  dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropzone.classList.add("dragging");
  }, { signal });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragging"), { signal });
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragging");
    addFiles(event.dataTransfer.files);
  }, { signal });

  state.history = loadHistory();
  renderHistory();
  setupTabs(signal);
  closeHistoryBtn.addEventListener("click", closeHistoryDetail, { signal });
  historyModal.addEventListener("click", (event) => {
    if (event.target === historyModal) {
      closeHistoryDetail();
    }
  }, { signal });
  clearHistoryBtn.addEventListener("click", () => {
    if (!state.history.length) {
      return;
    }
    state.history = [];
    state.historyPage = 0;
    void clearHistoryAssets();
    persistHistory();
    renderHistory();
  }, { signal });
  historyPrevBtn.addEventListener("click", () => {
    if (state.historyPage > 0) {
      state.historyPage -= 1;
      renderHistory();
    }
  }, { signal });
  historyNextBtn.addEventListener("click", () => {
    if ((state.historyPage + 1) * HISTORY_PAGE_SIZE < state.history.length) {
      state.historyPage += 1;
      renderHistory();
    }
  }, { signal });
  historyStoryPrevBtn.addEventListener("click", () => showHistoryStory(state.historyStoryIndex - 1), { signal });
  historyStoryNextBtn.addEventListener("click", () => showHistoryStory(state.historyStoryIndex + 1), { signal });

  // 이전에 쌓아둔 state(업로드 이미지, 키워드, 마지막 분석 결과)를 새 DOM에 복원합니다.
  renderPreviews();
  renderFocusKeywords();
  if (state.lastResult) {
    renderResult(state.lastResult, state.lastPayload || {});
  }
}

// window/document 레벨 리스너는 페이지 생명주기 동안 유지되는 대상이라 모듈 로드 시 한 번만 등록합니다.
window.addEventListener("beforeunload", stopCamera);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && historyModal && !historyModal.classList.contains("hidden")) {
    closeHistoryDetail();
  }
});
