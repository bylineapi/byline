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

        // ─── Enlazado Interno y Etiquetado SEO Semántico Inteligente ─────
        $this->enlazar_internamente_y_etiquetar($post_id, $contenido, $titulo);

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
        $image_mode = get_option('nwwp_image_mode', 'original');

        $image_to_load = '';
        $original_url = !empty($article['image_url']) ? $article['image_url'] : '';
        $premium_url  = !empty($article['premium_image_url']) ? $article['premium_image_url'] : '';

        if ($image_mode === 'premium') {
            $image_to_load = !empty($premium_url) ? $premium_url : $original_url;
        } elseif ($image_mode === 'mixed') {
            $image_to_load = !empty($original_url) ? $original_url : $premium_url;
        } else {
            $image_to_load = $original_url;
        }

        if (!empty($image_to_load)) {
            if (!function_exists('media_sideload_image')) {
                require_once ABSPATH . 'wp-admin/includes/media.php';
                require_once ABSPATH . 'wp-admin/includes/file.php';
                require_once ABSPATH . 'wp-admin/includes/image.php';
            }

            $attachment_id = media_sideload_image(esc_url($image_to_load), $post_id, null, 'id');
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

    private function enlazar_internamente_y_etiquetar($post_id, $contenido, $titulo) {
        // ─── 1. Etiquetado Automático Inteligente ──────────────────────
        $palabras = explode(' ', strtolower($titulo));
        $stopwords = array(
            'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para',
            'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'más', 'pero', 'sus', 'le', 'ya', 'o', 'este',
            'sí', 'porque', 'esta', 'entre', 'cuando', 'muy', 'sin', 'sobre', 'también', 'me', 'hasta',
            'desde', 'nos', 'durante', 'uno', 'ni', 'contra', 'tres', 'sus', 'les', 'e', 'hacia', 'haber'
        );
        $tags = array();
        foreach ($palabras as $p) {
            $p_limpia = trim(preg_replace('/[^a-z0-9áéíóúñü]/i', '', $p));
            if (strlen($p_limpia) > 4 && !in_array($p_limpia, $stopwords)) {
                $tags[] = $p_limpia;
            }
        }
        if (!empty($tags)) {
            wp_set_post_tags($post_id, array_slice($tags, 0, 5), true);
        }

        // ─── 2. Enlazado Interno Semántico Automático (SEO) ─────────────
        $existing_posts = get_posts(array(
            'post_type'      => 'post',
            'post_status'    => 'publish',
            'posts_per_page' => 15,
            'exclude'        => array($post_id),
            'orderby'        => 'date',
            'order'          => 'DESC',
        ));

        if (!empty($existing_posts)) {
            $nuevo_contenido = $contenido;
            $modificado = false;

            foreach ($existing_posts as $ex_post) {
                $ex_titulo = $ex_post->post_title;
                // Extraer palabra clave principal (las primeras dos palabras significativas del título)
                $ex_words = explode(' ', $ex_titulo);
                $kw_candidate = '';
                $count = 0;
                foreach ($ex_words as $w) {
                    $w_clean = trim(preg_replace('/[^a-z0-9áéíóúñü]/i', '', strtolower($w)));
                    if (strlen($w_clean) > 4 && !in_array($w_clean, $stopwords)) {
                        $kw_candidate .= ($kw_candidate ? ' ' : '') . $w;
                        $count++;
                        if ($count >= 2) break;
                    }
                }

                if (empty($kw_candidate)) {
                    // Fallback a la primera palabra larga del título
                    foreach ($ex_words as $w) {
                        if (strlen($w) > 5) {
                            $kw_candidate = $w;
                            break;
                        }
                    }
                }

                if (!empty($kw_candidate)) {
                    // Reemplazar la primera ocurrencia de la palabra clave con el link si no está ya enlazada
                    $kw_escaped = preg_quote($kw_candidate, '/');
                    // Regex para buscar la palabra clave fuera de etiquetas de enlaces HTML existentes
                    $pattern = '/(?<!<a[^>]*)\b(' . $kw_escaped . ')\b(?![^<]*<\/a>)/i';
                    
                    // Solo reemplazar una vez
                    $temp_content = preg_replace($pattern, '<a href="' . esc_url(get_permalink($ex_post->ID)) . '">$1</a>', $nuevo_contenido, 1);
                    if ($temp_content !== null && $temp_content !== $nuevo_contenido) {
                        $nuevo_contenido = $temp_content;
                        $modificado = true;
                    }
                }
            }

            if ($modificado) {
                wp_update_post(array(
                    'ID'           => $post_id,
                    'post_content' => $nuevo_contenido,
                ));
            }
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
