<?php
/**
 * Página de ajustes del plugin NewsWire WP
 * Diseño profesional con estadísticas, estados de conexión y secciones organizadas
 *
 * @package NewsWire_WP
 */

if (!defined('ABSPATH')) {
    exit;
}

include nwwp_PLUGIN_DIR . 'admin/css/admin-styles.php';

// Obtener configuración actual
$detected_plan = get_option('nwwp_detected_plan', 'basic');
$plan_class    = sanitize_html_class($detected_plan);
$api_url       = get_option('nwwp_api_url', '');
$api_key       = get_option('nwwp_api_key', '');
$content_mode  = get_option('nwwp_content_mode', 'excerpt');
$posts_per_hour = get_option('nwwp_posts_per_hour', 5);
$activar_breaking = get_option('nwwp_activar_breaking', false);
$default_image_id = get_option('nwwp_default_image_id', 0);
$category_map = get_option('nwwp_category_map', array());
$extra_keywords = get_option('nwwp_extra_keywords', '');
$nwwp_sources = get_option('nwwp_sources', array());
$last_sync = get_option('nwwp_last_sync', '');

// Calcular estadísticas
global $wpdb;
$table_articles = $wpdb->prefix . 'nwwp_imported_articles';
$today = date('Y-m-d');

// Artículos importados hoy
$imported_today = 0;
if ($wpdb->get_var("SHOW TABLES LIKE '$table_articles'") === $table_articles) {
    $imported_today = (int) $wpdb->get_var($wpdb->prepare(
        "SELECT COUNT(*) FROM $table_articles WHERE DATE(imported_at) = %s",
        $today
    ));
}

// Breaking news hoy (posts con meta nwwp_impact_score >= 80 hoy)
$breaking_today = 0;
$breaking_today = (int) $wpdb->get_var($wpdb->prepare(
    "SELECT COUNT(*) FROM $wpdb->posts p
     INNER JOIN $wpdb->postmeta pm ON p.ID = pm.post_id
     WHERE p.post_date LIKE %s
     AND pm.meta_key = 'nwwp_impact_score'
     AND CAST(pm.meta_value AS UNSIGNED) >= 80
     AND p.post_status = 'publish'",
    $today . '%'
));

// Fuentes activas
$sources_count = is_array($nwwp_sources) ? count($nwwp_sources) : 0;

// Última sync
$sync_text = 'Nunca';
if (!empty($last_sync)) {
    $sync_time = current_time('timestamp') - strtotime($last_sync);
    $minutes = floor($sync_time / 60);
    if ($minutes < 1) {
        $sync_text = 'Hace menos de 1 min';
    } elseif ($minutes < 60) {
        $sync_text = "Hace $minutes min";
    } else {
        $hours = floor($minutes / 60);
        $sync_text = "Hace $hours h";
    }
}

// Categorías de WordPress
$wp_categories = get_categories(array('hide_empty' => false));
$wp_cats_by_id = array();
foreach ($wp_categories as $cat) {
    $wp_cats_by_id[$cat->term_id] = $cat->name;
}

// URL de API verificada (solo lectura si ya hay conexión)
$api_verified = !empty($api_url) && !empty($api_key);
?>

