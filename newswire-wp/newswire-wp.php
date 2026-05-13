<?php
/**
 * Plugin Name: NewsWire WP
 * Description: NewsWire WP — Conecta con la API Byline para distribuir noticias como artículos en WordPress.
 * Version: 1.0.0
 * Author: NewsWire WP Team
 * Text Domain: newswire-wp
 *
 * @package NewsWire_WP
 */

// Evitar acceso directo
if (!defined('ABSPATH')) {
    exit;
}

// ─── Constantes ─────────────────────────────────────────────────────────────

define('nwwp_VERSION', '1.0.0');
define('nwwp_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('nwwp_PLUGIN_URL', plugin_dir_url(__FILE__));

// ─── Includes ───────────────────────────────────────────────────────────────

require_once nwwp_PLUGIN_DIR . 'includes/class-api-client.php';
require_once nwwp_PLUGIN_DIR . 'includes/class-author-manager.php';
require_once nwwp_PLUGIN_DIR . 'includes/class-importer.php';
require_once nwwp_PLUGIN_DIR . 'includes/class-cron.php';
require_once nwwp_PLUGIN_DIR . 'includes/class-admin.php';

// ─── Hook de activación ─────────────────────────────────────────────────────

register_activation_hook(__FILE__, 'nwwp_activar_plugin');
register_deactivation_hook(__FILE__, 'nwwp_desactivar_plugin');

function nwwp_activar_plugin() {
    global $wpdb;

    $charset_collate = $wpdb->get_charset_collate();

    // Tabla de artículos importados
    $table_imported = $wpdb->prefix . 'nwwp_imported_articles';
    $sql_imported = "CREATE TABLE IF NOT EXISTS {$table_imported} (
        id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        article_api_id VARCHAR(255) NOT NULL,
        wp_post_id BIGINT UNSIGNED NOT NULL,
        source_url VARCHAR(500) DEFAULT '',
        imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_article_api_id (article_api_id),
        KEY idx_wp_post_id (wp_post_id)
    ) {$charset_collate};";

    // Tabla de log de actividad
    $table_log = $wpdb->prefix . 'nwwp_activity_log';
    $sql_log = "CREATE TABLE IF NOT EXISTS {$table_log} (
        id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        action VARCHAR(100) NOT NULL,
        result VARCHAR(20) NOT NULL DEFAULT '',
        message TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        KEY idx_timestamp (timestamp)
    ) {$charset_collate};";

    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    dbDelta($sql_imported);
    dbDelta($sql_log);

    // Registrar eventos cron
    $cron = new nwwp_Cron();
    $cron->registrar_eventos_cron();
}

function nwwp_desactivar_plugin() {
    nwwp_Cron::limpiar_eventos_cron();
}

// ─── Estilos del admin ─────────────────────────────────────────────────────

function nwwp_admin_styles() {
    $screen = get_current_screen();
    if (isset($screen->id) && strpos($screen->id, 'newswire-wp') !== false) {
        wp_enqueue_style(
            'nwwp-admin-css',
            nwwp_PLUGIN_URL . 'admin/css/admin.css',
            array(),
            nwwp_VERSION
        );
    }
}
add_action('admin_enqueue_scripts', 'nwwp_admin_styles', 999);

// ─── Footer en el admin ─────────────────────────────────────────────────────

add_filter('admin_footer_text', 'nwwp_admin_footer');

function nwwp_admin_footer($text) {
    $screen = get_current_screen();
    if ($screen && strpos($screen->id, 'nwwp') !== false) {
        return 'NewsWire WP &middot; Powered by Byline';
    }
    return $text;
}

// ─── Inicialización ─────────────────────────────────────────────────────────

add_action('plugins_loaded', 'nwwp_init');

function nwwp_init() {
    new nwwp_Cron();

    if (is_admin()) {
        new nwwp_Admin();
    }
}

// ─── Integración WooCommerce (Modo Dueño) ────────────────────────────────────

add_action('plugins_loaded', 'nwwp_cargar_woocommerce_integration');

function nwwp_cargar_woocommerce_integration() {
    if (!class_exists('WooCommerce')) {
        return;
    }

    if (!function_exists('nwwp_es_modo_dueno') || !nwwp_es_modo_dueno()) {
        return;
    }

    require_once nwwp_PLUGIN_DIR . 'includes/class-woocommerce.php';
}
