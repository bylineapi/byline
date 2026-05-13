<?php
/**
 * NWWP_WooCommerce
 *
 * Integración de WooCommerce con Byline API para gestión automática de clientes.
 * Solo se carga en el Modo Dueño (cuando owner_secret está configurado y validado).
 *
 * @package NewsWire_WP
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * Obtiene el plan de Byline asociado a un producto de WooCommerce.
 *
 * @param int $product_id ID del producto de WooCommerce.
 * @return string|false Plan asociado (basic/pro/business) o false si no se encuentra.
 */
function nwwp_get_plan_by_product($product_id) {
    $product_map = get_option('nwwp_product_map', array());

    foreach ($product_map as $plan => $mapped_product_id) {
        if (absint($mapped_product_id) === absint($product_id)) {
            return sanitize_text_field($plan);
        }
    }

    error_log('[NWWP] Warning: Producto WooCommerce ID ' . $product_id . ' no mapeado a ningún plan');

    return false;
}

/**
 * Registra una operación en el log de actividad de NWWP.
 *
 * @param string $action  Acción realizada (ej: 'woo_payment', 'woo_cancel').
 * @param string $result  Resultado ('success' o 'error').
 * @param string $message Detalle adicional.
 */
function nwwp_log_woo_activity($action, $result, $message = '') {
    global $wpdb;
    $table_log = $wpdb->prefix . 'nwwp_activity_log';

    $wpdb->insert(
        $table_log,
        array(
            'action' => sanitize_text_field($action),
            'result' => sanitize_text_field($result),
            'message' => sanitize_text_field($message),
        ),
        array('%s', '%s', '%s')
    );
}

/**
 * Envía email con la API Key al cliente.
 *
 * @param int    $order_id ID del pedido de WooCommerce.
 * @param string $api_key  API Key generada.
 * @param string $plan     Plan del cliente.
 */
function nwwp_enviar_email_apikey($order_id, $api_key, $plan) {
    $order = wc_get_order($order_id);
    if (!$order) {
        return;
    }

    $email = $order->get_billing_email();
    $nombre = $order->get_billing_first_name();
    $api_url = NWWP_API_URL;

    if (empty($email)) {
        return;
    }

    $subject = sprintf('Tu acceso a NewsWire WP está listo — Plan %s', ucfirst($plan));

    $message = sprintf(
        "Hola %s,\n\nTu suscripción al plan %s de NewsWire WP ha sido activada.\n\nTu API Key es:\n%s\n\nIMPORTANTE: Guarda esta key en un lugar seguro.\n\nCómo activar tu plugin:\n1. Instala NewsWire WP en tu WordPress\n2. Ve a NewsWire WP → Ajustes\n3. Pega tu API Key en el campo correspondiente\n4. Haz clic en 'Verificar conexión'\n\nURL de la API: %s\n\nSi tienes dudas escríbenos a soporte@byline.io\n\n— El equipo de Byline",
        $nombre ? $nombre : 'Cliente',
        ucfirst($plan),
        $api_key,
        $api_url
    );

    $headers = array('Content-Type: text/plain; charset=UTF-8');
    wp_mail($email, $subject, $message, $headers);
}

/**
 * Programa un reintento para crear el cliente si la API falló.
 *
 * @param int $order_id ID del pedido de WooCommerce.
 */
function nwwp_programar_reintento($order_id) {
    $order = wc_get_order($order_id);
    if (!$order) {
        return;
    }

    $intentos = (int) $order->get_meta('_nwwp_intentos');
    $intentos++;

    if ($intentos >= 3) {
        $order->add_order_note('[NWWP] ERROR: Se alcanzaron los 3 reintentos máximos. No se pudo crear el cliente en Byline API. Contacta al administrador.');
        nwwp_log_woo_activity('woo_payment', 'error', 'Pedido ' . $order_id . ': máx reintentos alcanzados');

        $admin_email = get_option('admin_email');
        if (!empty($admin_email)) {
            $subject = '⚠️ Fallo crítico: Nuevo cliente NewsWire WP - Pedido #' . $order_id;
            $message = "Se produjo un error al crear un cliente en Byline API después de 3 intentos:\n\n";
            $message .= "Pedido WooCommerce: #" . $order_id . "\n";
            $message .= "Email del cliente: " . $order->get_billing_email() . "\n";
            $message .= "Nombre: " . $order->get_billing_first_name() . ' ' . $order->get_billing_last_name() . "\n";
            $message .= "Plan: " . $order->get_meta('_nwwp_plan') . "\n\n";
            $message .= "Por favor, revisa los logs de actividad y verifica la conexión con Byline API.";

            wp_mail($admin_email, $subject, $message, array('Content-Type: text/plain; charset=UTF-8'));
        }

        return;
    }

    $order->update_meta_data('_nwwp_intentos', $intentos);
    $order->save();

    $order->add_order_note('[NWWP] Programando reintento ' . $intentos . '/3 para crear cliente en Byline API...');
    nwwp_log_woo_activity('woo_payment', 'retry', 'Pedido ' . $order_id . ': reintento ' . $intentos . '/3');

    wp_schedule_single_event(
        time() + 300,
        'nwwp_reintentar_crear_cliente',
        array($order_id)
    );
}

