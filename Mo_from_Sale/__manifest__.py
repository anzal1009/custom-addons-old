{''
 'name': 'MO from sale order',
 'summary': """Custom for ERP""",
 'version': '0.1',
 'sequence':'-1000',
 'description': """Custom for ERP""",
 'author': 'Anzal',
 'company': 'Anzal',
 'website': '',
 'category': 'Tools',
  'depends': ['sale','stock','purchase','mrp'],
 'license': 'AGPL-3',
 'data': [
'report/reports.xml',
'report/sale_report.xml',
'report/purchase_inherit.xml',
'security/ir.model.access.csv',
'wizard/sale_wizard.xml',
'views/sales.xml',
        ],
 'demo': [],
 'installable': True,
 'auto_install': False,
 'application' : True
 }