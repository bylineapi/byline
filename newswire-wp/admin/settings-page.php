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

// Los estilos están en admin/css/admin.css que se carga automáticamente

// Obtener configuración actual
$detected_plan = get_option('nwwp_detected_plan', 'basic');
$plan_class    = sanitize_html_class($detected_plan);
$api_key       = get_option('nwwp_api_key', '');
$content_mode  = get_option('nwwp_content_mode', 'excerpt');
$posts_per_hour = get_option('nwwp_posts_per_hour', 5);
$activar_breaking = get_option('nwwp_breaking_enabled', false);
$default_image_id = get_option('nwwp_default_image_id', 0);
$category_map = get_option('nwwp_category_map', array());
$extra_keywords = get_option('nwwp_extra_keywords', '');
$nwwp_sources = get_option('nwwp_sources', array());
$last_sync = get_option('nwwp_last_sync', '');

// Funciones helper para verificar planes
function nwwp_is_pro_or_higher($plan)
{
    return in_array($plan, array('pro', 'business'), true);
}

function nwwp_is_business($plan)
{
    return $plan === 'business';
}

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

// API verificada
$api_verified = !empty($api_key);

// Owner Secret y modo dueño
$owner_secret = get_option('nwwp_owner_secret', '');
$is_owner_mode = nwwp_es_modo_dueno();
$product_map = get_option('nwwp_product_map', array());

// Detectar si WooCommerce está activo
$woocommerce_active = class_exists('WooCommerce');

// Obtener productos de WooCommerce si está activo
$woo_products = array();
if ($woocommerce_active) {
    $products = wc_get_products(array('status' => 'publish', 'limit' => -1));
    foreach ($products as $product) {
        $woo_products[$product->get_id()] = $product->get_name();
    }
}