/**
 * Envía email de notificación al dueño cuando se crea un cliente exitosamente.
 *
 * @param int    $order_id ID del pedido de WooCommerce.
 * @param string $nombre   Nombre del cliente.
 * @param string $email    Email del cliente.
 * @param string $plan     Plan del cliente.
 */
function nwwp_enviar_email_dueño($order_id, $nombre, $email, $plan) {
    $admin_email = get_option('admin_email');

    if (empty($admin_email)) {
        return;
    }

    $subject = 'Nuevo cliente NewsWire WP — Plan ' . ucfirst($plan);

    $message = "Se ha registrado un nuevo cliente:\n\n";
    $message .= "Nombre: " . sanitize_text_field($nombre) . "\n";
    $message .= "Email: " . sanitize_email($email) . "\n";
    $message .= "Plan: " . ucfirst($plan) . "\n";
    $message .= "Pedido WooCommerce: #" . $order_id . "\n\n";
    $message .= "El cliente ya recibió su API Key por email.";

    $headers = array('Content-Type: text/plain; charset=UTF-8');
    wp_mail($admin_email, $subject, $message, $headers);
}

/**
 * Hook: woocommerce_payment_complete
 * Se ejecuta cuando un pago se completa exitosamente.
 *
 * @param int $order_id ID del pedido.
 */
function nwwp_pago_completado($order_id) {
    $order = wc_get_order($order_id);
    if (!$order) {
        return;
    }

    $ya_procesado = $order->get_meta('_nwwp_procesado');
    if (!empty($ya_procesado)) {
        return;
    }

    $nombre = trim($order->get_billing_first_name() . ' ' . $order->get_billing_last_name());
    $email = $order->get_billing_email();

    if (empty($email)) {
        nwwp_log_woo_activity('woo_payment', 'error', 'Pedido ' . $order_id . ' sin email');
        return;
    }

    $plan_detectado = false;
    foreach ($order->get_items() as $item) {
        $product_id = $item->get_product_id();
        $plan = nwwp_get_plan_by_product($product_id);
        if ($plan) {
            $plan_detectado = $plan;
            break;
        }
    }

    if (!$plan_detectado) {
        $order->add_order_note('[NWWP] Error: No se detectó plan de Byline en los productos del pedido.');
        nwwp_log_woo_activity('woo_payment', 'error', 'Pedido ' . $order_id . ': no se detectó plan');
        return;
    }

    $api_url = NWWP_API_URL;
    $owner_secret = get_option('nwwp_owner_secret', '');

    if (empty($api_url) || empty($owner_secret)) {
        $order->add_order_note('[NWWP] Error: Owner Secret o URL de API no configurados.');
        nwwp_log_woo_activity('woo_payment', 'error', 'Pedido ' . $order_id . ': Owner Secret no configurado');
        return;
    }

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
                'name' => sanitize_text_field($nombre),
                'email' => sanitize_email($email),
                'plan' => $plan_detectado,
            )),
            'sslverify' => true,
        )
    );

    if (is_wp_error($response)) {
        $order->add_order_note('[NWWP] Error al conectar con Byline API: ' . $response->get_error_message());
        nwwp_log_woo_activity('woo_payment', 'error', 'Pedido ' . $order_id . ': error de conexión - ' . $response->get_error_message());
        nwwp_programar_reintento($order_id);
        return;
    }

    $status_code = wp_remote_retrieve_response_code($response);

    if (200 !== $status_code) {
        $body = wp_remote_retrieve_body($response);
        $error_msg = 'Código HTTP: ' . $status_code;
        if (!empty($body)) {
            $data = json_decode($body, true);
            if (isset($data['detail'])) {
                $error_msg .= ' - ' . sanitize_text_field($data['detail']);
            }
        }
        $order->add_order_note('[NWWP] Error de Byline API: ' . $error_msg);
        nwwp_log_woo_activity('woo_payment', 'error', 'Pedido ' . $order_id . ': ' . $error_msg);
        nwwp_programar_reintento($order_id);
        return;
    }

    $body = wp_remote_retrieve_body($response);
    $data = json_decode($body, true);

    if (!isset($data['api_key']) || !isset($data['id'])) {
        $order->add_order_note('[NWWP] Error: Respuesta de API incompleta.');
        nwwp_log_woo_activity('woo_payment', 'error', 'Pedido ' . $order_id . ': respuesta de API incompleta');
        return;
    }

    $api_key = sanitize_text_field($data['api_key']);
    $client_id = absint($data['id']);

    $order->update_meta_data('_nwwp_api_key', $api_key);
    $order->update_meta_data('_nwwp_client_id', $client_id);
    $order->update_meta_data('_nwwp_plan', $plan_detectado);
    $order->update_meta_data('_nwwp_procesado', true);
    $order->save();

    $order->add_order_note(sprintf(
        '[NWWP] Cliente creado en Byline API. Plan: %s. Client ID: %d',
        $plan_detectado,
        $client_id
    ));

    nwwp_enviar_email_apikey($order_id, $api_key, $plan_detectado);

    nwwp_enviar_email_dueño($order_id, $nombre, $email, $plan_detectado);

    nwwp_log_woo_activity('woo_payment', 'success', 'Pedido ' . $order_id . ' - Cliente: ' . $email . ' - Plan: ' . $plan_detectado);
}

