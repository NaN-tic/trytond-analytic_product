# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .product import *


def register():
    Pool.register(
        Template,
        Account,
        InvoiceLine,
        SaleLine,
        PurchaseLine,
        module='analytic_product', type_='model')
    Pool.register(
        CreatePurchase,
        module='analytic_product', type_='wizard')
