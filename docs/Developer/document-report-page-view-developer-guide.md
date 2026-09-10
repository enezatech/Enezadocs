---
menu name: Document Report Page View
position: 2
---

# Document Report Page View — Developer Guide

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [BaseDocumentReport Class](#basedocumentreport-class)
5. [Print Dropdown on Detail Views](#print-dropdown-on-detail-views)
6. [URL Auto-Registration](#url-auto-registration)
7. [Designer Integration](#designer-integration)
8. [Rendering Paths](#rendering-paths)
9. [Complete Example](#complete-example)
10. [Reference](#reference)

---

## Overview

The Document Report Page View feature enables developers to create document-type reports (header+lines documents such as Invoices, Purchase Orders, Statements) that render directly from a detail view's **Print dropdown**. The report auto-populates with the current document's data via URL `pk`, requiring no form submission or query parameters.

**Problem solved:** Previously, document reports required the full form/parameter flow via `ReportEngineView` — there was no dedicated view to render them from a URL path alone. The Print dropdown on detail views was also absent; developers had to misuse the general `action_list` for print/report actions.

**User outcome:**
1. Subclass `BaseDocumentReport`, set `model`, `header_model`, `header_fields`, `line_columns`, `line_total_fields`
2. Optionally set `report_name` to control the URL name (one model can power many reports)
3. Decorate with `@auto_url_register`
4. URL is auto-registered as `{app_name}:{report_name}_report` accepting `<str:pk>`
5. Set `print_actions` on the detail view — these appear in a **Print dropdown** (distinct from Actions)
6. User clicks a Print option → report renders immediately for that document in `#detail-container` via HTMX

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│ Developer writes a single class:                      │
│   @auto_url_register                                  │
│   class InvoiceReportView(BaseDocumentReport):        │
│     model = Invoice                                   │
│     report_name = "invoice"                           │
│     header_model = Invoice                            │
│     header_fields = [...]                             │
│     lines_related_name = "lines"                      │
│     line_columns = [...]                              │
│     line_total_fields = [...]                         │
├──────────────────────────────────────────────────────┤
│ BaseDocumentReport(DocumentReport,                    │
│                    DocumentReportPageView)            │
│   - Single class: type + view combined                │
├──────────────────────────────────────────────────────┤
│ DocumentReportPageView (DesignTemplateMixin,          │
│                         ReportEngineView)             │
│   - get() → _get_document_report_results()            │
│   - render_to_response() → extract lines for designer │
├──────────────────────────────────────────────────────┤
│ get_registered_urls() (enezaframework/utils.py)       │
│   - view_type == 'document_report'                    │
│   - Uses report_name if set, else model_name          │
│   - URL pattern: {report_name}_report/<str:pk>/       │
├──────────────────────────────────────────────────────┤
│ BaseDetailView (enezaframework/views/base.py)          │
│   - print_actions = []                                │
│   - context['print_actions']                          │
├──────────────────────────────────────────────────────┤
│ ActionMixin.get_print_action_config()                  │
│   - Converts dict list → template-safe format          │
│   - No _action suffix (unlike action_list)             │
├──────────────────────────────────────────────────────┤
│ navactions.html                                       │
│   - Print dropdown (hx-get, no confirmation)          │
│   - Positioned: Save → Delete → Print → Workflow      │
└──────────────────────────────────────────────────────┘
```

**Data flow for a Print action:**

```
User clicks "Invoice Report" in Print dropdown on detail page
  → HTMX hx-get → /myapp/invoice_report/42/
  → DocumentReportPageView.get(pk='42')
    → _get_document_report_results()
      → DocumentReportGenerator.get_report_data(42)
      → {header, lines, totals}
    → get_context_data(report_data=...)
    → render_to_response(context)
      → Standard: document_report.html (header + lines table + totals)
      → Designer: DesignTemplateMixin.render_to_response() → paginated
```

---

## Quick Start

### Step 1: Define the Report View (Single Class)

```python
# myapp/views/report_views.py
from enezareporting.views import BaseDocumentReport
from enezaframework.utils import auto_url_register
from myapp.models import Invoice

@auto_url_register
class InvoiceReportView(BaseDocumentReport):
    model = Invoice
    report_name = "invoice"
    header_model = Invoice
    lines_related_name = "lines"
    header_fields = ["invoice_number", "customer", "date", "due_date", "status"]
    line_columns = ["item", "description", "quantity", "unit_price", "line_total"]
    line_total_fields = ["line_total", "quantity"]
```

One import, one base class, one class definition. `BaseDocumentReport` combines `DocumentReport` (report type semantics) and `DocumentReportPageView` (view machinery).

### Step 2: Add Print Action to Detail View

```python
# myapp/views/invoice_views.py
from enezaframework.views import BaseSourceDocumentDetailView
from enezaframework.utils import auto_url_register
from myapp.models import Invoice

@auto_url_register
class InvoiceDetailView(BaseSourceDocumentDetailView):
    model = Invoice
    print_actions = [
        {
            'name': 'Invoice Report',
            'icon': 'printer',
            'url': 'invoice_report',    # matches report_name + '_report'
        }
    ]

    def detail_ui_view(self):
        return [
            {
                'name': 'Invoice Information',
                'icon': 'Home',
                'Fieldcolumns': [
                    {'fields': ['invoice_number', 'customer']},
                    {'fields': ['date', 'due_date', 'status']},
                ],
            },
        ]
```

### Step 3: Import the Report Views Module

```python
# myapp/views/__init__.py
from .report_views import *
from .invoice_views import *
```

### Step 4: Ensure URL Discovery

Your app's `urls.py` must include `*dynamic_urls` (most EnezaFramework apps already do):

```python
# myapp/urls.py
from django.urls import path
from enezaframework.utils import get_registered_urls

app_name = 'myapp'
dynamic_urls = get_registered_urls(app_name)

urlpatterns = [
    *dynamic_urls,
]
```

---

## BaseDocumentReport Class

**Location:** `enezareporting/views.py`

**Definition:**

```python
class BaseDocumentReport(DocumentReport, DocumentReportPageView):
    """Single base class for document reports accessed via URL pk."""
    pass
```

Internally combines `DocumentReport` (from `report_types.py`) with `DocumentReportPageView`. The MRO is:
`BaseDocumentReport` → `DocumentReport` → `DocumentReportPageView` → `DesignTemplateMixin` → `ReportEngineView`

### Required Attributes

| Attribute | Description |
|-----------|-------------|
| `model` | **Required.** Django model for the document header. Required by `get_registered_urls()`. |
| `header_model` | **Required.** Same as `model` (document header model for the generator). |
| `header_fields` | **Required.** List of field name strings to display in the header grid. |
| `line_columns` | **Required.** List of field name strings as columns in the lines table. |

### Optional Attributes

| Attribute | Default | Description |
|-----------|---------|-------------|
| `report_name` | `model.__name__.lower()` | Custom URL name segment. Set when one model has multiple reports. |
| `lines_related_name` | `"lines"` | Related name on header model for line items. |
| `line_total_fields` | `[]` | Numeric fields to sum in the totals footer. |
| `design_slug` | `None` | Set to a `ReportDesign.slug` for designer layout. |

### report_name: Multiple Reports Per Model

Since one model may serve many different reports, the URL name is controlled by the `report_name` attribute:

```python
# If report_name is NOT set, URL defaults to model name:
class SalesInvoiceView(BaseDocumentReport):
    model = Invoice
    # No report_name → URL: salesapp:invoice_report

# Set report_name to distinguish multiple reports:
class PurchaseInvoiceView(BaseDocumentReport):
    model = Invoice
    report_name = "purchase_invoice"
    # URL: purchaseapp:purchase_invoice_report

class TaxInvoiceView(BaseDocumentReport):
    model = Invoice
    report_name = "tax_invoice"
    # URL: taxapp:tax_invoice_report
```

### Important: `model` Must Be Set

The `get_registered_urls()` function checks `issubclass(view_class.model, Model)`. Every `BaseDocumentReport` child **must** set `model = TheHeaderModel`, even though `@auto_url_register` on a `View` subclass technically does not require it.

```python
@auto_url_register
class InvoiceReportView(BaseDocumentReport):
    model = Invoice  # ← REQUIRED for URL registration
```

---

## Print Dropdown on Detail Views

### Setting print_actions

Add `print_actions` to any detail view that inherits from `BaseDetailView` (or its subclasses):

```python
class InvoiceDetailView(BaseSourceDocumentDetailView):
    model = Invoice
    print_actions = [
        {
            'name': 'Invoice Report',       # Display name in dropdown
            'icon': 'printer',              # Icon name from static/assets/icons/
            'url': 'invoice_report',        # URL name — matches report_name + '_report'
        },
    ]
```

### Print vs Actions Dropdown

| Aspect | Print (`print_actions`) | Actions (`action_list`) |
|--------|--------------------------|------------------------|
| HTTP method | `hx-get` (no confirmation) | `hx-post` + confirmation |
| URL suffix | Direct — no suffix appended | `_action` appended automatically |
| Icon | Printer icon | Share icon (branching) |
| Position | After Save/Delete, before Workflow | After Workflow |
| Purpose | Report/print rendering | Operational actions (Post, Approve, etc.) |

### Template (navactions.html)

The Print dropdown is rendered at `enezaframework/templates/core/partials/navactions.html`. It uses:

- **Alpine.js** `x-data="dropdown"` for toggle behavior
- **HTMX** `hx-get` targeting `#detail-container` with `hx-swap="innerHTML"`
- URL construction: `{% url current_app|add:':'|add:action.url object.id %}`
- Conditional display: hidden when `print_actions` is empty/falsy

### ActionMixin.get_print_action_config()

Defined in `enezaframework/views/mixins.py`. Converts raw `print_actions` dict list into template-safe format with SVG icons:

```python
def get_print_action_config(self, print_actions):
    print_action_config = []
    for action in print_actions:
        action_dict = {
            'name': action.get('name', None),
            'icon': load_icon(action.get('icon', 'printer')),
            'url': action.get('url', ''),
        }
        print_action_config.append(action_dict)
    return print_action_config
```

Unlike `get_action_name_config()`, this method does **NOT** append `_action` to the URL — the URL name in `print_actions` is used verbatim.

### BaseDetailView Changes

`print_actions = []` is added to `BaseDetailView` (`enezaframework/views/base.py`), giving all detail view subclasses Print dropdown capability with no additional code.

---

## URL Auto-Registration

The `get_registered_urls()` function in `enezaframework/utils.py` dispatches on `view_type`. When a class has `view_type = 'document_report'` and a `model`, it generates:

```python
elif view_type == 'document_report':
    report_name = getattr(view_class, 'report_name', None)
    if report_name:
        url_name = f'{report_name}_report'
        url_pattern = f'{report_name}_report/<str:pk>/'
    else:
        url_name = f'{model_name}_report'
        url_pattern = f'{model_name}_report/<str:pk>/'
    urlpatterns.append(
        path(url_pattern, view_class.as_view(), name=url_name)
    )
```

### URL Naming

| `report_name` set? | URL Pattern | URL Name |
|--------------------|-------------|----------|
| Yes, `"invoice"` | `/myapp/invoice_report/<str:pk>/` | `myapp:invoice_report` |
| Yes, `"tax_invoice"` | `/myapp/tax_invoice_report/<str:pk>/` | `myapp:tax_invoice_report` |
| No (falls back to `model_name`) | `/myapp/invoice_report/<str:pk>/` | `myapp:invoice_report` |

---

## Designer Integration

Set `design_slug` on the view class to use a designer-created report layout:

```python
@auto_url_register
class InvoiceReportView(BaseDocumentReport):
    model = Invoice
    report_name = "invoice"
    header_model = Invoice
    header_fields = [...]
    line_columns = [...]
    line_total_fields = [...]
    design_slug = "invoice-standard-layout"
```

### How It Works

`BaseDocumentReport` inherits `DesignTemplateMixin` (via `DocumentReportPageView`), which provides:

- **`get_design()`** — Returns the `ReportDesign` object by slug, or `None` if not found/not set
- **`render_to_response()`** — When a design exists, compiles via `ReportDesignCompiler`, paginates, renders through `design_report.html`
- **`get_template_names()`** — Returns compiled template string or falls back to defaults

The `render_to_response()` override in `DocumentReportPageView` extracts the `lines` list from document data dict before calling the designer compiler, which expects `data` as a flat list for pagination.

---

## Rendering Paths

### 1. Without Designer Template (default)

When `design_slug` is not set, `DesignTemplateMixin.get_design()` returns `None`. Standard template rendering:

```
report.html → document_report.html
```

The template receives:
- `document_header` — dict of header field values
- `document_lines` — list of line item dicts
- `document_totals` — dict of total field values
- `is_document_report` — `True`

### 2. With Designer Template

When `design_slug` resolves to a valid `ReportDesign`, the designer compiler handles pagination:

```
get() → _get_document_report_results() → render_to_response()
  → DesignTemplateMixin.render_to_response()
    → ReportDesignCompiler.compile_paginated_report(data_rows)
    → design_report.html with paginated A4 pages
```

---

## Complete Example

### Model Layer

```python
# myapp/models.py
from enezaframework.models import EnezaDocument, EnezaDocumentLines
from django.db import models

class Invoice(EnezaDocument):
    invoice_number = models.CharField(max_length=100, verbose_name="Invoice Number")
    customer = models.CharField(max_length=200, verbose_name="Customer")
    date = models.DateField(verbose_name="Date")
    due_date = models.DateField(verbose_name="Due Date")
    status = models.CharField(max_length=30, verbose_name="Status")
    sequence_field_name = 'invoice_number'
    document_name = 'SALES_INVOICE'

    class Meta:
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"


class InvoiceLine(EnezaDocumentLines):
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE,
        related_name="lines", verbose_name="Invoice"
    )
    item_code = models.CharField(max_length=100, verbose_name="Item Code")
    description = models.CharField(max_length=200, verbose_name="Description")
    quantity = models.IntegerField(verbose_name="Quantity")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Unit Price")
    line_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Line Total")

    class Meta:
        verbose_name = "Invoice Line"
        verbose_name_plural = "Invoice Lines"
```

### Report View

```python
# myapp/views/report_views.py
from enezareporting.views import BaseDocumentReport
from enezaframework.utils import auto_url_register
from myapp.models import Invoice


@auto_url_register
class InvoiceReportView(BaseDocumentReport):
    model = Invoice
    report_name = "invoice"
    header_model = Invoice
    header_fields = ["invoice_number", "customer", "date", "due_date", "status"]
    lines_related_name = "lines"
    line_columns = ["item_code", "description", "quantity", "unit_price", "line_total"]
    line_total_fields = ["line_total", "quantity"]
```

### Multiple Reports for One Model

```python
# myapp/views/report_views.py
from enezareporting.views import BaseDocumentReport
from enezaframework.utils import auto_url_register
from myapp.models import Invoice


@auto_url_register
class InvoiceSummaryReportView(BaseDocumentReport):
    model = Invoice
    report_name = "invoice_summary"
    header_model = Invoice
    header_fields = ["invoice_number", "customer", "date", "status"]
    lines_related_name = "lines"
    line_columns = ["item_code", "description", "line_total"]
    line_total_fields = ["line_total"]


@auto_url_register
class InvoiceDetailReportView(BaseDocumentReport):
    model = Invoice
    report_name = "invoice_detail"
    header_model = Invoice
    header_fields = ["invoice_number", "customer", "date", "due_date", "status"]
    lines_related_name = "lines"
    line_columns = ["item_code", "description", "quantity", "unit_price", "line_total"]
    line_total_fields = ["line_total", "quantity"]


@auto_url_register
class InvoiceTaxReportView(BaseDocumentReport):
    model = Invoice
    report_name = "invoice_tax"
    header_model = Invoice
    header_fields = ["invoice_number", "customer", "date", "status"]
    lines_related_name = "lines"
    line_columns = ["item_code", "description", "unit_price", "tax_amount", "line_total"]
    line_total_fields = ["tax_amount", "line_total"]
```

### Detail View with Multiple Print Actions

```python
# myapp/views/invoice_views.py
from enezaframework.views import BaseSourceDocumentDetailView
from enezaframework.utils import auto_url_register
from myapp.models import Invoice


@auto_url_register
class InvoiceDetailView(BaseSourceDocumentDetailView):
    model = Invoice
    print_actions = [
        {'name': 'Invoice Summary', 'icon': 'printer', 'url': 'invoice_summary_report'},
        {'name': 'Invoice Detail', 'icon': 'printer', 'url': 'invoice_detail_report'},
        {'name': 'Tax Report', 'icon': 'printer', 'url': 'invoice_tax_report'},
    ]

    def detail_ui_view(self):
        return [
            {
                'name': 'Invoice Information',
                'icon': 'Home',
                'Fieldcolumns': [
                    {'fields': ['invoice_number', 'customer']},
                    {'fields': ['date', 'due_date', 'status']},
                ],
            },
        ]
```

### Views Module Init

```python
# myapp/views/__init__.py
from .report_views import *
from .invoice_views import *
```

### With Designer Template

```python
@auto_url_register
class InvoiceDesignReportView(BaseDocumentReport):
    model = Invoice
    report_name = "invoice_design"
    header_model = Invoice
    header_fields = ["invoice_number", "customer", "date", "due_date", "status"]
    lines_related_name = "lines"
    line_columns = ["item_code", "description", "quantity", "unit_price", "line_total"]
    line_total_fields = ["line_total", "quantity"]
    design_slug = "invoice-pdf-layout"
```

---

## Reference

### Files Modified

| File | Change | Purpose |
|------|--------|---------|
| `enezaframework/utils.py` | Added `elif view_type == 'document_report'` with `report_name` support | URL auto-registration |
| `enezareporting/views.py` | Added `DocumentReportPageView` class | Base view for pk-driven document reports |
| `enezareporting/views.py` | Added `BaseDocumentReport(DocumentReport, DocumentReportPageView)` | Single-class convenience base |
| `enezareporting/views.py` | Fixed `_get_document_report_results()` with `getattr` | Works without form initialization |
| `enezaframework/views/mixins.py` | Added `get_print_action_config()` to `ActionMixin` | Converts print_actions to template format |
| `enezaframework/views/base.py` | Added `print_actions = []` + context | Print dropdown on all detail views |
| `enezaframework/templates/core/partials/navactions.html` | Added Print dropdown section | Printer icon + hx-get dropdown menu |

### BaseDocumentReport API

| Attribute | Required | Default | Description |
|-----------|----------|---------|-------------|
| `model` | **Yes** | — | Django model for URL registration and header |
| `header_model` | **Yes** | — | Same as `model`; document header model for generator |
| `header_fields` | **Yes** | — | Field name strings for header grid |
| `line_columns` | **Yes** | — | Field name strings for lines table columns |
| `report_name` | No | `model.__name__.lower()` | Custom URL name segment |
| `lines_related_name` | No | `"lines"` | Related name for line items FK |
| `line_total_fields` | No | `[]` | Numeric fields summed in footer |
| `design_slug` | No | `None` | `ReportDesign.slug` for designer layout |

### print_actions Dict Format

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `name` | `str` | Yes | Display name in Print dropdown |
| `icon` | `str` | Yes | Icon filename from `static/assets/icons/` (without extension) |
| `url` | `str` | Yes | URL name — matches `report_name` + `_report` |

### URL Registration

| `report_name` set? | URL Pattern | URL Name |
|--------------------|-------------|----------|
| Yes | `{report_name}_report/<str:pk>/` | `{report_name}_report` |
| No | `{model_name}_report/<str:pk>/` | `{model_name}_report` |

### Key Constraints

- **`model` must be set** — `get_registered_urls()` requires `issubclass(view_class.model, Model)`
- **Use `report_name` for distinct URLs** when one model has multiple report views
- **`lines_related_name`** must match the `related_name` on the line model's FK to the header
- **Print dropdown position**: Between Delete and Workflow buttons
- **Print actions use `hx-get`** (no confirmation), unlike `action_list` which uses `hx-post`
- **Print action URLs** are used verbatim — no `_action` suffix appended
