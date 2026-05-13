<?php
/**
 * Clase NWWP_Importer
 *
 * Importa artículos obtenidos de la API Byline como posts de WordPress.
 *
 * @package NewsWire_WP
 */

if (!defined('ABSPATH')) {
    exit;
}

class nwwp_Importer {

    private $api_client;
    private $author_manager;
    private $tabla_importados;

    public function __construct($api_client, $author_manager) {
        global $wpdb;
        $this->api_client       = $api_client;
        $this->author_manager   = $author_manager;
        $this->tabla_importados = $wpdb->prefix . 'nwwp_imported_articles';
    }

    public function import_article($article, $options = array()) {
        // ─── Anti-duplicado ──────────────────────────────────────────────
        if ($this->articulo_ya_importado($article)) {
            return false;
        }

        // ─── Obtener autor ───────────────────────────────────────────────
        // Ahora la API devuelve los datos de la fuente en un objeto anidado 'source'
        $source_name = isset($article['source']['name']) ? $article['source']['name'] : '';
        $source_url  = isset($article['source']['url']) ? $article['source']['url'] : '';
        $favicon_url = isset($article['source']['favicon_url']) ? $article['source']['favicon_url'] : '';

        if (empty($source_name)) {
            $source_name = 'Fuente-' . (isset($article['source_id']) ? $article['source_id'] : 'desconocida');
        }

        $author_id = $this->author_manager->get_or_create_author($source_name, $source_url, $favicon_url);
        if (is_wp_error($author_id)) {
            return $author_id;
        }

        // ─── Determinar categoría ────────────────────────────────────────
        $cat_id = $this->determinar_categoria($article, $options);

        // ─── Preparar contenido ──────────────────────────────────────────
        $content_mode = isset($options['content_mode']) ? $options['content_mode'] : 'full';
        $contenido = $this->preparar_contenido($article, $content_mode);

        // ─── Sanitizar título ────────────────────────────────────────────
        $titulo = isset($article['title']) ? sanitize_text_field($article['title']) : '';
        if (empty($titulo)) {
            $titulo = __('Artículo sin título', 'newswire-wp') . ' - ' . current_time('mysql');
        }

        // ─── Determinar fecha ────────────────────────────────────────────
        $post_date = current_time('mysql');
        if (!empty($article['published_at'])) {
            $fecha_api = $article['published_at'];
            if (is_string($fecha_api)) {
                $timestamp = strtotime($fecha_api);
                if (false !== $timestamp) {
                    $post_date = date('Y-m-d H:i:s', $timestamp);
                }
            } elseif (is_numeric($fecha_api)) {
                $post_date = date('Y-m-d H:i:s', $fecha_api);
            }
        }

        // ─── Crear el post ───────────────────────────────────────────────
        $post_id = wp_insert_post(array(
            'post_title'    => $titulo,
            'post_content'  => $contenido,
            'post_status'   => 'publish',
            'post_author'   => $author_id,
            'post_category' => array($cat_id),
            'post_date'     => $post_date,
            'post_date_gmt' => get_gmt_from_date($post_date),
        ), true);

        if (is_wp_error($post_id)) {
            return $post_id;
        }

        // ─── Imagen destacada ────────────────────────────────────────────
        $this->set_imagen_destacada($post_id, $article);

        // ─── Guardar meta fields ─────────────────────────────────────────
        if (!empty($article['original_url'])) {
            update_post_meta($post_id, 'nwwp_original_url', esc_url($article['original_url']));
        }
        update_post_meta($post_id, 'nwwp_source_name', sanitize_text_field($source_name));
        if (isset($article['impact_score'])) {
            update_post_meta($post_id, 'nwwp_impact_score', intval($article['impact_score']));
        }

        // ─── Registrar en tabla de importados ────────────────────────────
        $this->registrar_importado($article, $post_id, $source_url);

        return $post_id;
    }

    private function articulo_ya_importado($article) {
        global $wpdb;

        $article_api_id = isset($article['id']) ? $article['id'] : '';
        if (!empty($article_api_id)) {
            $existe = $wpdb->get_var($wpdb->prepare(
                "SELECT id FROM {$this->tabla_importados} WHERE article_api_id = %s LIMIT 1",
                $article_api_id
            ));
            if ($existe) return true;
        }

        if (!empty($article['original_url'])) {
            $posts = get_posts(array(
                'post_type'      => 'any',
                'meta_key'       => 'nwwp_original_url',
                'meta_value'     => esc_url($article['original_url']),
                'posts_per_page' => 1,
                'fields'         => 'ids',
            ));
            if (!empty($posts)) return true;
        }

        return false;
    }

