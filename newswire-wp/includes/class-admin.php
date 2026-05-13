<?php
/**
 * Clase NWWP_Admin
 *
 * Registra el menú de administración, subpáginas y maneja AJAX.
 *
 * @package NewsWire_WP
 */

if (!defined('ABSPATH')) {
    exit;
}

class nwwp_Admin {

    const PAGE_SLUG = 'newswire-wp';

    public function __construct() {
        add_action('admin_menu', array($this, 'registrar_menu'));
        add_action('admin_init', array($this, 'registrar_configuracion'));
        add_action('wp_ajax_nwwp_verify_connection', array($this, 'ajax_verificar_conexion'));
        add_action('wp_ajax_nwwp_verify_owner_secret', array($this, 'ajax_verificar_owner_secret'));
        add_action('wp_ajax_nwwp_save_settings_ajax', array($this, 'ajax_guardar_settings'));
        add_action('wp_ajax_nwwp_crear_cliente', array($this, 'ajax_crear_cliente'));
        add_action('admin_enqueue_scripts', array($this, 'cargar_assets'));
        add_filter('plugin_action_links_' . plugin_basename(nwwp_PLUGIN_DIR . 'newswire-wp.php'), array($this, 'agregar_enlace_ajustes'));
    }

    public function registrar_menu() {
        add_menu_page(
            __('NewsWire WP', 'newswire-wp'),
            __('NewsWire WP', 'newswire-wp'),
            'manage_options',
            self::PAGE_SLUG,
            array($this, 'pagina_principal'),
            'dashicons-rss',
            30
        );

        add_submenu_page(
            self::PAGE_SLUG,
            __('Ajustes', 'newswire-wp'),
            __('Ajustes', 'newswire-wp'),
            'manage_options',
            self::PAGE_SLUG,
            '__return_false'
        );
    }

    public function pagina_principal() {
        include nwwp_PLUGIN_DIR . 'admin/settings-page.php';
    }

    public function registrar_configuracion() {
        register_setting('nwwp_settings_group', 'nwwp_api_key', array(
            'sanitize_callback' => 'sanitize_text_field',
        ));

        register_setting('nwwp_settings_group', 'nwwp_content_mode', array(
            'sanitize_callback' => array($this, 'sanitize_content_mode'),
        ));

        register_setting('nwwp_settings_group', 'nwwp_posts_per_hour', array(
            'sanitize_callback' => array($this, 'sanitize_posts_per_hour'),
        ));

        register_setting('nwwp_settings_group', 'nwwp_activar_breaking', array(
            'sanitize_callback' => 'rest_sanitize_boolean',
        ));

        register_setting('nwwp_settings_group', 'nwwp_default_image_id', array(
            'sanitize_callback' => 'absint',
        ));

        register_setting('nwwp_settings_group', 'nwwp_category_map', array(
            'sanitize_callback' => array($this, 'sanitize_category_map'),
        ));

        register_setting('nwwp_settings_group', 'nwwp_extra_keywords', array(
            'sanitize_callback' => 'sanitize_textarea_field',
        ));

        register_setting('nwwp_settings_group', 'nwwp_detected_plan', array(
            'sanitize_callback' => 'sanitize_text_field',
        ));

        register_setting('nwwp_settings_group', 'nwwp_owner_secret', array(
            'sanitize_callback' => 'sanitize_text_field',
        ));

        register_setting('nwwp_settings_group', 'nwwp_product_map', array(
            'sanitize_callback' => array($this, 'sanitize_product_map'),
        ));
    }

    public function sanitize_product_map($value) {
        if (is_string($value)) {
            $decoded = json_decode($value, true);
            if (is_array($decoded)) {
                $value = $decoded;
            } else {
                return array();
            }
        }

        if (!is_array($value)) {
            return array();
        }

        $clean = array();
        $allowed_plans = array('basic', 'pro', 'business');

        foreach ($value as $plan => $product_id) {
            $plan = sanitize_text_field($plan);
            $product_id = absint($product_id);

            if (in_array($plan, $allowed_plans, true) && $product_id > 0) {
                $clean[$plan] = $product_id;
            }
        }

        return $clean;
    }

