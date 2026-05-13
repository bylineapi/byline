<?php
/**
 * Clase NWWP_API_Client
 *
 * Cliente HTTP para consumir la API Byline de distribución de noticias.
 *
 * @package NewsWire_WP
 */

if (!defined('ABSPATH')) {
    exit;
}

class nwwp_API_Client {

    private $api_url;
    private $api_key;

    public function __construct() {
        $this->api_url = trailingslashit(NWWP_API_URL);
        $this->api_key = get_option('nwwp_api_key', '');
    }

    public function get_news($category = '', $only_breaking = false, $limit = 0) {
        if (empty($this->api_url) || empty($this->api_key)) {
            return new WP_Error(
                'nwwp_api_no_config',
                __('La URL de la API o la API Key no están configuradas.', 'newswire-wp')
            );
        }

        $endpoint = $this->api_url . 'news';
        $args_query = array();

        if (!empty($category)) {
            $args_query['category'] = sanitize_text_field($category);
        }
        if ($only_breaking) {
            $args_query['only_breaking'] = 'true';
        }
        if ($limit > 0) {
            $args_query['limit'] = absint($limit);
        }
        if (!empty($args_query)) {
            $endpoint = add_query_arg($args_query, $endpoint);
        }

        $args = array(
            'timeout'   => 30,
            'headers'   => array(
                'X-API-KEY' => $this->api_key,
            ),
            'sslverify' => true,
        );

        $response = wp_remote_get($endpoint, $args);

        if (is_wp_error($response)) {
            return new WP_Error(
                'nwwp_api_transport_error',
                sprintf(
                    __('Error de conexión con la API: %s', 'newswire-wp'),
                    $response->get_error_message()
                )
            );
        }

        $status_code = wp_remote_retrieve_response_code($response);
        if (200 !== $status_code) {
            $body = wp_remote_retrieve_body($response);
            $mensaje = __('La API respondió con código', 'newswire-wp') . " {$status_code}";
            if (!empty($body)) {
                $data = json_decode($body, true);
                if (isset($data['detail'])) {
                    $mensaje .= ': ' . sanitize_text_field($data['detail']);
                }
            }
            return new WP_Error('nwwp_api_http_error', $mensaje);
        }

        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);

        if (null === $data || !is_array($data)) {
            return new WP_Error(
                'nwwp_api_parse_error',
                __('Error al parsear la respuesta JSON de la API.', 'newswire-wp')
            );
        }

        return $data;
    }
}
