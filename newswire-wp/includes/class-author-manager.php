<?php
/**
 * Clase NWWP_Author_Manager
 *
 * Gestiona la creación y obtención de autores en WordPress a partir
 * de las fuentes de noticias provenientes de la API Byline.
 *
 * @package NewsWire_WP
 */

if (!defined('ABSPATH')) {
    exit;
}

class nwwp_Author_Manager {

    const EMAIL_DOMAIN = '@newswire-wp.local';

    public function get_or_create_author($source_name, $source_url = '', $favicon_url = '') {
        $user_login = sanitize_title($source_name);

        if (empty($user_login)) {
            $user_login = 'fuente-' . uniqid();
        }
        $user_login = substr($user_login, 0, 60);

        $usuario = get_user_by('login', $user_login);
        if ($usuario) {
            return $usuario->ID;
        }

        $email = $user_login . self::EMAIL_DOMAIN;
        $contador = 0;
        while (email_exists($email)) {
            $contador++;
            $email = $user_login . '-' . $contador . self::EMAIL_DOMAIN;
        }

        $user_id = wp_create_user($user_login, wp_generate_password(), $email);
        if (is_wp_error($user_id)) {
            return $user_id;
        }

        wp_update_user(array(
            'ID'           => $user_id,
            'display_name' => sanitize_text_field($source_name),
            'role'         => 'author',
            'user_url'     => esc_url_raw($source_url),
        ));

        if (!empty($favicon_url)) {
            $this->set_author_avatar($user_id, $favicon_url);
        }

        return $user_id;
    }

    public function set_author_avatar($user_id, $favicon_url) {
        $respuesta = wp_remote_get(esc_url_raw($favicon_url), array(
            'timeout'   => 15,
            'sslverify' => true,
        ));

        if (is_wp_error($respuesta) || 200 !== wp_remote_retrieve_response_code($respuesta)) {
            return false;
        }

        $image_data = wp_remote_retrieve_body($respuesta);
        if (empty($image_data)) {
            return false;
        }

        $extension = $this->get_image_extension($favicon_url, $image_data);
        $filename = 'avatar-' . md5($user_id) . '.' . $extension;

        $upload = wp_upload_bits($filename, null, $image_data);
        if (!empty($upload['error'])) {
            return false;
        }

        $wp_filetype = wp_check_filetype($filename, null);
        $attachment_id = wp_insert_attachment(array(
            'post_mime_type' => $wp_filetype['type'],
            'post_title'     => sanitize_file_name('avatar-' . $user_id),
            'post_content'   => '',
            'post_status'    => 'inherit',
        ), $upload['file']);

        if (is_wp_error($attachment_id) || 0 === $attachment_id) {
            return false;
        }

        require_once ABSPATH . 'wp-admin/includes/image.php';
        $attach_data = wp_generate_attachment_metadata($attachment_id, $upload['file']);
        wp_update_attachment_metadata($attachment_id, $attach_data);

        update_user_meta($user_id, 'nwwp_avatar_attachment_id', $attachment_id);

        return $attachment_id;
    }

    private function get_image_extension($url, $image_data) {
        $path = parse_url($url, PHP_URL_PATH);
        if ($path) {
            $ext = strtolower(pathinfo($path, PATHINFO_EXTENSION));
            $valid_extensions = array('jpg', 'jpeg', 'png', 'gif', 'ico', 'svg', 'webp');
            if (in_array($ext, $valid_extensions, true)) {
                return $ext;
            }
        }
        if (0 === strpos($image_data, "\x89PNG")) return 'png';
        if (0 === strpos($image_data, "\xFF\xD8")) return 'jpg';
        if (0 === strpos($image_data, "GIF87a") || 0 === strpos($image_data, "GIF89a")) return 'gif';
        if (false !== strpos($image_data, '<svg')) return 'svg';
        return 'png';
    }

    public function custom_avatar($avatar, $id_or_email, $size) {
        $user_id = 0;

        if (is_numeric($id_or_email)) {
            $user_id = (int) $id_or_email;
        } elseif (is_string($id_or_email) && is_email($id_or_email)) {
            $usuario = get_user_by('email', $id_or_email);
            if ($usuario) $user_id = $usuario->ID;
        } elseif ($id_or_email instanceof WP_User) {
            $user_id = $id_or_email->ID;
        }

        if (0 === $user_id) return $avatar;

        $attachment_id = get_user_meta($user_id, 'nwwp_avatar_attachment_id', true);
        if (empty($attachment_id)) return $avatar;

        $image_src = wp_get_attachment_image_src($attachment_id, array($size, $size));
        if (!$image_src) return $avatar;

        $url  = esc_url($image_src[0]);
        $alt  = esc_attr(get_the_author_meta('display_name', $user_id));
        $size = absint($size);

        return "<img alt='{$alt}' src='{$url}' class='avatar avatar-{$size} photo nwwp-avatar' height='{$size}' width='{$size}' />";
    }
}