    public function ajax_verificar_owner_secret() {
        check_ajax_referer('nwwp_verify_owner_nonce', 'nonce');

        if (!current_user_can('manage_options')) {
            wp_send_json_error(array('message' => 'Sin permisos.'));
        }

        $api_url = NWWP_API_URL;
        $owner_secret = isset($_POST['owner_secret']) ? sanitize_text_field($_POST['owner_secret']) : '';

        if (empty($owner_secret)) {
            wp_send_json_error(array('message' => 'Owner Secret es obligatorio.'));
        }

        $health_url = trailingslashit($api_url) . 'health';

        $response = wp_remote_get($health_url, array(
            'timeout' => 15,
            'headers' => array(
                'X-Admin-Secret' => $owner_secret,
            ),
            'sslverify' => true,
        ));

        if (is_wp_error($response)) {
            wp_send_json_error(array(
                'message' => 'No se pudo conectar: ' . $response->get_error_message(),
            ));
        }

        $status_code = wp_remote_retrieve_response_code($response);

        if (200 !== $status_code) {
            wp_send_json_error(array(
                'message' => 'Owner Secret inválido. Código HTTP: ' . $status_code,
            ));
        }

        update_option('nwwp_owner_secret', $owner_secret);

        wp_send_json_success(array(
            'message' => 'Modo Dueño activado correctamente.',
        ));
    }

    public function sanitize_content_mode($value) {
        $allowed = array('full', 'excerpt', 'summary');
        return in_array($value, $allowed, true) ? $value : 'excerpt';
    }

    public function sanitize_posts_per_hour($value) {
        $value = absint($value);
        $plan  = get_option('nwwp_detected_plan', 'basic');

        if ('basic' === $plan) {
            return min($value, 2);
        }

        return max(1, min($value, 999));
    }

    public function sanitize_category_map($value) {
        // Si viene como string (JSON), decodificarlo
        if (is_string($value)) {
            $decoded = json_decode($value, true);
            if (is_array($decoded)) {
                $value = $decoded;
            } else {
                return array();
            }
        }

        if (!is_array($value)) {
            return array();
        }

        $clean = array();
        foreach ($value as $api_cat => $wp_cat_id) {
            $api_cat   = sanitize_text_field($api_cat);
            $wp_cat_id = absint($wp_cat_id);
            if (!empty($api_cat) && $wp_cat_id > 0) {
                $clean[$api_cat] = $wp_cat_id;
            }
        }

        return $clean;
    }

    public function ajax_verificar_conexion() {
        check_ajax_referer('nwwp_verify_connection_nonce', 'nonce');

        if (!current_user_can('manage_options')) {
            wp_send_json_error(array('message' => __('Sin permisos.', 'newswire-wp')));
        }

        $api_url = NWWP_API_URL;
        $api_key = isset($_POST['api_key']) ? sanitize_text_field($_POST['api_key']) : '';
        $owner_secret = get_option('nwwp_owner_secret', '');

        if (empty($api_key)) {
            wp_send_json_error(array('message' => __('API Key es obligatoria.', 'newswire-wp')));
        }

        // Si hay Owner Secret, usar /admin/clients/verify para buscar el cliente por API Key
        $detected_plan = 'basic';
        $sources_count = 0;

        if (!empty($owner_secret)) {
            $verify_url = add_query_arg('api_key', $api_key, trailingslashit($api_url) . 'admin/clients/verify');
            
            $response = wp_remote_get($verify_url, array(
                'timeout' => 15,
                'headers' => array(
                    'X-Admin-Secret' => $owner_secret,
                ),
                'sslverify' => true,
            ));

            if (!is_wp_error($response)) {
                $status_code = wp_remote_retrieve_response_code($response);
                if (200 === $status_code) {
                    $body = wp_remote_retrieve_body($response);
                    $data = json_decode($body, true);
                    
                    if (isset($data['plan'])) {
                        $detected_plan = sanitize_text_field($data['plan']);
                    }
                }
            }
        } else {
            // Sin Owner Secret, usar /health solo para verificar conectividad
            $health_url = trailingslashit($api_url) . 'health';

            $response = wp_remote_get($health_url, array(
                'timeout' => 15,
                'headers' => array(
                    'X-API-KEY' => $api_key,
                ),
                'sslverify' => true,
            ));

            if (is_wp_error($response)) {
                wp_send_json_error(array(
                    'message' => __('No se pudo conectar: ', 'newswire-wp') . $response->get_error_message(),
                ));
            }

            $status_code = wp_remote_retrieve_response_code($response);
            if (200 !== $status_code) {
                $body = wp_remote_retrieve_body($response);
                $result_data = json_decode($body, true);
                $msg = isset($result_data['detail']) ? sanitize_text_field($result_data['detail']) : "Código HTTP: {$status_code}";
                wp_send_json_error(array(
                    'message' => __('API Key inválida: ', 'newswire-wp') . $msg,
                ));
            }
        }

        // Validar que el plan sea válido
        if (!in_array($detected_plan, array('basic', 'pro', 'business'), true)) {
            $detected_plan = 'basic';
        }

        update_option('nwwp_detected_plan', $detected_plan, true);

        // Obtener fuentes disponibles
        $sources_count = 0;
        $sources_url = trailingslashit($api_url) . 'admin/sources';
        if (!empty($owner_secret)) {
            $sources_response = wp_remote_get($sources_url, array(
                'timeout' => 15,
                'headers' => array(
                    'X-Admin-Secret' => $owner_secret,
                ),
                'sslverify' => true,
            ));
            if (!is_wp_error($sources_response)) {
                $sources_status = wp_remote_retrieve_response_code($sources_response);
                if (200 === $sources_status) {
                    $sources_body = wp_remote_retrieve_body($sources_response);
                    $sources_data = json_decode($sources_body, true);
                    if (is_array($sources_data)) {
                        $sources_count = count($sources_data);
                    }
                }
            }
        }

        $plan_labels = array(
            'basic'    => __('Básico', 'newswire-wp'),
            'pro'     => __('Pro', 'newswire-wp'),
            'business' => __('Business', 'newswire-wp'),
        );
        $plan_label = isset($plan_labels[$detected_plan]) ? $plan_labels[$detected_plan] : $detected_plan;

        wp_send_json_success(array(
            'success'  => true,
            'plan'     => $detected_plan,
            'sources'  => $sources_count,
            'message'  => sprintf(__('Conexión exitosa. Plan detectado: %s.', 'newswire-wp'), $plan_label),
        ));
    }