<div class="nwwp-wrap">
    <!-- Header del panel -->
    <div class="nwwp-header">
        <div class="nwwp-header-left">
            <div class="nwwp-logo">NW</div>
            <div class="nwwp-header-title">
                <h1>NewsWire WP</h1>
                <p>Sistema de distribución de noticias</p>
            </div>
        </div>
        <div class="nwwp-header-right">
            <span class="nwwp-plan-badge-header <?php echo esc_attr($plan_class); ?>">
                <?php echo esc_html(ucfirst($detected_plan)); ?>
            </span>
            <button type="submit" id="nwwp-save-btn" class="nwwp-btn-guardar" form="nwwp-settings-form">
                Guardar cambios
            </button>
            <span id="nwwp-save-message" style="font-size:13px; margin-left:10px;"></span>
        </div>
    </div>

    <!-- Barra de estadísticas -->
    <div class="nwwp-stats-grid">
        <div class="nwwp-stat-card">
            <div class="nwwp-stat-icon imported">📰</div>
            <div class="nwwp-stat-content">
                <h3><?php echo esc_html($imported_today); ?></h3>
                <p>Artículos importados hoy</p>
            </div>
        </div>
        <div class="nwwp-stat-card">
            <div class="nwwp-stat-icon breaking">⚡</div>
            <div class="nwwp-stat-content">
                <h3 class="stat-value-red"><?php echo esc_html($breaking_today); ?></h3>
                <p>Breaking news hoy</p>
            </div>
        </div>
        <div class="nwwp-stat-card">
            <div class="nwwp-stat-icon sources">📡</div>
            <div class="nwwp-stat-content">
                <h3><?php echo esc_html($sources_count); ?></h3>
                <p>Fuentes activas</p>
            </div>
        </div>
        <div class="nwwp-stat-card">
            <div class="nwwp-stat-icon sync">🔄</div>
            <div class="nwwp-stat-content">
                <h3><?php echo esc_html($sync_text); ?></h3>
                <p>Última sincronización</p>
            </div>
        </div>
    </div>

    <!-- Barra de estado de conexión -->
    <div class="nwwp-connection-bar">
        <div class="nwwp-connection-status">
            <span class="nwwp-connection-dot <?php echo $api_verified ? 'connected' : 'disconnected'; ?>"></span>
            <span class="nwwp-connection-text">
                <?php if ($api_verified) : ?>
                    <strong>Conectado a Byline API</strong> — <?php echo esc_url($api_url); ?>
                <?php else : ?>
                    No conectado — Configura la API para comenzar
                <?php endif; ?>
            </span>
        </div>
        <div class="nwwp-sync-time">
            Última sync: <?php echo esc_html($sync_text); ?>
        </div>
    </div>

    <!-- Formulario principal -->
    <form id="nwwp-settings-form" method="post" action="#">
        <?php 
        wp_nonce_field('nwwp_save_settings');
        ?>

        <!-- Sección 1: Conexión API -->
        <div class="nwwp-section">
            <div class="nwwp-section-header">
                <div class="nwwp-section-icon blue">🔗</div>
                <div class="nwwp-section-title">
                    <h2>Conexión API</h2>
                    <p>Configura la conexión con Byline API</p>
                </div>
            </div>
            <div class="nwwp-section-content">
                <div class="nwwp-form-row">
                    <div class="nwwp-form-label">
                        <label for="nwwp_api_url">URL de la API</label>
                    </div>
                    <div class="nwwp-form-input">
                        <input type="url" 
                               id="nwwp_api_url" 
                               name="nwwp_api_url" 
                               value="<?php echo esc_attr($api_url); ?>"
                               placeholder="https://tu-api.onrender.com"
                               <?php echo $api_verified ? 'readonly' : ''; ?> />
                    </div>
                </div>
                <div class="nwwp-form-row">
                    <div class="nwwp-form-label">
                        <label for="nwwp_api_key">API Key</label>
                    </div>
                    <div class="nwwp-form-input">
                        <div class="nwwp-input-with-btn">
                            <input type="password" 
                                   id="nwwp_api_key" 
                                   name="nwwp_api_key" 
                                   value="<?php echo esc_attr($api_key); ?>"
                                   autocomplete="new-password" />
                            <button type="button" id="nwwp-verify-btn">Verificar</button>
                            <span id="nwwp-verify-msg" class="nwwp-verify-msg"></span>
                        </div>
                        <p class="nwwp-form-hint">Obtén tu API Key en <a href="https://byline.io/admin" target="_blank">byline.io/admin</a></p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Sección 2: Publicación -->
        <div class="nwwp-section">
            <div class="nwwp-section-header">
                <div class="nwwp-section-icon green">📝</div>
                <div class="nwwp-section-title">
                    <h2>Publicación</h2>
                    <p>Configura cómo se publican las noticias</p>
                </div>
            </div>
            <div class="nwwp-section-content">
                <!-- Modo de contenido -->
                <div class="nwwp-form-row">
                    <div class="nwwp-form-label">
                        <label>Modo de contenido</label>
                    </div>
                    <div class="nwwp-form-input">
                        <div class="nwwp-radio-cards">
                            <div class="nwwp-radio-card <?php echo 'full' === $content_mode ? 'selected' : ''; ?>">
                                <input type="radio" 
                                       id="content_full" 
                                       name="nwwp_content_mode" 
                                       value="full" 
                                       <?php checked('full', $content_mode); ?>
                                       <?php disabled('basic' === $detected_plan); ?> />
                                <label for="content_full">
                                    Artículo completo
                                    <?php if ('basic' === $detected_plan) : ?>
                                        <span class="nwwp-badge-pro">Pro</span>
                                    <?php endif; ?>
                                </label>
                            </div>
                            <div class="nwwp-radio-card selected">
                                <input type="radio" 
                                       id="content_excerpt" 
                                       name="nwwp_content_mode" 
                                       value="excerpt" 
                                       <?php checked('excerpt', $content_mode); ?> />
                                <label for="content_excerpt">Extracto + enlace</label>
                            </div>
                            <div class="nwwp-radio-card <?php echo 'summary' === $content_mode ? 'selected' : ''; ?>">
                                <input type="radio" 
                                       id="content_summary" 
                                       name="nwwp_content_mode" 
                                       value="summary" 
                                       <?php checked('summary', $content_mode); ?>
                                       <?php disabled('basic' === $detected_plan); ?> />
                                <label for="content_summary">
                                    Resumen IA
                                    <?php if ('basic' === $detected_plan) : ?>
                                        <span class="nwwp-badge-pro">Pro</span>
                                    <?php endif; ?>
                                </label>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Noticias por hora -->
                <div class="nwwp-form-row">
                    <div class="nwwp-form-label">
                        <label for="nwwp_posts_per_hour">Noticias por hora</label>
                    </div>
                    <div class="nwwp-form-input">
                        <input type="number" 
                               id="nwwp_posts_per_hour" 
                               name="nwwp_posts_per_hour" 
                               value="<?php echo esc_attr($posts_per_hour); ?>"
                               min="1" 
                               max="<?php echo 'basic' === $detected_plan ? '2' : '999'; ?>"
                               <?php echo 'basic' === $detected_plan ? 'readonly style="background:#f0f0f0;"' : ''; ?> />
                        <?php if ('basic' === $detected_plan) : ?>
                            <p class="nwwp-form-hint">Límite del plan básico: 2 noticias/hora</p>
                        <?php endif; ?>
                    </div>
                </div>

                <!-- Breaking news toggle -->
                <div class="nwwp-form-row">
                    <div class="nwwp-form-label">
                        <label>Breaking news</label>
                    </div>
                    <div class="nwwp-form-input">
                        <div class="nwwp-toggle-label">
                            <label class="nwwp-toggle">
                                <input type="checkbox" 
                                       id="nwwp_activar_breaking" 
                                       name="nwwp_activar_breaking" 
                                       value="1"
                                       <?php checked(1, $activar_breaking); ?>
                                       <?php disabled('basic' === $detected_plan); ?> />
                                <span class="nwwp-toggle-slider"></span>
                            </label>
                            <span>Verificar noticias de último momento cada 5 min</span>
                        </div>
                        <?php if ('basic' === $detected_plan) : ?>
                            <p class="nwwp-toggle-note">Solo disponible en plan Pro</p>
                        <?php endif; ?>
                    </div>
                </div>

                <!-- Imagen por defecto -->
                <div class="nwwp-form-row">
                    <div class="nwwp-form-label">
                        <label>Imagen por defecto</label>
                    </div>
                    <div class="nwwp-form-input">
                        <input type="hidden" 
                               id="nwwp_default_image_id" 
                               name="nwwp_default_image_id" 
                               value="<?php echo esc_attr($default_image_id); ?>" />
                        <div class="nwwp-image-preview">
                            <?php
                            $img_id = intval($default_image_id);
                            if ($img_id > 0) {
                                $img_url = wp_get_attachment_image_url($img_id, 'thumbnail');
                                if ($img_url) {
                                    echo '<img src="' . esc_url($img_url) . '" alt="Preview" />';
                                }
                            }
                            ?>
                        </div>
                        <div class="nwwp-image-actions">
                            <button type="button" id="nwwp-upload-image-btn" class="nwwp-btn-upload">
                                Seleccionar imagen
                            </button>
                            <button type="button" id="nwwp-remove-image-btn" class="nwwp-btn-remove">
                                Quitar
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Sección 3: Mapeo de categorías -->
        <div class="nwwp-section">
            <div class="nwwp-section-header">
                <div class="nwwp-section-icon purple">📂</div>
                <div class="nwwp-section-title">
                    <h2>Mapeo de categorías</h2>
                    <p>Asocia categorías de la API con categorías de WordPress</p>
                </div>
            </div>
            <div class="nwwp-section-content">
                <div id="nwwp-category-map-rows" class="nwwp-category-rows">
                    <?php
                    if (empty($category_map)) {
                        $category_map = array('' => '');
                    }

                    foreach ($category_map as $api_cat => $wp_cat_id) :
                        $wp_cat_id = $wp_cat_id ? intval($wp_cat_id) : '';
                    ?>
                        <div class="nwwp-category-row">
                            <input type="text" 
                                   name="nwwp_category_map_api[]" 
                                   value="<?php echo esc_attr($api_cat); ?>"
                                   placeholder="Categoría API" />
                            <span class="nwwp-category-arrow">→</span>
                            <select name="nwwp_category_map_wp[]">
                                <option value="">— Seleccionar —</option>
                                <?php foreach ($wp_cats_by_id as $id => $name) : ?>
                                    <option value="<?php echo esc_attr($id); ?>" <?php selected($wp_cat_id, $id); ?>>
                                        <?php echo esc_html($name); ?>
                                    </option>
                                <?php endforeach; ?>
                            </select>
                            <button type="button" class="nwwp-btn-remove-row" title="Eliminar">×</button>
                        </div>
                    <?php endforeach; ?>
                </div>
                <button type="button" id="nwwp-add-category-row" class="nwwp-btn-add-category">
                    + Agregar categoría
                </button>
                <!-- Campo hidden para almacenar el mapeo como JSON -->
                <input type="hidden" id="nwwp_category_map_json" name="nwwp_category_map" value="" />
            </div>
        </div>

        <!-- Sección 4: Palabras clave urgentes -->
        <div class="nwwp-section">
            <div class="nwwp-section-header">
                <div class="nwwp-section-icon amber">🔑</div>
                <div class="nwwp-section-title">
                    <h2>Palabras clave urgentes</h2>
                    <p>Palabras clave adicionales para priorizar en la importación</p>
                </div>
            </div>
            <div class="nwwp-section-content">
                <div class="nwwp-form-row">
                    <div class="nwwp-form-label">
                        <label for="nwwp_extra_keywords">Palabras clave</label>
                    </div>
                    <div class="nwwp-form-input">
                        <textarea id="nwwp_extra_keywords" 
                                  name="nwwp_extra_keywords" 
                                  class="nwwp-keywords-textarea"
                                  placeholder="Ejemplo: elecciones, crisis, emergencia, cumbre mundial"><?php echo esc_textarea($extra_keywords); ?></textarea>
                        <p class="nwwp-form-hint">Palabras separadas por coma. Se suman a las palabras clave base de la API.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="nwwp-footer">
            <div class="nwwp-footer-left">
                NewsWire WP v1.0 · Powered by <strong>Byline</strong>
            </div>
            <div class="nwwp-footer-right">
                <button type="submit" name="submit" class="nwwp-btn-guardar">
                    Guardar todos los cambios
                </button>
            </div>
        </div>
    </form>
