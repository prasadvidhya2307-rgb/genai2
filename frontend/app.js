// FastAPI serves the frontend and API from the same origin. An empty base URL
// makes every request relative, for example /health and /chat.
const configuredApiUrl = window.RAG_API_URL || '';
const API_BASE_URL = configuredApiUrl.replace(/\/$/, '');

const SOURCES_STORAGE_KEY = 'sourceAtlasSources';
const THEME_STORAGE_KEY = 'sourceAtlasTheme';

const state = {
  sources: loadSources(),
  activeSourceType: 'pdf',
  selectedFile: null,
  isChatLoading: false,
};

let activeRequestCount = 0;
let lottieAnimation = null;

const elements = {
  sourceTabs: [...document.querySelectorAll('.source-tab')],
  sourceForms: [...document.querySelectorAll('[data-source-form]')],
  ingestStatus: document.querySelector('#ingest-status'),
  sourceList: document.querySelector('#source-list'),
  sourceCount: document.querySelector('#source-count'),
  pdfInput: document.querySelector('#pdf-input'),
  pdfDropzone: document.querySelector('#pdf-dropzone'),
  pdfFileName: document.querySelector('#pdf-file-name'),
  pdfForm: document.querySelector('#pdf-form'),
  websiteForm: document.querySelector('#website-form'),
  websiteUrl: document.querySelector('#website-url'),
  youtubeForm: document.querySelector('#youtube-form'),
  youtubeUrl: document.querySelector('#youtube-url'),
  chatForm: document.querySelector('#chat-form'),
  questionInput: document.querySelector('#question-input'),
  sourceFilter: document.querySelector('#source-filter'),
  topK: document.querySelector('#top-k'),
  sendButton: document.querySelector('#send-button'),
  chatEmpty: document.querySelector('#chat-empty'),
  chatLoading: document.querySelector('#chat-loading'),
  chatResponse: document.querySelector('#chat-response'),
  chatStatus: document.querySelector('#chat-status'),
  answerText: document.querySelector('#answer-text'),
  answerSources: document.querySelector('#answer-sources'),
  apiBaseLabel: document.querySelector('#api-base-label'),
  themeToggle: document.querySelector('#theme-toggle'),
  loadingOverlay: document.querySelector('#loading-overlay'),
  loadingAnimation: document.querySelector('#loading-animation'),
  loadingTitle: document.querySelector('#loading-title'),
  loadingMessage: document.querySelector('#loading-message'),
};

function loadSources() {
  try {
    const stored = JSON.parse(localStorage.getItem(SOURCES_STORAGE_KEY) || '[]');
    return Array.isArray(stored) ? stored.filter(isValidSource) : [];
  } catch {
    return [];
  }
}

function saveSources() {
  try {
    localStorage.setItem(SOURCES_STORAGE_KEY, JSON.stringify(state.sources));
  } catch {
    // The app remains usable when browser storage is unavailable.
  }
}

function isValidSource(source) {
  return source && typeof source === 'object' && typeof source.source_id === 'string';
}

function applyTheme(theme) {
  const isDark = theme === 'dark';
  document.documentElement.dataset.theme = isDark ? 'dark' : 'light';
  elements.themeToggle.setAttribute('aria-pressed', String(isDark));
  elements.themeToggle.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
  elements.themeToggle.title = isDark ? 'Switch to light mode' : 'Switch to dark mode';
}

function toggleTheme() {
  const nextTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  applyTheme(nextTheme);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  } catch {
    // Theme still works for this page if browser storage is unavailable.
  }
}

function getLoadingMessage(path, options = {}) {
  if (options.method === 'DELETE') return 'Deleting the source from your library…';
  if (path === '/sources/pdf') return 'Extracting, chunking, and embedding your PDF…';
  if (path === '/sources/website') return 'Extracting and embedding your website…';
  if (path === '/sources/youtube') return 'Extracting and embedding your transcript…';
  if (path === '/chat') return 'Retrieving relevant chunks and thinking…';
  return 'Loading your request…';
}

function showLoadingOverlay(path, options = {}) {
  activeRequestCount += 1;
  if (activeRequestCount > 1) return;
  const isDelete = options.method === 'DELETE';
  elements.loadingTitle.textContent = isDelete
    ? 'Removing your source'
    : path === '/chat'
      ? 'Finding your answer'
      : 'Preparing your source';
  elements.loadingMessage.textContent = getLoadingMessage(path, options);
  elements.loadingOverlay.hidden = false;
  document.body.classList.add('loading-active');
}