    private function determinar_categoria($article, $options) {
        $api_category = isset($article['category']) ? $article['category'] : '';

        $category_map = isset($options['category_map']) ? $options['category_map'] : array();
        if (empty($category_map)) {
            $category_map = get_option('nwwp_category_map', array());
            if (!is_array($category_map)) $category_map = array();
        }

        if (!empty($api_category) && isset($category_map[$api_category])) {
            return intval($category_map[$api_category]);
        }

        if (!empty($api_category)) {
            $cat_slug = sanitize_title($api_category);
            $categoria = get_category_by_slug($cat_slug);
            if ($categoria) return (int) $categoria->term_id;

            $nueva = wp_create_category(sanitize_text_field($api_category));
            if (!is_wp_error($nueva) && $nueva > 0) return $nueva;
        }

        return intval(get_option('default_category'));
    }

    private function preparar_contenido($article, $content_mode) {
        $contenido = '';

        switch ($content_mode) {
            case 'full':
                $contenido = isset($article['content']) ? wp_kses_post($article['content']) : '';
                break;

            case 'excerpt':
                $excerpt = isset($article['excerpt']) ? wp_kses_post($article['excerpt']) : '';
                $contenido = $excerpt;
                if (!empty($article['original_url'])) {
                    $contenido .= "\n\n" . '<p><a href="' . esc_url($article['original_url']) . '" target="_blank" rel="noopener noreferrer">'
                                . esc_html__('Leer artículo completo en la fuente original', 'newswire-wp') . '</a></p>';
                }
                break;

            case 'summary':
                $contenido = !empty($article['ai_summary']) ? wp_kses_post($article['ai_summary']) : (isset($article['excerpt']) ? wp_kses_post($article['excerpt']) : '');
                if (!empty($article['original_url'])) {
                    $contenido .= "\n\n" . '<p><a href="' . esc_url($article['original_url']) . '" target="_blank" rel="noopener noreferrer">'
                                . esc_html__('Leer artículo completo en la fuente original', 'newswire-wp') . '</a></p>';
                }
                break;

            default:
                $contenido = isset($article['content']) ? wp_kses_post($article['content']) : '';
                break;
        }

        return $contenido;
    }

    private function set_imagen_destacada($post_id, $article) {
        $attachment_id = 0;

        if (!empty($article['image_url'])) {
            if (!function_exists('media_sideload_image')) {
                require_once ABSPATH . 'wp-admin/includes/media.php';
                require_once ABSPATH . 'wp-admin/includes/file.php';
                require_once ABSPATH . 'wp-admin/includes/image.php';
            }

            $attachment_id = media_sideload_image(esc_url($article['image_url']), $post_id, null, 'id');
            if (is_wp_error($attachment_id)) $attachment_id = 0;
        }

        if (0 === $attachment_id) {
            $default_image_id = get_option('nwwp_default_image_id', 0);
            if ($default_image_id > 0) $attachment_id = intval($default_image_id);
        }

        if ($attachment_id > 0) {
            set_post_thumbnail($post_id, $attachment_id);
        }
    }

    private function registrar_importado($article, $post_id, $source_url) {
        global $wpdb;

        $article_api_id = isset($article['id']) ? $article['id'] : '';
        if (!empty($article_api_id)) {
            $wpdb->insert(
                $this->tabla_importados,
                array(
                    'article_api_id' => sanitize_text_field($article_api_id),
                    'wp_post_id'     => intval($post_id),
                    'source_url'     => esc_url($source_url),
                    'imported_at'    => current_time('mysql'),
                ),
                array('%s', '%d', '%s', '%s')
            );
        }
    }

    public function import_multiple($articulos, $options = array()) {
        $resultados = array(
            'importados' => 0,
            'saltados'   => 0,
            'errores'    => array(),
        );

        if (empty($articulos) || !is_array($articulos)) {
            return $resultados;
        }

        foreach ($articulos as $index => $article) {
            if (!is_array($article)) continue;

            $post_id = $this->import_article($article, $options);

            if (false === $post_id) {
                $resultados['saltados']++;
            } elseif (is_wp_error($post_id)) {
                $resultados['errores'][] = array(
                    'indice' => $index,
                    'error'  => $post_id->get_error_message(),
                );
            } else {
                $resultados['importados']++;
            }
        }

        return $resultados;
    }
}
