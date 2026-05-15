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

                var apiKeyInput = document.getElementById('nwwp_api_key');
                var apiKey = apiKeyInput ? apiKeyInput.value.trim() : '';

                if (!apiKey) {
                    msgBox.innerHTML = '<span style="color:#c62828;">Por favor, completa la API Key.</span>';
                    return;
                }

                var originalText = verifyBtn.textContent;
                verifyBtn.disabled = true;
                verifyBtn.textContent = 'Verificando...';
                msgBox.innerHTML = '';

                var formData = new FormData();
                formData.append('action', 'nwwp_verify_connection');
                formData.append('nonce', typeof nwwpAdmin !== 'undefined' ? nwwpAdmin.nonce : '');
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
            var breakingCheck = document.getElementById('nwwp_breaking_enabled');
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
        
        // --- Gestión de Fuentes (Modo Dueño) ---
        var sourcesTbody = document.getElementById('nwwp-sources-tbody');
        if (sourcesTbody) {
            cargarFuentes();
        }

        function cargarFuentes() {
            var formData = new FormData();
            formData.append('action', 'nwwp_get_sources');
            formData.append('nonce', nwwpAdmin.nonce);

            fetch(nwwpAdmin.ajaxUrl, {
                method: 'POST',
                body: formData
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.success) {
                    renderizarFuentes(data.data);
                } else {
                    sourcesTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:red;">Error al cargar fuentes: ' + data.data.message + '</td></tr>';
                }
            })
            .catch(function() {
                sourcesTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:red;">Error de conexión.</td></tr>';
            });
        }

        function renderizarFuentes(fuentes) {
            if (!fuentes || fuentes.length === 0) {
                sourcesTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No hay fuentes configuradas.</td></tr>';
                return;
            }

            var html = '';
            fuentes.forEach(function(f) {
                var urlDisplay = f.rss_url ? f.rss_url : f.url;
                var typeBadge = f.rss_url ? '<span class="nwwp-badge-rss">RSS</span>' : '<span class="nwwp-badge-url">URL</span>';
                
                html += '<tr>' +
                    '<td><strong>' + f.name + '</strong></td>' +
                    '<td><code style="font-size:11px;">' + urlDisplay + '</code> ' + typeBadge + '</td>' +
                    '<td>' + (f.category || '-') + '</td>' +
                    '<td><span class="nwwp-status-' + (f.is_active ? 'active' : 'inactive') + '">' + (f.is_active ? 'Activa' : 'Inactiva') + '</span></td>' +
                    '<td>' +
                        '<button type="button" class="nwwp-btn-delete-source" data-id="' + f.id + '" style="color:#d32f2f;background:none;border:none;cursor:pointer;padding:0;font-size:12px;">Eliminar</button>' +
                    '</td>' +
                    '</tr>';
            });
            sourcesTbody.innerHTML = html;

            // Bind delete buttons
            document.querySelectorAll('.nwwp-btn-delete-source').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    if (confirm('¿Estás seguro de eliminar esta fuente? Se eliminarán también sus artículos asociados.')) {
                        eliminarFuente(this.getAttribute('data-id'));
                    }
                });
            });
        }

        function eliminarFuente(id) {
            var formData = new FormData();
            formData.append('action', 'nwwp_delete_source');
            formData.append('nonce', nwwpAdmin.nonce);
            formData.append('source_id', id);

            fetch(nwwpAdmin.ajaxUrl, {
                method: 'POST',
                body: formData
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.success) {
                    cargarFuentes();
                } else {
                    alert('Error: ' + data.data.message);
                }
            });
        }

        var addSourceBtn = document.getElementById('nwwp-add-source-btn');
        if (addSourceBtn) {
            addSourceBtn.addEventListener('click', function() {
                var name = document.getElementById('nwwp_new_source_name').value.trim();
                var category = document.getElementById('nwwp_new_source_category').value.trim();
                var url = document.getElementById('nwwp_new_source_url').value.trim();
                var rss = document.getElementById('nwwp_new_source_rss').value.trim();
                var msg = document.getElementById('nwwp-add-source-msg');

                if (!name || !url) {
                    msg.innerHTML = '<span style="color:red;">Nombre y URL son obligatorios.</span>';
                    return;
                }

                addSourceBtn.disabled = true;
                addSourceBtn.textContent = 'Agregando...';
                msg.innerHTML = '';

                var formData = new FormData();
                formData.append('action', 'nwwp_add_source');
                formData.append('nonce', nwwpAdmin.nonce);
                formData.append('name', name);
                formData.append('category', category);
                formData.append('url', url);
                formData.append('rss_url', rss);

                fetch(nwwpAdmin.ajaxUrl, {
                    method: 'POST',
                    body: formData
                })
                .then(function(response) { return response.json(); })
                .then(function(data) {
                    if (data.success) {
                        msg.innerHTML = '<span style="color:green;">Fuente agregada!</span>';
                        document.getElementById('nwwp_new_source_name').value = '';
                        document.getElementById('nwwp_new_source_category').value = '';
                        document.getElementById('nwwp_new_source_url').value = '';
                        document.getElementById('nwwp_new_source_rss').value = '';
                        cargarFuentes();
                    } else {
                        msg.innerHTML = '<span style="color:red;">Error: ' + data.data.message + '</span>';
                    }
                })
                .finally(function() {
                    addSourceBtn.disabled = false;
                    addSourceBtn.textContent = 'Agregar Fuente';
                });
            });
        }
    });

})();