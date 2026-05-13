<?php
/**
 * Template de email para enviar la API Key al cliente.
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

?>
<?php do_action('woocommerce_email_header', $email_heading, $email); ?>

<p style="margin-bottom: 20px;">
    Hola <strong><?php echo esc_html($nombre); ?></strong>,
</p>

<p style="margin-bottom: 20px;">
    Tu suscripción al plan <strong><?php echo esc_html($plan); ?></strong> de NewsWire WP ha sido activada correctamente.
</p>

<div style="background-color: #f5f5f5; padding: 20px; border-radius: 4px; margin: 20px 0; text-align: center;">
    <p style="margin: 0 0 10px 0; font-size: 14px; color: #666;">Tu API Key es:</p>
    <code style="font-size: 16px; font-family: monospace; background-color: #fff; padding: 10px 20px; border-radius: 4px; display: inline-block; border: 1px solid #ddd;">
        <?php echo esc_html($api_key); ?>
    </code>
</div>

<div style="background-color: #fff3cd; border: 1px solid #ffeeba; padding: 15px; border-radius: 4px; margin: 20px 0;">
    <strong>IMPORTANTE:</strong> Guarda esta API Key en un lugar seguro. No podrás verla nuevamente.
</div>

<h3 style="margin-top: 25px; margin-bottom: 15px;">Cómo activar tu plugin:</h3>
<ol style="margin-bottom: 20px;">
    <li>Instala el plugin NewsWire WP en tu WordPress</li>
    <li>Ve a <strong>NewsWire WP → Ajustes</strong></li>
    <li>Pega tu API Key en el campo correspondiente</li>
    <li>Haz clic en "Verificar conexión"</li>
</ol>

<?php if (!empty($api_url)): ?>
<p style="margin-bottom: 20px;">
    <strong>URL de la API:</strong> <?php echo esc_url($api_url); ?>
</p>
<?php endif; ?>

<p style="margin-top: 25px;">
    Si tienes dudas escríbenos a <a href="mailto:soporte@byline.io">soporte@byline.io</a>
</p>

<p style="margin-top: 30px; color: #666; font-size: 14px;">
    — El equipo de Byline
</p>

<?php do_action('woocommerce_email_footer', $email); ?>