function hideLoadingOverlay() {
  activeRequestCount = Math.max(0, activeRequestCount - 1);
  if (activeRequestCount > 0) return;
  elements.loadingOverlay.hidden = true;
  document.body.classList.remove('loading-active');
}

function initLottieAnimation() {
  if (!window.lottie || !elements.loadingAnimation) return;
  lottieAnimation = window.lottie.loadAnimation({
    container: elements.loadingAnimation,
    renderer: 'svg',
    loop: true,
    autoplay: true,
    path: 'assets/wait-loading.json',
    rendererSettings: {
      preserveAspectRatio: 'xMidYMid meet',
    },
  });
}

async function apiRequest(path, options = {}) {
  showLoadingOverlay(path, options);
  try {
    let response;
    try {
      response = await fetch(`${API_BASE_URL}${path}`, options);
    } catch {
      throw new Error('The backend could not be reached. Is it running on the configured port?');
    }

    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (!response.ok) {
      throw new Error(getErrorMessage(payload, `Request failed (${response.status}).`));
    }
    return payload;
  } finally {
    hideLoadingOverlay();
  }
}

function getErrorMessage(payload, fallback) {
  if (typeof payload?.detail === 'string') return payload.detail;
  if (Array.isArray(payload?.detail) && payload.detail[0]?.msg) return payload.detail[0].msg;
  return fallback;
}

function setIngestStatus(message, type = 'success') {
  if (!message) {
    elements.ingestStatus.hidden = true;
    elements.ingestStatus.textContent = '';
    elements.ingestStatus.className = 'status-message';
    return;
  }
  elements.ingestStatus.hidden = false;
  elements.ingestStatus.className = `status-message status-${type}`;
  elements.ingestStatus.textContent = message;
}

function setChatStatus(message) {
  if (!message) {
    elements.chatStatus.hidden = true;
    elements.chatStatus.textContent = '';
    return;
  }
  elements.chatStatus.hidden = false;
  elements.chatStatus.textContent = message;
}

function setButtonLoading(button, isLoading, loadingText) {
  const label = button.querySelector('.button-label') || button.querySelector('.send-label');
  if (!button.dataset.defaultLabel && label) button.dataset.defaultLabel = label.textContent;
  button.disabled = isLoading;
  if (label) label.textContent = isLoading ? loadingText : button.dataset.defaultLabel;
  button.classList.toggle('is-loading', isLoading);
}

function switchSourceType(type) {
  state.activeSourceType = type;
  for (const tab of elements.sourceTabs) {
    const isActive = tab.dataset.sourceType === type;
    tab.classList.toggle('is-active', isActive);
    tab.setAttribute('aria-selected', String(isActive));
  }
  for (const form of elements.sourceForms) {
    form.hidden = form.dataset.sourceForm !== type;
  }
  setIngestStatus('');
}

