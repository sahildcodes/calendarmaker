/**
 * Image-to-Calendar Application
 * Frontend Controller, Google OAuth 2.0 Flow & Reactive Validation
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements - Upload & Visualizer
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const dropzonePlaceholder = document.getElementById('dropzonePlaceholder');
  const previewContainer = document.getElementById('previewContainer');
  const imagePreview = document.getElementById('imagePreview');
  const btnClearImage = document.getElementById('btnClearImage');

  // OCR Inspector
  const ocrInspectorCard = document.getElementById('ocrInspectorCard');
  const normalizedTextBox = document.getElementById('normalizedTextBox');
  const rawTextBox = document.getElementById('rawTextBox');
  const ocrConfidenceChip = document.getElementById('ocrConfidenceChip');
  const ocrConfidenceValue = document.getElementById('ocrConfidenceValue');
  const statAvgConf = document.getElementById('statAvgConf');
  const statLinesCount = document.getElementById('statLinesCount');
  const statUnreliableCount = document.getElementById('statUnreliableCount');
  const ocrWarningsContainer = document.getElementById('ocrWarningsContainer');

  // Events Workspace
  const eventsWorkspace = document.getElementById('eventsWorkspace');
  const emptyState = document.getElementById('emptyState');
  const loadingState = document.getElementById('loadingState');
  const loadingText = document.getElementById('loadingText');
  const loadingSubtext = document.getElementById('loadingSubtext');
  const uploadProgressContainer = document.getElementById('uploadProgressContainer');
  const uploadProgressBar = document.getElementById('uploadProgressBar');
  const uploadProgressPercent = document.getElementById('uploadProgressPercent');
  const uploadProgressLabel = document.getElementById('uploadProgressLabel');
  const eventCardsList = document.getElementById('eventCardsList');
  const actionFooter = document.getElementById('actionFooter');
  const eventCountBadge = document.getElementById('eventCountBadge');
  const btnSubmitCalendar = document.getElementById('btnSubmitCalendar');
  const btnSubmitText = document.getElementById('btnSubmitText');
  const btnDownloadIcs = document.getElementById('btnDownloadIcs');

  // Dropzone Overlay Elements
  const dropzoneUploadOverlay = document.getElementById('dropzoneUploadOverlay');
  const dropzoneFileName = document.getElementById('dropzoneFileName');
  const dropzoneFileSize = document.getElementById('dropzoneFileSize');
  const dropzoneStageLabel = document.getElementById('dropzoneStageLabel');
  const dropzonePercentVal = document.getElementById('dropzonePercentVal');
  const dropzoneProgressFill = document.getElementById('dropzoneProgressFill');
  const dropzoneStatusSubtext = document.getElementById('dropzoneStatusSubtext');

  // Calendar Header & Status
  const calendarStatusBadge = document.getElementById('calendarStatusBadge');
  const calendarStatusText = document.getElementById('calendarStatusText');
  const btnConnectGoogle = document.getElementById('btnConnectGoogle');
  const btnConnectGoogleText = document.getElementById('btnConnectGoogleText');
  const btnOpenCalendarModal = document.getElementById('btnOpenCalendarModal');

  // Google Auth Modal Elements
  const googleAuthModal = document.getElementById('googleAuthModal');
  const btnCloseGoogleAuthModal = document.getElementById('btnCloseGoogleAuthModal');
  const btnCloseGoogleAuthModalBtn = document.getElementById('btnCloseGoogleAuthModalBtn');
  const displayRedirectUri = document.getElementById('displayRedirectUri');
  const btnCopyRedirectUri = document.getElementById('btnCopyRedirectUri');
  const btnStartGoogleOAuth = document.getElementById('btnStartGoogleOAuth');
  const connectedProfileBox = document.getElementById('connectedProfileBox');
  const connectedUserEmail = document.getElementById('connectedUserEmail');
  const btnDisconnectGoogle = document.getElementById('btnDisconnectGoogle');

  // Calendar Table Modal
  const calendarModal = document.getElementById('calendarModal');
  const btnCloseCalendarModal = document.getElementById('btnCloseCalendarModal');
  const btnCloseCalendarModalBtn = document.getElementById('btnCloseCalendarModalBtn');
  const calendarTableBody = document.getElementById('calendarTableBody');

  // Success Modal
  const successModal = document.getElementById('successModal');
  const btnCloseSuccessModal = document.getElementById('btnCloseSuccessModal');
  const successMessage = document.getElementById('successMessage');
  const syncedEventsList = document.getElementById('syncedEventsList');

  // State
  let currentEvents = [];
  let existingCalendarEvents = [];
  let currentImageFile = null;
  let isGoogleConnected = false;

  // Initialize Redirect URI display
  const currentRedirectUri = `${window.location.origin}/api/calendar/oauth-callback`;
  if (displayRedirectUri) {
    displayRedirectUri.textContent = currentRedirectUri;
  }

  // Handle OAuth Callback Redirect in URL Query
  handleUrlAuthCallback();

  // Initial status check
  fetchCalendarStatus();


  // =========================================================================
  // Dynamic Interactive Ambient Spotlight (Smooth Easing on Pointer Movement)
  // =========================================================================
  function initAmbientSpotlight() {
    const spotlight = document.getElementById('ambientSpotlight');
    if (!spotlight) return;

    let targetX = window.innerWidth / 2;
    let targetY = window.innerHeight * 0.3;
    let currentX = targetX;
    let currentY = targetY;
    let rafId = null;

    function onPointerMove(x, y) {
      targetX = x;
      targetY = y;
      if (!rafId) {
        rafId = requestAnimationFrame(updateSpotlight);
      }
    }

    function updateSpotlight() {
      currentX += (targetX - currentX) * 0.12;
      currentY += (targetY - currentY) * 0.12;

      const px = ((currentX / window.innerWidth) * 100).toFixed(1);
      const py = ((currentY / window.innerHeight) * 100).toFixed(1);

      spotlight.style.setProperty('--spotlight-x', `${px}%`);
      spotlight.style.setProperty('--spotlight-y', `${py}%`);

      if (Math.abs(targetX - currentX) > 0.5 || Math.abs(targetY - currentY) > 0.5) {
        rafId = requestAnimationFrame(updateSpotlight);
      } else {
        rafId = null;
      }
    }

    window.addEventListener('mousemove', (e) => onPointerMove(e.clientX, e.clientY), { passive: true });
    window.addEventListener('touchmove', (e) => {
      if (e.touches && e.touches[0]) {
        onPointerMove(e.touches[0].clientX, e.touches[0].clientY);
      }
    }, { passive: true });
  }
  initAmbientSpotlight();

  // =========================================================================
  // URL Query OAuth Callback Handling
  // =========================================================================
  function handleUrlAuthCallback() {
    const params = new URLSearchParams(window.location.search);
    if (params.has('auth')) {
      const authStatus = params.get('auth');
      if (authStatus === 'success') {
        showToast('Google Calendar successfully connected! Real sync is active.', 'success');
      } else if (authStatus === 'error') {
        const errorMsg = params.get('msg') || 'Google authentication failed';
        showToast(`Google Auth Error: ${decodeURIComponent(errorMsg)}`, 'danger');
      }
      // Clean query params from URL bar
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }

  // =========================================================================
  // Google OAuth 1-Click Redirect & Setup Logic
  // =========================================================================
  let hasServerCredentials = false;

  btnConnectGoogle.addEventListener('click', async () => {
    // 1. If user is already authenticated: open account dialog showing their email & Disconnect button
    if (isGoogleConnected) {
      googleAuthModal.style.display = 'flex';
      return;
    }

    // 2. If the server has credentials configured: DIRECT 1-CLICK REDIRECT TO GOOGLE!
    if (hasServerCredentials) {
      try {
        btnConnectGoogle.disabled = true;
        btnConnectGoogle.innerHTML = '<span class="spinner-ring" style="width:14px;height:14px;border-width:2px;margin:0 6px 0 0;"></span> Connecting...';
        const urlRes = await fetch(`/api/calendar/auth-url?redirect_uri=${encodeURIComponent(currentRedirectUri)}`);
        if (urlRes.ok) {
          const data = await urlRes.json();
          window.location.href = data.auth_url; // Directly jump to Google login!
          return;
        } else {
          const err = await urlRes.json();
          showToast(err.detail || 'Could not initiate Google login', 'danger');
        }
      } catch (err) {
        showToast(`Connection error: ${err.message}`, 'danger');
      } finally {
        btnConnectGoogle.disabled = false;
        fetchCalendarStatus();
      }
      return;
    }

    // 3. Only if server has NO credentials.json at all, show the admin setup modal
    googleAuthModal.style.display = 'flex';
  });

  if (btnCloseGoogleAuthModal) btnCloseGoogleAuthModal.addEventListener('click', () => googleAuthModal.style.display = 'none');
  if (btnCloseGoogleAuthModalBtn) btnCloseGoogleAuthModalBtn.addEventListener('click', () => googleAuthModal.style.display = 'none');

  // Copy Redirect URI Button
  if (btnCopyRedirectUri) {
    btnCopyRedirectUri.addEventListener('click', () => {
      navigator.clipboard.writeText(currentRedirectUri).then(() => {
        btnCopyRedirectUri.innerHTML = '✓ Copied!';
        setTimeout(() => {
          btnCopyRedirectUri.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg> Copy
          `;
        }, 2000);
        showToast('Redirect URI copied to clipboard!', 'info');
      });
    });
  }

  // Launch Google OAuth
  btnStartGoogleOAuth.addEventListener('click', async () => {
    // Request OAuth authorization URL directly from server
    try {
      const urlRes = await fetch(`/api/calendar/auth-url?redirect_uri=${encodeURIComponent(currentRedirectUri)}`);
      if (!urlRes.ok) {
        const err = await urlRes.json();
        throw new Error(err.detail || 'Google OAuth credentials are not configured on the server yet.');
      }
      const data = await urlRes.json();
      // Redirect to Google's consent screen
      window.location.href = data.auth_url;
    } catch (err) {
      showToast(err.message, 'danger');
    }
  });

  // Disconnect Google Account
  btnDisconnectGoogle.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/calendar/disconnect', { method: 'POST' });
      if (res.ok) {
        showToast('Google account disconnected. Switched to Sandbox.', 'info');
        googleAuthModal.style.display = 'none';
        fetchCalendarStatus();
      }
    } catch (err) {
      showToast('Failed to disconnect account', 'danger');
    }
  });

  // Prevent browser from opening dropped files outside dropzone
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => e.preventDefault());

  // Clear file input value on click so selecting the exact same file fires 'change' every time
  fileInput.addEventListener('click', () => {
    fileInput.value = '';
  });

  // Prevent native file dialog only if clear button was clicked, and ensure input is cleared
  dropzone.addEventListener('click', (e) => {
    if (e.target.closest('#btnClearImage')) {
      e.preventDefault();
      return;
    }
    fileInput.value = '';
  });

  // Highlight dropzone on drag over
  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  // Remove highlight on drag leave
  dropzone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!dropzone.contains(e.relatedTarget)) {
      dropzone.classList.remove('dragover');
    }
  });

  // Handle dropped file
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove('dragover');
    const dt = e.dataTransfer;
    const files = dt ? dt.files : null;
    if (files && files.length > 0) {
      handleImageSelection(files[0]);
    }
  });

  // Handle selected file via browser dialog
  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      handleImageSelection(file);
    }
  });

  // Keyboard accessibility for dropzone
  dropzone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

  // Paste from Clipboard (Ctrl+V / Cmd+V)
  window.addEventListener('paste', (e) => {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (let item of items) {
      if (item.type.indexOf('image') !== -1) {
        const file = item.getAsFile();
        showToast('Processing pasted screenshot from clipboard...', 'info');
        handleImageSelection(file);
        break;
      }
    }
  });

  btnClearImage.addEventListener('click', resetWorkspace);

  // Preset Demo Buttons
  document.querySelectorAll('.btn-preset').forEach(btn => {
    btn.addEventListener('click', async () => {
      const sampleFile = btn.dataset.sample;
      try {
        showToast(`Loading demo sample: ${sampleFile}`, 'info');
        const res = await fetch(`/samples/${sampleFile}`);
        if (!res.ok) throw new Error('Failed to fetch sample image');
        const blob = await res.blob();
        const file = new File([blob], sampleFile, { type: 'image/png' });
        handleImageSelection(file);
      } catch (err) {
        showToast(`Error loading sample: ${err.message}`, 'danger');
      }
    });
  });

  // =========================================================================
  // Process Image via FastAPI Pipeline with Upload Progress
  // =========================================================================
  async function handleImageSelection(file) {
    if (!file) return;
    currentImageFile = file;

    // 1. Instant thumbnail preview using URL.createObjectURL
    try {
      const objectUrl = URL.createObjectURL(file);
      imagePreview.src = objectUrl;
      dropzonePlaceholder.style.display = 'none';
      previewContainer.style.display = 'block';
      btnClearImage.style.display = 'inline-flex';
    } catch (e) {
      console.warn('Could not create ObjectURL:', e);
    }

    // 2. Format file size helper
    const sizeStr = file.size > 1024 * 1024 
      ? (file.size / (1024 * 1024)).toFixed(2) + ' MB'
      : (file.size / 1024).toFixed(1) + ' KB';

    // 3. Show upload overlay directly on the dropzone
    if (dropzoneUploadOverlay) {
      dropzoneUploadOverlay.style.display = 'flex';
      if (dropzoneFileName) dropzoneFileName.textContent = file.name;
      if (dropzoneFileSize) dropzoneFileSize.textContent = sizeStr;
      if (dropzonePercentVal) dropzonePercentVal.textContent = '0%';
      if (dropzoneProgressFill) {
        dropzoneProgressFill.style.width = '0%';
        dropzoneProgressFill.classList.remove('processing-pulse');
      }
      if (dropzoneStageLabel) dropzoneStageLabel.textContent = 'Uploading image...';
      if (dropzoneStatusSubtext) dropzoneStatusSubtext.textContent = 'Transferring file to server...';
    }

    // 4. Show loading state in right events workspace
    emptyState.style.display = 'none';
    eventCardsList.innerHTML = '';
    loadingState.style.display = 'flex';
    actionFooter.style.display = 'none';

    const laserScanner = document.getElementById('laserScanner');
    if (laserScanner) laserScanner.style.display = 'block';

    if (uploadProgressContainer) {
      uploadProgressContainer.style.display = 'block';
      uploadProgressBar.style.width = '0%';
      uploadProgressBar.classList.remove('processing-pulse');
      uploadProgressPercent.textContent = '0%';
      uploadProgressLabel.textContent = 'Uploading image (0%)...';
    }
    loadingText.textContent = 'Uploading screenshot (0%)...';
    if (loadingSubtext) {
      loadingSubtext.textContent = `File: ${file.name} (${sizeStr}) • Preparing OCR`;
    }

    showToast(`Uploading ${file.name} (${sizeStr})...`, 'info');

    // 5. Send file with XMLHttpRequest for granular progress tracking
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/process-image');

    // Real-time upload percentage tracking
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.min(100, Math.round((e.loaded / e.total) * 100));
        
        // Update dropzone overlay
        if (dropzoneUploadOverlay) {
          if (dropzoneProgressFill) dropzoneProgressFill.style.width = percent + '%';
          if (dropzonePercentVal) dropzonePercentVal.textContent = percent + '%';
        }

        // Update right panel
        if (uploadProgressContainer) {
          if (uploadProgressBar) uploadProgressBar.style.width = percent + '%';
          if (uploadProgressPercent) uploadProgressPercent.textContent = percent + '%';
        }

        if (percent < 100) {
          if (dropzoneStageLabel) dropzoneStageLabel.textContent = `Uploading (${percent}%)...`;
          if (dropzoneStatusSubtext) {
            const loadedMb = (e.loaded / (1024 * 1024)).toFixed(2);
            const totalMb = (e.total / (1024 * 1024)).toFixed(2);
            dropzoneStatusSubtext.textContent = `${loadedMb} MB of ${totalMb} MB transferred`;
          }
          if (uploadProgressLabel) uploadProgressLabel.textContent = `Uploading image (${percent}%)...`;
          loadingText.textContent = `Uploading screenshot (${percent}%)...`;
        } else {
          // 100% upload finished, now running OCR on server
          if (dropzoneStageLabel) dropzoneStageLabel.textContent = 'Upload Complete (100%)';
          if (dropzoneStatusSubtext) dropzoneStatusSubtext.textContent = 'Extracting text with AI OCR & checking calendar...';
          if (dropzoneProgressFill) dropzoneProgressFill.classList.add('processing-pulse');

          if (uploadProgressLabel) uploadProgressLabel.textContent = 'Upload Complete (100%)';
          if (uploadProgressBar) uploadProgressBar.classList.add('processing-pulse');
          loadingText.textContent = 'Analyzing image with AI OCR...';
          if (loadingSubtext) {
            loadingSubtext.textContent = 'Extracting dates, times & course titles, resolving ambiguities and schedule conflicts...';
          }
        }
      }
    };

    xhr.onload = () => {
      // Hide overlays
      if (dropzoneUploadOverlay) dropzoneUploadOverlay.style.display = 'none';
      loadingState.style.display = 'none';
      if (uploadProgressContainer) uploadProgressContainer.style.display = 'none';
      if (laserScanner) laserScanner.style.display = 'none';

      // Reset fileInput so selecting same or new image works anytime
      fileInput.value = '';

      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText);
          currentEvents = data.events || [];
          existingCalendarEvents = data.existing_calendar_events || [];

          // Render OCR details
          renderOCRInspector(data.ocr);

          // Render Event Confirmation Cards
          renderEventCards(currentEvents);

          showToast(`Successfully extracted ${currentEvents.length} event(s)!`, 'success');
        } catch (err) {
          console.error('Parse error:', err);
          emptyState.style.display = 'flex';
          showToast('Failed to parse server response.', 'danger');
        }
      } else {
        emptyState.style.display = 'flex';
        try {
          const errData = JSON.parse(xhr.responseText);
          showToast(errData.detail || 'Image processing failed', 'danger');
        } catch (_) {
          if (xhr.status === 504 || xhr.status === 524) {
            showToast('OCR processing timed out. Please try a clearer or cropped screenshot.', 'danger');
          } else if (xhr.status === 500 || xhr.status === 502) {
            showToast('Server encountered a temporary processing error. Please try again.', 'danger');
          } else if (xhr.status === 413) {
            showToast('Image file is too large (max 10 MB).', 'danger');
          } else {
            showToast(`Server returned error (${xhr.status})`, 'danger');
          }
        }
      }
    };

    xhr.onerror = () => {
      if (dropzoneUploadOverlay) dropzoneUploadOverlay.style.display = 'none';
      loadingState.style.display = 'none';
      if (uploadProgressContainer) uploadProgressContainer.style.display = 'none';
      if (laserScanner) laserScanner.style.display = 'none';
      emptyState.style.display = 'flex';
      fileInput.value = '';
      showToast('Network error during image upload.', 'danger');
    };

    xhr.send(formData);
  }

  // =========================================================================
  // Render OCR Inspector Tabs
  // =========================================================================
  function renderOCRInspector(ocr) {
    ocrInspectorCard.style.display = 'flex';
    normalizedTextBox.textContent = ocr.normalized_text || '(No text detected)';
    rawTextBox.textContent = ocr.raw_text || '(No text detected)';
    
    const conf = ocr.avg_confidence || 0;
    ocrConfidenceValue.textContent = `${conf}%`;
    statAvgConf.textContent = `${conf}%`;
    statLinesCount.textContent = (ocr.lines || []).length;
    statUnreliableCount.textContent = (ocr.unreliable_lines || []).length;

    // Warnings
    ocrWarningsContainer.innerHTML = '';
    if (ocr.warnings && ocr.warnings.length > 0) {
      ocr.warnings.forEach(w => {
        const pill = document.createElement('div');
        pill.className = 'alert-pill warning';
        pill.innerHTML = `<span>⚠️</span> <span>${escapeHtml(w)}</span>`;
        ocrWarningsContainer.appendChild(pill);
      });
    } else {
      ocrWarningsContainer.innerHTML = '<p style="font-size:0.8rem; color:#94a3b8;">No OCR quality warnings detected.</p>';
    }
  }

  // OCR Inspector Tabs Click Handling
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const tabName = btn.dataset.tab;
      const targetPane = document.getElementById(
        tabName === 'normalized' ? 'paneNormalized' :
        tabName === 'raw' ? 'paneRaw' : 'paneConfidence'
      );
      if (targetPane) targetPane.classList.add('active');
    });
  });

  // =========================================================================
  // Dynamic Conflict Status Ribbon & Auto-Shift All
  // =========================================================================
  function updateConflictStatusRibbon(events) {
    const ribbon = document.getElementById('conflictStatusRibbon');
    if (!ribbon) return;

    if (!events || events.length === 0) {
      ribbon.style.display = 'none';
      return;
    }

    const conflictingEvents = events.filter(e => e.has_conflict && e.conflicts && e.conflicts.length > 0);
    const count = conflictingEvents.length;

    if (count > 0) {
      ribbon.style.display = 'flex';
      ribbon.className = 'conflict-status-ribbon';
      const title = document.getElementById('conflictRibbonTitle');
      const sub = document.getElementById('conflictRibbonSub');
      const btn = document.getElementById('btnRibbonAutoShiftAll');
      const icon = document.getElementById('ribbonIcon');

      if (icon) icon.textContent = '🚨';
      if (title) title.textContent = `${count} Schedule Conflict${count > 1 ? 's' : ''} Detected`;
      if (sub) sub.textContent = `Overlap on existing calendar entries. Auto-Shift to resolve or Keep Both.`;
      if (btn) btn.style.display = 'inline-flex';
    } else {
      // All clear!
      ribbon.style.display = 'flex';
      ribbon.className = 'conflict-status-ribbon cleared';
      const title = document.getElementById('conflictRibbonTitle');
      const sub = document.getElementById('conflictRibbonSub');
      const btn = document.getElementById('btnRibbonAutoShiftAll');
      const icon = document.getElementById('ribbonIcon');

      if (icon) icon.textContent = '✓';
      if (title) title.textContent = 'All Schedule Conflicts Clear';
      if (sub) sub.textContent = 'All events are clear of overlapping calendar entries. Ready to sync!';
      if (btn) btn.style.display = 'none';
    }
  }

  window.autoShiftAllConflicts = async () => {
    const conflicting = currentEvents.filter(e => e.has_conflict && e.conflicts && e.conflicts.length > 0);
    if (conflicting.length === 0) {
      showToast('No active conflicts to auto-shift.', 'info');
      return;
    }
    for (const e of conflicting) {
      await window.rescheduleEvent(e.id, 1);
    }
    showToast(`Auto-shifted ${conflicting.length} conflicting event(s) to clear schedule!`, 'success');
  };

  // =========================================================================
  // Render Event Confirmation Cards
  // =========================================================================
  function renderEventCards(events) {
    eventCardsList.innerHTML = '';

    if (!events || events.length === 0) {
      emptyState.style.display = 'flex';
      actionFooter.style.display = 'none';
      eventCountBadge.textContent = '0 Events';
      updateConflictStatusRibbon([]);
      return;
    }

    emptyState.style.display = 'none';
    actionFooter.style.display = 'flex';
    eventCountBadge.textContent = `${events.length} Event${events.length > 1 ? 's' : ''} Ready for Review`;

    events.forEach((evt, idx) => {
      const card = createEventCardElement(evt, idx);
      eventCardsList.appendChild(card);
    });

    updateConflictStatusRibbon(events);
  }

  function getPriorityTier(score) {
    const s = parseInt(score, 10) || 5;
    if (s <= 3) return 'low';
    if (s <= 6) return 'normal';
    if (s <= 8) return 'high';
    return 'critical';
  }

  function getPriorityLabel(score) {
    const s = parseInt(score, 10) || 5;
    if (s <= 3) return 'Low';
    if (s <= 6) return 'Normal';
    if (s <= 8) return 'High';
    return 'Critical';
  }

  function createEventCardElement(evt, idx) {
    const card = document.createElement('div');
    const hasConflict = evt.has_conflict;
    const hasDuplicate = evt.has_duplicate;
    const isValid = evt.is_valid && !hasConflict;

    card.className = `event-card ${hasConflict ? 'has-conflict' : (hasDuplicate ? 'has-duplicate' : (isValid ? 'is-validated' : ''))}`;
    card.id = `card_${evt.id}`;

    // Category badge styling
    const catClass = `badge-${(evt.category || 'event').toLowerCase()}`;

    // Format validation alerts HTML
    let alertsHtml = '';

    // Ambiguous Date Alert
    const ambiguousFlag = (evt.validation_flags || []).find(f => f.type === 'AMBIGUOUS_DATE');
    if (ambiguousFlag) {
      alertsHtml += `
        <div class="alert-box warning">
          <span class="alert-icon">⚠️</span>
          <div class="alert-content">
            <div class="alert-title">Ambiguous Date Detected</div>
            <p>${ambiguousFlag.message} Confirm or adjust the date below before submission.</p>
          </div>
        </div>
      `;
    }

    // Missing Time Alert
    const missingTimeFlag = (evt.validation_flags || []).find(f => f.type === 'MISSING_TIME');
    if (missingTimeFlag) {
      alertsHtml += `
        <div class="alert-box info">
          <span class="alert-icon">ℹ️</span>
          <div class="alert-content">
            <div class="alert-title">Missing Time Specified</div>
            <p>${missingTimeFlag.message}</p>
          </div>
        </div>
      `;
    }

    // Duplicate Alert
    if (hasDuplicate && evt.duplicates && evt.duplicates.length > 0) {
      const dup = evt.duplicates[0];
      alertsHtml += `
        <div class="alert-box warning">
          <span class="alert-icon">⚠️</span>
          <div class="alert-content">
            <div class="alert-title">Duplicate Calendar Event Detected</div>
            <p>An event titled <strong>"${escapeHtml(dup.title)}"</strong> already exists on your Google Calendar on ${dup.start_date}. Proceeding will create a duplicate.</p>
          </div>
        </div>
      `;
    }

    // Unreliable OCR Alert
    const ocrFlag = (evt.validation_flags || []).find(f => f.type === 'UNRELIABLE_OCR');
    if (ocrFlag) {
      alertsHtml += `
        <div class="alert-box warning">
          <span class="alert-icon">🔍</span>
          <div class="alert-content">
            <div class="alert-title">Low OCR Confidence</div>
            <p>${ocrFlag.message} Please review parsed fields carefully.</p>
          </div>
        </div>
      `;
    }

    // Schedule Conflict & Priority Advisory Alert with Enlarged Buttons
    if (hasConflict && evt.conflicts && evt.conflicts.length > 0) {
      evt.conflicts.forEach(c => {
        const adv = c.priority_advice;
        const higherBadge = adv.winner === 'new' 
          ? '<span class="advisory-badge higher">New Event is Higher Priority</span>'
          : '<span class="advisory-badge lower">Existing Event is Higher Priority</span>';

        alertsHtml += `
          <div class="alert-box danger">
            <span class="alert-icon">🚨</span>
            <div class="alert-content">
              <div class="alert-title">Schedule Conflict with "${escapeHtml(c.existing_event.title)}"</div>
              <p>Overlap on <strong>${evt.start_date}</strong> between <strong>${c.overlap_time}</strong>.</p>
              
              <div class="conflict-advisory-block">
                ${higherBadge}
                <p style="font-size: 0.85rem; margin-top: 6px; line-height: 1.45; color: #f1f5f9;">${adv.advisory_reason}</p>
                <div class="conflict-quick-actions">
                  <button class="btn-conflict-action btn-action-reschedule" onclick="window.rescheduleEvent('${evt.id}', 1)" title="Automatically move this event +1 hour later">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="12" cy="12" r="10"></circle>
                      <polyline points="12 6 12 12 16 14"></polyline>
                      <path d="M16 10l4-2-4-2"></path>
                    </svg>
                    <div class="btn-conflict-text">
                      <span class="btn-conflict-title">Auto-Shift (+1 Hour)</span>
                      <span class="btn-conflict-sub">Move event later to avoid clash</span>
                    </div>
                  </button>

                  <button class="btn-conflict-action btn-action-ignore" onclick="window.dismissConflict('${evt.id}')" title="Dismiss conflict and keep both overlapping on calendar">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="2" y="7" width="16" height="14" rx="2"></rect>
                      <path d="M6 3h14a2 2 0 0 1 2 2v12"></path>
                    </svg>
                    <div class="btn-conflict-text">
                      <span class="btn-conflict-title">Keep Both (Overlap)</span>
                      <span class="btn-conflict-sub">Allow simultaneous schedule</span>
                    </div>
                  </button>
                </div>
              </div>
            </div>
          </div>
        `;
      });
    }

    // Validated Ready badge
    if (isValid && !ambiguousFlag && !missingTimeFlag) {
      alertsHtml += `
        <div class="alert-box info" style="background: rgba(16, 185, 129, 0.1); border-color: rgba(16, 185, 129, 0.25); color: #6ee7b7;">
          <span class="alert-icon">✓</span>
          <div class="alert-content">
            <div class="alert-title">Event Validated</div>
            <p>No conflicts or ambiguities detected. Ready to push to Google Calendar.</p>
          </div>
        </div>
      `;
    }

    card.innerHTML = `
      <!-- Card Header -->
      <div class="card-header-row">
        <div class="card-title-field">
          <input type="text" class="input-title" id="input_title_${evt.id}" value="${escapeHtml(evt.title)}" placeholder="Event Title" onchange="window.handleFieldChange('${evt.id}')">
        </div>
        <div class="card-badges-row">
          <span class="badge ${catClass}">${evt.category || 'Event'}</span>
          <span class="badge badge-priority" id="card_priority_badge_${evt.id}">Priority ${evt.priority_score}/10</span>
          ${evt.weight_pct ? `<span class="badge" style="background:rgba(244,63,94,0.15); color:#f43f5e;">${evt.weight_pct}% of Grade</span>` : ''}
          ${evt.is_mandatory ? `<span class="badge" style="background:rgba(234,179,8,0.15); color:#eab308;">Mandatory</span>` : ''}
        </div>
      </div>

      <!-- Editable Fields -->
      <div class="fields-grid">
        <div class="field-group">
          <label class="field-label">Date</label>
          <input type="date" class="field-input" id="input_date_${evt.id}" value="${evt.start_date}" onchange="window.handleFieldChange('${evt.id}')">
        </div>
        <div class="field-group">
          <label class="field-label">Start Time</label>
          <input type="time" class="field-input" id="input_start_time_${evt.id}" value="${evt.start_time}" onchange="window.handleFieldChange('${evt.id}')">
        </div>
        <div class="field-group">
          <label class="field-label">End Time</label>
          <input type="time" class="field-input" id="input_end_time_${evt.id}" value="${evt.end_time}" onchange="window.handleFieldChange('${evt.id}')">
        </div>
        <div class="field-group">
          <label class="field-label">Location / Link</label>
          <input type="text" class="field-input" id="input_location_${evt.id}" value="${escapeHtml(evt.location || '')}" placeholder="Room 101 or Zoom link" onchange="window.handleFieldChange('${evt.id}')">
        </div>
      </div>

      <!-- Priority Customization Control (User-Settable) -->
      <div class="priority-control-card">
        <div class="priority-header">
          <div class="priority-label-wrap">
            <span class="priority-icon">⚡</span>
            <span class="priority-section-title">Event Priority</span>
            <span class="priority-score-badge priority-badge-${getPriorityTier(evt.priority_score)}" id="priority_badge_${evt.id}">
              <span id="priority_num_${evt.id}">${evt.priority_score || 5}</span>/10 • <span id="priority_label_${evt.id}">${getPriorityLabel(evt.priority_score || 5)}</span>
            </span>
          </div>
          <span class="priority-hint">Adjust score to resolve conflict rankings</span>
        </div>

        <div class="priority-slider-row">
          <button type="button" class="btn-priority-step" onclick="window.adjustPriority('${evt.id}', -1)" title="Decrease Priority">−</button>
          <div class="slider-track-wrap">
            <input type="range" class="priority-range-slider" id="input_priority_${evt.id}" 
              min="1" max="10" step="1" value="${evt.priority_score || 5}" 
              oninput="window.updatePriorityPreview('${evt.id}', this.value)"
              onchange="window.handlePriorityChange('${evt.id}', this.value)">
            <div class="slider-ticks">
              <span>1 Low</span>
              <span>3</span>
              <span>5 Normal</span>
              <span>8 High</span>
              <span>10 Urgent</span>
            </div>
          </div>
          <button type="button" class="btn-priority-step" onclick="window.adjustPriority('${evt.id}', 1)" title="Increase Priority">+</button>
        </div>

        <div class="priority-presets-row">
          <span class="preset-tag">Presets:</span>
          <button type="button" class="btn-priority-chip ${(evt.priority_score || 5) == 3 ? 'active' : ''}" onclick="window.handlePriorityChange('${evt.id}', 3)">Low (3)</button>
          <button type="button" class="btn-priority-chip ${(evt.priority_score || 5) == 5 ? 'active' : ''}" onclick="window.handlePriorityChange('${evt.id}', 5)">Normal (5)</button>
          <button type="button" class="btn-priority-chip ${(evt.priority_score || 5) == 8 ? 'active' : ''}" onclick="window.handlePriorityChange('${evt.id}', 8)">High (8)</button>
          <button type="button" class="btn-priority-chip ${(evt.priority_score || 5) == 10 ? 'active' : ''}" onclick="window.handlePriorityChange('${evt.id}', 10)">Critical (10)</button>
        </div>
      </div>

      <!-- Validation & Conflict Alerts -->
      <div class="validation-alerts-stack">
        ${alertsHtml}
      </div>
    `;

    return card;
  }

  // =========================================================================
  // Priority Control Interactivity & Real-Time Sync
  // =========================================================================
  window.updatePriorityPreview = (eventId, val) => {
    const score = Math.max(1, Math.min(10, parseInt(val, 10) || 5));
    const badge = document.getElementById(`priority_badge_${eventId}`);
    const num = document.getElementById(`priority_num_${eventId}`);
    const lbl = document.getElementById(`priority_label_${eventId}`);
    const topBadge = document.getElementById(`card_priority_badge_${eventId}`);
    
    if (num) num.textContent = score;
    if (lbl) lbl.textContent = getPriorityLabel(score);
    if (badge) {
      badge.className = `priority-score-badge priority-badge-${getPriorityTier(score)}`;
    }
    if (topBadge) {
      topBadge.textContent = `Priority ${score}/10`;
    }
  };

  window.handlePriorityChange = (eventId, val) => {
    const score = Math.max(1, Math.min(10, parseInt(val, 10) || 5));
    const evt = currentEvents.find(e => e.id === eventId);
    if (evt) {
      evt.priority_score = score;
    }
    const priInput = document.getElementById(`input_priority_${eventId}`);
    if (priInput) priInput.value = score;
    window.updatePriorityPreview(eventId, score);
    window.handleFieldChange(eventId);
  };

  window.adjustPriority = (eventId, delta) => {
    const evt = currentEvents.find(e => e.id === eventId);
    const curScore = evt ? (evt.priority_score || 5) : 5;
    const newScore = Math.max(1, Math.min(10, curScore + delta));
    window.handlePriorityChange(eventId, newScore);
  };

  // =========================================================================
  // Real-time Event Editing & Dynamic Re-Validation
  // =========================================================================
  window.handleFieldChange = async (eventId) => {
    const evt = currentEvents.find(e => e.id === eventId);
    if (!evt) return;

    // Update local state from inputs
    const tInput = document.getElementById(`input_title_${eventId}`);
    const dInput = document.getElementById(`input_date_${eventId}`);
    const sInput = document.getElementById(`input_start_time_${eventId}`);
    const eInput = document.getElementById(`input_end_time_${eventId}`);
    const lInput = document.getElementById(`input_location_${eventId}`);
    const pInput = document.getElementById(`input_priority_${eventId}`);

    if (tInput) evt.title = tInput.value;
    if (dInput) {
      evt.start_date = dInput.value;
      evt.end_date = dInput.value;
    }
    if (sInput) evt.start_time = sInput.value;
    if (eInput) evt.end_time = eInput.value;
    if (lInput) evt.location = lInput.value;
    if (pInput) evt.priority_score = parseInt(pInput.value, 10) || evt.priority_score || 5;

    // Call re-validation endpoint
    try {
      const response = await fetch('/api/validate-event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event: evt })
      });

      if (response.ok) {
        const data = await response.json();
        const updatedEvt = data.event;
        // Keep priority_score consistent
        if (evt.priority_score !== undefined) {
          updatedEvt.priority_score = evt.priority_score;
        }
        const index = currentEvents.findIndex(e => e.id === eventId);
        if (index !== -1) {
          currentEvents[index] = updatedEvt;
          const oldCard = document.getElementById(`card_${eventId}`);
          if (oldCard) {
            const newCard = createEventCardElement(updatedEvt, index);
            oldCard.replaceWith(newCard);
          }
          updateConflictStatusRibbon(currentEvents);
          showToast(`Re-validated "${updatedEvt.title}" (Priority ${updatedEvt.priority_score}/10)`, 'info');
        }
      }
    } catch (err) {
      console.error('Validation error:', err);
    }
  };

  window.rescheduleEvent = async (eventId, addHours = 1) => {
    const evt = currentEvents.find(e => e.id === eventId);
    if (!evt) return;

    // Calculate smart shift past conflicting event if one exists
    if (evt.conflicts && evt.conflicts.length > 0) {
      let latestConflictEndMinutes = null;
      evt.conflicts.forEach(c => {
        const existEnd = c.existing_event ? c.existing_event.end_time : null;
        if (existEnd) {
          const [h, m] = existEnd.split(':').map(Number);
          const totalM = h * 60 + m;
          if (latestConflictEndMinutes === null || totalM > latestConflictEndMinutes) {
            latestConflictEndMinutes = totalM;
          }
        }
      });

      if (latestConflictEndMinutes !== null) {
        const [curStartH, curStartM] = (evt.start_time || '09:00').split(':').map(Number);
        const [curEndH, curEndM] = (evt.end_time || '10:00').split(':').map(Number);
        const curDurationM = (curEndH * 60 + curEndM) - (curStartH * 60 + curStartM);
        const duration = curDurationM > 0 ? curDurationM : 60;

        const newStartH = Math.floor(latestConflictEndMinutes / 60) % 24;
        const newStartM = latestConflictEndMinutes % 60;
        const newEndMinutes = latestConflictEndMinutes + duration;
        const newEndH = Math.floor(newEndMinutes / 60) % 24;
        const newEndM = newEndMinutes % 60;

        evt.start_time = `${String(newStartH).padStart(2, '0')}:${String(newStartM).padStart(2, '0')}`;
        evt.end_time = `${String(newEndH).padStart(2, '0')}:${String(newEndM).padStart(2, '0')}`;
      } else {
        const [h1, m1] = (evt.start_time || '09:00').split(':').map(Number);
        const [h2, m2] = (evt.end_time || '10:00').split(':').map(Number);
        const newH1 = (h1 + addHours) % 24;
        const newH2 = (h2 + addHours) % 24;
        evt.start_time = `${String(newH1).padStart(2, '0')}:${String(m1).padStart(2, '0')}`;
        evt.end_time = `${String(newH2).padStart(2, '0')}:${String(m2).padStart(2, '0')}`;
      }
    } else {
      const [h1, m1] = (evt.start_time || '09:00').split(':').map(Number);
      const [h2, m2] = (evt.end_time || '10:00').split(':').map(Number);
      const newH1 = (h1 + addHours) % 24;
      const newH2 = (h2 + addHours) % 24;
      evt.start_time = `${String(newH1).padStart(2, '0')}:${String(m1).padStart(2, '0')}`;
      evt.end_time = `${String(newH2).padStart(2, '0')}:${String(m2).padStart(2, '0')}`;
    }

    const sInput = document.getElementById(`input_start_time_${eventId}`);
    const eInput = document.getElementById(`input_end_time_${eventId}`);
    if (sInput) sInput.value = evt.start_time;
    if (eInput) eInput.value = evt.end_time;

    await window.handleFieldChange(eventId);
    showToast(`Shifted "${evt.title}" to ${evt.start_time} - ${evt.end_time} to avoid conflict`, 'success');
  };

  window.dismissConflict = (eventId) => {
    const evt = currentEvents.find(e => e.id === eventId);
    if (!evt) return;
    evt.has_conflict = false;
    evt.conflicts = [];
    evt.validation_flags = (evt.validation_flags || []).filter(f => f.type !== 'SCHEDULE_CONFLICT');
    const oldCard = document.getElementById(`card_${eventId}`);
    const index = currentEvents.findIndex(e => e.id === eventId);
    if (oldCard) {
      const newCard = createEventCardElement(evt, index);
      oldCard.replaceWith(newCard);
    }
    updateConflictStatusRibbon(currentEvents);
    showToast('Conflict dismissed. Both events will be scheduled simultaneously.', 'info');
  };

  // =========================================================================
  // Submit Validated Events to Google Calendar
  // =========================================================================
  btnSubmitCalendar.addEventListener('click', async () => {
    if (!currentEvents || currentEvents.length === 0) return;

    btnSubmitCalendar.disabled = true;
    btnSubmitCalendar.innerHTML = '<span class="spinner-ring" style="width:18px;height:18px;border-width:2px;margin:0 6px 0 0;"></span> Submitting...';

    try {
      const response = await fetch('/api/calendar/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ events: currentEvents })
      });

      if (!response.ok) {
        throw new Error('Calendar submission failed');
      }

      const data = await response.json();
      const isLiveGoogle = data.is_live_google;

      if (isLiveGoogle) {
        successMessage.innerHTML = `Your events have been <strong>created directly on your Google Calendar</strong>!`;
      } else {
        successMessage.innerHTML = `Your events have been verified and saved to the <strong>Calendar Sandbox</strong>.<br>
          <div style="margin-top: 10px; padding: 10px; background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.25); border-radius: 8px;">
            <div style="font-size:0.82rem; color:#cbd5e1; margin-bottom: 6px;">Want them on your real Google Calendar?</div>
            <button class="btn btn-google btn-sm" onclick="document.getElementById('btnCloseSuccessModal').click(); document.getElementById('btnConnectGoogle').click();">
              Sign in with Google to Sync
            </button>
          </div>`;
      }
      
      // Render Synced Events List
      syncedEventsList.innerHTML = '';
      data.results.forEach(r => {
        const item = document.createElement('div');
        item.style.cssText = 'padding: 10px 14px; background: rgba(255,255,255,0.04); border-radius: 8px; margin-bottom: 8px; text-align: left;';
        
        const hasGoogleLink = r.result.html_link && r.result.html_link.startsWith('http');
        const linkBtn = hasGoogleLink 
          ? `<a href="${r.result.html_link}" target="_blank" rel="noopener" class="btn btn-secondary btn-sm" style="margin-top:6px; display:inline-flex; font-size:0.75rem;">
               <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
               Open in Google Calendar ↗
             </a>`
          : '';

        item.innerHTML = `
          <div style="font-weight:600;">✓ ${escapeHtml(r.title)}</div>
          <div style="font-size:0.75rem; color:#94a3b8;">${r.result.message || 'Synced successfully'}</div>
          ${linkBtn}
        `;
        syncedEventsList.appendChild(item);
      });

      successModal.style.display = 'flex';
      showToast('Successfully synced events to calendar!', 'success');
      fetchCalendarStatus();
    } catch (err) {
      showToast(`Submission failed: ${err.message}`, 'danger');
    } finally {
      btnSubmitCalendar.disabled = false;
      btnSubmitCalendar.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
          <polyline points="17 21 17 13 7 13 7 21"></polyline>
          <polyline points="7 3 7 8 15 8"></polyline>
        </svg>
        <span id="btnSubmitText">${isGoogleConnected ? 'Sync to Real Google Calendar' : 'Confirm & Sync Events'}</span>
      `;
    }
  });

  // Download .ICS File
  btnDownloadIcs.addEventListener('click', async () => {
    if (!currentEvents || currentEvents.length === 0) return;

    try {
      const response = await fetch('/api/calendar/export-ics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ events: currentEvents })
      });

      if (!response.ok) throw new Error('Failed to generate .ics');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'calendar_events.ics';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
      showToast('Downloaded calendar_events.ics successfully!', 'success');
    } catch (err) {
      showToast(`Download failed: ${err.message}`, 'danger');
    }
  });

  // =========================================================================
  // Calendar Modal & Status Management
  // =========================================================================
  async function fetchCalendarStatus() {
    try {
      const res = await fetch('/api/calendar/status');
      if (res.ok) {
        const data = await res.json();
        hasServerCredentials = data.has_credentials;
        const credentialsDetectedBanner = document.getElementById('credentialsDetectedBanner');
        const credSourceName = document.getElementById('credSourceName');
        const credentialsMissingNotice = document.getElementById('credentialsMissingNotice');

        if (data.has_credentials) {
          if (credentialsDetectedBanner) credentialsDetectedBanner.style.display = 'block';
          if (credSourceName) credSourceName.textContent = data.credentials_source || 'credentials.json';
          if (credentialsMissingNotice) credentialsMissingNotice.style.display = 'none';
        } else {
          if (credentialsDetectedBanner) credentialsDetectedBanner.style.display = 'none';
          if (credentialsMissingNotice) credentialsMissingNotice.style.display = 'block';
        }

        if (data.authenticated) {
          calendarStatusBadge.style.color = '#10b981';
          calendarStatusBadge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
          calendarStatusText.textContent = `Google Calendar: ${data.email || 'Connected'}`;
          btnConnectGoogleText.textContent = 'Google Settings';
          if (btnSubmitText) btnSubmitText.textContent = 'Sync to Real Google Calendar';

          // Profile box in modal
          connectedProfileBox.style.display = 'flex';
          connectedUserEmail.textContent = data.email || 'Connected User';
        } else {
          calendarStatusBadge.style.color = '#f59e0b';
          calendarStatusBadge.style.borderColor = 'rgba(245, 158, 11, 0.3)';
          calendarStatusText.textContent = `Calendar Sandbox Active (${data.total_calendar_events} events)`;
          btnConnectGoogleText.textContent = 'Connect Google';
          if (btnSubmitText) btnSubmitText.textContent = 'Confirm & Sync Events';
          connectedProfileBox.style.display = 'none';
        }
      }
    } catch (err) {
      console.warn('Status check warning:', err);
    }
  }

  btnOpenCalendarModal.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/calendar/events');
      if (res.ok) {
        const data = await res.json();
        calendarTableBody.innerHTML = '';
        data.events.forEach(e => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td><strong>${escapeHtml(e.title)}</strong></td>
            <td>${e.start_date}</td>
            <td>${e.start_time} - ${e.end_time}</td>
            <td><span class="badge badge-${(e.category || 'event').toLowerCase()}">${e.category}</span></td>
            <td>${e.priority_score}/10</td>
          `;
          calendarTableBody.appendChild(tr);
        });
        calendarModal.style.display = 'flex';
      }
    } catch (err) {
      showToast('Failed to load calendar events', 'danger');
    }
  });

  btnCloseCalendarModal.addEventListener('click', () => calendarModal.style.display = 'none');
  btnCloseCalendarModalBtn.addEventListener('click', () => calendarModal.style.display = 'none');
  btnCloseSuccessModal.addEventListener('click', () => successModal.style.display = 'none');

  // Helper: Reset Workspace
  function resetWorkspace() {
    currentImageFile = null;
    currentEvents = [];
    fileInput.value = '';
    imagePreview.src = '';
    previewContainer.style.display = 'none';
    const laserScanner = document.getElementById('laserScanner');
    if (laserScanner) laserScanner.style.display = 'none';
    updateConflictStatusRibbon([]);
    dropzonePlaceholder.style.display = 'flex';
    if (dropzoneUploadOverlay) dropzoneUploadOverlay.style.display = 'none';
    btnClearImage.style.display = 'none';
    ocrInspectorCard.style.display = 'none';
    eventCardsList.innerHTML = '';
    emptyState.style.display = 'flex';
    actionFooter.style.display = 'none';
    eventCountBadge.textContent = '0 Events';
  }

  // Toast Helper
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icon = type === 'success' ? '✓' : (type === 'danger' ? '✕' : (type === 'warning' ? '⚠️' : 'ℹ️'));
    
    const iconSpan = document.createElement('span');
    iconSpan.textContent = icon;
    const msgSpan = document.createElement('span');
    msgSpan.textContent = message;
    
    toast.appendChild(iconSpan);
    toast.appendChild(msgSpan);
    const container = document.getElementById('toastContainer');
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }
});