/**
 * Hook: woocommerce_subscription_status_cancelled
 * Hook: woocommerce_subscription_status_expired
 * Se ejecuta cuando una suscripción se cancela o expira.
 *
 * @param WC_Subscription $subscription Suscripción de WooCommerce.
 */
function nwwp_suscripcion_cancelada($subscription) {
    if (!class_exists('WC_Subscriptions')) {
        return;
    }

    $order = $subscription->get_parent();
    if (!$order) {
        return;
    }

    $client_id = $order->get_meta('_nwwp_client_id');
    if (empty($client_id)) {
        return;
    }

    $api_url = NWWP_API_URL;
    $owner_secret = get_option('nwwp_owner_secret', '');

    if (empty($api_url) || empty($owner_secret)) {
        return;
    }

    $endpoint = trailingslashit($api_url) . 'admin/clients/' . absint($client_id);

    $response = wp_remote_request(
        $endpoint,
        array(
            'method' => 'PATCH',
            'timeout' => 30,
            'headers' => array(
                'X-Admin-Secret' => $owner_secret,
                'Content-Type' => 'application/json',
            ),
            'body' => wp_json_encode(array('is_active' => false)),
            'sslverify' => true,
        )
    );

    if (is_wp_error($response)) {
        nwwp_log_woo_activity('woo_cancel', 'error', 'Suscripción cancelada - Client ID: ' . $client_id . ' - Error: ' . $response->get_error_message());
        return;
    }

    $status_code = wp_remote_retrieve_response_code($response);
    if (200 !== $status_code) {
        nwwp_log_woo_activity('woo_cancel', 'error', 'Suscripción cancelada - Client ID: ' . $client_id . ' - Código: ' . $status_code);
        return;
    }

    $order->add_order_note('[NWWP] Cliente desactivado en Byline API por cancelación de suscripción.');
    nwwp_log_woo_activity('woo_cancel', 'success', 'Suscripción cancelada - Client ID: ' . $client_id);
}

/**
 * Hook: woocommerce_subscription_renewal_payment_complete
 * Se ejecuta cuando una suscripción se renueva exitosamente.
 *
 * @param WC_Subscription $subscription Suscripción de WooCommerce.
 */
function nwwp_suscripcion_renovada($subscription) {
    if (!class_exists('WC_Subscriptions')) {
        return;
    }

    $order = $subscription->get_parent();
    if (!$order) {
        return;
    }

    $client_id = $order->get_meta('_nwwp_client_id');
    if (empty($client_id)) {
        return;
    }

    $api_url = NWWP_API_URL;
    $owner_secret = get_option('nwwp_owner_secret', '');

    if (empty($api_url) || empty($owner_secret)) {
        return;
    }

    $endpoint = trailingslashit($api_url) . 'admin/clients/' . absint($client_id);

    $response = wp_remote_request(
        $endpoint,
        array(
            'method' => 'PATCH',
            'timeout' => 30,
            'headers' => array(
                'X-Admin-Secret' => $owner_secret,
                'Content-Type' => 'application/json',
            ),
            'body' => wp_json_encode(array('is_active' => true)),
            'sslverify' => true,
        )
    );

    if (is_wp_error($response)) {
        nwwp_log_woo_activity('woo_renewal', 'error', 'Suscripción renovada - Client ID: ' . $client_id . ' - Error: ' . $response->get_error_message());
        return;
    }

    $status_code = wp_remote_retrieve_response_code($response);
    if (200 !== $status_code) {
        nwwp_log_woo_activity('woo_renewal', 'error', 'Suscripción renovada - Client ID: ' . $client_id . ' - Código: ' . $status_code);
        return;
    }

    nwwp_log_woo_activity('woo_renewal', 'success', 'Suscripción renovada - Client ID: ' . $client_id);
}