// Últimas transacciones de WooCommerce (últimos 10 pedidos procesados)
$woo_transactions = array();
if ($woocommerce_active && $is_owner_mode) {
    $orders = wc_get_orders(array(
        'status' => 'completed',
        'limit' => 20,
        'orderby' => 'date',
        'order' => 'DESC',
    ));

    foreach ($orders as $order) {
        $procesado = $order->get_meta('_nwwp_procesado');
        if (!empty($procesado)) {
            $woo_transactions[] = array(
                'id' => $order->get_id(),
                'cliente' => $order->get_billing_first_name() . ' ' . $order->get_billing_last_name(),
                'email' => $order->get_billing_email(),
                'plan' => $order->get_meta('_nwwp_plan'),
                'api_key' => $order->get_meta('_nwwp_api_key'),
                'fecha' => $order->get_date_created()->date('Y-m-d H:i'),
            );
            if (count($woo_transactions) >= 10) break;
        }
    }
}
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
    <?php
    $connection_class = 'disconnected';
    $connection_text = 'Sin configurar — Ingresa tu API Key para comenzar';

    if (!empty($api_key)) {
        if ($api_verified) {
            $connection_class = 'connected';
            $connection_text = '<strong>Conectado a Byline</strong> · Plan ' . ucfirst($detected_plan) . ' · Última sync: ' . $sync_text;
        } else {
            $connection_class = 'pending';
            $connection_text = 'API Key ingresada — Haz clic en Verificar';
        }
    }
    ?>
    <div class="nwwp-connection-bar <?php echo $connection_class; ?>">
        <div class="nwwp-connection-status">
            <span class="nwwp-connection-dot <?php echo $connection_class; ?>"></span>
            <span class="nwwp-connection-text">
                <?php echo $connection_text; ?>
            </span>
        </div>
        <div class="nwwp-sync-time">
            Última sync: <?php echo esc_html($sync_text); ?>
        </div>
    </div>

    <!-- Formulario principal -->
    <form id="nwwp-settings-form" method="post" action="#">
        <?php
        wp_nonce_field('nwwp_verify_connection_nonce', 'nwwp_settings_nonce');
        ?>

        <!-- Sección 1: Conexión API -->
        <div class="nwwp-section">
            <div class="nwwp-section-header">
                <div class="nwwp-section-icon blue">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M4 11a9 9 0 0 1 9 9"></path>
                        <path d="M4 4a16 16 0 0 1 16 16"></path>
                        <circle cx="5" cy="19" r="1"></circle>
                    </svg>
                </div>
                <div class="nwwp-section-title">
                    <h2>Conexión API</h2>
                    <p>Configura la conexión con Byline API</p>
                </div>
            </div>
            <div class="nwwp-section-content">
                <div class="nwwp-form-row">
                    <div class="nwwp-form-label">
                        <label for="nwwp_api_key">Tu API Key</label>
                    </div>
                    <div class="nwwp-form-input">
                        <div class="nwwp-input-with-btn">
                            <input type="password"
                                id="nwwp_api_key"
                                name="nwwp_api_key"
                                value="<?php echo esc_attr($api_key); ?>"
                                placeholder="nwwp_••••••••••••••••"
                                autocomplete="new-password"
                                class="nwwp-api-key-input" />
                            <button type="button" id="nwwp-verify-btn">Verificar</button>
                        </div>
                        <span id="nwwp-verify-msg" class="nwwp-verify-msg"></span>
                        <div id="nwwp-api-info" class="nwwp-api-info" style="display: none;">
                            <span class="nwwp-dot-connected"></span>
                            Conectado a <strong>Byline API</strong>
                            <span class="nwwp-api-version">v1.0.0</span>
                        </div>
                    </div>
                </div>

                <?php if (empty($api_key)): ?>
                    <div class="nwwp-form-row">
                        <div class="nwwp-form-label">
                            <label for="nwwp_owner_secret">Owner Secret (Modo Dueño)</label>
                        </div>
                        <div class="nwwp-form-input">
                            <div class="nwwp-input-with-btn">
                                <input type="password"
                                    id="nwwp_owner_secret"
                                    name="nwwp_owner_secret"
                                    value="<?php echo esc_attr($owner_secret); ?>"
                                    autocomplete="new-password" />
                                <button type="button" id="nwwp-verify-owner-btn">Verificar</button>
                                <span id="nwwp-verify-owner-msg" class="nwwp-verify-msg"></span>
                            </div>
                            <p class="nwwp-form-hint">El Owner Secret activa el modo Dueño. Consíguelo en el archivo .env de tu Byline API.</p>
                            <?php if ($is_owner_mode): ?>
                                <p class="nwwp-form-hint" style="color:#2e7d32;">✓ Modo Dueño activo</p>

                                <div class="nwwp-create-client-form" style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 6px; border: 1px solid #dcdcde;">
                                    <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; color: #1d2327;">Crear nuevo cliente</h4>
                                    <div class="nwwp-form-row" style="margin-bottom: 10px;">
                                        <div class="nwwp-form-label" style="width: 100px;">
                                            <label for="nwwp_client_name" style="font-size: 12px;">Nombre</label>
                                        </div>
                                        <div class="nwwp-form-input">
                                            <input type="text" id="nwwp_client_name" placeholder="Nombre del cliente" style="padding: 6px 10px; font-size: 13px;" />
                                        </div>
                                    </div>
                                    <div class="nwwp-form-row" style="margin-bottom: 10px;">
                                        <div class="nwwp-form-label" style="width: 100px;">
                                            <label for="nwwp_client_email" style="font-size: 12px;">Email</label>
                                        </div>
                                        <div class="nwwp-form-input">
                                            <input type="email" id="nwwp_client_email" placeholder="email@ejemplo.com" style="padding: 6px 10px; font-size: 13px;" />
                                        </div>
                                    </div>
                                    <div class="nwwp-form-row" style="margin-bottom: 10px;">
                                        <div class="nwwp-form-label" style="width: 100px;">
                                            <label for="nwwp_client_plan" style="font-size: 12px;">Plan</label>
                                        </div>
                                        <div class="nwwp-form-input">
                                            <select id="nwwp_client_plan" style="padding: 6px 10px; font-size: 13px;">
                                                <option value="basic">Básico</option>
                                                <option value="pro">Pro</option>
                                                <option value="business">Business</option>
                                            </select>
                                        </div>
                                    </div>
                                    <button type="button" id="nwwp-create-client-btn" class="button button-primary" style="font-size: 13px; padding: 6px 16px;">
                                        Crear Cliente
                                    </button>
                                    <span id="nwwp-create-client-msg" class="nwwp-verify-msg" style="margin-left: 10px;"></span>
                                </div>
                            <?php endif; ?>
                        </div>
                    </div>
                <?php endif; ?>
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
                                    <?php disabled(!nwwp_is_pro_or_higher($detected_plan)); ?> />
                                <label for="content_full">
                                    Artículo completo
                                    <?php if (!nwwp_is_pro_or_higher($detected_plan)) : ?>
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
                                    <?php disabled(!nwwp_is_pro_or_higher($detected_plan)); ?> />
                                <label for="content_summary">
                                    Resumen IA
                                    <?php if (!nwwp_is_pro_or_higher($detected_plan)) : ?>
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
                            max="<?php echo !nwwp_is_pro_or_higher($detected_plan) ? '2' : (nwwp_is_business($detected_plan) ? '100' : '50'); ?>"
                            <?php echo !nwwp_is_pro_or_higher($detected_plan) ? 'readonly style="background:#f0f0f0;"' : ''; ?> />
                        <?php if (!nwwp_is_pro_or_higher($detected_plan)) : ?>
                            <p class="nwwp-form-hint">Límite del plan básico: 2 noticias/hora</p>
                        <?php elseif (nwwp_is_business($detected_plan)) : ?>
                            <p class="nwwp-form-hint">Plan Business: hasta 100 noticias/hora</p>
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
                                    id="nwwp_breaking_enabled"
                                    name="nwwp_breaking_enabled"
                                    value="1"
                                    <?php checked(1, $activar_breaking); ?>
                                    <?php disabled(!nwwp_is_pro_or_higher($detected_plan)); ?> />
                                <span class="nwwp-toggle-slider"></span>
                            </label>
                            <?php if (!nwwp_is_pro_or_higher($detected_plan)) : ?>
                                <span class="nwwp-plan-badge">Solo Plan Pro</span>
                            <?php endif; ?>
                            <span>Verificar noticias de último momento cada 5 min</span>
                        </div>
                        <p class="nwwp-form-hint">
                            Publica noticias urgentes en tiempo real, sin esperar el ciclo horario.
                        </p>
                    </div>
                </div>

                <!-- Auto-publicación programada -->
                <div class="nwwp-form-row">
                    <div class="nwwp-form-label">
                        <label>Auto-publicación</label>
                    </div>
                    <div class="nwwp-form-input">
                        <div class="nwwp-toggle-label">
                            <label class="nwwp-toggle">
                                <input type="checkbox"
                                    id="nwwp_auto_publish_enabled"
                                    name="nwwp_auto_publish_enabled"
                                    value="1"
                                    <?php checked(1, get_option('nwwp_auto_publish_enabled', 0)); ?>
                                    <?php disabled(!nwwp_is_pro_or_higher($detected_plan)); ?> />
                                <span class="nwwp-toggle-slider"></span>
                            </label>
                            <?php if (!nwwp_is_pro_or_higher($detected_plan)) : ?>
                                <span class="nwwp-plan-badge">Solo Plan Pro</span>
                            <?php endif; ?>
                            <span>Publicar artículos automáticamente</span>
                        </div>
                        <p class="nwwp-form-hint">
                            El plugin llamará al scraper automáticamente para obtener contenido nuevo y publicarlo en tu sitio.
                        </p>
                    </div>
                </div>

                <!-- Frecuencia de auto-publicación -->
                <div class="nwwp-form-row" id="nwwp-auto-publish-frequency-row" style="display: <?php echo get_option('nwwp_auto_publish_enabled', 0) ? 'block' : 'none'; ?>;">
                    <div class="nwwp-form-label">
                        <label for="nwwp_auto_publish_frequency">Frecuencia de publicación</label>
                    </div>
                    <div class="nwwp-form-input">
                        <select id="nwwp_auto_publish_frequency"
                            name="nwwp_auto_publish_frequency"
                            <?php disabled(!nwwp_is_pro_or_higher($detected_plan)); ?>>
                            <option value="15" <?php selected('15', get_option('nwwp_auto_publish_frequency', '30')); ?>>Cada 15 minutos</option>
                            <option value="30" <?php selected('30', get_option('nwwp_auto_publish_frequency', '30')); ?>>Cada 30 minutos</option>
                            <option value="60" <?php selected('60', get_option('nwwp_auto_publish_frequency', '30')); ?>>Cada hora</option>
                            <option value="120" <?php selected('120', get_option('nwwp_auto_publish_frequency', '30')); ?>>Cada 2 horas</option>
                            <option value="360" <?php selected('360', get_option('nwwp_auto_publish_frequency', '30')); ?>>Cada 6 horas</option>
                        </select>
                        <p class="nwwp-form-hint">
                            Cada cuánto tiempo el plugin debe solicitar artículos nuevos al scraper.
                        </p>
                    </div>
                </div>

                <!-- Categoría de publicación -->
                <div class="nwwp-form-row" id="nwwp-auto-publish-category-row" style="display: <?php echo get_option('nwwp_auto_publish_enabled', 0) ? 'block' : 'none'; ?>;">
                    <div class="nwwp-form-label">
                        <label for="nwwp_auto_publish_category">Categoría de WordPress</label>
                    </div>
                    <div class="nwwp-form-input">
                        <?php
                        $categories = get_categories(array('hide_empty' => false));
                        $selected_category = get_option('nwwp_auto_publish_category', '');
                        ?>
                        <select id="nwwp_auto_publish_category"
                            name="nwwp_auto_publish_category"
                            <?php disabled(!nwwp_is_pro_or_higher($detected_plan)); ?>>
                            <option value="">-- Seleccionar categoría --</option>
                            <?php foreach ($categories as $cat) : ?>
                                <option value="<?php echo esc_attr($cat->term_id); ?>"
                                    <?php selected($cat->term_id, $selected_category); ?>>
                                    <?php echo esc_html($cat->name); ?>
                                </option>
                            <?php endforeach; ?>
                        </select>
                        <p class="nwwp-form-hint">
                            Los artículos se publicarán en esta categoría de WordPress.
                        </p>
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

        <?php if ($is_owner_mode): ?>
            <div class="nwwp-section">
                <div class="nwwp-section-header">
                    <div class="nwwp-section-icon orange">🛒</div>
                    <div class="nwwp-section-title">
                        <h2>Integración WooCommerce</h2>
                        <p>Automatiza la gestión de clientes con WooCommerce</p>
                    </div>
                </div>
                <div class="nwwp-section-content">
                    <?php if (!$woocommerce_active): ?>
                        <div class="nwwp-notice-warning">
                            <strong>WooCommerce no está instalado.</strong>
                            <p>Instala WooCommerce para automatizar la gestión de clientes y cobros.</p>
                        </div>
                    <?php else: ?>
                        <p class="nwwp-form-hint">Mapea los productos de WooCommerce con los planes de Byline:</p>

                        <div class="nwwp-product-map">
                            <div class="nwwp-form-row">
                                <div class="nwwp-form-label">
                                    <label for="nwwp_product_basic">Plan Basic</label>
                                </div>
                                <div class="nwwp-form-input">
                                    <select id="nwwp_product_basic" name="nwwp_product_map[basic]">
                                        <option value="">— Seleccionar producto —</option>
                                        <?php foreach ($woo_products as $id => $name): ?>
                                            <option value="<?php echo esc_attr($id); ?>" <?php selected(isset($product_map['basic']) ? $product_map['basic'] : '', $id); ?>>
                                                <?php echo esc_html($id . ' - ' . $name); ?>
                                            </option>
                                        <?php endforeach; ?>
                                    </select>
                                </div>
                            </div>
                            <div class="nwwp-form-row">
                                <div class="nwwp-form-label">
                                    <label for="nwwp_product_pro">Plan Pro</label>
                                </div>
                                <div class="nwwp-form-input">
                                    <select id="nwwp_product_pro" name="nwwp_product_map[pro]">
                                        <option value="">— Seleccionar producto —</option>
                                        <?php foreach ($woo_products as $id => $name): ?>
                                            <option value="<?php echo esc_attr($id); ?>" <?php selected(isset($product_map['pro']) ? $product_map['pro'] : '', $id); ?>>
                                                <?php echo esc_html($id . ' - ' . $name); ?>
                                            </option>
                                        <?php endforeach; ?>
                                    </select>
                                </div>
                            </div>
                            <div class="nwwp-form-row">
                                <div class="nwwp-form-label">
                                    <label for="nwwp_product_business">Plan Business</label>
                                </div>
                                <div class="nwwp-form-input">
                                    <select id="nwwp_product_business" name="nwwp_product_map[business]">
                                        <option value="">— Seleccionar producto —</option>
                                        <?php foreach ($woo_products as $id => $name): ?>
                                            <option value="<?php echo esc_attr($id); ?>" <?php selected(isset($product_map['business']) ? $product_map['business'] : '', $id); ?>>
                                                <?php echo esc_html($id . ' - ' . $name); ?>
                                            </option>
                                        <?php endforeach; ?>
                                    </select>
                                </div>
                            </div>
                        </div>

                        <?php if (!empty($woo_transactions)): ?>
                            <h3 style="margin-top:30px; margin-bottom:15px;">Últimas transacciones</h3>
                            <table class="nwwp-transactions-table">
                                <thead>
                                    <tr>
                                        <th>Cliente</th>
                                        <th>Email</th>
                                        <th>Plan</th>
                                        <th>API Key</th>
                                        <th>Fecha</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($woo_transactions as $tx): ?>
                                        <tr>
                                            <td><?php echo esc_html($tx['cliente']); ?></td>
                                            <td><?php echo esc_html($tx['email']); ?></td>
                                            <td><span class="nwwp-plan-badge <?php echo esc_attr($tx['plan']); ?>"><?php echo esc_html(ucfirst($tx['plan'])); ?></span></td>
                                            <td><code><?php echo esc_html(substr($tx['api_key'], 0, 8) . '...'); ?></code></td>
                                            <td><?php echo esc_html($tx['fecha']); ?></td>
                                        </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        <?php endif; ?>

                        <div class="nwwp-woo-info" style="margin-top:20px; padding:15px; background:#f5f5f5; border-radius:4px;">
                            <h4>Información de integración:</h4>
                            <ul style="margin:10px 0; padding-left:20px;">
                                <li>Los clientes se crean automáticamente cuando completan un pago.</li>
                                <li>Las suscripciones canceladas o expiradas desactivan el cliente en Byline.</li>
                                <li>Los cambios de plan actualizan automáticamente el plan del cliente.</li>
                                <li>El cliente recibe un email con su API Key al completar el pago.</li>
                            </ul>
                            <?php if (!class_exists('WC_Subscriptions')): ?>
                                <p style="color:#f57c00;"><strong>Nota:</strong> WooCommerce Subscriptions no está instalado. Las funciones de cancelación y renovación automática no estarán disponibles, pero el registro de clientes funcionará.</p>
                            <?php endif; ?>
                        </div>
                    <?php endif; ?>
                </div>
            </div>
        <?php endif; ?>

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
    (function() {
        'use strict';

        // Guardado por AJAX
        var settingsForm = document.getElementById('nwwp-settings-form');
        if (settingsForm) {
            settingsForm.addEventListener('submit', function(e) {
                e.preventDefault();

                var categoryRows = document.querySelectorAll('#nwwp-category-map-rows .nwwp-category-row');
                var mapData = {};
                for (var i = 0; i < categoryRows.length; i++) {
                    var apiCat = categoryRows[i].querySelector('input[type="text"]').value;
                    var wpCat = categoryRows[i].querySelector('select').value;
                    if (apiCat && wpCat) {
                        mapData[apiCat] = wpCat;
                    }
                }

                var formData = new FormData();
                formData.append('action', 'nwwp_save_settings_ajax');
                formData.append('nwwp_settings_nonce', nwwpAdmin.nonce);
                formData.append('nwwp_api_key', document.getElementById('nwwp_api_key').value);

                var contentModeInputs = document.querySelectorAll('input[name="nwwp_content_mode"]');
                for (var i = 0; i < contentModeInputs.length; i++) {
                    if (contentModeInputs[i].checked) {
                        formData.append('nwwp_content_mode', contentModeInputs[i].value);
                        break;
                    }
                }

                formData.append('nwwp_posts_per_hour', document.getElementById('nwwp_posts_per_hour').value);

                var breakingCheckbox = document.getElementById('nwwp_activar_breaking');
                formData.append('nwwp_activar_breaking', breakingCheckbox && breakingCheckbox.checked ? 1 : 0);

                formData.append('nwwp_default_image_id', document.getElementById('nwwp_default_image_id').value);
                formData.append('nwwp_category_map', JSON.stringify(mapData));
                formData.append('nwwp_extra_keywords', document.getElementById('nwwp_extra_keywords').value);

                var saveBtn = document.getElementById('nwwp-save-btn');
                var saveMessage = document.getElementById('nwwp-save-message');
                var originalBtnText = saveBtn.textContent;

                saveBtn.disabled = true;
                saveBtn.textContent = 'Guardando...';

                fetch(nwwpAdmin.ajaxUrl, {
                        method: 'POST',
                        body: formData
                    })
                    .then(function(response) {
                        return response.json();
                    })
                    .then(function(data) {
                        if (data.success) {
                            saveMessage.innerHTML = '<span style="color:#2e7d32;">Cambios guardados correctamente</span>';
                            saveMessage.style.display = 'inline';
                            setTimeout(function() {
                                saveMessage.style.display = 'none';
                            }, 3000);
                        } else {
                            saveMessage.innerHTML = '<span style="color:#c62828;">Error: ' + (data.data && data.data.message ? data.data.message : 'Error desconocido') + '</span>';
                            saveMessage.style.display = 'inline';
                        }
                    })
                    .catch(function() {
                        saveMessage.innerHTML = '<span style="color:#c62828;">Error de conexión</span>';
                        saveMessage.style.display = 'inline';
                    })
                    .finally(function() {
                        saveBtn.disabled = false;
                        saveBtn.textContent = originalBtnText;
                    });
            });
        }

        // Agregar nueva fila de categoría
        var addCategoryBtn = document.getElementById('nwwp-add-category-row');
        var categoryRowsContainer = document.getElementById('nwwp-category-map-rows');

        if (addCategoryBtn && categoryRowsContainer) {
            addCategoryBtn.addEventListener('click', function() {
                var firstSelect = categoryRowsContainer.querySelector('select');
                var options = '<option value="">— Seleccionar —</option>';

                if (firstSelect) {
                    var selectOptions = firstSelect.querySelectorAll('option');
                    for (var i = 0; i < selectOptions.length; i++) {
                        options += '<option value="' + selectOptions[i].value + '">' + selectOptions[i].textContent + '</option>';
                    }
                }

                var newRow = document.createElement('div');
                newRow.className = 'nwwp-category-row';
                newRow.innerHTML =
                    '<input type="text" name="nwwp_category_map_api[]" value="" placeholder="Categoría API" />' +
                    '<span class="nwwp-category-arrow">→</span>' +
                    '<select name="nwwp_category_map_wp[]">' + options + '</select>' +
                    '<button type="button" class="nwwp-btn-remove-row" title="Eliminar">×</button>';

                categoryRowsContainer.appendChild(newRow);
            });
        }

        // Eliminar fila de categoría (delegated event)
        if (categoryRowsContainer) {
            categoryRowsContainer.addEventListener('click', function(e) {
                if (e.target.classList.contains('nwwp-btn-remove-row')) {
                    var rows = categoryRowsContainer.querySelectorAll('.nwwp-category-row');
                    if (rows.length > 1) {
                        e.target.closest('.nwwp-category-row').remove();
                    } else {
                        var row = e.target.closest('.nwwp-category-row');
                        var input = row.querySelector('input');
                        var select = row.querySelector('select');
                        if (input) input.value = '';
                        if (select) select.value = '';
                    }
                }
            });
        }

        // Selector de imagen
        var uploadImageBtn = document.getElementById('nwwp-upload-image-btn');
        var removeImageBtn = document.getElementById('nwwp-remove-image-btn');
        var defaultImageIdInput = document.getElementById('nwwp_default_image_id');
        var imagePreview = document.getElementById('nwwp-image-preview');

        if (uploadImageBtn && typeof wp !== 'undefined' && wp.media) {
            uploadImageBtn.addEventListener('click', function(e) {
                e.preventDefault();

                var mediaFrame = wp.media({
                    title: 'Seleccionar imagen por defecto',
                    button: {
                        text: 'Usar imagen'
                    },
                    multiple: false,
                    library: {
                        type: 'image'
                    }
                });

                mediaFrame.on('select', function() {
                    var attachment = mediaFrame.state().get('selection').first().toJSON();
                    if (defaultImageIdInput) defaultImageIdInput.value = attachment.id;
                    if (imagePreview && attachment.sizes && attachment.sizes.thumbnail) {
                        imagePreview.innerHTML = '<img src="' + attachment.sizes.thumbnail.url + '" alt="Preview" />';
                    }
                });

                mediaFrame.open();
            });
        }

        if (removeImageBtn) {
            removeImageBtn.addEventListener('click', function(e) {
                e.preventDefault();
                if (defaultImageIdInput) defaultImageIdInput.value = '';
                if (imagePreview) imagePreview.innerHTML = '';
            });
        }
    })();
