function initBookFormset(options) {
  const profileUrl = options.profileUrl;
  const tempUploadUrl = options.tempUploadUrl;

  const container = document.getElementById('books-container');
  const form = document.getElementById('books-form');
  const cancelBtn = document.getElementById('cancel-btn');
  const cancelBtnText = document.getElementById('cancel-btn-text');
  const saveBtnContainer = document.getElementById('save-btn-container');
  let newEntryCounter = 1;
  let isDirty = false;

  // Track form changes
  function markDirty() {
    if (!isDirty) {
      isDirty = true;
      cancelBtnText.textContent = 'Cancelar';
      saveBtnContainer.style.display = '';
    }
  }

  // Setup change listeners to track form modifications
  function setupChangeListeners(element) {
    const inputs = element.querySelectorAll('input[type="text"], textarea');
    inputs.forEach(input => {
      input.addEventListener('input', () => {
        markDirty();
      });
    });
  }

  // Auto-add new entry when typing in the last entry
  function setupAutoAddEntry() {
    const lastEntry = container.querySelector('.new-entry:last-of-type');
    if (!lastEntry) return;

    const inputs = lastEntry.querySelectorAll('input[type="text"], textarea');
    inputs.forEach(input => {
      input.addEventListener('input', (e) => {
        // Check if any field in the last entry has content
        const hasContent = Array.from(inputs).some(inp => inp.value.trim() !== '');

        if (hasContent) {
          // Check if there's already another empty entry
          const emptyEntries = container.querySelectorAll('.new-entry');
          const hasEmptyEntry = Array.from(emptyEntries).some(entry => {
            const entryInputs = entry.querySelectorAll('input[type="text"], textarea');
            return Array.from(entryInputs).every(inp => inp.value.trim() === '');
          });

          if (!hasEmptyEntry) {
            addNewEntry();
          }
        }
      });
    });
  }

  // Add a new empty entry
  function addNewEntry() {
    // Get current total forms count
    const totalFormsInput = document.querySelector('[name$="TOTAL_FORMS"]');
    const currentTotal = parseInt(totalFormsInput.value);
    const newIndex = currentTotal;

    // Update total forms
    totalFormsInput.value = currentTotal + 1;

    // Clone the template
    const template = document.getElementById('empty-form-template');
    const newEntry = template.content.cloneNode(true).querySelector('.book-entry');

    // Replace __prefix__ with the actual index
    newEntry.innerHTML = newEntry.innerHTML.replace(/__prefix__/g, newIndex);

    container.appendChild(newEntry);
    setupAutoAddEntry();
    setupDeleteButtons();
    setupChangeListeners(newEntry);
    setupTempPhotoUploads();
  }

  // Handle delete buttons
  function setupDeleteButtons() {
    const deleteButtons = container.querySelectorAll('.delete-btn');
    deleteButtons.forEach(btn => {
      // Remove old listeners by cloning
      const newBtn = btn.cloneNode(true);
      btn.parentNode.replaceChild(newBtn, btn);

      newBtn.addEventListener('click', (e) => {
        const entry = e.currentTarget.closest('.book-entry');

        // If it's an existing book (has data-book-id), mark for deletion
        if (entry.dataset.bookId) {
          entry.classList.add('is-deleted');

          // Check the Django formset DELETE checkbox
          const deleteCheckbox = entry.querySelector('input[name$="-DELETE"]');
          if (deleteCheckbox) {
            deleteCheckbox.checked = true;
          }

          markDirty();
        } else {
          // If it's a new entry, just remove it (but keep at least one empty entry)
          const newEntries = container.querySelectorAll('.new-entry:not(.is-deleted)');
          if (newEntries.length > 1) {
            entry.remove();
            markDirty();
          } else {
            // Clear the fields instead of removing
            const fields = entry.querySelectorAll('input[type="text"], textarea');
            fields.forEach(field => field.value = '');
          }
        }
      });
    });
  }

  // Setup temp photo uploads
  function setupTempPhotoUploads() {
    if (!tempUploadUrl) return;

    // Trigger file input when button is clicked
    document.querySelectorAll('.temp-upload-trigger').forEach(button => {
      // Remove old listeners by cloning
      const newBtn = button.cloneNode(true);
      button.parentNode.replaceChild(newBtn, button);

      newBtn.addEventListener('click', () => {
        const formPrefix = newBtn.dataset.formPrefix;
        const fileInput = document.querySelector(
          `.temp-photo-input[data-form-prefix="${formPrefix}"]`
        );
        if (fileInput) {
          fileInput.click();
        }
      });
    });

    // Handle file selection and upload
    document.querySelectorAll('.temp-photo-input').forEach(input => {
      // Remove old listeners by cloning
      const newInput = input.cloneNode(true);
      input.parentNode.replaceChild(newInput, input);

      newInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formPrefix = newInput.dataset.formPrefix;
        const button = document.querySelector(
          `.temp-upload-trigger[data-form-prefix="${formPrefix}"]`
        );
        const container = document.querySelector(
          `.temp-photo-container[data-form-prefix="${formPrefix}"]`
        );
        const icon = button.querySelector('.icon i');
        const text = button.querySelector('.temp-upload-text');

        // Show loading state
        const originalIcon = icon.className;
        icon.className = 'fas fa-spinner fa-pulse';
        button.disabled = true;

        try {
          // Upload via AJAX
          const formData = new FormData();
          formData.append('cover_image', file);

          const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
          const response = await fetch(tempUploadUrl, {
            method: 'POST',
            body: formData,
            headers: {
              'X-CSRFToken': csrfToken,
              'X-Requested-With': 'XMLHttpRequest'
            }
          });

          if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || 'Upload failed');
          }

          const data = await response.json();

          if (data.success) {
            // Store temp cover ID in hidden field
            const hiddenField = document.querySelector(
              `input[name="${formPrefix}-temp_cover_id"]`
            );
            if (hiddenField) {
              hiddenField.value = data.temp_cover_id;
            }

            // Update image in left column
            if (container) {
              const existingImg = container.querySelector('img');
              if (existingImg) {
                // Update existing image
                existingImg.src = data.image_url;
              } else {
                // Replace placeholder with image
                container.innerHTML = `<img src="${data.image_url}" alt="Cover" class="book-cover-image">`;
              }
            }

            // Update button text
            text.textContent = 'Cambiar foto';

            markDirty();
          } else {
            throw new Error(data.error || 'Upload failed');
          }
        } catch (error) {
          console.error('Upload error:', error);
          alert('Error al subir la foto: ' + (error.message || 'Por favor intentá de nuevo.'));
        } finally {
          // Restore button state
          icon.className = originalIcon;
          button.disabled = false;
          newInput.value = '';  // Reset file input
        }
      });
    });
  }

  // Cancel button
  cancelBtn.addEventListener('click', () => {
    if (isDirty) {
      if (confirm('¿Descartar los cambios?')) {
        window.location.reload();
      }
    } else {
      window.location.href = profileUrl;
    }
  });

  // Form submission - Django will handle validation and ignore empty forms

  // Ensure there's always at least one empty entry
  function ensureEmptyEntry() {
    const emptyEntries = container.querySelectorAll('.new-entry');
    const hasEmptyEntry = Array.from(emptyEntries).some(entry => {
      const entryInputs = entry.querySelectorAll('input[type="text"], textarea');
      return Array.from(entryInputs).every(inp => inp.value.trim() === '');
    });

    if (!hasEmptyEntry) {
      addNewEntry();
    }
  }

  // Initialize
  setupAutoAddEntry();
  setupDeleteButtons();
  ensureEmptyEntry();
  setupTempPhotoUploads();

  // Setup change listeners for all existing entries
  container.querySelectorAll('.book-entry').forEach(entry => {
    setupChangeListeners(entry);
  });
}