/**
 * Hook: woocommerce_subscription_item_switched
 * Se ejecuta cuando se cambia de plan en una suscripción.
 *
 * @param WC_Subscription $subscription     Nueva suscripción.
 * @param WC_Order_Item   $new_item        Nuevo item de suscripción.
 * @param WC_Order_Item   $old_item        Item anterior.
 * @param WC_Subscription $old_subscription Suscripción anterior.
 */
function nwwp_plan_cambiado($subscription, $new_item, $old_item, $old_subscription) {
    if (!class_exists('WC_Subscriptions')) {
        return;
    }

    $new_product_id = $new_item->get_product_id();
    $nuevo_plan = nwwp_get_plan_by_product($new_product_id);

    if (!$nuevo_plan) {
        nwwp_log_woo_activity('woo_plan_change', 'error', 'Cambio de plan - No se detectó nuevo plan');
        return;
    }

    $order = $subscription->get_parent();
    if (!$order) {
        return;
    }

    $client_id = $order->get_meta('_nwwp_client_id');
    if (empty($client_id)) {
        return;
    }

    $api_url = NWWP_API_URL;
    $owner_secret = get_option('nwwp_owner_secret', '');

    if (empty($api_url) || empty($owner_secret)) {
        return;
    }

    $endpoint = trailingslashit($api_url) . 'admin/clients/' . absint($client_id);

    $response = wp_remote_request(
        $endpoint,
        array(
            'method' => 'PATCH',
            'timeout' => 30,
            'headers' => array(
                'X-Admin-Secret' => $owner_secret,
                'Content-Type' => 'application/json',
            ),
            'body' => wp_json_encode(array('plan' => $nuevo_plan)),
            'sslverify' => true,
        )
    );

    if (is_wp_error($response)) {
        nwwp_log_woo_activity('woo_plan_change', 'error', 'Cambio de plan - Client ID: ' . $client_id . ' - Error: ' . $response->get_error_message());
        return;
    }

    $status_code = wp_remote_retrieve_response_code($response);
    if (200 !== $status_code) {
        nwwp_log_woo_activity('woo_plan_change', 'error', 'Cambio de plan - Client ID: ' . $client_id . ' - Código: ' . $status_code);
        return;
    }

    $order->update_meta_data('_nwwp_plan', $nuevo_plan);
    $order->save();

    $order->add_order_note('[NWWP] Plan cambiado a: ' . ucfirst($nuevo_plan) . ' (cambio de plan en suscripción)');
    nwwp_log_woo_activity('woo_plan_change', 'success', 'Cambio de plan - Client ID: ' . $client_id . ' - Nuevo plan: ' . $nuevo_plan);
}

/**
 * Registra la clase de email personalizada en WooCommerce.
 *
 * @param array $emails Emails registrados en WooCommerce.
 * @return array Emails actualizados.
 */
function nwwp_registrar_email_apikey($emails) {
    require_once nwwp_PLUGIN_DIR . 'includes/class-woocommerce-email.php';
    $emails['NWWP_Email_ApiKey'] = new NWWP_Email_ApiKey();
    return $emails;
}

/**
 * Clase principal de integración de WooCommerce.
 */
class NWWP_WooCommerce {

    public function __construct() {
        $this->registrar_hooks();
    }

    /**
     * Registra todos los hooks necesarios para la integración.
     */
    private function registrar_hooks() {
        add_action('woocommerce_payment_complete', 'nwwp_pago_completado', 10);

        if (class_exists('WC_Subscriptions')) {
            add_action('woocommerce_subscription_status_cancelled', 'nwwp_suscripcion_cancelada', 10);
            add_action('woocommerce_subscription_status_expired', 'nwwp_suscripcion_cancelada', 10);
            add_action('woocommerce_subscription_renewal_payment_complete', 'nwwp_suscripcion_renovada', 10);
            add_action('woocommerce_subscription_item_switched', 'nwwp_plan_cambiado', 10, 4);
        }

        add_filter('woocommerce_email_classes', 'nwwp_registrar_email_apikey');

        add_action('nwwp_reintentar_crear_cliente', 'nwwp_pago_completado');
    }
}

new NWWP_WooCommerce();