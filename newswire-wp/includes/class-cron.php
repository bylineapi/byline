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

class nwwp_Cron
{

    const HOOK_BREAKING_NEWS = 'nwwp_breaking_news_check';
    const HOOK_HOURLY_IMPORT = 'nwwp_hourly_import';
    const HOOK_AUTO_PUBLISH = 'nwwp_auto_publish';
    const SCHEDULE_FIVE_MIN  = 'nwwp_five_minutes';

    public function __construct()
    {
        add_filter('cron_schedules', array($this, 'agregar_intervalo_cinco_minutos'));
        add_filter('cron_schedules', array($this, 'agregar_intervalos_auto_publish'));
        add_action('admin_init', array($this, 'registrar_eventos_cron'));
        add_action(self::HOOK_BREAKING_NEWS, array($this, 'ejecutar_breaking_news'));
        add_action(self::HOOK_HOURLY_IMPORT, array($this, 'ejecutar_import_horaria'));
        add_action(self::HOOK_AUTO_PUBLISH, array($this, 'ejecutar_auto_publicacion'));
    }

    public function agregar_intervalo_cinco_minutos($schedules)
    {
        $schedules[self::SCHEDULE_FIVE_MIN] = array(
            'interval' => 300,
            'display'  => __('Cada 5 minutos', 'newswire-wp'),
        );
        return $schedules;
    }

    public function agregar_intervalos_auto_publish($schedules)
    {
        // Agregar intervalos personalizados para auto-publicación
        $intervals = array(
            15 => 'Cada 15 minutos',
            30 => 'Cada 30 minutos',
            60 => 'Cada hora',
            120 => 'Cada 2 horas',
            360 => 'Cada 6 horas',
        );

        foreach ($intervals as $minutes => $label) {
            $schedule_name = 'nwwp_auto_publish_' . $minutes . 'min';
            $schedules[$schedule_name] = array(
                'interval' => $minutes * 60,
                'display'  => __($label, 'newswire-wp'),
            );
        }

        return $schedules;
    }

    public function registrar_eventos_cron()
    {
        if (!wp_next_scheduled(self::HOOK_BREAKING_NEWS)) {
            wp_schedule_event(time(), self::SCHEDULE_FIVE_MIN, self::HOOK_BREAKING_NEWS);
        }

        if (!wp_next_scheduled(self::HOOK_HOURLY_IMPORT)) {
            wp_schedule_event(time(), 'hourly', self::HOOK_HOURLY_IMPORT);
        }

        // Registrar evento de auto-publicación si está habilitado
        $auto_publish_enabled = get_option('nwwp_auto_publish_enabled', false);
        if ($auto_publish_enabled) {
            $frequency = get_option('nwwp_auto_publish_frequency', '30');
            $schedule_name = 'nwwp_auto_publish_' . $frequency . 'min';

            // Limpiar evento anterior si existe
            $timestamp = wp_next_scheduled(self::HOOK_AUTO_PUBLISH);
            if ($timestamp) {
                wp_unschedule_event($timestamp, self::HOOK_AUTO_PUBLISH);
            }

            // Programar nuevo evento con la frecuencia seleccionada
            wp_schedule_event(time(), $schedule_name, self::HOOK_AUTO_PUBLISH);
        } else {
            // Si está deshabilitado, limpiar evento
            $timestamp = wp_next_scheduled(self::HOOK_AUTO_PUBLISH);
            if ($timestamp) {
                wp_unschedule_event($timestamp, self::HOOK_AUTO_PUBLISH);
            }
        }
    }

    public function ejecutar_breaking_news()
    {
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

    public function ejecutar_import_horaria()
    {
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
                $errores           = array_map(function ($e) {
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

    private function obtener_mapeo_categorias()
    {
        $map = get_option('nwwp_category_map', array());
        if (!is_array($map)) {
            $map = array();
        }
        return $map;
    }

    private function registrar_log($accion, $resultado, $mensaje)
    {
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

    /**
     * Ejecutar auto-publicación programada
     * 
     * Llama al scraper para obtener artículos nuevos y los publica en WordPress
     */
    public function ejecutar_auto_publicacion()
    {
        // Verificar si la auto-publicación está habilitada
        $auto_publish_enabled = get_option('nwwp_auto_publish_enabled', false);
        if (!$auto_publish_enabled) {
            return;
        }

        $api_key = get_option('nwwp_api_key', '');
        if (empty($api_key)) {
            $this->registrar_log(
                'auto_publish',
                'error',
                'No se puede ejecutar auto-publicación: API Key no configurada'
            );
            return;
        }

        // Obtener categoría de publicación
        $publish_category = get_option('nwwp_auto_publish_category', '');

        // Obtener modo de contenido
        $content_mode = get_option('nwwp_content_mode', 'excerpt');

        // Llamar a la API para obtener artículos nuevos
        $api_url = NWWP_API_URL;
        $fetch_url = add_query_arg(
            array(
                'api_key' => $api_key,
                'limit' => 5, // Obtener máximo 5 artículos por ejecución
            ),
            trailingslashit($api_url) . 'api/articles/fetch'
        );

        $response = wp_remote_post($fetch_url, array(
            'timeout' => 120, // 2 minutos de timeout para scraping
            'sslverify' => true,
        ));

        if (is_wp_error($response)) {
            $this->registrar_log(
                'auto_publish',
                'error',
                'Error al conectar con API: ' . $response->get_error_message()
            );
            return;
        }

        $status_code = wp_remote_retrieve_response_code($response);
        if ($status_code !== 200) {
            $this->registrar_log(
                'auto_publish',
                'error',
                'API respondió con código: ' . $status_code
            );
            return;
        }

        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);

        if (!isset($data['success']) || !$data['success']) {
            $this->registrar_log(
                'auto_publish',
                'error',
                'API respondió con error: ' . ($data['message'] ?? 'Error desconocido')
            );
            return;
        }

        $articles_fetched = $data['articles_fetched'] ?? 0;

        if ($articles_fetched === 0) {
            $this->registrar_log(
                'auto_publish',
                'info',
                'No se encontraron artículos nuevos en esta ejecución'
            );
            return;
        }

        // Importar los artículos obtenidos
        $api_client = new nwwp_API_Client();
        $author_manager = new nwwp_Author_Manager();
        $importer = new nwwp_Importer($api_client, $author_manager);

        // Obtener artículos recientes de la API para importar
        $articulos = $api_client->get_news('', false, $articles_fetched);

        if (is_wp_error($articulos) || empty($articulos)) {
            $this->registrar_log(
                'auto_publish',
                'error',
                'No se pudieron obtener los artículos para importar'
            );
            return;
        }

        // Preparar mapeo de categorías si se especificó
        $category_map = array();
        if (!empty($publish_category)) {
            // Mapear todas las categorías de API a la categoría seleccionada
            $category_map = array(
                '*' => absint($publish_category),
            );
        }

        // Importar artículos
        $resultados = $importer->import_multiple($articulos, array(
            'content_mode' => $content_mode,
            'category_map' => $category_map,
        ));

        $this->registrar_log(
            'auto_publish',
            'success',
            sprintf(
                'Auto-publish: %d artículos obtenidos, %d importados, %d duplicados, %d errores',
                $articles_fetched,
                $resultados['importados'],
                $resultados['saltados'],
                count($resultados['errores'])
            )
        );
    }

    public static function limpiar_eventos_cron()
    {
        wp_clear_scheduled_hook(self::HOOK_BREAKING_NEWS);
        wp_clear_scheduled_hook(self::HOOK_HOURLY_IMPORT);
    }
}