    public function ajax_guardar_settings() {
        check_ajax_referer('nwwp_verify_connection_nonce', 'nwwp_settings_nonce');

        if (!current_user_can('manage_options')) {
            wp_send_json_error(array('message' => 'Sin permisos'));
        }

        // Guardar cada opción
        if (isset($_POST['nwwp_api_key'])) {
            update_option('nwwp_api_key', sanitize_text_field($_POST['nwwp_api_key']));
        }
        if (isset($_POST['nwwp_content_mode'])) {
            $mode = sanitize_text_field($_POST['nwwp_content_mode']);
            if (in_array($mode, array('full', 'excerpt', 'summary'), true)) {
                update_option('nwwp_content_mode', $mode);
            }
        }
        if (isset($_POST['nwwp_posts_per_hour'])) {
            update_option('nwwp_posts_per_hour', absint($_POST['nwwp_posts_per_hour']));
        }
        if (isset($_POST['nwwp_activar_breaking'])) {
            update_option('nwwp_activar_breaking', (bool) $_POST['nwwp_activar_breaking']);
        }
        if (isset($_POST['nwwp_default_image_id'])) {
            update_option('nwwp_default_image_id', absint($_POST['nwwp_default_image_id']));
        }
        if (isset($_POST['nwwp_category_map'])) {
            $map = json_decode(stripslashes($_POST['nwwp_category_map']), true);
            if (is_array($map)) {
                $clean = array();
                foreach ($map as $api_cat => $wp_cat_id) {
                    $api_cat = sanitize_text_field($api_cat);
                    $wp_cat_id = absint($wp_cat_id);
                    if (!empty($api_cat) && $wp_cat_id > 0) {
                        $clean[$api_cat] = $wp_cat_id;
                    }
                }
                update_option('nwwp_category_map', $clean);
            }
        }
        if (isset($_POST['nwwp_extra_keywords'])) {
            update_option('nwwp_extra_keywords', sanitize_textarea_field($_POST['nwwp_extra_keywords']));
        }
        if (isset($_POST['nwwp_owner_secret'])) {
            update_option('nwwp_owner_secret', sanitize_text_field($_POST['nwwp_owner_secret']));
        }
        if (isset($_POST['nwwp_product_map']) && is_array($_POST['nwwp_product_map'])) {
            $clean_map = array();
            foreach ($_POST['nwwp_product_map'] as $plan => $product_id) {
                $plan = sanitize_text_field($plan);
                $product_id = absint($product_id);
                if (in_array($plan, array('basic', 'pro', 'business'), true) && $product_id > 0) {
                    $clean_map[$plan] = $product_id;
                }
            }
            update_option('nwwp_product_map', $clean_map);
        }

        wp_send_json_success(array('message' => 'Configuración guardada correctamente'));
    }

