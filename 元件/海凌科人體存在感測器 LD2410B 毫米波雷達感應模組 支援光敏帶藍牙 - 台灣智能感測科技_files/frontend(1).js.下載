'use strict';

(function ($) {
    var woosb_timeout = null;

    $(function () {
        if ($('.woosb-wrap').length) {
            $('.woosb-wrap').each(function () {
                woosb_init($(this), 'ready');
            });
        }
    });

    $(document).on('woosq_loaded', function () {
        // product bundles in the quick view popup
        woosb_init($('#woosq-popup .woosb-wrap'), 'woosq');
    });

    $(document).on('click touch', '.woosb-quantity-input-plus, .woosb-quantity-input-minus', function () {
        // get values
        var $qty = $(this).closest('.woosb-quantity').find('.woosb-qty');

        if (!$qty.length) {
            $qty = $(this).closest('.woosb-quantity').find('.qty');
        }

        var val = parseFloat($qty.val()), max = parseFloat($qty.attr('max')), min = parseFloat($qty.attr('min')),
            step = $qty.attr('step');

        // format values
        if (!val || val === '' || val === 'NaN') {
            val = 0;
        }

        if (max === '' || max === 'NaN') {
            max = '';
        }

        if (min === '' || min === 'NaN') {
            min = 0;
        }

        if (step === 'any' || step === '' || step === undefined || step === 'NaN') {
            step = 1;
        } else {
            step = parseFloat(step);
        }

        // change the value
        if ($(this).is('.woosb-quantity-input-plus')) {
            if (max && (val >= max)) {
                $qty.val(max);
            } else {
                $qty.val((val + step).toFixed(woosb_decimal_places(step)));
            }
        } else {
            if (min && (val <= min)) {
                $qty.val(min);
            } else if (val > 0) {
                $qty.val((val - step).toFixed(woosb_decimal_places(step)));
            }
        }

        // trigger change event
        $qty.trigger('change');
    });

    $(document).on('click touch', '.single_add_to_cart_button', function (e) {
        var $this = $(this);

        if ($this.hasClass('woosb-disabled')) {
            e.preventDefault();
        }
    });

    if ($('.woosb-qty').length) {
        $(document).on('change', '.woosb-qty', function () {
            var $this = $(this);

            woosb_check_qty($this);
        });

        $(document).on('keyup', '.woosb-qty', function () {
            var $this = $(this);

            if (woosb_timeout != null) clearTimeout(woosb_timeout);
            woosb_timeout = setTimeout(woosb_check_qty, 1000, $this);
        });
    } else {
        $(document).on('change', '.woosb-quantity .qty', function () {
            var $this = $(this);

            woosb_check_qty($this);
        });

        $(document).on('keyup', '.woosb-quantity .qty', function () {
            var $this = $(this);

            if (woosb_timeout != null) clearTimeout(woosb_timeout);
            woosb_timeout = setTimeout(woosb_check_qty, 1000, $this);
        });
    }
})(jQuery);

function woosb_init($wrap, context = null) {
    woosb_check_ready($wrap, context);
    woosb_check_stock($wrap, context);
    woosb_save_ids($wrap, context);

    jQuery(document).trigger('woosb_init', [$wrap, context]);
}