function handleFileSelection(file) {
  state.selectedFile = file || null;
  if (!file) {
    elements.pdfFileName.textContent = 'Text-based PDF · up to 20 MB';
    return;
  }
  elements.pdfFileName.textContent = `${file.name} · ${formatBytes(file.size)}`;
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 KB';
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getSourceTypeLabel(type) {
  return { pdf: 'PDF', website: 'Website', youtube: 'YouTube' }[type] || 'Source';
}

function getSourceTypeIcon(type) {
  return { pdf: 'PDF', website: '↗', youtube: '▶' }[type] || '•';
}

function formatDate(value) {
  if (!value) return 'Recently added';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Recently added';
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(date);
}

function renderSources() {
  elements.sourceCount.textContent = `${state.sources.length} ${state.sources.length === 1 ? 'source' : 'sources'}`;
  elements.sourceList.replaceChildren();

  if (state.sources.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-library';
    empty.innerHTML = '<span class="empty-icon" aria-hidden="true">✦</span><strong>Your library is empty</strong><span>Add a source to start asking questions.</span>';
    elements.sourceList.append(empty);
    renderSourceFilter();
    return;
  }

  for (const source of state.sources) {
    const card = document.createElement('article');
    card.className = 'source-card';

    const icon = document.createElement('span');
    icon.className = `source-card-icon ${source.source_type || 'website'}`;
    icon.textContent = getSourceTypeIcon(source.source_type);
    icon.setAttribute('aria-hidden', 'true');

    const main = document.createElement('div');
    main.className = 'source-card-main';
    const title = document.createElement('div');
    title.className = 'source-card-title';
    title.textContent = source.title || 'Untitled source';
    title.title = source.title || '';
    const meta = document.createElement('div');
    meta.className = 'source-card-meta';
    const type = document.createElement('span');
    type.textContent = getSourceTypeLabel(source.source_type);
    const date = document.createElement('span');
    date.textContent = formatDate(source.created_at);
    meta.append(type, date);
    main.append(title, meta);

    card.append(icon, main);

    const actions = document.createElement('div');
    actions.className = 'source-card-actions';

    if (source.source_url) {
      const link = document.createElement('a');
      link.className = 'source-card-link';
      link.href = source.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.title = 'Open source URL';
      link.setAttribute('aria-label', `Open ${source.title || 'source'}`);
      link.innerHTML = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M14 5h5v5M19 5l-8 8M19 13v4.5A1.5 1.5 0 0 1 17.5 19h-11A1.5 1.5 0 0 1 5 17.5v-11A1.5 1.5 0 0 1 6.5 5H11" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg>';
      actions.append(link);
    }

    const deleteButton = document.createElement('button');
    deleteButton.className = 'source-card-delete';
    deleteButton.type = 'button';
    deleteButton.title = 'Delete source';
    deleteButton.setAttribute('aria-label', `Delete ${source.title || 'source'}`);
    deleteButton.innerHTML = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 7h14M10 11v5M14 11v5M8 7l.7-2h6.6l.7 2m-9.5 0 .7 12h9.6l.7-12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>';
    deleteButton.addEventListener('click', () => deleteSource(source, deleteButton));
    actions.append(deleteButton);
    card.append(actions);

    elements.sourceList.append(card);
  }
  renderSourceFilter();
}

function renderSourceFilter() {
  const selected = elements.sourceFilter.value;
  elements.sourceFilter.replaceChildren();
  const allOption = document.createElement('option');
  allOption.value = 'all';
  allOption.textContent = 'All sources';
  elements.sourceFilter.append(allOption);

  for (const source of state.sources) {
    const option = document.createElement('option');
    option.value = source.source_id;
    option.textContent = source.title || getSourceTypeLabel(source.source_type);
    elements.sourceFilter.append(option);
  }
  elements.sourceFilter.value = [...elements.sourceFilter.options].some((option) => option.value === selected)
    ? selected
    : 'all';
}

function rememberSource(data) {
  const source = data?.source;
  if (!isValidSource(source)) return;
  const saved = { ...source, chunks_created: data.chunks_created ?? source.chunks_created };
  state.sources = [saved, ...state.sources.filter((item) => item.source_id !== saved.source_id)];
  saveSources();
  renderSources();
}

async function deleteSource(source, button) {
  const title = source.title || 'this source';
  if (!window.confirm(`Delete ${title}? This removes its stored chunks from ChromaDB.`)) return;

  button.disabled = true;
  try {
    const data = await apiRequest(`/sources/${encodeURIComponent(source.source_id)}`, {
      method: 'DELETE',
    });
    state.sources = state.sources.filter((item) => item.source_id !== source.source_id);
    saveSources();
    renderSources();
    setIngestStatus(`${title} deleted · ${data.deleted_chunks} chunks removed.`);
  } catch (error) {
    button.disabled = false;
    setIngestStatus(error.message, 'error');
  }
}

async function submitPdf(event) {
  event.preventDefault();
  if (!state.selectedFile) {
    setIngestStatus('Choose a PDF first.', 'error');
    return;
  }
  const formData = new FormData();
  formData.append('file', state.selectedFile);
  const button = elements.pdfForm.querySelector('button[type="submit"]');
  setIngestStatus('Extracting, chunking, and embedding your PDF…');
  setButtonLoading(button, true, 'Working…');
  try {
    const data = await apiRequest('/sources/pdf', { method: 'POST', body: formData });
    rememberSource(data);
    setIngestStatus(`${data.source.title} added · ${data.chunks_created} chunks created.`);
    state.selectedFile = null;
    elements.pdfInput.value = '';
    handleFileSelection(null);
  } catch (error) {
    setIngestStatus(error.message, 'error');
  } finally {
    setButtonLoading(button, false);
  }
}

async function submitJsonSource(event, endpoint, input, type) {
  event.preventDefault();
  const value = input.value.trim();
  if (!value) return;
  const button = event.currentTarget.querySelector('button[type="submit"]');
  setIngestStatus(`Extracting and embedding your ${getSourceTypeLabel(type).toLowerCase()}…`);
  setButtonLoading(button, true, 'Working…');
  try {
    const data = await apiRequest(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: value }),
    });
    rememberSource(data);
    setIngestStatus(`${data.source.title} added · ${data.chunks_created} chunks created.`);
    input.value = '';
  } catch (error) {
    setIngestStatus(error.message, 'error');
  } finally {
    setButtonLoading(button, false);
  }
}

