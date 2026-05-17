<?php

/**
 * Clase NWWP_Cron
 *
 * Gestiona la sincronización con Byline API:
 * - Obtiene artículos pendientes filtrados por las categorías del cliente
 * - Los importa como posts en WordPress
 * - NO ejecuta scraping (el scraper corre 24/7 en la API)
 *
 * @package NewsWire_WP
 */

if (!defined('ABSPATH')) {
    exit;
}

class nwwp_Cron
{

    const HOOK_SYNC = 'nwwp_sync_articles';

    public function __construct()
    {
        add_filter('cron_schedules', array($this, 'agregar_intervalos_sync'));
        add_action('admin_init', array($this, 'registrar_eventos_cron'));
        add_action(self::HOOK_SYNC, array($this, 'ejecutar_sincronizacion'));
    }

    public function agregar_intervalos_sync($schedules)
    {
        $schedules['nwwp_5min'] = array(
            'interval' => 300,
            'display'  => __('Cada 5 minutos', 'newswire-wp'),
        );
        $schedules['nwwp_15min'] = array(
            'interval' => 900,
            'display'  => __('Cada 15 minutos', 'newswire-wp'),
        );
        $schedules['nwwp_30min'] = array(
            'interval' => 1800,
            'display'  => __('Cada 30 minutos', 'newswire-wp'),
        );
        return $schedules;
    }

    public function registrar_eventos_cron()
    {
        if (!wp_next_scheduled(self::HOOK_SYNC)) {
            $frequency = get_option('nwwp_auto_publish_frequency', '15');
            $schedule_map = array('5' => 'nwwp_5min', '15' => 'nwwp_15min', '30' => 'nwwp_30min');
            $schedule = isset($schedule_map[$frequency]) ? $schedule_map[$frequency] : 'nwwp_15min';
            wp_schedule_event(time(), $schedule, self::HOOK_SYNC);
        }
    }

    /**
     * Único método de sincronización:
     * 1. Llama a sync_articles() con las categorías del cliente
     * 2. Importa los artículos recibidos como posts de WordPress
     * 3. NO ejecuta scraping (el scraper ya corre 24/7 en la API)
     */
    public function ejecutar_sincronizacion($force = false)
    {
        $api_key = get_option('nwwp_api_key', '');
        if (empty($api_key)) {
            $this->registrar_log('sync', 'error', 'API Key no configurada');
            return;
        }

        $limit = $this->obtener_limite_plan();
        $content_mode = get_option('nwwp_content_mode', 'excerpt');
        $category_map = $this->obtener_mapeo_categorias();

        $api_client = new nwwp_API_Client();
        $author_manager = new nwwp_Author_Manager();
        $importer = new nwwp_Importer($api_client, $author_manager);

        // Obtener categorías del mapeo (solo las que el cliente necesita en su web)
        $categorias_api = !empty($category_map) ? array_keys($category_map) : array();

        $total_importados = 0;
        $total_saltados = 0;
        $errores = array();

        if (!empty($categorias_api)) {
            // Sincronizar por cada categoría que el cliente maneja
            foreach ($categorias_api as $api_category) {
                $articulos = $api_client->sync_articles($api_category, $limit);
                if (is_wp_error($articulos)) {
                    $errores[] = "Categoría {$api_category}: " . $articulos->get_error_message();
                    continue;
                }
                if (empty($articulos)) {
                    continue;
                }

                $resultados = $importer->import_multiple($articulos, array(
                    'content_mode' => $content_mode,
                    'category_map' => $category_map,
                ));
                $total_importados += $resultados['importados'];
                $total_saltados += $resultados['saltados'];
                foreach ($resultados['errores'] as $err) {
                    $errores[] = "Categoría {$api_category}: " . $err['error'];
                }
            }
        } else {
            // Sin mapeo: traer artículos de todas las categorías
            $articulos = $api_client->sync_articles('', $limit);
            if (!is_wp_error($articulos) && !empty($articulos)) {
                $resultados = $importer->import_multiple($articulos, array(
                    'content_mode' => $content_mode,
                ));
                $total_importados = $resultados['importados'];
                $total_saltados = $resultados['saltados'];
                $errores = array_map(function ($e) {
                    return $e['error'];
                }, $resultados['errores']);
            }
        }

        $this->registrar_log(
            'sync',
            empty($errores) ? 'success' : 'partial',
            sprintf(
                'Sincronización: %d importados, %d duplicados, %d errores',
                $total_importados,
                $total_saltados,
                count($errores)
            )
        );
    }

    /**
     * Ejecuta sincronización inmediata (llamada externa o desde guardar settings)
     */
    public static function ejecutar_sincronizacion_inmediata()
    {
        $cron = new self();
        $cron->ejecutar_sincronizacion(true);
    }

    /**
     * Obtiene el límite de artículos según el plan
     */
    private function obtener_limite_plan()
    {
        $plan = get_option('nwwp_detected_plan', 'basic');
        $configurado = intval(get_option('nwwp_posts_per_hour', 5));

        if ('basic' === $plan) {
            return min($configurado, 2);
        } elseif ('pro' === $plan) {
            return min($configurado, 50);
        } elseif ('business' === $plan) {
            return min($configurado, 100);
        }
        return max(1, $configurado);
    }

    private function obtener_mapeo_categorias()
    {
        $map = get_option('nwwp_category_map', array());
        return is_array($map) ? $map : array();
    }

    private function registrar_log($accion, $resultado, $mensaje)
    {
        global $wpdb;
        $tabla = $wpdb->prefix . 'nwwp_activity_log';
        $wpdb->insert(
            $tabla,
            array(
                'action'    => sanitize_text_field($accion),
                'result'    => sanitize_text_field($resultado),
                'message'   => sanitize_text_field($mensaje),
                'timestamp' => current_time('mysql'),
            ),
            array('%s', '%s', '%s', '%s')
        );
    }

    public static function limpiar_eventos_cron()
    {
        wp_clear_scheduled_hook(self::HOOK_SYNC);
    }
}
