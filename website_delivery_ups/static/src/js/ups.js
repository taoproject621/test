odoo.define("website_sale_ups.arrival", function (require) {
    'use strict';

    var core = require("web.core");
    var publicWidget = require("web.public.widget");
    var _t = core._t;

    // var websiteSaleDelivery = require("web.websiteSaleDelivery");

    publicWidget.registry.websiteSaleDelivery.include({

        _handleCarrierUpdateResultBadge: function (result) {
            var $carrierBadge = $('#delivery_carrier input[name="delivery_type"][value=' + result.carrier_id + '] ~ .o_wsale_delivery_badge_price');

            if (result.status === true) {
                // if free delivery (`free_over` field), show 'Free', not '$0'
                console.log('----')
                console.log(result)
                if (result.is_free_delivery) {
                    $carrierBadge.text(_t('Free'));
                } else {
                    $carrierBadge.html("Arrival Date:<span>" + result.arrival_date + "</span>&nbsp;&nbsp;Price:" + result.new_amount_delivery);
                }
                $carrierBadge.removeClass('o_wsale_delivery_carrier_error');
            } else {
                $carrierBadge.addClass('o_wsale_delivery_carrier_error');
                $carrierBadge.text(result.error_message);
            }
        }

    });
});