function setChatLoading(isLoading) {
  state.isChatLoading = isLoading;
  elements.sendButton.disabled = isLoading;
  elements.sendButton.querySelector('.send-label').textContent = isLoading ? 'Thinking…' : 'Ask Atlas';
  elements.chatLoading.hidden = !isLoading;
  if (isLoading) {
    elements.chatEmpty.hidden = true;
    elements.chatResponse.hidden = true;
  }
}

function renderAnswerSources(sources) {
  elements.answerSources.replaceChildren();
  if (!Array.isArray(sources) || sources.length === 0) return;

  for (const source of sources) {
    const item = document.createElement('div');
    item.className = 'answer-source';
    const type = document.createElement('span');
    type.className = 'answer-source-type';
    type.textContent = getSourceTypeLabel(source.source_type);
    const title = document.createElement('span');
    title.className = 'answer-source-title';
    title.textContent = source.title || 'Untitled source';
    title.title = source.title || '';
    item.append(type, title);
    if (Array.isArray(source.page_numbers) && source.page_numbers.length > 0) {
      const pages = document.createElement('span');
      pages.className = 'answer-source-pages';
      pages.textContent = `p. ${source.page_numbers.join(', ')}`;
      item.append(pages);
    } else if (source.relevant_chunks) {
      const chunks = document.createElement('span');
      chunks.className = 'answer-source-pages';
      chunks.textContent = `${source.relevant_chunks} chunk${source.relevant_chunks === 1 ? '' : 's'}`;
      item.append(chunks);
    }
    elements.answerSources.append(item);
  }
}

async function submitChat(event) {
  event.preventDefault();
  const question = elements.questionInput.value.trim();
  if (!question || state.isChatLoading) return;
  if (state.sources.length === 0) {
    setChatStatus('Add at least one source before asking a question.');
    return;
  }

  setChatStatus('');
  setChatLoading(true);
  const payload = {
    question,
    top_k: Number(elements.topK.value) || 5,
  };
  const selectedSource = elements.sourceFilter.value;
  if (selectedSource !== 'all') payload.source_ids = [selectedSource];

  try {
    const data = await apiRequest('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    elements.answerText.textContent = data.answer || "I couldn't find that in the ingested sources.";
    renderAnswerSources(data.sources);
    elements.chatResponse.hidden = false;
    elements.chatEmpty.hidden = true;
    elements.questionInput.value = '';
    elements.questionInput.focus();
  } catch (error) {
    setChatStatus(error.message);
    elements.chatResponse.hidden = true;
    elements.chatEmpty.hidden = false;
  } finally {
    setChatLoading(false);
  }
}

function bindEvents() {
  elements.themeToggle.addEventListener('click', toggleTheme);
  elements.sourceTabs.forEach((tab) => tab.addEventListener('click', () => switchSourceType(tab.dataset.sourceType)));

  elements.pdfInput.addEventListener('change', (event) => handleFileSelection(event.target.files?.[0]));
  elements.pdfForm.addEventListener('submit', submitPdf);
  elements.websiteForm.addEventListener('submit', (event) => submitJsonSource(event, '/sources/website', elements.websiteUrl, 'website'));
  elements.youtubeForm.addEventListener('submit', (event) => submitJsonSource(event, '/sources/youtube', elements.youtubeUrl, 'youtube'));
  elements.chatForm.addEventListener('submit', submitChat);

  ['dragenter', 'dragover'].forEach((eventName) => {
    elements.pdfDropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.pdfDropzone.classList.add('is-dragging');
    });
  });
  ['dragleave', 'drop'].forEach((eventName) => {
    elements.pdfDropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.pdfDropzone.classList.remove('is-dragging');
    });
  });
  elements.pdfDropzone.addEventListener('drop', (event) => {
    const file = event.dataTransfer?.files?.[0];
    if (file) handleFileSelection(file);
  });

  document.querySelectorAll('[data-question]').forEach((button) => {
    button.addEventListener('click', () => {
      elements.questionInput.value = button.dataset.question;
      elements.questionInput.focus();
    });
  });
}

function initialize() {
  applyTheme(document.documentElement.dataset.theme || 'light');
  const apiLabel = API_BASE_URL
    ? API_BASE_URL.replace(/^https?:\/\//, '').split('/')[0]
    : window.location.host;
  elements.apiBaseLabel.textContent = `API: ${apiLabel}`;
  initLottieAnimation();
  renderSources();
  bindEvents();
}

document.addEventListener('DOMContentLoaded', initialize);