    public function cargar_assets($hook) {
        if (false === strpos($hook, 'newswire-wp') && false === strpos($hook, 'nwwp')) {
            return;
        }

        wp_enqueue_media();

        wp_enqueue_style(
            'nwwp-admin-css',
            nwwp_PLUGIN_URL . 'admin/css/admin.css',
            array(),
            nwwp_VERSION
        );

        wp_enqueue_script(
            'nwwp-admin-js',
            nwwp_PLUGIN_URL . 'admin/admin.js',
            array('jquery'),
            nwwp_VERSION,
            true
        );

        $detected_plan = get_option('nwwp_detected_plan', 'basic');
        
        wp_localize_script('nwwp-admin-js', 'nwwpAdmin', array(
            'ajaxUrl' => admin_url('admin-ajax.php'),
            'nonce'   => wp_create_nonce('nwwp_verify_connection_nonce'),
            'detectedPlan' => $detected_plan,
        ));
    }

    public function agregar_enlace_ajustes($links) {
        $ajustes_link = '<a href="' . admin_url('admin.php?page=' . self::PAGE_SLUG) . '">'
                      . __('Ajustes', 'newswire-wp') . '</a>';
        array_unshift($links, $ajustes_link);
        return $links;
    }
}

function nwwp_es_modo_dueno() {
    $owner_secret = get_option('nwwp_owner_secret', '');

    if (empty($owner_secret)) {
        return false;
    }

$health_url = trailingslashit(NWWP_API_URL) . 'health';

        $response = wp_remote_get($health_url, array(
            'timeout' => 10,
            'headers' => array(
                'X-Admin-Secret' => $owner_secret,
            ),
            'sslverify' => true,
        ));

        if (is_wp_error($response)) {
            return false;
        }

        $status_code = wp_remote_retrieve_response_code($response);

        return 200 === $status_code;
    }

    public function ajax_crear_cliente() {
        check_ajax_referer('nwwp_verify_connection_nonce', 'nonce');

        if (!current_user_can('manage_options')) {
            wp_send_json_error(array('message' => __('Sin permisos.', 'newswire-wp')));
        }

        $owner_secret = get_option('nwwp_owner_secret', '');
        
        if (empty($owner_secret)) {
            wp_send_json_error(array('message' => __('Owner Secret no configurado.', 'newswire-wp')));
        }

        $name = isset($_POST['name']) ? sanitize_text_field($_POST['name']) : '';
        $email = isset($_POST['email']) ? sanitize_email($_POST['email']) : '';
        $plan = isset($_POST['plan']) ? sanitize_text_field($_POST['plan']) : 'basic';

        if (empty($name) || empty($email)) {
            wp_send_json_error(array('message' => __('Nombre y email son obligatorios.', 'newswire-wp')));
        }

        if (!in_array($plan, array('basic', 'pro', 'business'), true)) {
            $plan = 'basic';
        }

        $api_url = NWWP_API_URL;
        $endpoint = trailingslashit($api_url) . 'admin/clients';

        $response = wp_remote_post(
            $endpoint,
            array(
                'timeout' => 30,
                'headers' => array(
                    'X-Admin-Secret' => $owner_secret,
                    'Content-Type' => 'application/json',
                ),
                'body' => wp_json_encode(array(
                    'name' => $name,
                    'email' => $email,
                    'plan' => $plan,
                )),
                'sslverify' => true,
            )
        );

        if (is_wp_error($response)) {
            wp_send_json_error(array('message' => __('Error de conexión: ', 'newswire-wp') . $response->get_error_message()));
        }

        $status_code = wp_remote_retrieve_response_code($response);

        if (200 !== $status_code && 201 !== $status_code) {
            $body = wp_remote_retrieve_body($response);
            $data = json_decode($body, true);
            $msg = isset($data['detail']) ? sanitize_text_field($data['detail']) : "Código HTTP: {$status_code}";
            wp_send_json_error(array('message' => __('Error al crear cliente: ', 'newswire-wp') . $msg));
        }

        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);

        wp_send_json_success(array(
            'message' => __('Cliente creado exitosamente.', 'newswire-wp'),
            'client' => $data,
        ));
    }
}

    $status_code = wp_remote_retrieve_response_code($response);

    return 200 === $status_code;
}