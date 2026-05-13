/**
 * NWWP Admin JS
 * Vanilla JS - Sin dependencias de jQuery
 *
 * @package NewsWire_WP
 */

(function() {
    'use strict';

    var NWWPSettings = {
        init: function() {
            this.bindVerifyConnection();
            this.bindMediaUploader();
        },

        bindVerifyConnection: function() {
            var verifyBtn = document.getElementById('nwwp-verify-btn');
            var msgBox = document.getElementById('nwwp-verify-msg');

            if (!verifyBtn || !msgBox) return;

            verifyBtn.addEventListener('click', function(e) {
                e.preventDefault();

                var apiUrlInput = document.getElementById('nwwp_api_url');
                var apiKeyInput = document.getElementById('nwwp_api_key');

                var apiUrl = apiUrlInput ? apiUrlInput.value.trim() : '';
                var apiKey = apiKeyInput ? apiKeyInput.value.trim() : '';

                if (!apiUrl || !apiKey) {
                    msgBox.innerHTML = '<span style="color:#c62828;">Por favor, completa la URL y la API Key.</span>';
                    return;
                }

                var originalText = verifyBtn.textContent;
                verifyBtn.disabled = true;
                verifyBtn.textContent = 'Verificando...';
                msgBox.innerHTML = '';

                var formData = new FormData();
                formData.append('action', 'nwwp_verify_connection');
                formData.append('nonce', typeof nwwpAdmin !== 'undefined' ? nwwpAdmin.nonce : '');
                formData.append('api_url', apiUrl);
                formData.append('api_key', apiKey);

                fetch(nwwpAdmin.ajaxUrl, {
                    method: 'POST',
                    body: formData
                })
                .then(function(response) {
                    return response.json();
                })
                .then(function(data) {
                    if (data.success) {
                        msgBox.innerHTML = '<span style="color:#2e7d32;">' + data.data.message + '</span>';
                        NWWPSettings.actualizarUIsegunPlan(data.data.plan);
                    } else {
                        msgBox.innerHTML = '<span style="color:#c62828;">' + data.data.message + '</span>';
                    }
                })
                .catch(function() {
                    msgBox.innerHTML = '<span style="color:#c62828;">Error de conexión AJAX.</span>';
                })
                .finally(function() {
                    verifyBtn.disabled = false;
                    verifyBtn.textContent = originalText;
                });
            });
        },

        actualizarUIsegunPlan: function(plan) {
            var contentFull = document.querySelector('input[name="nwwp_content_mode"][value="full"]');
            var contentSummary = document.querySelector('input[name="nwwp_content_mode"][value="summary"]');
            var breakingCheck = document.getElementById('nwwp_activar_breaking');
            var postsPerHour = document.getElementById('nwwp_posts_per_hour');

            if (plan === 'basic') {
                if (contentFull) {
                    contentFull.disabled = true;
                    var fullLabel = contentFull.closest('label');
                    if (fullLabel && !fullLabel.querySelector('.nwwp-disabled-note')) {
                        var note = document.createElement('span');
                        note.className = 'nwwp-disabled-note';
                        note.textContent = 'Actualiza tu plan';
                        fullLabel.appendChild(note);
                    }
                }
                if (contentSummary) {
                    contentSummary.disabled = true;
                    var summaryLabel = contentSummary.closest('label');
                    if (summaryLabel && !summaryLabel.querySelector('.nwwp-disabled-note')) {
                        var note = document.createElement('span');
                        note.className = 'nwwp-disabled-note';
                        note.textContent = 'Actualiza tu plan';
                        summaryLabel.appendChild(note);
                    }
                }
                if (breakingCheck) {
                    breakingCheck.disabled = true;
                    var breakingLabel = breakingCheck.closest('label');
                    if (breakingLabel && !breakingLabel.querySelector('.nwwp-disabled-note')) {
                        var note = document.createElement('span');
                        note.className = 'nwwp-disabled-note';
                        note.textContent = 'Solo disponible en plan Pro';
                        breakingLabel.appendChild(note);
                    }
                }
                if (postsPerHour) {
                    postsPerHour.setAttribute('max', '2');
                }
            } else if (plan === 'pro' || plan === 'business') {
                if (contentFull) {
                    contentFull.disabled = false;
                    var fullLabel = contentFull.closest('label');
                    var fullNote = fullLabel ? fullLabel.querySelector('.nwwp-disabled-note') : null;
                    if (fullNote) fullNote.remove();
                }
                if (contentSummary) {
                    contentSummary.disabled = false;
                    var summaryLabel = contentSummary.closest('label');
                    var summaryNote = summaryLabel ? summaryLabel.querySelector('.nwwp-disabled-note') : null;
                    if (summaryNote) summaryNote.remove();
                }
                if (breakingCheck) {
                    breakingCheck.disabled = false;
                    var breakingLabel = breakingCheck.closest('label');
                    var breakingNote = breakingLabel ? breakingLabel.querySelector('.nwwp-disabled-note') : null;
                    if (breakingNote) breakingNote.remove();
                }
                if (postsPerHour) {
                    postsPerHour.setAttribute('max', '999');
                }
            }
        },

        bindMediaUploader: function() {
            var uploadBtn = document.getElementById('nwwp-upload-image-btn');
            var removeBtn = document.getElementById('nwwp-remove-image-btn');
            var imageInput = document.getElementById('nwwp_default_image_id');
            var imagePreview = document.getElementById('nwwp-image-preview');

            if (uploadBtn && typeof wp !== 'undefined' && wp.media) {
                uploadBtn.addEventListener('click', function(e) {
                    e.preventDefault();

                    var mediaFrame = wp.media({
                        title: 'Seleccionar imagen por defecto',
                        button: { text: 'Usar imagen' },
                        multiple: false,
                        library: { type: 'image' }
                    });

                    mediaFrame.on('select', function() {
                        var attachment = mediaFrame.state().get('selection').first().toJSON();
                        if (imageInput) {
                            imageInput.value = attachment.id;
                        }
                        if (imagePreview) {
                            imagePreview.innerHTML = '<img src="' + attachment.url + '" style="max-width:200px;height:auto;" />';
                        }
                    });

                    mediaFrame.open();
                });
            }

            if (removeBtn) {
                removeBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    if (imageInput) {
                        imageInput.value = '';
                    }
                    if (imagePreview) {
                        imagePreview.innerHTML = '';
                    }
                });
            }
        }
    };

    document.addEventListener('DOMContentLoaded', function() {
        NWWPSettings.init();
    });

})();