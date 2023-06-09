# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.


from odoo import models, api
from datetime import date
from odoo.tools.float_utils import float_round


class sales_daybook_product_category_report(models.AbstractModel):
    _name = 'report.inventory_valuation_reports.sales_daybook_template'
    _description = 'Report bi_inventory_valuation_reports.sales_daybook_template'

    def _get_report_values(self, docids, data=None):
        data = data if data is not None else {}
        docs = self.env['sale.day.book.wizard'].browse(docids)
        data  = {'product_ids':docs.product_ids , 'filter_by':docs.filter_by,'start_date': docs.start_date, 'end_date': docs.end_date,'warehouse':docs.warehouse,'category':docs.category,'location_id':docs.location_id,'company_id':docs.company_id.name,'display_sum':docs.display_sum,'currency':docs.company_id.currency_id.name}
        return {
                   'doc_model': 'sale.day.book.wizard',
                   'data' : data,
                   'get_warehouse' : self._get_warehouse_name,
                   'get_lines': self._get_lines,
                   'get_data' : self._get_data,
                   'currency' : self.env.user.company_id.currency_id,
                   }

    def _get_warehouse_name(self,data):
        if data:
            l1 = []
            l2 = []
            for i in data:
                l1.append(i.name)
                myString = ",".join(l1 )
            return myString
        return ''

    def _get_company(self, data):
        if data['company_id']:
            l1 = []
            l2 = []
            obj = self.env['res.company'].search([('name', '=', data['company_id'])])
            l1.append(obj.name)
            return l1
        return ''

    def _get_currency(self,data):
        if data['company_id']:
            l1 = []
            l2 = []
            obj = self.env['res.company'].search([('name', '=', data['company_id'])])
            l1.append(obj.currency_id.name)
            return l1
        return ''


    def _compute_quantities_product_quant_dic(self,lot_id, owner_id, package_id,from_date,to_date,product_obj,data):
        loc_list = []
        domain_quant_loc, domain_move_in_loc, domain_move_out_loc = product_obj._get_domain_locations()
        custom_domain = []
        custom_dest_domain = []
        custom_location_domain = []
        locations = []
        if data['company_id']:
            obj = self.env['res.company'].search([('name', '=', data['company_id'])])
            custom_domain.append(('company_id','=',obj.id))
            custom_dest_domain.append(('company_id', '=', obj.id))
            custom_location_domain.append(('company_id', '=', obj.id))
        if data['location_id'] :
            custom_domain.append(('location_id','=',data['location_id'].id))
            custom_dest_domain.append(('location_dest_id', '=', data['location_id'].id))
            custom_location_domain.append(('location_id', '=', data['location_id'].id))
            # Added by kabeer 23/05/2022
            locations = [data['location_id'].id]
        # if data['warehouse']:
        if data['warehouse'] and not data['location_id']:
            ware_check_domain = [a.id for a in data['warehouse']]
            locations = []
            for i in ware_check_domain:
                loc_ids = self.env['stock.warehouse'].search([('id','=',i)])
                locations.append(loc_ids.view_location_id.id)
                for i in loc_ids.view_location_id.child_ids :
                  locations.append(i.id)
                loc_list.append(loc_ids.lot_stock_id.id)
            custom_domain.append(('location_id','in',locations))
            custom_dest_domain.append(('location_dest_id','in',locations))
            custom_location_domain.append(('location_id','in',locations))
        if not data['location_id'] and not data['warehouse']:
            ware_check_domain = [a.id for a in self.env['stock.warehouse'].search([])]
            locations = []
            for i in ware_check_domain:
                loc_ids = self.env['stock.warehouse'].search([('id', '=', i)])
                locations.append(loc_ids.view_location_id.id)
                for i in loc_ids.view_location_id.child_ids:
                    locations.append(i.id)
                loc_list.append(loc_ids.lot_stock_id.id)
            custom_domain.append(('location_id', 'in', locations))
            custom_dest_domain.append(('location_dest_id', 'in', locations))
            custom_location_domain.append(('location_id', 'in', locations))

        # domain_quant = [('product_id', 'in', product_obj.ids)] + domain_quant_loc + custom_domain
        domain_quant = [('product_id', 'in', product_obj.ids)] + domain_quant_loc + custom_domain + [('date','<',from_date)]
        domain_dest_quant = [('product_id', 'in', product_obj.ids)] + custom_dest_domain + [('date','<',from_date)]
        domain_location_quant = [('product_id', 'in', product_obj.ids)] + custom_location_domain + [('date','<',from_date)]
        dates_in_the_past = False
        # only to_date as to_date will correspond to qty_available
        if to_date and to_date < date.today():
            dates_in_the_past = True
        domain_move_in = [('product_id', 'in', product_obj.ids),('location_dest_id','in',locations)] + domain_move_in_loc
        domain_move_out = [('product_id', 'in', product_obj.ids)] + domain_move_out_loc + custom_domain
        if lot_id is not None:
            domain_quant += [('lot_id', '=', lot_id)]
            domain_dest_quant += [('lot_id', '=', lot_id)]
            domain_location_quant += [('lot_id', '=', lot_id)]
        if owner_id is not None:
            domain_quant += [('owner_id', '=', owner_id)]
            domain_dest_quant += [('owner_id', '=', owner_id)]
            domain_location_quant += [('owner_id', '=', owner_id)]
            domain_move_in += [('restrict_partner_id', '=', owner_id)]
            domain_move_out += [('restrict_partner_id', '=', owner_id)]
        if package_id is not None:
            domain_quant += [('package_id', '=', package_id)]
            domain_dest_quant += [('package_id', '=', package_id)]
            domain_location_quant += [('package_id', '=', package_id)]
        if dates_in_the_past:
            domain_move_in_done = list(domain_move_in)
            domain_move_out_done = list(domain_move_out)
        if from_date:
            domain_move_in += [('date', '>=', from_date)]
            domain_move_out += [('date', '>=', from_date)]
        if to_date:
            domain_move_in += [('date', '<=', to_date)]
            domain_move_out += [('date', '<=', to_date)]
        # print('domain_quant',domain_quant)
        Move = self.env['stock.move']
        MoveLine = self.env['stock.move.line']
        Quant = self.env['stock.quant']
        domain_move_in_todo = [('state', 'in', ('waiting', 'confirmed', 'assigned', 'partially_available'))] + domain_move_in
        domain_move_out_todo = [('state', 'in', ('waiting', 'confirmed', 'assigned', 'partially_available'))] + domain_move_out
        moves_in_res = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_in_todo, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
        moves_out_res = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_out_todo, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
        # quants_res = dict((item['product_id'][0], item['quantity']) for item in Quant.read_group(domain_quant, ['product_id', 'quantity'], ['product_id'], orderby='id'))
        domain_dest_quant += [('state', 'in', ['done'])]
        domain_location_quant += [('state', 'in', ['done'])]
        quants_res_out = dict((item['product_id'][0], item['qty_done']) for item in MoveLine.read_group(domain_dest_quant, ['product_id', 'qty_done'], ['product_id'], orderby='id'))
        quants_res_in = dict((item['product_id'][0], item['qty_done']) for item in MoveLine.read_group(domain_location_quant, ['product_id', 'qty_done'], ['product_id'], orderby='id'))
        q_res = {}
        for k, v in quants_res_out.items():
            q_res[k] = v - quants_res_in.get(k, 0)
        quants_res = q_res
        # print('quants_res',quants_res)
        # print('dates_in_the_past',dates_in_the_past)
        if dates_in_the_past:
            # Calculate the moves that were done before now to calculate back in time (as most questions will be recent ones)
            domain_move_in_done = [('state', '=', 'done'), ('date', '>', to_date)] + domain_move_in_done
            domain_move_out_done = [('state', '=', 'done'), ('date', '>', to_date)] + domain_move_out_done
            moves_in_res_past = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_in_done, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
            moves_out_res_past = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_out_done, ['product_id', 'product_qty'], ['product_id'], orderby='id'))

        res = dict()
        for product in product_obj.with_context(prefetch_fields=False):
            product_id = product.id
            rounding = product.uom_id.rounding
            res[product_id] = {}
            # Comemnted by kabeer at 23-05-2022
            # if dates_in_the_past:
            #     qty_available = quants_res.get(product_id, 0.0) - moves_in_res_past.get(product_id, 0.0) + moves_out_res_past.get(product_id, 0.0)
            # else:
            #     qty_available = quants_res.get(product_id, 0.0)
            qty_available = quants_res.get(product_id, 0.0)
            # Comemnted by kabeer at 23-05-2022 ends here

            res[product_id]['qty_available'] = float_round(qty_available, precision_rounding=rounding)
            res[product_id]['incoming_qty'] = float_round(moves_in_res.get(product_id, 0.0), precision_rounding=rounding)
            res[product_id]['outgoing_qty'] = float_round(moves_out_res.get(product_id, 0.0), precision_rounding=rounding)
            res[product_id]['virtual_available'] = float_round(
                qty_available + res[product_id]['incoming_qty'] - res[product_id]['outgoing_qty'],
                precision_rounding=rounding)
        return res





    # def _compute_quantities_product_quant_dic(self,lot_id, owner_id, package_id,from_date,to_date,product_obj,data):
    #     loc_list = []
    #     domain_quant_loc, domain_move_in_loc, domain_move_out_loc = product_obj._get_domain_locations()
    #     custom_domain = []
    #     locations = []
    #     if data['company_id']:
    #         obj = self.env['res.company'].search([('name', '=', data['company_id'])])
    #         custom_domain.append(('company_id','=',obj.id))
    #     if data['location_id'] :
    #         custom_domain.append(('location_id','=',data['location_id'].id))
    #         # Added by kabeer 23/05/2022
    #         locations = [data['location_id'].id]
    #     # if data['warehouse']:
    #     if data['warehouse'] and not data['location_id']:
    #         ware_check_domain = [a.id for a in data['warehouse']]
    #         locations = []
    #         for i in ware_check_domain:
    #             loc_ids = self.env['stock.warehouse'].search([('id','=',i)])
    #             locations.append(loc_ids.view_location_id.id)
    #             for i in loc_ids.view_location_id.child_ids :
    #               locations.append(i.id)
    #             loc_list.append(loc_ids.lot_stock_id.id)
    #         custom_domain.append(('location_id','in',locations))
    #
    #     # domain_quant = [('product_id', 'in', product_obj.ids)] + domain_quant_loc + custom_domain
    #     domain_quant = [('product_id', 'in', product_obj.ids)] + domain_quant_loc + custom_domain + [('in_date','<',from_date)]
    #     dates_in_the_past = False
    #     # only to_date as to_date will correspond to qty_available
    #     if to_date and to_date < date.today():
    #         dates_in_the_past = True
    #     domain_move_in = [('product_id', 'in', product_obj.ids),('location_dest_id','in',locations)] + domain_move_in_loc
    #     domain_move_out = [('product_id', 'in', product_obj.ids)] + domain_move_out_loc + custom_domain
    #     if lot_id is not None:
    #         domain_quant += [('lot_id', '=', lot_id)]
    #     if owner_id is not None:
    #         domain_quant += [('owner_id', '=', owner_id)]
    #         domain_move_in += [('restrict_partner_id', '=', owner_id)]
    #         domain_move_out += [('restrict_partner_id', '=', owner_id)]
    #     if package_id is not None:
    #         domain_quant += [('package_id', '=', package_id)]
    #     if dates_in_the_past:
    #         domain_move_in_done = list(domain_move_in)
    #         domain_move_out_done = list(domain_move_out)
    #     if from_date:
    #         domain_move_in += [('date', '>=', from_date)]
    #         domain_move_out += [('date', '>=', from_date)]
    #     if to_date:
    #         domain_move_in += [('date', '<=', to_date)]
    #         domain_move_out += [('date', '<=', to_date)]
    #     print('domain_quant',domain_quant)
    #     Move = self.env['stock.move']
    #     Quant = self.env['stock.quant']
    #     domain_move_in_todo = [('state', 'in', ('waiting', 'confirmed', 'assigned', 'partially_available'))] + domain_move_in
    #     domain_move_out_todo = [('state', 'in', ('waiting', 'confirmed', 'assigned', 'partially_available'))] + domain_move_out
    #     moves_in_res = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_in_todo, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
    #     moves_out_res = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_out_todo, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
    #     quants_res = dict((item['product_id'][0], item['quantity']) for item in Quant.read_group(domain_quant, ['product_id', 'quantity'], ['product_id'], orderby='id'))
    #     print('quants_res',quants_res)
    #     print('dates_in_the_past',dates_in_the_past)
    #     if dates_in_the_past:
    #         # Calculate the moves that were done before now to calculate back in time (as most questions will be recent ones)
    #         domain_move_in_done = [('state', '=', 'done'), ('date', '>', to_date)] + domain_move_in_done
    #         domain_move_out_done = [('state', '=', 'done'), ('date', '>', to_date)] + domain_move_out_done
    #         moves_in_res_past = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_in_done, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
    #         moves_out_res_past = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_out_done, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
    #
    #     res = dict()
    #     for product in product_obj.with_context(prefetch_fields=False):
    #         product_id = product.id
    #         rounding = product.uom_id.rounding
    #         res[product_id] = {}
    #         # Comemnted by kabeer at 23-05-2022
    #         # if dates_in_the_past:
    #         #     qty_available = quants_res.get(product_id, 0.0) - moves_in_res_past.get(product_id, 0.0) + moves_out_res_past.get(product_id, 0.0)
    #         # else:
    #         #     qty_available = quants_res.get(product_id, 0.0)
    #         qty_available = quants_res.get(product_id, 0.0)
    #         # Comemnted by kabeer at 23-05-2022 ends here
    #
    #         res[product_id]['qty_available'] = float_round(qty_available, precision_rounding=rounding)
    #         res[product_id]['incoming_qty'] = float_round(moves_in_res.get(product_id, 0.0), precision_rounding=rounding)
    #         res[product_id]['outgoing_qty'] = float_round(moves_out_res.get(product_id, 0.0), precision_rounding=rounding)
    #         res[product_id]['virtual_available'] = float_round(
    #             qty_available + res[product_id]['incoming_qty'] - res[product_id]['outgoing_qty'],
    #             precision_rounding=rounding)
    #     return res

    def _get_lines(self, data):

        product_res = self.env['product.product'].search([('qty_available', '!=', 0),
                                                          ('type', '=', 'product'),

                                                          ])
        category_lst = []
        if data['category'] and data['filter_by'] == 'categ':
            for cate in data['category']:
                if cate.id not in category_lst:
                    category_lst.append(cate.id)

                for child in cate.child_id:
                    if child.id not in category_lst:
                        category_lst.append(child.id)
        if len(category_lst) > 0:
            product_res = self.env['product.product'].search(
                [('categ_id', 'in', category_lst), ('qty_available', '!=', 0), ('type', '=', 'product')])
        if data['product_ids'] and data['filter_by'] == 'product':
            product_res = data['product_ids']
        lines = []
        for product in product_res:
            sales_value = 0.0
            manufacturing_value = 0.0
            consumed_components = 0.0
            unbuild_components = 0.0
            unbuild_main = 0.0
            incoming = 0.0
            # opening = self._compute_quantities_product_quant_dic(self._context.get('lot_id'), self._context.get('owner_id'), self._context.get('package_id'),False,data['start_date'],product,data)
            opening = self._compute_quantities_product_quant_dic(self._context.get('lot_id'),
                                                                 self._context.get('owner_id'),
                                                                 self._context.get('package_id'),
                                                                 data['start_date'], data['end_date'], product,
                                                                 data)
            custom_domain = []

            bom_domain = []

            # where = ''
            # params = [str(data['start_date']),str(data['end_date'])]
            # Added by kabeer to create domain for location
            location_domain = []
            location_adj_domain = []
            if data['location_id']:
                location_domain.append(('location_dest_id', '=', data['location_id'].id))
                location_adj_domain.append(('location_id', '=', data['location_id'].id))
            # Added by kabeer to create domain for location ends here
            if data['company_id']:
                obj = self.env['res.company'].search([('name', '=', data['company_id'])])
                custom_domain.append(('company_id', '=', obj.id))
                bom_domain.append(('company_id', '=', obj.id))
                # where += 'sp.company_id in %s'
                # params.append(obj.id)

            if data['warehouse'] and not data['location_id']:
                warehouse_lst = [a.id for a in data['warehouse']]
                custom_domain.append(('picking_id.picking_type_id.warehouse_id', 'in', warehouse_lst))
                bom_domain.append(('picking_type_id.warehouse_id', 'in', warehouse_lst))
                # Added by kabeer to create domain for location for choosen warehouse
                locations_dd = []
                for i in warehouse_lst:
                    loc_ids = self.env['stock.warehouse'].search([('id', '=', i)])
                    locations_dd.append(loc_ids.view_location_id.id)
                    for i in loc_ids.view_location_id.child_ids:
                        locations_dd.append(i.id)
                    # loc_list.append(loc_ids.lot_stock_id.id)
                location_domain.append(('location_dest_id', 'in', locations_dd))
                location_adj_domain.append(('location_id', 'in', locations_dd))
            # Added by kabeer to create domain for location for choose warehouse ends here

            # Added by kabeer 23/05/2022
            # stock_move_line = self.env['stock.move'].search([
            #     ('product_id','=',product.id),
            #     ('picking_id.date_done','>',data['start_date']),
            #     ('picking_id.date_done',"<=",data['end_date']),
            #     ('state','=','done')
            #     ] + custom_domain)
            # print('custom_domain',custom_domain)
            stock_move_line = self.env['stock.move'].search([
                                                                ('product_id', '=', product.id),
                                                                ('picking_id.date_done', '>=', data['start_date']),
                                                                ('picking_id.date_done', "<=", data['end_date']),
                                                                ('state', '=', 'done')
                                                            ] + custom_domain)
            #                 query = """select sp.id as id from stock_move sm
            # LEFT JOIN stock_picking sp ON sp.id = sm.picking_id
            # where DATE(sp.date_done) > '%s' and DATE(sp.date_to) <=%s"""+where+""" order by sm.id desc"""
            #
            #
            # #
            # #                 print('start_date',data['start_date'])
            #
            #                 self.env.cr.execute(query,tuple(str(data['start_date'])))
            #                 move_line_ids = self.env.cr.fetchall()
            #                 print('move_line_ids',move_line_ids)
            #                 stock_move_line = self.env['stock.move'].browse([move_line_ids.get('id')])
            #
            # print('stock_move_line',stock_move_line)
            # Added by kabeer 23/05/2022 ends here

            unbuild_main_lines = self.env['stock.move'].search([
                                                                   # ('location_id.usage', '=', 'internal'),
                                                                   # ('location_dest_id.usage', '=', 'production'),
                                                                   ('date', '>=', data['start_date']),
                                                                   ('date', "<=", data['end_date']),
                                                                   ('product_id.id', '=', product.id),
                                                                   ('unbuild_id', '!=', False),
                                                                   ('state', '=',
                                                                    'done')] + bom_domain + location_domain)

            for moves in unbuild_main_lines:
                if moves.location_id.usage == 'internal' and moves.location_dest_id.usage == 'production':
                    if data['location_id']:
                        locations_list = [data['location_id'].id]
                        for i in data['location_id'].child_ids:
                            locations_list.append(i.id)
                        if moves.location_dest_id.id in locations_list or moves.location_id.id in locations_list:
                            unbuild_main = unbuild_main + moves.product_uom_qty
                    else:
                        unbuild_main = unbuild_main + moves.product_uom_qty
            unbuild_component_lines = self.env['stock.move'].search([
                                                                        # ('location_id.usage', '=', 'production'),
                                                                        # ('location_dest_id.usage', '=', 'internal'),
                                                                        ('date', '>=', data['start_date']),
                                                                        ('date', "<=", data['end_date']),
                                                                        ('product_id.id', '=', product.id),
                                                                        ('unbuild_id', '!=', False),
                                                                        ('state', '=',
                                                                         'done')] + bom_domain + location_domain)

            for moves in unbuild_component_lines:
                if moves.location_id.usage == 'production' and moves.location_dest_id.usage == 'internal':
                    if data['location_id']:
                        locations_list = [data['location_id'].id]
                        for i in data['location_id'].child_ids:
                            locations_list.append(i.id)
                        if moves.location_dest_id.id in locations_list or moves.location_id.id in locations_list:
                            unbuild_components = unbuild_components + moves.product_uom_qty
                    else:
                        unbuild_components = unbuild_components + moves.product_uom_qty

            bom_move_line = self.env['stock.move'].search([
                                                              ('product_id', '=', product.id),
                                                              ('date', '>=', data['start_date']),
                                                              ('date', "<=", data['end_date']),
                                                              ('state', '=', 'done'),
                                                              ('raw_material_production_id', '!=', False),
                                                              ('picking_type_id.code', '=', 'mrp_operation')
                                                          ] + bom_domain)

            manufacturing_line = self.env['stock.move'].search([
                                                                   ('product_id', '=', product.id),
                                                                   ('date', '>=', data['start_date']),
                                                                   ('date', "<=", data['end_date']),
                                                                   ('state', '=', 'done'),
                                                                   ('production_id', '!=', False),
                                                                   ('picking_type_id.code', '=', 'mrp_operation')
                                                               ] + bom_domain)

            for moves in manufacturing_line:
                if data['location_id']:
                    locations_list = [data['location_id'].id]
                    for i in data['location_id'].child_ids:
                        locations_list.append(i.id)
                    if moves.location_dest_id.id in locations_list or moves.location_id.id in locations_list:
                        manufacturing_value = manufacturing_value + moves.product_uom_qty
                else:
                    manufacturing_value = manufacturing_value + moves.product_uom_qty

            for moves in bom_move_line:
                if data['location_id']:
                    locations_list = [data['location_id'].id]
                    for i in data['location_id'].child_ids:
                        locations_list.append(i.id)
                    if moves.location_dest_id.id in locations_list or moves.location_id.id in locations_list:
                        consumed_components = consumed_components + moves.product_uom_qty
                else:
                    consumed_components = consumed_components + moves.product_uom_qty

            for move in stock_move_line:
                if move.picking_id.picking_type_id.code == "outgoing":
                    if data['location_id']:
                        locations_lst = [data['location_id'].id]
                        for i in data['location_id'].child_ids:
                            locations_lst.append(i.id)
                        if move.location_id.id in locations_lst:
                            sales_value = sales_value + move.product_uom_qty
                    else:
                        sales_value = sales_value + move.product_uom_qty
                if move.picking_id.picking_type_id.code == "incoming":
                    if data['location_id']:
                        locations_lst = [data['location_id'].id]
                        for i in data['location_id'].child_ids:
                            locations_lst.append(i.id)
                        if move.location_dest_id.id in locations_lst:
                            incoming = incoming + move.product_uom_qty
                    else:
                        incoming = incoming + move.product_uom_qty

            stock_val_layer = self.env['stock.valuation.layer'].search([
                ('product_id', '=', product.id),
                ('create_date', '>=', data['start_date']),
                ('create_date', "<=", data['end_date']),

            ])

            cost = 0
            qty = 0
            for layer in stock_val_layer:
                if layer.stock_move_id.picking_id.picking_type_id.code == "incoming":
                    cost = cost + layer.value
                    qty = qty + layer.quantity

                if not layer.stock_move_id.picking_id:
                    cost = cost + layer.value
                    qty = qty + layer.quantity

            avg_cost = 0
            if qty > 0:
                avg_cost = cost / qty
                avg_cost = round(avg_cost, 2)

            if not stock_val_layer and avg_cost == 0:
                avg_cost = product.standard_price

            # inventory_domain = [
            #     ('date','>',data['start_date']),
            #     ('date',"<",data['end_date'])
            #     ]
            inventory_domain = [
                ('date', '>=', data['start_date']),
                ('date', "<=", data['end_date'])
            ]
            # Commented and modified by kabeer at 23-05-2022
            print('location_adj_domain', location_adj_domain)
            # stock_pick_lines = self.env['stock.move'].search([('location_id.usage', '=', 'inventory'),('product_id.id','=',product.id)] + inventory_domain)
            stock_pick_lines = self.env['stock.move'].search([('location_id.usage', '=', 'inventory'), (
                'product_id.id', '=', product.id)] + inventory_domain + location_domain)
            #
            # stock_internal_lines = self.env['stock.move'].search([('location_id.usage', '=', 'internal'),('location_dest_id.usage', '=', 'internal'),('product_id.id','=',product.id)] + inventory_domain)
            # Commented and modified by kabeer at 23-05-2022 ends here
            stock_internal_lines = self.env['stock.move'].search(
                [('location_id.usage', '=', 'internal'), ('location_dest_id.usage', '=', 'internal'),
                 ('product_id.id', '=', product.id), ('state', '=', 'done')] + inventory_domain + location_domain)
            stock_internal_minus_lines = self.env['stock.move'].search(
                [('location_id.usage', '=', 'internal'), ('location_dest_id.usage', '=', 'internal'),
                 ('product_id.id', '=', product.id),
                 ('state', '=', 'done')] + inventory_domain + location_adj_domain)
            # stock_internal_lines_2 = self.env['stock.move'].search([('location_id.usage', '=', 'internal'),('location_dest_id.usage', '=', 'inventory'),('product_id.id','=',product.id)] + inventory_domain)
            stock_internal_lines_2 = self.env['stock.move'].search(
                [('location_id.usage', '=', 'internal'), ('location_dest_id.usage', '=', 'inventory'),
                 ('product_id.id', '=', product.id)] + inventory_domain + location_domain)
            stock_internal_adjstment_minus = self.env['stock.move'].search(
                [('location_id.usage', '=', 'internal'), ('location_dest_id.usage', '=', 'inventory'),
                 ('product_id.id', '=', product.id)] + inventory_domain + location_adj_domain)
            # print('stock_internal_adjstment_minus',stock_internal_adjstment_minus)
            adjust = 0
            adjust_minus = 0
            internal = 0
            internal_minus = 0
            plus_picking = 0
            plus_min = 0
            # print('stock_internal_lines',stock_internal_lines)
            # print('stock_pick_lines',stock_pick_lines)
            # print('stock_internal_lines_2',stock_internal_lines_2)

            # Commented by kabeer at 24-05-2022 to get sum of adjusted amount
            # if stock_pick_lines:
            #     for invent in stock_pick_lines:
            #         adjust = invent.product_uom_qty
            #         plus_picking = invent.id
            # min_picking = 0
            # if stock_internal_lines_2 :
            #     for inter in stock_internal_lines_2:
            #         plus_min = inter.product_uom_qty
            #         min_picking = inter.id
            # if plus_picking > min_picking :
            #     picking_id = self.env['stock.move'].browse(plus_picking)
            #     adjust = picking_id.product_uom_qty
            # else :
            #     picking_id = self.env['stock.move'].browse(min_picking)
            #     adjust = -int(picking_id.product_uom_qty)
            # if stock_internal_lines:
            #     for inter in stock_internal_lines:
            #         internal = inter.product_uom_qty
            if stock_internal_adjstment_minus:
                for invent_adj in stock_internal_adjstment_minus:
                    adjust_minus += invent_adj.product_uom_qty
                    # plus_picking = invent_adj.id
                adjust_minus = -adjust_minus
            # print('adjust_minus',adjust_minus)

            if stock_pick_lines:
                for invent in stock_pick_lines:
                    adjust += invent.product_uom_qty
                    plus_picking = invent.id
                # print('adjust1',adjust)
            min_picking = 0
            if stock_internal_lines_2:
                for inter in stock_internal_lines_2:
                    plus_min += inter.product_uom_qty
                    min_picking = inter.id
            # print('min_picking',min_picking)
            # print('plus_picking',plus_picking)
            # if plus_picking > min_picking :
            #     picking_id = self.env['stock.move'].browse(plus_picking)
            #     adjust += picking_id.product_uom_qty
            #     print('adjust2',adjust)
            # else :
            #     picking_id = self.env['stock.move'].browse(min_picking)
            #     adjust += -int(picking_id.product_uom_qty)
            #     print('adjust3',adjust)
            if stock_internal_lines:
                for inter in stock_internal_lines:
                    internal += inter.product_uom_qty
            # print('internal11111111',internal)
            if stock_internal_minus_lines:
                for inter_minus in stock_internal_minus_lines:
                    internal_minus += inter_minus.product_uom_qty
                # print('internal_minus',internal_minus)
                internal = internal + (-internal_minus)
            # print('adjust444444',adjust)
            # print('internal',internal)
            adjust = adjust + adjust_minus
            # print('adjust444444',adjust.dd)
            # ending_bal = opening[product.id]['qty_available'] - sales_value + incoming + adjust
            ending_bal = opening[product.id][
                             'qty_available'] - sales_value + incoming + adjust + internal + manufacturing_value - consumed_components + unbuild_components - unbuild_main
            # ending_bal = opening[product.id]['qty_available'] - sales_value + incoming + adjust + internal
            method = ''
            price_used = product.standard_price
            if product.categ_id.property_cost_method == 'average':
                method = 'Average Cost (AVCO)'
                price_used = avg_cost
            elif product.categ_id.property_cost_method == 'standard':
                method = 'Standard Price'
                price_used = product.standard_price
            vals = {
                'sku': product.default_code or '',
                'name': product.get_prd_name_with_atrr() or '',
                'category': product.categ_id.name or '',
                'cost_price': round(price_used or 0, 2),
                'available': 0,
                'virtual': 0,
                'incoming': incoming or 0,
                'outgoing': adjust,
                'net_on_hand': ending_bal,
                'total_value': round(ending_bal * price_used or 0, 2),
                'sale_value': sales_value or 0,
                'purchase_value': 0,
                'beginning': opening[product.id]['qty_available'] or 0,
                'internal': internal,
                'costing_method': method,
                'currency': product.currency_id or self.env.user.company_id.currency_id,
                'uom': product.uom_id.name,
                'manufacturing_value': manufacturing_value or 0,
                'consumed_components': consumed_components or 0,
                'unbuild_main': unbuild_main or 0,
                'unbuild_components': unbuild_components or 0
            }
            lines.append(vals)
        return lines

    def _get_data(self, data):
        product_res = self.env['product.product'].search([('qty_available', '!=', 0),
                                                          ('type', '=', 'product'),

                                                          ])
        category_lst = []
        if data['category']:
            for cate in data['category']:
                if cate.id not in category_lst:
                    category_lst.append(cate.id)
                for child in cate.child_id:
                    if child.id not in category_lst:
                        category_lst.append(child.id)
        if len(category_lst) > 0:
            product_res = self.env['product.product'].search(
                [('categ_id', 'in', category_lst), ('qty_available', '!=', 0), ('type', '=', 'product')])
        lines = []
        for product in product_res:
            sales_value = 0.0
            manufacturing_value = 0.0
            consumed_components = 0.0
            unbuild_components = 0.0
            unbuild_main = 0.0
            incoming = 0.0
            opening = self._compute_quantities_product_quant_dic(self._context.get('lot_id'),
                                                                 self._context.get('owner_id'),
                                                                 self._context.get('package_id'), data['start_date'],
                                                                 data['end_date'], product, data)

            # opening = self._compute_quantities_product_quant_dic(self._context.get('lot_id'), self._context.get('owner_id'), self._context.get('package_id'),False,data['start_date'],product,data)
            custom_domain = []
            bom_domain = []
            location_domain = []
            location_adj_domain = []
            if data['location_id']:
                location_domain.append(('location_dest_id', '=', data['location_id'].id))
                location_adj_domain.append(('location_id', '=', data['location_id'].id))
            # Added by kabeer to create domain for location ends here

            if data['company_id']:
                obj = self.env['res.company'].search([('name', '=', data['company_id'])])
                custom_domain.append(('company_id', '=', obj.id))
                bom_domain.append(('company_id', '=', obj.id))
            if data['warehouse']:
                warehouse_lst = [a.id for a in data['warehouse']]
                custom_domain.append(('picking_id.picking_type_id.warehouse_id', 'in', warehouse_lst))
                bom_domain.append(('picking_type_id.warehouse_id', 'in', warehouse_lst))
                locations_dd = []
                for i in warehouse_lst:
                    loc_ids = self.env['stock.warehouse'].search([('id', '=', i)])
                    locations_dd.append(loc_ids.view_location_id.id)
                    for i in loc_ids.view_location_id.child_ids:
                        locations_dd.append(i.id)
                    # loc_list.append(loc_ids.lot_stock_id.id)
                location_domain.append(('location_dest_id', 'in', locations_dd))
                location_adj_domain.append(('location_id', 'in', locations_dd))
            stock_move_line = self.env['stock.move'].search([
                                                                ('product_id', '=', product.id),
                                                                ('picking_id.date_done', '>', data['start_date']),
                                                                ('picking_id.date_done', "<=", data['end_date']),
                                                                ('state', '=', 'done')
                                                            ] + custom_domain)

            unbuild_main_lines = self.env['stock.move'].search([
                                                                   ('date', '>=', data['start_date']),
                                                                   ('date', "<=", data['end_date']),
                                                                   ('product_id.id', '=', product.id),
                                                                   ('unbuild_id', '!=', False),
                                                                   ('state', '=',
                                                                    'done')] + location_adj_domain)
            # unbuild_main_lines = self.env['stock.move'].search([
            #                                                        ('location_id.usage', '=', 'internal'),
            #                                                        ('location_dest_id.usage', '=', 'production'),
            #                                                        ('date', '>=', data['start_date']),
            #                                                        ('date', "<=", data['end_date']),
            #                                                        ('product_id.id', '=', product.id),
            #                                                        ('unbuild_id', '!=', False),
            #                                                        ('state', '=', 'done')] + bom_domain)

            for moves in unbuild_main_lines:
                if moves.location_id.usage == 'internal' and moves.location_dest_id.usage == 'production':
                    if data['location_id']:
                        locations_list = [data['location_id'].id]
                        for i in data['location_id'].child_ids:
                            locations_list.append(i.id)
                        if moves.location_dest_id.id in locations_list or moves.location_id.id in locations_list:
                            unbuild_main = unbuild_main + moves.product_uom_qty
                    else:
                        unbuild_main = unbuild_main + moves.product_uom_qty
            unbuild_component_lines = self.env['stock.move'].search([
                                                                        # ('location_id.usage', '=', 'production'),
                                                                        # ('location_dest_id.usage', '=', 'internal'),
                                                                        ('date', '>=', data['start_date']),
                                                                        ('date', "<=", data['end_date']),
                                                                        ('product_id.id', '=', product.id),
                                                                        ('unbuild_id', '!=', False),
                                                                        ('state', '=',
                                                                         'done')] + location_domain)

            for moves in unbuild_component_lines:
                if moves.location_id.usage == 'production' and moves.location_dest_id.usage == 'internal':
                    if data['location_id']:
                        locations_list = [data['location_id'].id]
                        for i in data['location_id'].child_ids:
                            locations_list.append(i.id)
                        if moves.location_dest_id.id in locations_list or moves.location_id.id in locations_list:
                            unbuild_components = unbuild_components + moves.product_uom_qty
                    else:
                        unbuild_components = unbuild_components + moves.product_uom_qty

            bom_move_line = self.env['stock.move'].search([
                                                              ('product_id', '=', product.id),
                                                              ('date', '>', data['start_date']),
                                                              ('date', "<=", data['end_date']),
                                                              ('state', '=', 'done'),
                                                              ('raw_material_production_id', '!=', False),
                                                              ('picking_type_id.code', '=', 'mrp_operation')
                                                          ] + bom_domain)
            manufacturing_line = self.env['stock.move'].search([
                                                                   ('product_id', '=', product.id),
                                                                   ('date', '>=', data['start_date']),
                                                                   ('date', "<=", data['end_date']),
                                                                   ('state', '=', 'done'),
                                                                   ('production_id', '!=', False),
                                                                   ('picking_type_id.code', '=', 'mrp_operation')
                                                               ] + bom_domain)

            for moves in manufacturing_line:
                if data['location_id']:
                    locations_list = [data['location_id'].id]
                    for i in data['location_id'].child_ids:
                        locations_list.append(i.id)
                    if moves.location_dest_id.id in locations_list or moves.location_id.id in locations_list:
                        manufacturing_value = manufacturing_value + moves.product_uom_qty
                else:
                    manufacturing_value = manufacturing_value + moves.product_uom_qty

            for moves in bom_move_line:
                if data['location_id']:
                    locations_list = [data['location_id'].id]
                    for i in data['location_id'].child_ids:
                        locations_list.append(i.id)
                    if moves.location_dest_id.id in locations_list or moves.location_id.id in locations_list:
                        consumed_components = consumed_components + moves.product_uom_qty
                else:
                    consumed_components = consumed_components + moves.product_uom_qty

            for move in stock_move_line:
                if move.picking_id.picking_type_id.code == "outgoing":
                    if data['location_id']:
                        locations_lst = [data['location_id'].id]
                        for i in data['location_id'].child_ids:
                            locations_lst.append(i.id)
                        if move.location_id.id in locations_lst:
                            sales_value = sales_value + move.product_uom_qty
                    else:
                        sales_value = sales_value + move.product_uom_qty
                if move.picking_id.picking_type_id.code == "incoming":
                    if data['location_id']:
                        locations_lst = [data['location_id'].id]
                        for i in data['location_id'].child_ids:
                            locations_lst.append(i.id)
                        if move.location_dest_id.id in locations_lst:
                            incoming = incoming + move.product_uom_qty
                    else:
                        incoming = incoming + move.product_uom_qty
            stock_val_layer = self.env['stock.valuation.layer'].search([
                ('product_id', '=', product.id),
                ('create_date', '>=', data['start_date']),
                ('create_date', "<=", data['end_date']),

            ])
            cost = 0
            count = 0
            for layer in stock_val_layer:
                if layer.stock_move_id.picking_id.picking_type_id.code == "incoming":
                    cost = cost + layer.unit_cost
                    count = count + 1
                if not layer.stock_move_id.picking_id:
                    cost = cost + layer.unit_cost
                    count = count + 1
            avg_cost = 0
            if count > 0:
                avg_cost = cost / count
            if not stock_val_layer and avg_cost == 0:
                avg_cost = product.standard_price
            inventory_domain = [
                ('date', '>', data['start_date']),
                ('date', "<", data['end_date'])
            ]
            stock_pick_lines = self.env['stock.move'].search(
                [('location_id.usage', '=', 'inventory'), ('product_id.id', '=', product.id)] + inventory_domain)
            stock_internal_lines = self.env['stock.move'].search(
                [('location_id.usage', '=', 'internal'), ('location_dest_id.usage', '=', 'internal'),
                 ('product_id.id', '=', product.id)] + inventory_domain)
            stock_internal_lines_2 = self.env['stock.move'].search(
                [('location_id.usage', '=', 'internal'), ('location_dest_id.usage', '=', 'inventory'),
                 ('product_id.id', '=', product.id)] + inventory_domain)
            adjust = 0
            internal = 0
            plus_picking = 0
            if stock_pick_lines:
                for invent in stock_pick_lines:
                    adjust = invent.product_uom_qty
                    plus_picking = invent.id
            min_picking = 0
            if stock_internal_lines_2:
                for inter in stock_internal_lines_2:
                    plus_min = inter.product_uom_qty
                    min_picking = inter.id
            if plus_picking > min_picking:
                picking_id = self.env['stock.move'].browse(plus_picking)
                adjust = picking_id.product_uom_qty
            else:
                picking_id = self.env['stock.move'].browse(min_picking)
                adjust = -int(picking_id.product_uom_qty)
            if stock_internal_lines:
                for inter in stock_internal_lines:
                    internal = inter.product_uom_qty
            ending_bal = opening[product.id][
                             'qty_available'] - sales_value + incoming + adjust + manufacturing_value - consumed_components + unbuild_components - unbuild_main
            method = ''
            price_used = product.standard_price
            if product.categ_id.property_cost_method == 'average':
                method = 'Average Cost (AVCO)'
                price_used = avg_cost

            elif product.categ_id.property_cost_method == 'standard':
                method = 'Standard Price'
                price_used = product.standard_price
            flag = False
            for i in lines:
                if i['category'] == product.categ_id.name:
                    i['beginning'] = i['beginning'] + opening[product.id]['qty_available']
                    i['internal'] = i['internal'] + internal
                    i['incoming'] = i['incoming'] + incoming
                    i['sale_value'] = i['sale_value'] + sales_value
                    i['outgoing'] = i['outgoing'] + adjust
                    i['net_on_hand'] = i['net_on_hand'] + ending_bal
                    i['total_value'] = i['total_value'] + (ending_bal * price_used)
                    flag = True

            if flag == False:
                vals = {
                    'category': product.categ_id.name,
                    'cost_price': price_used or 0,
                    'available': 0,
                    'virtual': 0,
                    'incoming': incoming or 0,
                    'outgoing': adjust or 0,
                    'net_on_hand': ending_bal or 0,
                    'total_value': round(ending_bal * price_used or 0, 2),
                    'sale_value': sales_value or 0,
                    'purchase_value': 0,
                    'beginning': opening[product.id]['qty_available'] or 0,
                    'internal': internal or 0,
                    'currency': product.currency_id or self.env.user.company_id.currency_id,
                    'uom': product.uom_id.name,
                    'manufacturing_value': manufacturing_value or 0,
                    'consumed_components': consumed_components or 0,
                    'unbuild_main': unbuild_main or 0,
                    'unbuild_components': unbuild_components or 0
                }

                lines.append(vals)
        return lines

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