function woosb_check_ready($wrap, context = null) {
    var qty = 0;
    var total = 0;
    var total_sale = 0;
    var is_selection = false;
    var selection_name = '';
    var is_unpurchasable = false;
    var unpurchasable_name = '';
    var is_empty = true;
    var is_min = false;
    var is_max = false;
    var is_total_min = false;
    var is_total_max = false;
    var wid = $wrap.attr('data-id');
    var $products = $wrap.find('.woosb-products');
    var $alert = $wrap.find('.woosb-alert');
    var $ids = jQuery('.woosb-ids-' + wid);
    var $btn = $ids.closest('form.cart').find('.single_add_to_cart_button');
    var price_suffix = $products.attr('data-price-suffix');
    var $total = $wrap.find('.woosb-total');
    var $count = $wrap.find('.woosb-count');
    var $price = jQuery('.woosb-price-' + wid);
    var $woobt = jQuery('.woobt-wrap-' + wid);
    var $woobt_products = $woobt.find('.woobt-products');
    var woobt_total = parseFloat($woobt_products.length ? $woobt.attr('data-total') : 0);
    var discount = parseFloat($products.attr('data-discount'));
    var discount_amount = parseFloat($products.attr('data-discount-amount'));
    var fixed_price = $products.attr('data-fixed-price') === 'yes';
    var has_optional = $products.attr('data-optional') === 'yes';
    var has_variables = $products.attr('data-variables') === 'yes';
    var exclude_unpurchasable = $products.attr('data-exclude-unpurchasable') === 'yes';
    var saved = '';
    var is_discount = discount > 0 && discount < 100;
    var is_discount_amount = discount_amount > 0;
    var qty_min = parseFloat($products.attr('data-min'));
    var qty_max = parseFloat($products.attr('data-max'));
    var total_min = parseFloat($products.attr('data-total-min'));
    var total_max = parseFloat($products.attr('data-total-max'));

    if (!$products.length || (!has_variables && !has_optional && !woosb_vars.recalc_price)) {
        // don't need to do anything - already calculated in PHP
        return;
    }

    // calculate price

    if (!fixed_price) {
        $products.find('.woosb-product').each(function () {
            var $this = jQuery(this);

            if ($this.hasClass('woosb-product-unpurchasable') && exclude_unpurchasable) {
                // don't count this product
                return;
            }

            if (parseFloat($this.attr('data-price')) > 0) {
                var _qty = parseFloat($this.attr('data-qty'));
                var _price = parseFloat($this.attr('data-price'));

                total += _price * _qty;

                if (!is_discount_amount && is_discount && woosb_vars.round_price) {
                    _price = woosb_round(_price * (100 - discount) / 100);
                }

                total_sale += _price * _qty;
            }
        });

        if (is_discount_amount && discount_amount < total) {
            total_sale = total - discount_amount;
            saved = woosb_format_price(discount_amount);
        } else if (is_discount) {
            if (!woosb_vars.round_price) {
                total_sale = woosb_round(total * (100 - discount) / 100);
            }

            saved = woosb_round(discount, 2) + '%';
        } else {
            total_sale = total;
        }

        var total_html = woosb_price_html(total, total_sale);
        var total_all_html = woosb_price_html(total + woobt_total, total_sale + woobt_total);

        if (saved !== '') {
            total_html += ' <small class="woocommerce-price-suffix">' + woosb_vars.saved_text.replace('[d]', saved) + '</small>';
        }

        // change the bundle total
        $total.html('<span class="woosb-total-label">' + woosb_vars.price_text + '</span> <span class="woosb-total-value">' + total_html + price_suffix + '</span>').slideDown();
        jQuery(document).trigger('woosb_change_total', [$total, total_html, price_suffix]);

        if (woosb_vars.change_price !== 'no') {
            // change the main price

            if (woosb_vars.change_price === 'yes_custom' && woosb_vars.price_selector != null && woosb_vars.price_selector !== '') {
                $price = jQuery(woosb_vars.price_selector);
            }

            if ($woobt_products.length) {
                // woobt
                $price.html(total_all_html + price_suffix);
            } else {
                if (typeof $price.attr('data-o_price') === 'undefined') {
                    $price.attr('data-o_price', woosb_encode_entities($price.html()));
                }

                $price.html(total_html + price_suffix);
            }
        }

        if ($woobt_products.length) {
            // woobt
            $woobt_products.attr('data-product-price-html', total_html);
            $woobt_products.find('.woobt-product-this').attr('data-price', total_sale).attr('data-regular-price', total);

            woobt_init($woobt);
        }

        jQuery(document).trigger('woosb_calc_price', [total_sale, total, total_html, price_suffix, $wrap]);
    }

    // check ready

    $products.find('.woosb-product').each(function () {
        var $this = jQuery(this);

        if (parseFloat($this.attr('data-qty')) > 0) {
            is_empty = false;
            qty += parseFloat($this.attr('data-qty'));

            if (parseInt($this.attr('data-id')) === 0) {
                is_selection = true;

                if (selection_name === '') {
                    selection_name = $this.attr('data-name');
                }
            }

            if ($this.hasClass('woosb-product-optional') && $this.hasClass('woosb-product-unpurchasable')) {
                is_unpurchasable = true;

                if (unpurchasable_name === '') {
                    unpurchasable_name = $this.attr('data-name');
                }
            }
        }
    });

    if (has_optional) {
        // check min
        if (qty_min > 0 && qty < qty_min) {
            is_min = true;
        }

        // check max
        if (qty_max > 0 && qty > qty_max) {
            is_max = true;
        }

        $count.html('<span class="woosb-count-label">' + woosb_vars.selected_text + '</span> <span class="woosb-count-value">' + qty + '</span>').slideDown();
        jQuery(document).trigger('woosb_change_count', [$count, qty, qty_min, qty_max]);
    }

    if (!fixed_price) {
        // check total min
        if (total_min > 0 && total_sale < total_min) {
            is_total_min = true;
        }

        // check total max
        if (total_max > 0 && total_sale > total_max) {
            is_total_max = true;
        }
    }

    if (is_selection || is_unpurchasable || is_empty || is_min || is_max || is_total_min || is_total_max) {
        $btn.addClass('woosb-disabled');

        if (is_selection) {
            $alert.html(woosb_vars.alert_selection.replace('[name]', '<strong>' + selection_name + '</strong>')).slideDown();
        } else if (is_unpurchasable) {
            $alert.html(woosb_vars.alert_unpurchasable.replace('[name]', '<strong>' + unpurchasable_name + '</strong>')).slideDown();
        } else if (is_empty) {
            $alert.html(woosb_vars.alert_empty).slideDown();
        } else if (is_min) {
            $alert.html(woosb_vars.alert_min.replace('[min]', qty_min).replace('[selected]', qty)).slideDown();
        } else if (is_max) {
            $alert.html(woosb_vars.alert_max.replace('[max]', qty_max).replace('[selected]', qty)).slideDown();
        } else if (is_total_min) {
            $alert.html(woosb_vars.alert_total_min.replace('[min]', woosb_format_price(total_min)).replace('[total]', woosb_format_price(total_sale))).slideDown();
        } else if (is_total_max) {
            $alert.html(woosb_vars.alert_total_max.replace('[max]', woosb_format_price(total_max)).replace('[total]', woosb_format_price(total_sale))).slideDown();
        }

        jQuery(document).trigger('woosb_check_ready', [false, is_selection, is_unpurchasable, is_empty, is_min, is_max, is_total_min, is_total_max, $wrap]);
    } else {
        $alert.html('').slideUp();
        $btn.removeClass('woosb-disabled');

        // ready
        jQuery(document).trigger('woosb_check_ready', [true, is_selection, is_unpurchasable, is_empty, is_min, is_max, is_total_min, is_total_max, $wrap]);
    }
}

