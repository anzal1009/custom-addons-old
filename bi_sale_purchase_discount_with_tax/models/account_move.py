# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_compare
from odoo.exceptions import UserError, ValidationError


class account_account(models.Model):
    _inherit = 'account.account'

    discount_account = fields.Boolean('Discount Account')


class account_move(models.Model):
    _inherit = 'account.move'

    is_line = fields.Boolean('Is a line')

    def _check_balanced(self):
        return True

        
    def calc_discount(self):
        for calculate in self:
            calculate._calculate_discount()

    @api.depends('discount_amount')
    def _calculate_discount(self):
        res = discount = 0.0
        for self_obj in self:
            if self_obj.discount_type == 'global':
                if self_obj.discount_method == 'fix':
                    res = self_obj.discount_amount
                elif self_obj.discount_method == 'per':
                    res = self_obj.amount_untaxed * (self_obj.discount_amount / 100)
            else:
                res = discount
        return res

    @api.depends(
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.debit',
        'line_ids.credit',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id', 'discount_method', 'discount_type', 'discount_amount')
    def _compute_amount(self):
        for move in self:
            if move.payment_state == 'invoicing_legacy':
                move.payment_state = move.payment_state
                continue

            total_untaxed = 0.0
            total_untaxed_currency = 0.0
            total_tax = 0.0
            total_tax_currency = 0.0
            total_to_pay = 0.0
            total_residual = 0.0
            total_residual_currency = 0.0
            total = 0.0
            total_currency = 0.0
            currencies = set()

            for line in move.line_ids:
                if line.currency_id:
                    currencies.add(line.currency_id)

                if move.is_invoice(include_receipts=True):

                    if not line.exclude_from_invoice_tab:
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.tax_line_id:
                        total_tax += line.balance
                        if move.currency_id == move.company_id.currency_id:
                            line.amount_currency = line.balance
                        else:
                            pass
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.account_id.user_type_id.type in ('receivable', 'payable'):
                        total_to_pay += line.balance
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    if line.debit:
                        total += line.balance
                        total_currency += line.amount_currency

            if move.move_type == 'entry' or move.is_outbound():
                sign = 1
            else:
                sign = -1
            move.amount_untaxed = sign * (total_untaxed_currency if len(currencies) == 1 else total_untaxed)
            move.amount_tax = sign * (total_tax_currency if len(currencies) == 1 else total_tax)
            if move.discount_amt_line:
                move.amount_total = sign * (total_currency if len(currencies) == 1 else total) - move.discount_amt_line
            elif move.discount_amt:
                move.amount_total = sign * (total_currency if len(currencies) == 1 else total) - move.discount_amt
            else:
                move.amount_total = sign * (total_currency if len(currencies) == 1 else total)

            move.amount_residual = -sign * (total_residual_currency if len(currencies) == 1 else total_residual)

            move.amount_untaxed_signed = -total_untaxed
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total

            move.amount_total_in_currency_signed = abs(move.amount_total) if move.move_type == 'entry' else -(sign * move.amount_total)

            move.amount_residual_signed = total_residual

            currency = len(currencies) == 1 and currencies.pop() or move.company_id.currency_id



            #
            # if move.move_type == 'entry' or move.is_outbound():
            #     sign = 1
            # else:
            #     sign = -1
            # move.amount_untaxed = sign * (total_untaxed_currency if len(currencies) == 1 else total_untaxed)
            # move.amount_tax = sign * (total_tax_currency if len(currencies) == 1 else total_tax)
            # move.amount_total = sign * (total_currency if len(currencies) == 1 else total)
            # move.amount_residual = -sign * (total_residual_currency if len(currencies) == 1 else total_residual)
            # move.amount_untaxed_signed = -total_untaxed
            # move.amount_tax_signed = -total_tax
            # move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
            # move.amount_residual_signed = total_residual
            # move.amount_total_in_currency_signed = abs(move.amount_total) if move.move_type == 'entry' else -(sign * move.amount_total)
            #
            # currency = currencies if len(currencies) == 1 else move.company_id.currency_id


           
            new_pmt_state = 'not_paid' if move.move_type != 'entry' else False

            if move.is_invoice(include_receipts=True) and move.state == 'posted':

                if currency.is_zero(move.amount_residual):
                    if all(payment.is_matched for payment in move._get_reconciled_payments()):
                        new_pmt_state = 'paid'
                    else:
                        new_pmt_state = move._get_invoice_in_payment_state()
                elif currency.compare_amounts(total_to_pay, total_residual) != 0:
                    new_pmt_state = 'partial'

            if new_pmt_state == 'paid' and move.move_type in ('in_invoice', 'out_invoice', 'entry'):
                reverse_type = move.move_type == 'in_invoice' and 'in_refund' or move.move_type == 'out_invoice' and 'out_refund' or 'entry'
                reverse_moves = self.env['account.move'].search(
                    [('reversed_entry_id', '=', move.id), ('state', '=', 'posted'), ('move_type', '=', reverse_type)])

               
                reverse_moves_full_recs = reverse_moves.mapped('line_ids.full_reconcile_id')
                if reverse_moves_full_recs.mapped('reconciled_line_ids.move_id').filtered(lambda x: x not in (
                        reverse_moves + reverse_moves_full_recs.mapped('exchange_move_id'))) == move:
                    new_pmt_state = 'reversed'

            move.payment_state = new_pmt_state

        # res_config = self.env['res.config.settings'].sudo().search([], order="id desc", limit=1)
        tax_discount_policy = self.env["ir.config_parameter"].sudo().get_param(
            "bi_sale_purchase_discount_with_tax.tax_discount_policy")
        sale_account_id = self.env["ir.config_parameter"].sudo().get_param(
            "bi_sale_purchase_discount_with_tax.sale_account_id")
        purchase_account_id = self.env["ir.config_parameter"].sudo().get_param(
            "bi_sale_purchase_discount_with_tax.purchase_account_id")
        if tax_discount_policy:
            for rec in self:
                if tax_discount_policy == 'tax':
                    if rec.discount_type == 'line':
                        rec.discount_amt = 0.00
                        total = 0
                        if self._context.get('default_move_type') in ['in_invoice', 'in_receipt', 'in_refund']:
                            for line in self.invoice_line_ids:
                                if line.discount_method == 'per':
                                    total += line.price_subtotal * (line.discount_amount / 100)
                                elif line.discount_method == 'fix':
                                    total += line.discount_amount
                            rec.discount_amt_line = total
                        if self._context.get('default_move_type') in ['out_invoice', 'out_receipt', 'out_refund']:
                            for line in self.invoice_line_ids:
                                if line.discount_method == 'per':
                                    total += line.price_subtotal * (line.discount_amount / 100)
                                elif line.discount_method == 'fix':
                                    total += line.discount_amount
                            rec.discount_amt_line = total
                        rec.amount_total = rec.amount_tax + rec.amount_untaxed - rec.discount_amt_line

                    elif rec.discount_type == 'global':
                        if rec.discount_method == 'fix':
                            rec.discount_amt = rec.discount_amount
                            rec.amount_total = rec.amount_tax + rec.amount_untaxed - rec.discount_amt
                        elif rec.discount_method == 'per':
                            rec.discount_amt = (rec.amount_untaxed) * (rec.discount_amount / 100.0)
                            rec.amount_total = rec.amount_tax + rec.amount_untaxed - rec.discount_amt
                        else:
                            rec.amount_total = rec.amount_tax + rec.amount_untaxed
                    else:
                        rec.amount_total = rec.amount_tax + rec.amount_untaxed
                elif tax_discount_policy == 'untax':
                    sums = 0.00
                    if rec.discount_type == 'line':
                        total = 0
                        if self._context.get('default_move_type') in ['in_invoice', 'in_receipt', 'in_refund']:
                            for line in self.invoice_line_ids:
                                if line.discount_method == 'per':
                                    total += line.price_unit * (line.discount_amount / 100)
                                elif line.discount_method == 'fix':
                                    total += line.discount_amount
                            rec.discount_amt_line = total
                        if self._context.get('default_move_type') in ['out_invoice', 'out_receipt', 'out_refund']:
                            for line in self.invoice_line_ids:
                                if line.discount_method == 'per':
                                    total += line.price_unit * (line.discount_amount / 100) * line.quantity
                                elif line.discount_method == 'fix':
                                    total += line.discount_amount
                            rec.discount_amt_line = total
                        rec.amount_total = rec.amount_tax + rec.amount_untaxed - rec.discount_amt_line
                        rec.discount_amt = 0.00
                    elif rec.discount_type == 'global':
                        if rec.discount_method == 'fix':
                            rec.discount_amt = self._calculate_discount()
                            if rec.invoice_line_ids:
                                for line in rec.invoice_line_ids:
                                    if line.tax_ids:
                                        if rec.amount_untaxed:
                                            final_discount = (
                                                        (rec.discount_amt * line.price_subtotal) / rec.amount_untaxed)
                                            discount = line.price_subtotal - final_discount

                                            taxes = line.tax_ids.compute_all(discount, rec.currency_id, 1.0,
                                                                             line.product_id, rec.partner_id)
                                            sums += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                            rec.amount_total = sums + rec.amount_untaxed - rec.discount_amt
                            rec.update({'amount_tax': sums})
                        elif rec.discount_method == 'per':
                            rec.discount_amt = self._calculate_discount()
                            if rec.invoice_line_ids:
                                for line in rec.invoice_line_ids:
                                    if line.tax_ids:
                                        final_discount = ((rec.discount_amount * line.price_subtotal) / 100.0)
                                        discount = line.price_subtotal - final_discount

                                        taxes = line.tax_ids._origin.compute_all(discount, rec.currency_id, 1.0,
                                                                                 line.product_id, rec.partner_id)
                                        sums += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                            rec.amount_total = sums + rec.amount_untaxed - rec.discount_amt
                            rec.update({'amount_tax': sums})
                    else:
                        rec.amount_total = rec.amount_tax + rec.amount_untaxed - rec.discount_amt
                else:
                    rec.amount_total = rec.amount_tax + rec.amount_untaxed - rec.discount_amt
                if rec.discount_amt_line or rec.discount_amt:
                    if rec.move_type in ['out_invoice', 'out_receipt', 'out_refund']:
                        if sale_account_id:
                            rec.discount_account_id = int(sale_account_id)

                        else:
                            account_id = False
                            account_id = rec.env['account.account'].sudo().search(
                                [('user_type_id.name', '=', 'Expenses'), ('discount_account', '=', True)], limit=1)
                            if not account_id:
                                raise UserError(_('Please define an sale discount account for this company.'))
                            else:
                                rec.discount_account_id = account_id.id

                    if rec.move_type in ['in_invoice', 'in_receipt', 'in_refund']:
                        if purchase_account_id:
                            rec.discount_account_id = int(purchase_account_id)
                        else:
                            account_id = False
                            account_id = rec.env['account.account'].sudo().search(
                                [('user_type_id.name', '=', 'Income'), ('discount_account', '=', True)], limit=1)
                            if not account_id:
                                raise UserError(_('Please define an purchase discount account for this company.'))
                            else:
                                rec.discount_account_id = account_id.id

    discount_method = fields.Selection([('fix', 'Fixed'), ('per', 'Percentage')], 'Discount Method')
    discount_amount = fields.Float('Discount Amount')
    discount_amt = fields.Float(string='Discount', readonly=True, store=True, digits='Discount',
                                compute='_compute_amount')
    amount_untaxed = fields.Float(string='Subtotal', digits='Account', store=True, readonly=True,
                                  compute='_compute_amount', tracking=True)
    amount_tax = fields.Float(string='Tax', digits='Account', store=True, readonly=True, compute='_compute_amount')
    amount_total = fields.Float(string='Total', digits='Account', store=True, readonly=True, compute='_compute_amount')
    discount_type = fields.Selection([('line', 'Order Line'), ('global', 'Global')], 'Discount Applies to',
                                     default='global')
    discount_account_id = fields.Many2one('account.account', 'Discount Account', compute='_compute_amount', store=True)
    discount_amt_line = fields.Float(compute='_compute_amount', string='Line Discount', digits='Discount', store=True,
                                     readonly=True)
    discount_amount_line = fields.Float(string="Discount Line")

    def _recompute_tax_lines(self, recompute_tax_base_amount=False):
        self.ensure_one()
        in_draft_mode = self != self._origin

        def _serialize_tax_grouping_key(grouping_dict):
            return '-'.join(str(v) for v in grouping_dict.values())

        def _compute_base_line_taxes(base_line):
            move = base_line.move_id

            if move.is_invoice(include_receipts=True):
                handle_price_include = True
                sign = -1 if move.is_inbound() else 1
                quantity = base_line.quantity
                is_refund = move.move_type in ('out_refund', 'in_refund')
                price_unit_wo_discount = sign * base_line.price_unit * (1 - (base_line.discount / 100.0))
            else:
                handle_price_include = False
                quantity = 1.0
                tax_type = base_line.tax_ids[0].type_tax_use if base_line.tax_ids else None
                is_refund = (tax_type == 'sale' and base_line.debit) or (tax_type == 'purchase' and base_line.credit)
                price_unit_wo_discount = base_line.balance

            # res_config = self.env['res.config.settings'].sudo().search([], order="id desc", limit=1)
            tax_discount_policy = self.env["ir.config_parameter"].sudo().get_param(
                "bi_sale_purchase_discount_with_tax.tax_discount_policy")
            if tax_discount_policy:
                for rec in self:
                    if tax_discount_policy == 'untax':

                        if rec.discount_type == 'line':
                            if base_line.discount_method == 'fix':
                                quantity = 1.0
                                price_unit_wo_discount = base_line.price_subtotal - base_line.discount_amount
                            elif base_line.discount_method == 'per':
                                quantity = 1.0
                                price_unit_wo_discount = base_line.price_subtotal * (
                                            1 - (base_line.discount_amount / 100.0))
                            else:
                                if self._context.get('default_move_type') in ['out_invoice', 'out_receipt']:
                                    price_unit_wo_discount = -(price_unit_wo_discount)
                                else:
                                    pass

                        elif rec.discount_type == 'global':
                            if rec.amount_untaxed != 0.0:
                                final_discount = ((rec.discount_amt * base_line.price_subtotal) / rec.amount_untaxed)
                                price_unit_wo_discount = base_line.price_subtotal - rec.currency_id.round(
                                    final_discount)
                            else:
                                final_discount = (rec.discount_amt * base_line.price_subtotal) / 1.0
                                discount = base_line.price_subtotal - rec.currency_id.round(final_discount)

                    else:
                        if self._context.get('default_move_type') in ['out_invoice', 'out_receipt']:
                            sign = -(sign)
                        else:
                            pass

                price_unit_wo_discount = sign * price_unit_wo_discount

            balance_taxes_res = base_line.tax_ids._origin.compute_all(
                price_unit_wo_discount,
                currency=base_line.currency_id,
                quantity=1 if tax_discount_policy == 'untax' else quantity,
                product=base_line.product_id,
                partner=base_line.partner_id,
                is_refund=is_refund,
                handle_price_include=handle_price_include,
            )
            if move.move_type == 'entry':
                repartition_field = is_refund and 'refund_repartition_line_ids' or 'invoice_repartition_line_ids'
                repartition_tags = base_line.tax_ids.mapped(repartition_field).filtered(
                    lambda x: x.repartition_type == 'base').tag_ids
                tags_need_inversion = (tax_type == 'sale' and not is_refund) or (tax_type == 'purchase' and is_refund)
                if tags_need_inversion:
                    balance_taxes_res['base_tags'] = base_line._revert_signed_tags(repartition_tags).ids
                    for tax_res in balance_taxes_res['taxes']:
                        tax_res['tag_ids'] = base_line._revert_signed_tags(
                            self.env['account.account.tag'].browse(tax_res['tag_ids'])).ids

            return balance_taxes_res

        taxes_map = {}

        to_remove = self.env['account.move.line']
        for line in self.line_ids.filtered('tax_repartition_line_id'):
            grouping_dict = self._get_tax_grouping_key_from_tax_line(line)
            grouping_key = _serialize_tax_grouping_key(grouping_dict)
            if grouping_key in taxes_map:
                to_remove += line
            else:
                taxes_map[grouping_key] = {
                    'tax_line': line,
                    'amount': 0.0,
                    'tax_base_amount': 0.0,
                    'grouping_dict': False,
                }
        self.line_ids -= to_remove
        for line in self.line_ids.filtered(lambda line: not line.tax_repartition_line_id):
            if not line.tax_ids:
                line.tax_tag_ids = [(5, 0, 0)]
                continue

            compute_all_vals = _compute_base_line_taxes(line)
            line.tax_tag_ids = compute_all_vals['base_tags']

            for tax_vals in compute_all_vals['taxes']:
                grouping_dict = self._get_tax_grouping_key_from_base_line(line, tax_vals)
                grouping_key = _serialize_tax_grouping_key(grouping_dict)
                tax_repartition_line = self.env['account.tax.repartition.line'].browse(
                    tax_vals['tax_repartition_line_id'])
                tax = tax_repartition_line.invoice_tax_id or tax_repartition_line.refund_tax_id


                taxes_map_entry = taxes_map.setdefault(grouping_key, {
                    'tax_line': None,
                    'amount': 0.0,
                    'tax_base_amount': 0.0,
                    'grouping_dict': False,
                })
                if self.discount_type == 'global':
                    taxes_map_entry['amount'] += tax_vals['amount'] / line.quantity * line.quantity
                else:
                    taxes_map_entry['amount'] += tax_vals['amount']
                taxes_map_entry['tax_base_amount'] += tax_vals['base']
                taxes_map_entry['grouping_dict'] = grouping_dict

        for taxes_map_entry in taxes_map.values():
         
            if taxes_map_entry['tax_line'] and not taxes_map_entry['grouping_dict']:
                self.line_ids -= taxes_map_entry['tax_line']
                continue

            currency = self.env['res.currency'].browse(taxes_map_entry['grouping_dict']['currency_id'])

          
            if currency.is_zero(taxes_map_entry['amount']):
                if taxes_map_entry['tax_line']:
                    self.line_ids -= taxes_map_entry['tax_line']
                continue

            tax_base_amount = (-1 if self.is_inbound() else 1) * taxes_map_entry['tax_base_amount']
        
            tax_base_amount = currency._convert(tax_base_amount, self.company_currency_id, self.company_id,
                                                self.date or fields.Date.context_today(self))

        
            if taxes_map_entry['tax_line'] and recompute_tax_base_amount:
                taxes_map_entry['tax_line'].tax_base_amount = tax_base_amount
                continue
            balance = currency._convert(
                taxes_map_entry['amount'],
                self.journal_id.company_id.currency_id,
                self.journal_id.company_id,
                self.date or fields.Date.context_today(self),
            )

            to_write_on_line = {
                'amount_currency': taxes_map_entry['amount'],
                'currency_id': taxes_map_entry['grouping_dict']['currency_id'],
                'debit': balance > 0.0 and balance or 0.0,
                'credit': balance < 0.0 and -balance or 0.0,
                'tax_base_amount': tax_base_amount,
            }

            if taxes_map_entry['tax_line']:
             
                taxes_map_entry['tax_line'].update(to_write_on_line)
            else:
                create_method = in_draft_mode and self.env['account.move.line'].new or self.env[
                    'account.move.line'].create
                tax_repartition_line_id = taxes_map_entry['grouping_dict']['tax_repartition_line_id']
                tax_repartition_line = self.env['account.tax.repartition.line'].browse(tax_repartition_line_id)
                tax = tax_repartition_line.invoice_tax_id or tax_repartition_line.refund_tax_id
                taxes_map_entry['tax_line'] = create_method({
                    **to_write_on_line,
                    'name': tax.name,
                    'move_id': self.id,
                    'partner_id': line.partner_id.id,
                    'company_id': line.company_id.id,
                    'company_currency_id': line.company_currency_id.id,
                    'tax_base_amount': tax_base_amount,
                    'exclude_from_invoice_tab': True,
                    **taxes_map_entry['grouping_dict'],
                })

            if in_draft_mode:
                taxes_map_entry['tax_line'].update(
                    taxes_map_entry['tax_line']._get_fields_onchange_balance(force_computation=True))

    @api.model_create_multi
    def create(self, vals_list):
      

        if any('state' in vals and vals.get('state') == 'posted' for vals in vals_list):
            raise UserError(
                _('You cannot create a move already in the posted state. Please create a draft move and post it after.'))

        vals_list = self._move_autocomplete_invoice_lines_create(vals_list)

        rslt = super(account_move, self).create(vals_list)
        # if 'line_ids' in vals_list:
        #     rslt.update_lines_tax_exigibility()
        # res_config = self.env['res.config.settings'].sudo().search([], order="id desc", limit=1)
        tax_discount_policy = self.env["ir.config_parameter"].sudo().get_param(
            "bi_sale_purchase_discount_with_tax.tax_discount_policy")
        if tax_discount_policy:
            for res in rslt:
                for line in res.line_ids:
                    name = line.name
                    if res.discount_type == 'line':
                        price = res.discount_amt_line

                    elif res.discount_type == 'global':
                        price = res.discount_amt
                    else:
                        price = 0
                if res.line_ids:
                    if name != 'Discount':
                        if res.discount_account_id:
                            discount_vals = {
                                'account_id': res.discount_account_id,
                                'quantity': 1,
                                'price_unit': -price,
                                'name': "Discount",
                                'exclude_from_invoice_tab': True,
                                'amount_currency': 200
                            }
                            res.with_context(check_move_validity=False).write({
                                'invoice_line_ids': [(0, 0, discount_vals)]

                            })
#             for line in rslt.line_ids:
#                 name = line.name
#             if rslt.discount_type == 'line':
#                 price = rslt.discount_amt_line
            
#             elif rslt.discount_type == 'global':
#                 price = rslt.discount_amt
#             else:
#                 price = 0
#             if rslt.line_ids:
#                 if name != 'Discount':
#                     if rslt.discount_account_id:
#                         discount_vals = {
#                             'account_id': rslt.discount_account_id,
#                             'quantity': 1,
#                             'price_unit': -price,
#                             'name': "Discount",
#                             'exclude_from_invoice_tab': True,
#                             'amount_currency': 200
#                         }
#                         rslt.with_context(check_move_validity=False).write({
#                             'invoice_line_ids': [(0, 0, discount_vals)]
            
#                         })
        return rslt

    @api.onchange('invoice_line_ids', 'discount_amount', 'discount_method')
    def _onchange_invoice_line_ids(self):
        current_invoice_lines = self.line_ids.filtered(lambda line: not line.exclude_from_invoice_tab)
        others_lines = self.line_ids - current_invoice_lines
        if others_lines and current_invoice_lines - self.invoice_line_ids:
            others_lines[0].recompute_tax_line = True
        self.line_ids = others_lines + self.invoice_line_ids
        self._onchange_recompute_dynamic_lines()
        if self._context.get('default_move_type') == 'out_invoice':
            total = 0.0
            for line in self.invoice_line_ids:
                if line.discount_method == 'per':
                    total += line.price_unit * (line.discount_amount / 100)
             
                elif line.discount_method == 'fix':
                    total += line.discount_amount
            self.discount_amount_line = total

    @api.onchange('invoice_vendor_bill_id')
    def _onchange_invoice_vendor_bill(self):
        if self.invoice_vendor_bill_id:
            
            for line in self.invoice_vendor_bill_id.invoice_line_ids:
                copied_vals = line.copy_data()[0]
                copied_vals['move_id'] = self.id
                new_line = self.env['account.move.line'].new(copied_vals)
                new_line.recompute_tax_line = True

          
            self.invoice_payment_term_id = self.invoice_vendor_bill_id.invoice_payment_term_id

         
            if self.currency_id != self.invoice_vendor_bill_id.currency_id:
                self.currency_id = self.invoice_vendor_bill_id.currency_id

           
            self.invoice_vendor_bill_id = False
            self._recompute_dynamic_lines()

    @api.depends('discount_amount', 'discount_method', 'discount_type')
    def write(self, vals):

        res = super(account_move, self).write(vals)

        for move in self:
            for rec in move.line_ids:
                if move._context.get('default_move_type') in ['in_invoice', 'in_receipt', 'out_refund']:
                    if rec.name == False or rec.name == '':
                        rec.with_context(check_move_validity=False).write({'credit': move.amount_total})
                    if move.discount_type != 'line':
                        if rec.name == "Discount":
                            rec.with_context(check_move_validity=False).write({'credit': move.discount_amt})

                    if move.discount_type == 'line':
                        if rec.name == "Discount":
                            rec.with_context(check_move_validity=False).write({'credit': move.discount_amt_line})

                if move._context.get('default_move_type') in ['out_invoice', 'out_receipt', 'in_refund']:

                    if move.discount_type != 'line':
                        if rec.name == "Discount":
                            rec.with_context(check_move_validity=False).write({'debit': move.discount_amt})

                    if move.discount_type == 'line':
                        if rec.name == "Discount":
                            rec.with_context(check_move_validity=False).write({'debit': move.discount_amt_line})
        return res

    @api.onchange('discount_amount', 'discount_method')
    def _onchange_taxes(self):
        for line in self.line_ids:
            if not line.tax_repartition_line_id:
                line.recompute_tax_line = True


class account_payment(models.Model):
    _inherit = "account.payment"

    def _prepare_payment_moves(self):
        res = super(account_payment, self)._prepare_payment_moves()
        for rec in res:
            rec.update({'flag': True})
        return res


class account_move_line(models.Model):
    _inherit = 'account.move.line'

    discount_method = fields.Selection([('fix', 'Fixed'), ('per', 'Percentage')], 'Discount Method')
    discount_type = fields.Selection(related='move_id.discount_type', string="Discount Applies to")
    discount_amount = fields.Float('Discount Amount')
    discount_amt = fields.Float('Discount Final Amount')

    @api.onchange('product_id', 'discount_method', 'discount_amount', 'amount_currency', 'currency_id', 'debit',
                  'credit', 'tax_ids', 'account_id', )
    def _onchange_mark_recompute_taxes(self):
        for line in self:
            if not line.tax_repartition_line_id:
                line.recompute_tax_line = True