</script>

<?php if ($is_owner_mode): ?>
    <script>
        (function() {
            'use strict';

            var verifyOwnerBtn = document.getElementById('nwwp-verify-owner-btn');
            var ownerSecretInput = document.getElementById('nwwp_owner_secret');
            var ownerMsg = document.getElementById('nwwp-verify-owner-msg');
            var apiUrl = 'https://byline-dgpt.onrender.com';

            if (verifyOwnerBtn && ownerSecretInput) {
                verifyOwnerBtn.addEventListener('click', function() {
                    var ownerSecret = ownerSecretInput.value.trim();

                    if (!ownerSecret) {
                        ownerMsg.innerHTML = '<span style="color:#c62828;">Por favor, completa el Owner Secret.</span>';
                        return;
                    }

                    verifyOwnerBtn.disabled = true;
                    verifyOwnerBtn.textContent = 'Verificando...';
                    ownerMsg.innerHTML = '';

                    var formData = new FormData();
                    formData.append('action', 'nwwp_verify_owner_secret');
                    formData.append('nonce', nwwpAdmin.nonce);
                    formData.append('api_url', apiUrl);
                    formData.append('owner_secret', ownerSecret);

                    fetch(nwwpAdmin.ajaxUrl, {
                            method: 'POST',
                            body: formData
                        })
                        .then(function(response) {
                            return response.json();
                        })
                        .then(function(data) {
                            if (data.success) {
                                ownerMsg.innerHTML = '<span style="color:#2e7d32;">' + data.data.message + '</span>';
                                location.reload();
                            } else {
                                ownerMsg.innerHTML = '<span style="color:#c62828;">' + data.data.message + '</span>';
                            }
                        })
                        .catch(function() {
                            ownerMsg.innerHTML = '<span style="color:#c62828;">Error de conexión.</span>';
                        })
                        .finally(function() {
                            verifyOwnerBtn.disabled = false;
                            verifyOwnerBtn.textContent = 'Verificar';
                        });
                });
            }

            // Crear cliente
            var createClientBtn = document.getElementById('nwwp-create-client-btn');
            var clientNameInput = document.getElementById('nwwp_client_name');
            var clientEmailInput = document.getElementById('nwwp_client_email');
            var clientPlanSelect = document.getElementById('nwwp_client_plan');
            var clientMsg = document.getElementById('nwwp-create-client-msg');

            if (createClientBtn && clientNameInput && clientEmailInput && clientPlanSelect) {
                createClientBtn.addEventListener('click', function() {
                    var name = clientNameInput.value.trim();
                    var email = clientEmailInput.value.trim();
                    var plan = clientPlanSelect.value;

                    if (!name || !email) {
                        clientMsg.innerHTML = '<span style="color:#c62828;">El nombre y email son obligatorios.</span>';
                        return;
                    }

                    createClientBtn.disabled = true;
                    createClientBtn.textContent = 'Creando...';
                    clientMsg.innerHTML = '';

                    var formData = new FormData();
                    formData.append('action', 'nwwp_crear_cliente');
                    formData.append('nonce', nwwpAdmin.nonce);
                    formData.append('name', name);
                    formData.append('email', email);
                    formData.append('plan', plan);

                    fetch(nwwpAdmin.ajaxUrl, {
                            method: 'POST',
                            body: formData
                        })
                        .then(function(response) {
                            return response.json();
                        })
                        .then(function(data) {
                            if (data.success) {
                                clientMsg.innerHTML = '<span style="color:#2e7d32;">Cliente creado exitosamente. API Key: ' + (data.data.client && data.data.client.api_key ? data.data.client.api_key : 'N/A') + '</span>';
                                clientNameInput.value = '';
                                clientEmailInput.value = '';
                            } else {
                                clientMsg.innerHTML = '<span style="color:#c62828;">' + data.data.message + '</span>';
                            }
                        })
                        .catch(function() {
                            clientMsg.innerHTML = '<span style="color:#c62828;">Error de conexión.</span>';
                        })
                        .finally(function() {
                            createClientBtn.disabled = false;
                            createClientBtn.textContent = 'Crear Cliente';
                        });
                });
            }
        })();
    </script>
<?php endif; ?>