function woosb_check_stock($wrap, context = null) {
    var wid = $wrap.attr('data-id');
    var $ids = jQuery('.woosb-ids-' + wid);
    var $products = $wrap.find('.woosb-products');
    var $qty = $ids.closest('form.cart').find('[name="quantity"]');
    var stock_arr = Array();
    var stock_min = 0;

    $products.find('.woosb-product').each(function () {
        var $this = jQuery(this);
        var id = parseInt($this.attr('data-id'));
        var qty = parseFloat($this.attr('data-qty'));
        var stock = parseFloat($this.attr('data-stock'));

        if (id > 0 && qty > 0 && (stock >= 0)) {
            stock_arr.push(Math.floor(stock / qty));
        }
    });

    stock_min = Math.min.apply(null, stock_arr);
    stock_min = isNaN(stock_min) ? 0 : stock_min;

    $qty.attr('max', stock_min);

    if ($qty.val() > stock_min) {
        $qty.val(stock_min).trigger('change');
    }

    jQuery(document).trigger('woosb_check_stock', [$wrap, context]);
}

function woosb_save_ids($wrap, context = null) {
    var ids = Array();
    var wid = $wrap.attr('data-id');
    var $ids = jQuery('.woosb-ids-' + wid);
    var $products = $wrap.find('.woosb-products');

    $products.find('.woosb-product').each(function () {
        var $this = jQuery(this);
        var id = parseInt($this.attr('data-id'));
        var key = $this.attr('data-key');
        var qty = parseFloat($this.attr('data-qty'));
        var attrs = $this.attr('data-attrs');

        if (id > 0 && qty > 0) {
            if (attrs !== undefined) {
                attrs = encodeURIComponent(attrs);
            } else {
                attrs = '';
            }

            ids.push(id + '/' + key + '/' + qty + '/' + attrs);
        }
    });

    $ids.val(ids.join(','));

    jQuery(document).trigger('woosb_save_ids', [ids, $wrap]);
}

