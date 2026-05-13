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
    const apiInfoDiv = document.getElementById('nwwp-api-info');
    const connectionBar = document.querySelector('.nwwp-connection-bar');
    const connectionDot = document.querySelector('.nwwp-connection-dot');
    const connectionText = document.querySelector('.nwwp-connection-text');
    const apiKeyInput = document.getElementById('nwwp_api_key');
    const planBadge = document.querySelector('.nwwp-plan-badge-header');

    // Función para verificar automáticamente la API Key
    function autoVerifyApiKey() {
        const apiKey = apiKeyInput ? apiKeyInput.value.trim() : '';
        
        if (!apiKey) {
            updateConnectionStatus('disconnected');
            return;
        }
        
        // Ya está verificado según el estado actual del DOM
        if (connectionBar && connectionBar.classList.contains('connected') && apiInfoDiv) {
            return;
        }
        
        // Mostrar estado pending temporalmente
        updateConnectionStatus('pending');
        
        if (typeof wp !== 'undefined' && wp.ajax) {
            wp.ajax.post('nwwp_verify_connection', {
                api_key: apiKey,
                nonce: nwwpAdmin ? nwwpAdmin.nonce : ''
            }).done(function(response) {
                if (response.success && response.data) {
                    const plan = response.data.plan || 'basic';
                    updateConnectionStatus('connected', plan);
                    if (apiInfoDiv) {
                        apiInfoDiv.style.display = 'flex';
                    }
                    if (planBadge) {
                        planBadge.className = 'nwwp-plan-badge-header ' + plan;
                        planBadge.textContent = plan.charAt(0).toUpperCase() + plan.slice(1);
                    }
                    unlockProFeatures(plan);
                } else {
                    updateConnectionStatus('pending');
                }
            }).fail(function() {
                updateConnectionStatus('pending');
            });
        }
    }

    // Función para desbloquear características según el plan
    function unlockProFeatures(plan) {
        if (plan === 'basic') return;
        
        // Desbloquear Artículo completo
        const contentFullRadio = document.getElementById('content_full');
        if (contentFullRadio) {
            contentFullRadio.disabled = false;
            const fullCard = contentFullRadio.closest('.nwwp-radio-card');
            if (fullCard) {
                fullCard.classList.remove('locked');
                fullCard.style.opacity = '1';
                fullCard.style.cursor = 'pointer';
            }
        }
        
        // Desbloquear Resumen IA
        const contentSummaryRadio = document.getElementById('content_summary');
        if (contentSummaryRadio) {
            contentSummaryRadio.disabled = false;
            const summaryCard = contentSummaryRadio.closest('.nwwp-radio-card');
            if (summaryCard) {
                summaryCard.classList.remove('locked');
                summaryCard.style.opacity = '1';
                summaryCard.style.cursor = 'pointer';
            }
        }
        
        // Desbloquear Breaking news
        const breakingCheckbox = document.getElementById('nwwp_breaking_enabled');
        if (breakingCheckbox) {
            breakingCheckbox.disabled = false;
            const breakingLabel = breakingCheckbox.closest('.nwwp-toggle-label');
            const breakingBadge = breakingLabel ? breakingLabel.querySelector('.nwwp-plan-badge') : null;
            if (breakingBadge) {
                breakingBadge.style.display = 'none';
            }
        }
        
        // Actualizar límite de posts por hora
        const postsPerHourInput = document.getElementById('nwwp_posts_per_hour');
        if (postsPerHourInput) {
            postsPerHourInput.removeAttribute('readonly');
            postsPerHourInput.style.background = '#fff';
        }
    }

    // Ejecutar verificación automática al cargar la página
    if (apiKeyInput && apiKeyInput.value.trim() !== '') {
        // Usar el plan detectado desde PHP si está disponible
        if (typeof nwwpAdmin !== 'undefined' && nwwpAdmin.detectedPlan && nwwpAdmin.detectedPlan !== 'basic') {
            updateConnectionStatus('connected', nwwpAdmin.detectedPlan);
            if (apiInfoDiv) {
                apiInfoDiv.style.display = 'flex';
            }
            if (planBadge) {
                planBadge.className = 'nwwp-plan-badge-header ' + nwwpAdmin.detectedPlan;
                planBadge.textContent = nwwpAdmin.detectedPlan.charAt(0).toUpperCase() + nwwpAdmin.detectedPlan.slice(1);
            }
            unlockProFeatures(nwwpAdmin.detectedPlan);
        } else {
            // Verificar con la API si el plan es basic o no hay plan
            autoVerifyApiKey();
        }
    }

    if (verifyBtn) {
        verifyBtn.addEventListener('click', function() {
            const apiKeyInput = document.getElementById('nwwp_api_key');
            const apiKey = apiKeyInput ? apiKeyInput.value.trim() : '';
            
            if (!apiKey) {
                showVerifyMessage('error', 'La API Key es obligatoria.');
                return;
            }
            
            const originalText = verifyBtn.textContent;
            
            verifyBtn.textContent = 'Verificando...';
            verifyBtn.disabled = true;
            verifyMsg.textContent = '';
            verifyMsg.className = 'nwwp-verify-msg';
            
            if (typeof wp !== 'undefined' && wp.ajax) {
                wp.ajax.post('nwwp_verify_connection', {
                    api_key: apiKey,
                    nonce: nwwpAdmin ? nwwpAdmin.nonce : ''
                }).done(function(response) {
                    if (response.success && response.data) {
                        showVerifyMessage('success', 'Conectado · Plan ' + (response.data.plan || 'Básico') + ' · ' + (response.data.sources || '0') + ' fuentes disponibles');
                        updateConnectionStatus('connected', response.data.plan || 'basic');
                        if (apiInfoDiv) {
                            apiInfoDiv.style.display = 'flex';
                        }
                    } else {
                        showVerifyMessage('error', response.data && response.data.message ? response.data.message : 'Error en la conexión');
                        updateConnectionStatus('disconnected');
                        if (apiInfoDiv) {
                            apiInfoDiv.style.display = 'none';
                        }
                    }
                }).fail(function(response) {
                    const errorMsg = response.responseJSON && response.responseJSON.data && response.responseJSON.data.message 
                        ? response.responseJSON.data.message 
                        : 'API Key inválida. Verifica en byline.io/admin';
                    showVerifyMessage('error', errorMsg);
                    updateConnectionStatus('disconnected');
                    if (apiInfoDiv) {
                        apiInfoDiv.style.display = 'none';
                    }
                }).always(function() {
                    verifyBtn.textContent = originalText;
                    verifyBtn.disabled = false;
                });
            } else {
                showVerifyMessage('error', 'WordPress AJAX no está disponible');
                verifyBtn.textContent = originalText;
                verifyBtn.disabled = false;
            }
        });
    }

    function showVerifyMessage(type, message) {
        if (!verifyMsg) return;
        
        verifyMsg.textContent = message;
        verifyMsg.className = 'nwwp-verify-msg ' + type;
    }

    function updateConnectionStatus(status, plan) {
        if (connectionBar) {
            connectionBar.classList.remove('connected', 'pending', 'disconnected');
            connectionBar.classList.add(status);
        }
        
        if (connectionDot) {
            connectionDot.classList.remove('connected', 'pending', 'disconnected');
            connectionDot.classList.add(status);
        }
        
        if (connectionText) {
            if (status === 'connected') {
                const planLabel = plan ? plan.charAt(0).toUpperCase() + plan.slice(1) : 'Básico';
                connectionText.innerHTML = '<strong>Conectado a Byline</strong> · Plan ' + planLabel + ' · Última sync: Nunca';
            } else if (status === 'pending') {
                connectionText.textContent = 'API Key ingresada — Haz clic en Verificar';
            } else {
                connectionText.textContent = 'Sin configurar — Ingresa tu API Key para comenzar';
            }
        }
    }

    // Verificar estado inicial
    const apiKeyInput = document.getElementById('nwwp_api_key');
    if (apiKeyInput && apiKeyInput.value.trim() !== '') {
        if (connectionBar && connectionBar.classList.contains('connected')) {
            if (apiInfoDiv) {
                apiInfoDiv.style.display = 'flex';
            }
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
    // Leer el plan desde nwwpAdmin (pasado desde PHP)
    let currentPlan = 'basic';

    if (typeof nwwpAdmin !== 'undefined' && nwwpAdmin.detectedPlan) {
        currentPlan = nwwpAdmin.detectedPlan;
    }

    // Si el plan NO es basic, desbloquear características Pro
    if (currentPlan !== 'basic') {
        // Desbloquear radio buttons de "Artículo completo" y "Resumen IA"
        const contentFullRadio = document.getElementById('content_full');
        const contentSummaryRadio = document.getElementById('content_summary');
        
        if (contentFullRadio) {
            contentFullRadio.disabled = false;
            const fullCard = contentFullRadio.closest('.nwwp-radio-card');
            if (fullCard) {
                fullCard.classList.remove('locked');
                fullCard.style.opacity = '1';
                fullCard.style.cursor = 'pointer';
            }
        }
        
        if (contentSummaryRadio) {
            contentSummaryRadio.disabled = false;
            const summaryCard = contentSummaryRadio.closest('.nwwp-radio-card');
            if (summaryCard) {
                summaryCard.classList.remove('locked');
                summaryCard.style.opacity = '1';
                summaryCard.style.cursor = 'pointer';
            }
        }

        // Desbloquear toggle de breaking news
        const breakingCheckbox = document.getElementById('nwwp_breaking_enabled');
        if (breakingCheckbox) {
            breakingCheckbox.disabled = false;
        }
        
        // Actualizar input de posts por hora
        const postsPerHour = document.getElementById('nwwp_posts_per_hour');
        if (postsPerHour) {
            postsPerHour.removeAttribute('readonly');
            postsPerHour.style.background = '#fff';
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