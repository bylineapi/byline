/**
 * NewsWire WP - Admin JavaScript
 * Funcionalidades del panel de administración sin jQuery
 * 
 * @package NewsWire_WP
 */

document.addEventListener('DOMContentLoaded', function() {
    // ============================================
    // 1. VERIFICAR CONEXIÓN API
    // ============================================
    const verifyBtn = document.getElementById('nwwp-verify-btn');
    const verifyMsg = document.getElementById('nwwp-verify-msg');
    const connectionDot = document.querySelector('.nwwp-connection-dot');
    const connectionText = document.querySelector('.nwwp-connection-text');

    if (verifyBtn) {
        verifyBtn.addEventListener('click', function() {
            // Obtener valores del formulario
            const apiUrlInput = document.getElementById('nwwp_api_url');
            const apiKeyInput = document.getElementById('nwwp_api_key');
            
            const apiUrl = apiUrlInput ? apiUrlInput.value.trim() : '';
            const apiKey = apiKeyInput ? apiKeyInput.value.trim() : '';
            
            // Validar que los campos no estén vacíos
            if (!apiUrl || !apiKey) {
                showVerifyMessage('error', 'La URL de la API y la API Key son obligatorias.');
                return;
            }
            
            // Guardar texto original del botón
            const originalText = verifyBtn.textContent;
            
            // Mostrar estado de carga
            verifyBtn.textContent = 'Verificando...';
            verifyBtn.disabled = true;
            verifyMsg.textContent = '';
            verifyMsg.className = 'nwwp-verify-msg';
            
            // Hacer petición AJAX a WordPress
            // Usamos wp.ajax.post que es la forma nativa de WordPress
            if (typeof wp !== 'undefined' && wp.ajax) {
                wp.ajax.post('nwwp_verify_connection', {
                    api_url: apiUrl,
                    api_key: apiKey,
                    nonce: nwwpAdmin ? nwwpAdmin.nonce : ''
                }).done(function(response) {
                    // Éxito: mostrar punto verde y plan detectado
                    if (response.success && response.data) {
                        showVerifyMessage('success', response.data.message || 'Conexión exitosa');
                        updateConnectionStatus(true, response.data.plan || 'basic', apiUrl);
                    } else {
                        showVerifyMessage('error', response.data && response.data.message ? response.data.message : 'Error en la conexión');
                        updateConnectionStatus(false);
                    }
                }).fail(function(response) {
                    // Error: mostrar punto rojo
                    const errorMsg = response.responseJSON && response.responseJSON.data && response.responseJSON.data.message 
                        ? response.responseJSON.data.message 
                        : 'Error de conexión';
                    showVerifyMessage('error', errorMsg);
                    updateConnectionStatus(false);
                }).always(function() {
                    // Restaurar botón
                    verifyBtn.textContent = originalText;
                    verifyBtn.disabled = false;
                });
            } else {
                // Fallback si wp.ajax no está disponible
                showVerifyMessage('error', 'WordPress AJAX no está disponible');
                verifyBtn.textContent = originalText;
                verifyBtn.disabled = false;
            }
        });
    }

    /**
     * Muestra el mensaje de verificación de conexión
     * @param {string} type - 'success' o 'error'
     * @param {string} message - Mensaje a mostrar
     */
    function showVerifyMessage(type, message) {
        if (!verifyMsg) return;
        
        verifyMsg.textContent = message;
        verifyMsg.className = 'nwwp-verify-msg ' + type;
    }

    /**
     * Actualiza el estado visual de conexión en la barra superior
     * @param {boolean} connected - Si está conectado o no
     * @param {string} plan - Plan detectado (opcional)
     * @param {string} url - URL de la API (opcional)
     */
    function updateConnectionStatus(connected, plan, url) {
        if (connectionDot) {
            connectionDot.classList.remove('connected', 'disconnected');
            connectionDot.classList.add(connected ? 'connected' : 'disconnected');
        }
        
        if (connectionText && connected && url) {
            const planLabel = plan ? plan.charAt(0).toUpperCase() + plan.slice(1) : '';
            connectionText.innerHTML = '<strong>Conectado a Byline API (' + planLabel + ')</strong> — ' + url;
        } else if (connectionText && !connected) {
            connectionText.textContent = 'No conectado — Error en la verificación';
        }
    }

    // ============================================
    // 2. MEDIA PICKER - SELECCIÓN DE IMAGEN
    // ============================================
    const uploadImageBtn = document.getElementById('nwwp-upload-image-btn');
    const removeImageBtn = document.getElementById('nwwp-remove-image-btn');
    const defaultImageIdInput = document.getElementById('nwwp_default_image_id');
    const imagePreview = document.querySelector('.nwwp-image-preview');

    if (uploadImageBtn) {
        uploadImageBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Abrir el selector de medios de WordPress
            if (typeof wp !== 'undefined' && wp.media) {
                const mediaFrame = wp.media({
                    title: 'Seleccionar imagen por defecto',
                    button: { text: 'Usar esta imagen' },
                    multiple: false,
                    library: { type: 'image' }
                });
                
                // Cuando se selecciona una imagen
                mediaFrame.on('select', function() {
                    const attachment = mediaFrame.state().get('selection').first().toJSON();
                    
                    // Actualizar campo hidden con el ID
                    if (defaultImageIdInput) {
                        defaultImageIdInput.value = attachment.id;
                    }
                    
                    // Mostrar preview de la imagen (48x48px)
                    if (imagePreview && attachment.sizes && attachment.sizes.thumbnail) {
                        imagePreview.innerHTML = '<img src="' + attachment.sizes.thumbnail.url + '" alt="Preview" />';
                    }
                });
                
                mediaFrame.open();
            }
        });
    }

    // Botón para quitar la imagen
    if (removeImageBtn) {
        removeImageBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Limpiar el campo hidden
            if (defaultImageIdInput) {
                defaultImageIdInput.value = '';
            }
            
            // Ocultar el preview
            if (imagePreview) {
                imagePreview.innerHTML = '';
            }
        });
    }

    // ============================================
    // 3. TABLA DINÁMICA DE CATEGORÍAS
    // ============================================
    const addCategoryBtn = document.getElementById('nwwp-add-category-row');
    const categoryRowsContainer = document.getElementById('nwwp-category-map-rows');

    // Botón para agregar nueva fila de categoría
    if (addCategoryBtn && categoryRowsContainer) {
        addCategoryBtn.addEventListener('click', function() {
            // Obtener las categorías de WordPress desde el PHP o construir opciones
            // Buscar las opciones en las filas existentes
            const firstSelect = categoryRowsContainer.querySelector('select');
            let optionsHtml = '<option value="">— Seleccionar —</option>';
            
            if (firstSelect) {
                // Copiar las opciones de la primera fila
                const selectOptions = firstSelect.querySelectorAll('option');
                selectOptions.forEach(function(option) {
                    optionsHtml += '<option value="' + option.value + '">' + option.textContent + '</option>';
                });
            }
            
            // Crear nueva fila
            const newRow = document.createElement('div');
            newRow.className = 'nwwp-category-row';
            newRow.innerHTML = 
                '<input type="text" name="nwwp_category_map_api[]" value="" placeholder="Categoría API" />' +
                '<span class="nwwp-category-arrow">→</span>' +
                '<select name="nwwp_category_map_wp[]">' + optionsHtml + '</select>' +
                '<button type="button" class="nwwp-btn-remove-row" title="Eliminar">×</button>';
            
            categoryRowsContainer.appendChild(newRow);
        });
    }

    // Delegar evento para eliminar filas (para rows agregados dinámicamente)
    if (categoryRowsContainer) {
        categoryRowsContainer.addEventListener('click', function(e) {
            if (e.target.classList.contains('nwwp-btn-remove-row')) {
                const rows = categoryRowsContainer.querySelectorAll('.nwwp-category-row');
                
                if (rows.length > 1) {
                    // Si hay más de una fila, eliminar la actual
                    e.target.closest('.nwwp-category-row').remove();
                } else {
                    // Si solo hay una fila, limpiar los valores
                    const input = e.target.closest('.nwwp-category-row').querySelector('input');
                    const select = e.target.closest('.nwwp-category-row').querySelector('select');
                    
                    if (input) input.value = '';
                    if (select) select.value = '';
                }
            }
        });
    }

    // ============================================
    // 4. ESTADO VISUAL DEL PLAN BÁSICO
    // ============================================
    // Leer el plan desde el badge del header
    const planBadge = document.querySelector('.nwwp-plan-badge-header');
    let currentPlan = 'basic';

    if (planBadge) {
        // El plan está en la clase del badge (basic, pro, business)
        if (planBadge.classList.contains('pro')) {
            currentPlan = 'pro';
        } else if (planBadge.classList.contains('business')) {
            currentPlan = 'business';
        } else {
            currentPlan = 'basic';
        }
    }

    // Si el plan es basic, deshabilitar visualmente los elementos Pro
    if (currentPlan === 'basic') {
        // Deshabilitar radio buttons de "Artículo completo" y "Resumen IA"
        const contentFullRadio = document.getElementById('content_full');
        const contentSummaryRadio = document.getElementById('content_summary');
        
        if (contentFullRadio) {
            contentFullRadio.disabled = true;
            // Buscar el contenedor padre para agregar clase visual
            const fullCard = contentFullRadio.closest('.nwwp-radio-card');
            if (fullCard) {
                fullCard.classList.add('locked');
                fullCard.style.opacity = '0.6';
                fullCard.style.cursor = 'not-allowed';
            }
        }
        
        if (contentSummaryRadio) {
            contentSummaryRadio.disabled = true;
            const summaryCard = contentSummaryRadio.closest('.nwwp-radio-card');
            if (summaryCard) {
                summaryCard.classList.add('locked');
                summaryCard.style.opacity = '0.6';
                summaryCard.style.cursor = 'not-allowed';
            }
        }

        // Agregar clase 'locked' al toggle de breaking news
        const breakingCheckbox = document.getElementById('nwwp_activar_breaking');
        const breakingToggle = breakingCheckbox ? breakingCheckbox.closest('.nwwp-toggle') : null;
        
        if (breakingToggle) {
            breakingToggle.classList.add('locked');
            breakingToggle.style.opacity = '0.6';
            breakingToggle.style.cursor = 'not-allowed';
        }
    }

    // ============================================
    // 5. GUARDADO DEL FORMULARIO (AJAX)
    // ============================================
    const settingsForm = document.getElementById('nwwp-settings-form');
    const saveBtn = document.getElementById('nwwp-save-btn');
    const saveMessage = document.getElementById('nwwp-save-message');

    if (settingsForm && saveBtn) {
        settingsForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Recolectar datos del formulario
            const apiUrl = document.getElementById('nwwp_api_url').value;
            const apiKey = document.getElementById('nwwp_api_key').value;
            
            // Obtener modo de contenido seleccionado
            const contentModeInputs = document.querySelectorAll('input[name="nwwp_content_mode"]');
            let contentMode = 'excerpt';
            contentModeInputs.forEach(function(input) {
                if (input.checked) {
                    contentMode = input.value;
                }
            });
            
            const postsPerHour = document.getElementById('nwwp_posts_per_hour').value;
            const breakingCheckbox = document.getElementById('nwwp_activar_breaking');
            const activarBreaking = breakingCheckbox && breakingCheckbox.checked ? 1 : 0;
            const defaultImageId = defaultImageIdInput ? defaultImageIdInput.value : '';
            
            // Recolectar mapeo de categorías
            const categoryMap = {};
            const categoryRows = categoryRowsContainer ? categoryRowsContainer.querySelectorAll('.nwwp-category-row') : [];
            categoryRows.forEach(function(row) {
                const apiInput = row.querySelector('input[type="text"]');
                const wpSelect = row.querySelector('select');
                
                if (apiInput && wpSelect && apiInput.value && wpSelect.value) {
                    categoryMap[apiInput.value] = wpSelect.value;
                }
            });
            
            const extraKeywords = document.getElementById('nwwp_extra_keywords') ? 
                document.getElementById('nwwp_extra_keywords').value : '';
            
            // Guardar texto original del botón
            const originalBtnText = saveBtn.textContent;
            
            // Deshabilitar botón y mostrar estado de carga
            saveBtn.disabled = true;
            saveBtn.textContent = 'Guardando...';
            
            // Enviar datos por AJAX
            if (typeof wp !== 'undefined' && wp.ajax) {
                wp.ajax.post('nwwp_save_settings_ajax', {
                    nonce: nwwpAdmin ? nwwpAdmin.nonce : '',
                    nwwp_api_url: apiUrl,
                    nwwp_api_key: apiKey,
                    nwwp_content_mode: contentMode,
                    nwwp_posts_per_hour: postsPerHour,
                    nwwp_activar_breaking: activarBreaking,
                    nwwp_default_image_id: defaultImageId,
                    nwwp_category_map: JSON.stringify(categoryMap),
                    nwwp_extra_keywords: extraKeywords
                }).done(function(response) {
                    if (response.success) {
                        saveMessage.innerHTML = '<span style="color:#2e7d32;">Cambios guardados correctamente</span>';
                        saveMessage.style.display = 'inline';
                        
                        // Ocultar mensaje después de 3 segundos
                        setTimeout(function() {
                            saveMessage.style.display = 'none';
                        }, 3000);
                    } else {
                        saveMessage.innerHTML = '<span style="color:#c62828;">Error: ' + 
                            (response.data && response.data.message ? response.data.message : 'Error desconocido') + '</span>';
                        saveMessage.style.display = 'inline';
                    }
                }).fail(function(response) {
                    const errorMsg = response.responseJSON && response.responseJSON.data && response.responseJSON.data.message 
                        ? response.responseJSON.data.message 
                        : 'Error de conexión';
                    saveMessage.innerHTML = '<span style="color:#c62828;">Error: ' + errorMsg + '</span>';
                    saveMessage.style.display = 'inline';
                }).always(function() {
                    // Restaurar botón
                    saveBtn.disabled = false;
                    saveBtn.textContent = originalBtnText;
                });
            }
        });
    }
});