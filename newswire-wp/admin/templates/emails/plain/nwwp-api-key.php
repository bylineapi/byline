<?php
/**
 * Template de email en texto plano para enviar la API Key al cliente.
 *
 * @package NewsWire_WP
 * @var WC_Order $order
 * @var string $email_heading
 * @var bool $sent_to_admin
 * @var bool $plain_text
 * @var WC_Email $email
 */

if (!defined('ABSPATH')) {
    exit;
}

$plan = isset($email->replace['plan']) ? $email->replace['plan'] : 'Basic';
$api_key = isset($email->replace['api_key']) ? $email->replace['api_key'] : '';
$api_url = isset($email->replace['api_url']) ? $email->replace['api_url'] : '';

$order_number = $order->get_order_number();
$billing_first_name = $order->get_billing_first_name();
$billing_last_name = $order->get_billing_last_name();
$nombre = trim($billing_first_name . ' ' . $billing_last_name);
$nombre = !empty($nombre) ? $nombre : 'Cliente';

echo "= " . wp_strip_all_tags($email_heading) . " =\n\n";
echo "Hola " . $nombre . ",\n\n";
echo "Tu suscripción al plan " . $plan . " de NewsWire WP ha sido activada correctamente.\n\n";
echo "------------------------------------\n";
echo "TU API KEY ES:\n";
echo "------------------------------------\n";
echo $api_key . "\n\n";
echo "------------------------------------\n";
echo "IMPORTANTE: Guarda esta key en un lugar seguro.\n\n";
echo "Cómo activar tu plugin:\n";
echo "1. Instala NewsWire WP en tu WordPress\n";
echo "2. Ve a NewsWire WP → Ajustes\n";
echo "3. Pega tu API Key en el campo correspondiente\n";
echo "4. Haz clic en 'Verificar conexión'\n\n";

if (!empty($api_url)) {
    echo "URL de la API: " . $api_url . "\n\n";
}

echo "Si tienes dudas escríbenos a soporte@byline.io\n\n";
echo "— El equipo de Byline\n\n";
echo "====================================\n\n";