# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool

import product


def register():
    Pool.register(
        product.Template,
        product.TemplateCompany,
        product.AnalyticAccountEntry,
        product.InvoiceLine,
        product.SaleLine,
        product.PurchaseLine,
        module='analytic_product', type_='model')
    Pool.register(
        product.CreatePurchase,
        module='analytic_product', type_='wizard')
