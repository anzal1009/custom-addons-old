# -*- coding: utf-8 -*-
##############################################################################
#
#    Globalteckz Pvt Ltd
#    Copyright (C) 2013-Today(www.globalteckz.com).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from odoo import api, exceptions, fields, models, _
import base64
import xlrd
import io
from odoo.tools import pycompat
from odoo.exceptions import ValidationError
from datetime import datetime


class Inventory_wizard(models.TransientModel):
    _name = 'inventory.wizard'


    file_type = fields.Selection([('csv', 'CSV File'), ('xls', 'XLS File')], string='File Type')
    imp_product_by = fields.Selection([('barcode', 'Barcode'), ('code', 'Code'), ('name', 'Name')],
                               string='Import Product By')
    ser_no_lot_expi = fields.Boolean(string="Import Serial/Lot number with Expiry Date")
    data_file = fields.Binary(string="File")
    option = fields.Selection([('create', 'Create'), ('skip', 'Skip ')], string='Operation')
    state = fields.Selection([('draft', 'Draft'), ('validate', 'Validated')], string='Import Stage Option')
    
  
    def Import_inventory(self):
        if self.file_type and self.data_file and self.option and self.imp_product_by:
            try:
                if self.file_type == 'csv':
                    csv_reader_data = pycompat.csv_reader(io.BytesIO(base64.b64decode(self.data_file)), quotechar=",",delimiter=",")
                    csv_reader_data = iter(csv_reader_data)
                    next(csv_reader_data)
                    file_data = csv_reader_data
                elif self.file_type == 'xls':
                    file_datas = base64.b64decode(self.data_file)
                    workbook = xlrd.open_workbook(file_contents=file_datas)
                    sheet = workbook.sheet_by_index(0)
                    data = [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]
                    data.pop(0)
                    file_data = data
            except:
                raise ValidationError(_('Please select proper file type.'))
        else:
            raise ValidationError(_('Please select all the required fields.'))
        
        Log = self.env['log.management']
        product_obj = self.env['product.product']
        location_obj = self.env['stock.location']
        inventory_vals={}
        
        for row in file_data:
            if self.file_type == 'csv' and len(row) != 5:
                raise ValidationError("You can not let empty cell in csv file or please use xls file.")
            if not row[1] or not row[0] or not row[2]:
                raise ValidationError(_('Name,Inventoried Location,Product values are required.'))
            
            location=location_obj.search([('name','=',row[1])],limit=1).id
            if not location:
                raise ValidationError(_('Could not find the Inventoried Location with name %s')% row[1])
            
            if self.imp_product_by=='barcode':
                product_id=product_obj.search([('barcode','=',str(int(row[2])) if isinstance(row[2],float) else row[2]),('active','=',True)],limit=1)
            if self.imp_product_by=='code':
                product_id=product_obj.search([('default_code','=',str(int(row[2])) if isinstance(row[2],float) else row[2]),('active','=',True)],limit=1)
            if self.imp_product_by=='name':
                product_id=product_obj.search([('name','=ilike',str(int(row[2])) if isinstance(row[2],float) else row[2]),('active','=',True)],limit=1)

            if not product_id:
                if self.option=='create':
                    product_id=product_obj.create({'name':str(int(row[2])) if isinstance(row[2],float) else row[2],'type':'product','default_code':str(int(row[2])) if isinstance(row[2],float) else row[2]})
                else:
                    Log.create({'operation':'inventory','message':'Skipped could not find the product with code %s'% str(row[2])})
                    continue
                    
            try:
                date=datetime.strptime(row[4], '%d-%m-%Y').strftime('%Y-%m-%d %H:%M:%S')
            except:
                raise ValidationError(_('Date format must be dd-mm-yyyy.'))
            if product_id:
                self.env['stock.quant'].create({
                    'location_id': location,
                    'product_id': product_id.id,
                    'inventory_quantity': row[3],
                    'inventory_date': date,
                }).action_apply_inventory()
        return True

                


