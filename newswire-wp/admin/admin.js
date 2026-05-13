/**
 * NWWP Admin JS
 *
 * @package NewsWire_WP
 */

(function($) {
    'use strict';

    var NWWPSettings = {

        init: function() {
            this.bindVerifyConnection();
            this.bindCategoryMapAdd();
            this.bindCategoryMapRemove();
            this.bindMediaUploader();
        },

        bindVerifyConnection: function() {
            $(document).on('click', '#nwwp-verify-btn', function(e) {
                e.preventDefault();

                var $btn     = $(this);
                var $msgBox  = $('#nwwp-verify-msg');
                var apiUrl   = $('#nwwp_api_url').val();
                var apiKey   = $('#nwwp_api_key').val();

                if (!apiUrl || !apiKey) {
                    $msgBox.html('<span style="color:#c62828;">Por favor, completa la URL y la API Key.</span>');
                    return;
                }

                $btn.prop('disabled', true).text('Verificando...');
                $msgBox.html('');

                $.ajax({
                    url: nwwpAdmin.ajaxUrl,
                    type: 'POST',
                    data: {
                        action: 'nwwp_verify_connection',
                        nonce: nwwpAdmin.nonce,
                        api_url: apiUrl,
                        api_key: apiKey
                    },
                    success: function(response) {
                        if (response.success) {
                            $msgBox.html(
                                '<span style="color:#2e7d32;">' + response.data.message + '</span>'
                            );
                            NWWPSettings.actualizarUIsegunPlan(response.data.plan);
                        } else {
                            $msgBox.html(
                                '<span style="color:#c62828;">' + response.data.message + '</span>'
                            );
                        }
                    },
                    error: function() {
                        $msgBox.html('<span style="color:#c62828;">Error de conexión AJAX.</span>');
                    },
                    complete: function() {
                        $btn.prop('disabled', false).text('Verificar conexión');
                    }
                });
            });
        },

        actualizarUIsegunPlan: function(plan) {
            var $contentFull    = $('input[name="nwwp_content_mode"][value="full"]');
            var $contentSummary  = $('input[name="nwwp_content_mode"][value="summary"]');
            var $breakingCheck  = $('#nwwp_activar_breaking');
            var $postsPerHour   = $('#nwwp_posts_per_hour');
            var $noteBasic       = $('#nwwp-note-basic');

            if ('basic' === plan) {
                $contentFull.prop('disabled', true)
                    .closest('label').append('<span class="nwwp-disabled-note">Actualiza tu plan</span>');
                $contentSummary.prop('disabled', true)
                    .closest('label').append('<span class="nwwp-disabled-note">Actualiza tu plan</span>');
                $breakingCheck.prop('disabled', true)
                    .closest('label').append('<span class="nwwp-disabled-note">Solo disponible en plan Pro</span>');
                $postsPerHour.attr('max', '2');
                $noteBasic.show();
            } else if ('pro' === plan || 'business' === plan) {
                $contentFull.prop('disabled', false);
                $contentSummary.prop('disabled', false);
                $breakingCheck.prop('disabled', false);
                $postsPerHour.attr('max', '999');
                $noteBasic.hide();
            }
        },

        bindCategoryMapAdd: function() {
            $(document).on('click', '#nwwp-add-category-row', function(e) {
                e.preventDefault();
                var $container = $('#nwwp-category-map-rows');
                var $row = $container.find('.nwwp-category-map-row').first().clone();
                $row.find('input').val('');
                $row.find('select').val('');
                $container.append($row);
            });
        },

        bindCategoryMapRemove: function() {
            $(document).on('click', '.nwwp-btn-remove', function(e) {
                e.preventDefault();
                var $row = $(this).closest('.nwwp-category-map-row');
                if ($('#nwwp-category-map-rows .nwwp-category-map-row').length > 1) {
                    $row.remove();
                } else {
                    $row.find('input').val('');
                    $row.find('select').val('');
                }
            });
        },

        bindMediaUploader: function() {
            $(document).on('click', '#nwwp-upload-image-btn', function(e) {
                e.preventDefault();

                var $preview = $('#nwwp-image-preview');
                var $input   = $('#nwwp_default_image_id');

                var mediaFrame = wp.media({
                    title: 'Seleccionar imagen por defecto',
                    button: { text: 'Usar imagen' },
                    multiple: false,
                    library: { type: 'image' }
                });

                mediaFrame.on('select', function() {
                    var attachment = mediaFrame.state().get('selection').first().toJSON();
                    $input.val(attachment.id);
                    $preview.html('<img src="' + attachment.url + '" style="max-width:200px;height:auto;" />');
                });

                mediaFrame.open();
            });

            $(document).on('click', '#nwwp-remove-image-btn', function(e) {
                e.preventDefault();
                $('#nwwp_default_image_id').val('');
                $('#nwwp-image-preview').html('');
            });
        }
    };

    $(document).ready(function() {
        NWWPSettings.init();
    });

})(jQuery);