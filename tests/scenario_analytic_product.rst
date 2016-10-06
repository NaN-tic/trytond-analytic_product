=========================
Analytic Product Scenario
=========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install stock_reservation Module::

    >>> Module = Model.get('ir.module')
    >>> modules = Module.find([
    ...     ('name', 'in', ['analytic_product', 'analytic_purchase',
    ...         'stock_supply', 'analytic_sale'])])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create analytic accounts::

    >>> AnalyticAccount = Model.get('analytic_account.account')
    >>> root = AnalyticAccount(type='root', name='Root')
    >>> root.save()
    >>> analytic_account = AnalyticAccount(root=root, parent=root,
    ...     name='Analytic')
    >>> analytic_account.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('5')
    >>> template.cost_price_method = 'fixed'
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template_company = template.companies.new()
    >>> len(template_company.analytic_accounts)
    1
    >>> template_company.analytic_accounts[0].account = analytic_account
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> input_loc, = Location.find([('code', '=', 'IN')])

Create purchase order point::

    >>> OrderPoint = Model.get('stock.order_point')
    >>> order_point = OrderPoint()
    >>> order_point.product = product
    >>> order_point.warehouse_location = warehouse_loc
    >>> order_point.type = 'purchase'
    >>> order_point.min_quantity = 10
    >>> order_point.max_quantity = 15
    >>> order_point.save()

Execute create purchase requests supply::

    >>> PurchaseRequest = Model.get('purchase.request')
    >>> Wizard('purchase.request.create').execute('create_')
    >>> request, = PurchaseRequest.find([])
    >>> request.state == 'draft'
    True
    >>> request.product.template.name == 'Product'
    True
    >>> request.quantity
    15.0

Confirm purchase request and check purchase line has valid analytic accounts::

    >>> PurchaseLine = Model.get('purchase.line')
    >>> request.party = supplier
    >>> request.save()
    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     models=[request])
    >>> purchase_line, = PurchaseLine.find([])
    >>> purchase_line.quantity
    15.0
    >>> purchase_line.purchase.warehouse.storage_location == storage_loc
    True
    >>> len(purchase_line.analytic_accounts)
    1
    >>> purchase_line.analytic_accounts[0].account == analytic_account
    True

Analytic accounts set when select product in invoice line::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = customer
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> len(line.analytic_accounts)
    1
    >>> line.analytic_accounts[0].account
    >>> line.product = product
    >>> len(line.analytic_accounts)
    1
    >>> line.analytic_accounts[0].account == analytic_account
    True

Analytic accounts set when select product in purchase line::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'order'
    >>> purchase_line = purchase.lines.new()
    >>> len(purchase_line.analytic_accounts)
    1
    >>> purchase_line.analytic_accounts[0].account
    >>> purchase_line.product = product
    >>> len(purchase_line.analytic_accounts)
    1
    >>> purchase_line.analytic_accounts[0].account == analytic_account
    True

Analytic accounts set when select product in sale line::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> len(sale_line.analytic_accounts)
    1
    >>> sale_line.analytic_accounts[0].account
    >>> sale_line.product = product
    >>> len(sale_line.analytic_accounts)
    1
    >>> sale_line.analytic_accounts[0].account == analytic_account
    True