</div>

<script>
jQuery(document).ready(function($) {
    // Guardado por AJAX en lugar de enviar a options.php
    $('#nwwp-settings-form').on('submit', function(e) {
        e.preventDefault();

        var mapData = {};
        $('#nwwp-category-map-rows .nwwp-category-row').each(function() {
            var apiCat = $(this).find('input[type="text"]').val();
            var wpCat = $(this).find('select').val();
            if (apiCat && wpCat) {
                mapData[apiCat] = wpCat;
            }
        });

        var formData = {
            action: 'nwwp_save_settings_ajax',
            nonce: nwwpAdmin.nonce,
            nwwp_api_url: $('#nwwp_api_url').val(),
            nwwp_api_key: $('#nwwp_api_key').val(),
            nwwp_content_mode: $('input[name="nwwp_content_mode"]:checked').val(),
            nwwp_posts_per_hour: $('#nwwp_posts_per_hour').val(),
            nwwp_activar_breaking: $('#nwwp_activar_breaking').is(':checked') ? 1 : 0,
            nwwp_default_image_id: $('#nwwp_default_image_id').val(),
            nwwp_category_map: JSON.stringify(mapData),
            nwwp_extra_keywords: $('#nwwp_extra_keywords').val()
        };

        $.ajax({
            url: nwwpAdmin.ajaxUrl,
            type: 'POST',
            data: formData,
            beforeSend: function() {
                $('#nwwp-save-btn').prop('disabled', true).text('Guardando...');
            },
            success: function(response) {
                if (response.success) {
                    $('#nwwp-save-message').html('<span style="color:#2e7d32;">Cambios guardados correctamente</span>').show();
                    setTimeout(function() {
                        $('#nwwp-save-message').fadeOut();
                    }, 3000);
                } else {
                    $('#nwwp-save-message').html('<span style="color:#c62828;">Error: ' + response.data.message + '</span>').show();
                }
            },
            error: function() {
                $('#nwwp-save-message').html('<span style="color:#c62828;">Error de conexión</span>').show();
            },
            complete: function() {
                $('#nwwp-save-btn').prop('disabled', false).text('Guardar cambios');
            }
        });
    });

    // Agregar nueva fila de categoría
    $('#nwwp-add-category-row').on('click', function() {
        var options = '<option value="">— Seleccionar —</option>';
        <?php foreach ($wp_cats_by_id as $id => $name) : ?>
        options += '<option value="<?php echo esc_attr($id); ?>"><?php echo esc_js($name); ?></option>';
        <?php endforeach; ?>

        var rowHtml = '<div class="nwwp-category-row">' +
            '<input type="text" name="nwwp_category_map_api[]" value="" placeholder="Categoría API" />' +
            '<span class="nwwp-category-arrow">→</span>' +
            '<select name="nwwp_category_map_wp[]">' + options + '</select>' +
            '<button type="button" class="nwwp-btn-remove-row" title="Eliminar">×</button>' +
            '</div>';
        $('#nwwp-category-map-rows').append(rowHtml);
    });

    // Eliminar fila de categoría
    $(document).on('click', '.nwwp-btn-remove-row', function() {
        var $rows = $('#nwwp-category-map-rows .nwwp-category-row');
        if ($rows.length > 1) {
            $(this).closest('.nwwp-category-row').remove();
        } else {
            $(this).closest('.nwwp-category-row').find('input').val('');
            $(this).closest('.nwwp-category-row').find('select').val('');
        }
    });

    // Selection de imagen
    $('#nwwp-upload-image-btn').on('click', function(e) {
        e.preventDefault();
        var mediaFrame = wp.media({
            title: 'Seleccionar imagen por defecto',
            button: { text: 'Usar imagen' },
            multiple: false,
            library: { type: 'image' }
        });

        mediaFrame.on('select', function() {
            var attachment = mediaFrame.state().get('selection').first().toJSON();
            $('#nwwp_default_image_id').val(attachment.id);
            $('#nwwp-image-preview').html('<img src="' + attachment.sizes.thumbnail.url + '" alt="Preview" />');
        });

        mediaFrame.open();
    });

    // Quitar imagen
    $('#nwwp-remove-image-btn').on('click', function(e) {
        e.preventDefault();
        $('#nwwp_default_image_id').val('');
        $('#nwwp-image-preview').html('');
    });
});
</script>