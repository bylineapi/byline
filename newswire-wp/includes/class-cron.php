<?php
/**
 * Clase NWWP_Cron
 *
 * Gestiona los eventos cron del plugin: importación horaria y
 * verificación de noticias de último momento.
 *
 * @package NewsWire_WP
 */

if (!defined('ABSPATH')) {
    exit;
}

class nwwp_Cron {

    const HOOK_BREAKING_NEWS = 'nwwp_breaking_news_check';
    const HOOK_HOURLY_IMPORT = 'nwwp_hourly_import';
    const SCHEDULE_FIVE_MIN  = 'nwwp_five_minutes';

    public function __construct() {
        add_filter('cron_schedules', array($this, 'agregar_intervalo_cinco_minutos'));
        add_action('admin_init', array($this, 'registrar_eventos_cron'));
        add_action(self::HOOK_BREAKING_NEWS, array($this, 'ejecutar_breaking_news'));
        add_action(self::HOOK_HOURLY_IMPORT, array($this, 'ejecutar_import_horaria'));
    }

    public function agregar_intervalo_cinco_minutos($schedules) {
        $schedules[self::SCHEDULE_FIVE_MIN] = array(
            'interval' => 300,
            'display'  => __('Cada 5 minutos', 'newswire-wp'),
        );
        return $schedules;
    }

    public function registrar_eventos_cron() {
        if (!wp_next_scheduled(self::HOOK_BREAKING_NEWS)) {
            wp_schedule_event(time(), self::SCHEDULE_FIVE_MIN, self::HOOK_BREAKING_NEWS);
        }

        if (!wp_next_scheduled(self::HOOK_HOURLY_IMPORT)) {
            wp_schedule_event(time(), 'hourly', self::HOOK_HOURLY_IMPORT);
        }
    }

    public function ejecutar_breaking_news() {
        $api_key = get_option('nwwp_api_key', '');

        if (empty($api_key)) {
            $this->registrar_log(
                'breaking_news',
                'error',
                'No se puede ejecutar breaking news: API Key no configurada'
            );
            return;
        }

        $activar_breaking = get_option('nwwp_breaking_enabled', false);
        if (!$activar_breaking) {
            return;
        }

        $api_client = new nwwp_API_Client();
        $articulos  = $api_client->get_news('', true);

        if (is_wp_error($articulos)) {
            $this->registrar_log(
                'breaking_news',
                'error',
                'Error al obtener noticias breaking: ' . $articulos->get_error_message()
            );
            return;
        }

        if (empty($articulos) || !is_array($articulos)) {
            $this->registrar_log('breaking_news', 'info', 'No se encontraron noticias breaking en esta verificación');
            return;
        }

        $author_manager = new nwwp_Author_Manager();
        $importer       = new nwwp_Importer($api_client, $author_manager);

        $content_mode = get_option('nwwp_content_mode', 'excerpt');
        $resultados   = $importer->import_multiple($articulos, array(
            'content_mode'  => $content_mode,
            'category_map'  => $this->obtener_mapeo_categorias(),
        ));

        $this->registrar_log(
            'breaking_news',
            'success',
            sprintf(
                'Breaking news: %d importados, %d duplicados, %d errores',
                $resultados['importados'],
                $resultados['saltados'],
                count($resultados['errores'])
            )
        );
    }

    public function ejecutar_import_horaria() {
        $api_key = get_option('nwwp_api_key', '');

        if (empty($api_key)) {
            $this->registrar_log(
                'hourly_import',
                'error',
                'No se puede ejecutar importación horaria: API Key no configurada'
            );
            return;
        }

        $api_client    = new nwwp_API_Client();
        $author_manager = new nwwp_Author_Manager();
        $importer       = new nwwp_Importer($api_client, $author_manager);
        $category_map   = $this->obtener_mapeo_categorias();
        $limit_por_cat  = intval(get_option('nwwp_posts_per_hour', 5));
        $content_mode  = get_option('nwwp_content_mode', 'excerpt');

        $total_importados = 0;
        $total_saltados   = 0;
        $errores          = array();

        if (!empty($category_map) && is_array($category_map)) {
            foreach ($category_map as $api_category => $wp_cat_id) {
                $articulos = $api_client->get_news($api_category, false, $limit_por_cat);

                if (is_wp_error($articulos)) {
                    $errores[] = "Categoría {$api_category}: " . $articulos->get_error_message();
                    continue;
                }

                if (empty($articulos) || !is_array($articulos)) {
                    continue;
                }

                $resultados = $importer->import_multiple($articulos, array(
                    'content_mode'  => $content_mode,
                    'category_map'  => $category_map,
                ));

                $total_importados += $resultados['importados'];
                $total_saltados   += $resultados['saltados'];
                foreach ($resultados['errores'] as $err) {
                    $errores[] = "Categoría {$api_category}: " . $err['error'];
                }
            }
        } else {
            $articulos = $api_client->get_news('', false, $limit_por_cat);

            if (!is_wp_error($articulos) && !empty($articulos) && is_array($articulos)) {
                $resultados = $importer->import_multiple($articulos, array(
                    'content_mode' => $content_mode,
                ));
                $total_importados = $resultados['importados'];
                $total_saltados   = $resultados['saltados'];
                $errores           = array_map(function($e) {
                    return $e['error'];
                }, $resultados['errores']);
            }
        }

        $this->registrar_log(
            'hourly_import',
            empty($errores) ? 'success' : 'partial',
            sprintf(
                'Importación horaria: %d importados, %d duplicados, %d errores',
                $total_importados,
                $total_saltados,
                count($errores)
            )
        );
    }

    private function obtener_mapeo_categorias() {
        $map = get_option('nwwp_category_map', array());
        if (!is_array($map)) {
            $map = array();
        }
        return $map;
    }

    private function registrar_log($accion, $resultado, $mensaje) {
        global $wpdb;

        $tabla = $wpdb->prefix . 'nwwp_activity_log';

        $wpdb->insert(
            $tabla,
            array(
                'action'     => sanitize_text_field($accion),
                'result'     => sanitize_text_field($resultado),
                'message'    => sanitize_text_field($mensaje),
                'timestamp'  => current_time('mysql'),
            ),
            array('%s', '%s', '%s', '%s')
        );
    }

    public static function limpiar_eventos_cron() {
        wp_clear_scheduled_hook(self::HOOK_BREAKING_NEWS);
        wp_clear_scheduled_hook(self::HOOK_HOURLY_IMPORT);
    }
}