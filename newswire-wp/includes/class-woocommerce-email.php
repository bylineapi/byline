<?php
/**
 * NWWP_Email_ApiKey
 *
 * Email personalizado de WooCommerce que se envía al cliente
 * cuando su pago es procesado y se genera la API Key.
 *
 * @package NewsWire_WP
 */

if (!defined('ABSPATH')) {
    exit;
}

if (!class_exists('WC_Email')) {
    return;
}

class NWWP_Email_ApiKey extends WC_Email {

    public function __construct() {
        $this->id = 'nwwp_api_key_email';
        $this->title = 'API Key de NewsWire WP';
        $this->description = 'Se envía al cliente cuando su pago es procesado y se genera su API Key.';

        $this->template_html = 'emails/nwwp-api-key.php';
        $this->template_plain = 'emails/plain/nwwp-api-key.php';
        $this->template_base = nwwp_PLUGIN_DIR . 'admin/templates/';

        add_action('nwwp_enviar_email_apikey_notification', array($this, 'trigger'), 10, 3);

        parent::__construct();
    }

    public function trigger($order_id, $api_key, $plan) {
        $order = wc_get_order($order_id);
        if (!$order) {
            return;
        }

        $this->object = $order;
        $this->recipient = $order->get_billing_email();

        $this->find['order-number'] = '{order_number}';
        $this->find['order-date'] = '{order_date}';
        $this->find['plan'] = '{plan}';
        $this->find['api_key'] = '{api_key}';
        $this->find['api_url'] = '{api_url}';

        $this->replace['order-number'] = $order->get_order_number();
        $this->replace['order-date'] = wc_format_datetime($order->get_date_created());
        $this->replace['plan'] = ucfirst($plan);
        $this->replace['api_key'] = $api_key;
        $this->replace['api_url'] = NWWP_API_URL;

        if (!$this->is_enabled() || empty($this->recipient)) {
            return;
        }

        $this->send($this->recipient, $this->get_subject(), $this->get_content(), $this->get_headers(), $this->get_attachments());
    }

    public function get_subject() {
        return apply_filters(
            'nwwp_email_subject_api_key',
            sprintf('Tu acceso a NewsWire WP está listo — Plan %s', $this->get_prop('plan', 'Basic')),
            $this->object
        );
    }

    public function get_content_html() {
        ob_start();
        wc_get_template(
            $this->template_html,
            array(
                'order' => $this->object,
                'email_heading' => $this->get_heading(),
                'sent_to_admin' => false,
                'plain_text' => false,
                'email' => $this,
            ),
            '',
            $this->template_base
        );
        return ob_get_clean();
    }

    public function get_content_plain() {
        ob_start();
        wc_get_template(
            $this->template_plain,
            array(
                'order' => $this->object,
                'email_heading' => $this->get_heading(),
                'sent_to_admin' => false,
                'plain_text' => true,
                'email' => $this,
            ),
            '',
            $this->template_base
        );
        return ob_get_clean();
    }

    public function init_form_fields() {
        $this->form_fields = array(
            'enabled' => array(
                'title' => 'Habilitado',
                'type' => 'checkbox',
                'label' => 'Habilitar este email',
                'default' => 'yes',
            ),
            'subject' => array(
                'title' => 'Asunto',
                'type' => 'text',
                'description' => sprintf(
                    'Asunto del email. Predeterminado: %s',
                    $this->get_default_subject()
                ),
                'placeholder' => $this->get_default_subject(),
                'default' => '',
            ),
            'heading' => array(
                'title' => 'Encabezado',
                'type' => 'text',
                'description' => sprintf(
                    'Encabezado del email. Predeterminado: %s',
                    $this->get_default_heading()
                ),
                'placeholder' => $this->get_default_heading(),
                'default' => '',
            ),
            'email_type' => array(
                'title' => 'Tipo de email',
                'type' => 'select',
                'description' => 'Elige el formato del email.',
                'default' => 'html',
                'class' => 'email_type',
                'options' => array(
                    'plain' => 'Texto plano',
                    'html' => 'HTML',
                ),
            ),
        );
    }

    private function get_default_subject() {
        return 'Tu acceso a NewsWire WP está listo';
    }

    private function get_default_heading() {
        return '¡Bienvenido a NewsWire WP!';
    }
}