function woosb_check_qty($qty) {
    var $wrap = $qty.closest('.woosb-wrap');
    var qty = parseFloat($qty.val());
    var min = parseFloat($qty.attr('min'));
    var max = parseFloat($qty.attr('max'));

    if (qty === '' || isNaN(qty)) {
        qty = 0;
    }

    if (!isNaN(min) && qty < min) {
        qty = min;
    }

    if (!isNaN(max) && qty > max) {
        qty = max;
    }

    $qty.val(qty);
    $qty.closest('.woosb-product').attr('data-qty', qty);

    // change subtotal
    if (woosb_vars.bundled_price === 'subtotal' || woosb_vars.bundled_price === 'subtotal_under_name') {
        var $products = $wrap.find('.woosb-products');
        var $product = $qty.closest('.woosb-product');
        var price_suffix = $product.attr('data-price-suffix');
        var ori_price = parseFloat($product.attr('data-price'));
        var qty = parseFloat($product.attr('data-qty'));
        var discount = parseFloat($products.attr('data-discount'));

        $product.find('.woosb-price-ori').hide();

        if (discount > 0 && $products.attr('data-fixed-price') === 'no') {
            var new_price = woosb_round(ori_price * (100 - discount) / 100);

            $product.find('.woosb-price-new').html(woosb_price_html(ori_price * qty, new_price * qty) + price_suffix).show();
        } else {
            $product.find('.woosb-price-new').html(woosb_price_html(ori_price * qty) + price_suffix).show();
        }
    }

    jQuery(document).trigger('woosb_check_qty', [qty, $qty]);

    woosb_init($wrap, 'woosb_check_qty');
}

function woosb_change_price($product, price, regular_price, price_html) {
    var $products = $product.closest('.woosb-products');
    var price_suffix = $product.attr('data-price-suffix');
    var qty = parseFloat($product.attr('data-qty'));
    var discount = parseFloat($products.attr('data-discount'));
    var new_price_html = '';

    // hide ori price
    $product.find('.woosb-price-ori').hide();

    // calculate new price
    if (woosb_vars.bundled_price === 'subtotal' || woosb_vars.bundled_price === 'subtotal_under_name') {
        var ori_price = parseFloat(price);

        if (woosb_vars.bundled_price_from === 'regular_price' && regular_price !== undefined) {
            ori_price = parseFloat(regular_price);
        }

        var new_price = ori_price;

        if (discount > 0) {
            new_price = woosb_round(ori_price * (100 - discount) / 100);
        }

        new_price_html = woosb_price_html(ori_price * qty, new_price * qty) + price_suffix;
    } else {
        if (discount > 0) {
            var ori_price = parseFloat(price);

            if (woosb_vars.bundled_price_from === 'regular_price' && regular_price !== undefined) {
                ori_price = parseFloat(regular_price);
            }

            var new_price = woosb_round(ori_price * (100 - discount) / 100);

            new_price_html = woosb_price_html(ori_price, new_price) + price_suffix;
        } else {
            if (woosb_vars.bundled_price_from === 'regular_price' && regular_price !== undefined) {
                new_price_html = woosb_price_html(regular_price) + price_suffix;
            } else if (price_html !== '') {
                new_price_html = price_html;
            }
        }
    }

    $product.find('.woosb-price-new').html(new_price_html).show();
    jQuery(document).trigger('woosb_change_price', [$product, new_price_html]);
}

