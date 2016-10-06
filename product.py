# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from sql.aggregate import Min
from sql.conditionals import Coalesce

from trytond import backend
from trytond.model import ModelView, Unique, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction

from trytond.modules.analytic_account import AnalyticMixin


__all__ = ['Template', 'TemplateCompany', 'AnalyticAccountEntry',
    'InvoiceLine', 'SaleLine', 'PurchaseLine', 'CreatePurchase']


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'
    companies = fields.One2Many('product.template.company', 'template',
        'Configuration by company')


class TemplateCompany(AnalyticMixin, ModelView):
    '''Analytics configuration by Product Template and Company'''
    __name__ = 'product.template.company'
    template = fields.Many2One('product.template', 'Template', required=True,
        readonly=True, ondelete='CASCADE')
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(TemplateCompany, cls).__setup__()
        cls.analytic_accounts.domain = [
            ('company', '=', If(~Eval('company'),
                    Eval('context', {}).get('company', -1),
                    Eval('company', -1))),
            ]
        cls.analytic_accounts.depends.append('company')
        t = cls.__table__()
        cls._sql_constraints = [
            ('company_uniq', Unique(t, t.template, t.company),
                'The Company must to be unique per Product Template.')
            ]

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Account = pool.get('analytic_account.account')
        AccountEntry = pool.get('analytic.account.entry')
        Company = pool.get('company.company')
        Template = pool.get('product.template')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()

        super(TemplateCompany, cls).__register__(module_name)

        template_handler = TableHandler(Template, module_name)
        # Migration from 3.4: analytic accounting in product.template changed
        # to reference field to new product.template.company model
        if template_handler.column_exist('analytic_accounts'):
            account = Account.__table__()
            company = Company.__table__()
            entry = AccountEntry.__table__()
            template = Template.__table__()
            table = cls.__table__()

            cursor.execute(*company.select(company.id,
                    order_by=company.id,
                    limit=1))
            default_company_id, = cursor.fetchone()

            cursor.execute(*table.insert([
                        table.create_uid,
                        table.create_date,
                        table.template,
                        table.company,
                        ],
                    template.join(entry,
                        condition=(
                            template.analytic_accounts == entry.selection)
                        ).join(account, condition=(entry.account == account.id)
                            ).select(
                                Min(entry.create_uid),
                                Min(entry.create_date),
                                template.id,
                                Coalesce(account.company, default_company_id),
                                group_by=(template.id, account.company))))
            cursor.execute(*template.join(entry,
                    condition=(template.analytic_accounts == entry.selection)
                    ).join(account, condition=(entry.account == account.id)
                        ).join(table,
                            condition=((table.template == template.id)
                                & (table.company == account.company)
                                )
                            ).select(
                                table.id, table.company,
                                template.analytic_accounts,
                                group_by=(table.id,
                                    template.analytic_accounts)))
            for loc_company_id, company_id, selection_id in cursor.fetchall():
                cursor.execute(*entry.update(
                        columns=[entry.origin],
                        values=['%s,%s' % (
                                TemplateCompany.__name__, loc_company_id)],
                        from_=[account],
                        where=((entry.account == account.id)
                            & (account.company == company_id)
                            & (entry.selection == selection_id))))
            template_handler.drop_column('analytic_accounts')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class AnalyticAccountEntry:
    __metaclass__ = PoolMeta
    __name__ = 'analytic.account.entry'

    @classmethod
    def _get_origin(cls):
        origins = super(AnalyticAccountEntry, cls)._get_origin()
        return origins + ['product.template.company']

    @fields.depends('origin')
    def on_change_with_company(self, name=None):
        pool = Pool()
        TemplateCompany = pool.get('product.template.company')
        company = super(AnalyticAccountEntry, self).on_change_with_company(
            name)
        if isinstance(self.origin, TemplateCompany):
            company = self.origin.company.id
        return company

    @classmethod
    def search_company(cls, name, clause):
        domain = super(AnalyticAccountEntry, cls).search_company(name, clause),
        return ['OR',
            domain,
            (('origin.company',) + tuple(clause[1:]) +
                ('product.template.company',)),
            ]


class AnalyticProductMixin(object):

    def _set_analytic_accounts(self, company_id):
        if not getattr(self, 'product'):
            return
        pool = Pool()
        AnalyticEntry = pool.get('analytic.account.entry')
        root2account = {e.root: e.account for e in AnalyticEntry.search([
                    ('origin.company', '=', company_id,
                        'product.template.company'),
                    ('origin.template', '=', self.product.template,
                        'product.template.company'),
                    ('account', '!=', None),
                    ])}
        if not hasattr(self, 'analytic_accounts'):
            self.analytic_accounts = []
        for current_entry in self.analytic_accounts:
            if current_entry.root in root2account:
                current_entry.account = root2account[current_entry.root]
                del root2account[current_entry.root]
        for root, account in root2account.items():
            self.analytic_accounts.append(AnalyticEntry(
                    root=root,
                    account=account))


class InvoiceLine(AnalyticProductMixin):
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'

    @fields.depends('product', 'analytic_accounts', 'company',
        '_parent_invoice.company')
    def on_change_product(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        super(InvoiceLine, self).on_change_product()
        if not self.product:
            return
        if self.company:
            company_id = self.company.id
        elif self.invoice and self.invoice.company:
            company_id = self.invoice.company.id
        else:
            company_id = Invoice.default_company()
        self._set_analytic_accounts(company_id)


class SaleLine(AnalyticProductMixin):
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'

    @fields.depends('product', 'analytic_accounts', '_parent_sale.company')
    def on_change_product(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        super(SaleLine, self).on_change_product()
        if not self.product:
            return
        if self.sale and self.sale.company:
            company_id = self.sale.company.id
        else:
            company_id = Sale.default_company()
        self._set_analytic_accounts(company_id)


class PurchaseLine(AnalyticProductMixin):
    __metaclass__ = PoolMeta
    __name__ = 'purchase.line'

    @fields.depends('product', 'analytic_accounts', '_parent_purchase.company')
    def on_change_product(self):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        super(PurchaseLine, self).on_change_product()
        if not self.product:
            return
        if self.purchase and self.purchase.company:
            company_id = self.purchase.company.id
        else:
            company_id = Purchase.default_company()
        self._set_analytic_accounts(company_id)


class CreatePurchase:
    __metaclass__ = PoolMeta
    __name__ = 'purchase.request.create_purchase'

    @classmethod
    def compute_purchase_line(cls, request, purchase):
        pool = Pool()
        AnalyticEntry = pool.get('analytic.account.entry')
        line = super(CreatePurchase, cls).compute_purchase_line(request,
            purchase)

        entries = AnalyticEntry.search([
                ('origin.company', '=', request.company,
                    'product.template.company'),
                ('origin.template', '=', line.product.template,
                    'product.template.company'),
                ('account', '!=', None),
                ])
        if entries:
            line.analytic_accounts = [AnalyticEntry(
                    root=e.root,
                    account=e.account) for e in entries]
        return line