function woosb_round(value, decimals = -1) {
    if (decimals < 0) {
        decimals = woosb_vars.price_decimals;
    }

    return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals);
}

function woosb_format_money(number, places, symbol, thousand, decimal) {
    number = number || 0;
    places = !isNaN(places = Math.abs(places)) ? places : 2;
    symbol = symbol !== undefined ? symbol : '$';
    thousand = thousand !== undefined ? thousand : ',';
    decimal = decimal !== undefined ? decimal : '.';

    var negative = number < 0 ? '-' : '', i = parseInt(number = Math.abs(+number || 0).toFixed(places), 10) + '', j = 0;

    if (i.length > 3) {
        j = i.length % 3;
    }

    if (woosb_vars.trim_zeros === '1') {
        return symbol + negative + (j ? i.substr(0, j) + thousand : '') + i.substr(j).replace(/(\d{3})(?=\d)/g, '$1' + thousand) + (places && (parseFloat(number) > parseFloat(i)) ? decimal + Math.abs(number - i).toFixed(places).slice(2).replace(/(\d*?[1-9])0+$/g, '$1') : '');
    } else {
        return symbol + negative + (j ? i.substr(0, j) + thousand : '') + i.substr(j).replace(/(\d{3})(?=\d)/g, '$1' + thousand) + (places ? decimal + Math.abs(number - i).toFixed(places).slice(2) : '');
    }
}

function woosb_format_price(price) {
    var price_html = '<span class="woocommerce-Price-amount amount">';
    var price_formatted = woosb_format_money(price, woosb_vars.wc_price_decimals, '', woosb_vars.wc_price_thousand_separator, woosb_vars.wc_price_decimal_separator);

    switch (woosb_vars.wc_price_format) {
        case '%1$s%2$s':
            //left
            price_html += '<span class="woocommerce-Price-currencySymbol">' + woosb_vars.wc_currency_symbol + '</span>' + price_formatted;
            break;
        case '%1$s %2$s':
            //left with space
            price_html += '<span class="woocommerce-Price-currencySymbol">' + woosb_vars.wc_currency_symbol + '</span> ' + price_formatted;
            break;
        case '%2$s%1$s':
            //right
            price_html += price_formatted + '<span class="woocommerce-Price-currencySymbol">' + woosb_vars.wc_currency_symbol + '</span>';
            break;
        case '%2$s %1$s':
            //right with space
            price_html += price_formatted + ' <span class="woocommerce-Price-currencySymbol">' + woosb_vars.wc_currency_symbol + '</span>';
            break;
        default:
            //default
            price_html += '<span class="woocommerce-Price-currencySymbol">' + woosb_vars.wc_currency_symbol + '</span> ' + price_formatted;
    }

    price_html += '</span>';

    return price_html;
}

function woosb_price_html(regular_price, sale_price) {
    var price_html = '';

    if (woosb_round(sale_price) < woosb_round(regular_price)) {
        price_html = '<del>' + woosb_format_price(regular_price) + '</del> <ins>' + woosb_format_price(sale_price) + '</ins>';
    } else {
        price_html = woosb_format_price(regular_price);
    }

    return price_html;
}

function woosb_decimal_places(num) {
    var match = ('' + num).match(/(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/);

    if (!match) {
        return 0;
    }

    return Math.max(0, // Number of digits right of decimal point.
        (match[1] ? match[1].length : 0) - // Adjust for scientific notation.
        (match[2] ? +match[2] : 0));
}

function woosb_encode_entities(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function woosb_decode_entities(str) {
    var textArea = document.createElement('textarea');
    textArea.innerHTML = str;
    return textArea.value;
}
