---
menu name: Eneza Reporting
position: 4
---

# Eneza Reporting Engine — Developer Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [Report Types](#report-types)
4. [Parameter System](#parameter-system)
5. [Generators](#generators)
6. [Views](#views)
7. [Templates](#templates)
8. [Settings](#settings)
9. [Migration Guide](#migration-guide)
10. [API Reference](#api-reference)
11. [Examples](#examples)

---

## Architecture Overview

The Reporting Engine is organized into four layers:

```
┌─────────────────────────────────────────────────────┐
│ Report Types  (report_types.py)                     │
│ Declarative: defines WHAT a report is               │
│ DocumentReport, TabularReport, CrosstabReport, ...  │
├─────────────────────────────────────────────────────┤
│ Parameters  (parameters.py)                         │
│ Declarative filter inputs: DateRangeParam, ...      │
├─────────────────────────────────────────────────────┤
│ Generators  (generators/*.py)                       │
│ Imperative: fetches data, computes, formats,        │
│ produces {data, columns, metadata} dict             │
├─────────────────────────────────────────────────────┤
│ View  (views.py: ReportEngineView)                  │
│ Wires HTTP request → form → generator → template   │
└─────────────────────────────────────────────────────┘
```

**Data flow for a single request:**

```
URL → ReportEngineView.get()
  → Resolve report_type from class MRO
  → Build parameter form based on report_type.parameter_spec
  → User submits parameters (GET/POST or modal)
  → ReportEngineView.get_report_results()
    → Instantiate report_type.generator_class with params
    → Generator.fetch_data() → raw data
    → Generator.transform() → formatted rows
    → Generator.get_columns() → column metadata
    → Return {data, columns, metadata, chart_settings}
  → Render through unified template (eneza_reporting/report.html)
```

---

## Quick Start

A minimal tabular report:

```python
from enezareporting.report_types import TabularReport
from enezareporting.parameters import ParameterSet, DateRangeParam
from enezareporting.views import ReportEngineView
from myapp.models import SalesLine

class SalesReport(TabularReport, ReportEngineView):
    report_model = SalesLine
    date_field = "date_placed"
    group_by = "item_code"
    columns = ["item_description", "__total__"]
    parameter_spec = ParameterSet(
        DateRangeParam(name="date_range", start_field="date_placed"),
    )
```

Register a URL:

```python
# urls.py
from django.urls import path
from myapp.views import SalesReport

urlpatterns = [
    path("sales-report/", SalesReport.as_view(), name="sales_report"),
]
```

---

## Report Types

All report types live in `enezareporting.report_types`. Each is an abstract class you subclass alongside `ReportEngineView`.

### Report Type Hierarchy

```
ReportType (abstract base)
├── DocumentReport        header+lines, param = document PK
├── TabularReport         rows+aggregates, params = date range + FK filters
│   ├── SummaryReport     aggregates only, no detail rows
│   └── DetailedReport    full granular rows, no aggregation
├── CrosstabReport        2D pivot, params = date range + dimensions
├── TimeSeriesReport      chronological buckets, params = date range + period
└── DrillDownReport       hierarchical levels, params = root node + depth
```

### TabularReport

Standard grouped/aggregated table. Requires `report_model`, usually `group_by` and `columns`.

| Attribute | Required | Description |
|-----------|----------|-------------|
| `report_model` | Yes | Django model for the data source |
| `columns` | Yes | List of field names, computation fields, or callables |
| `group_by` | No | Field name to group rows by |
| `date_field` | No | Date field for date-range filtering |
| `time_series_pattern` | No | If set, adds per-bucket columns (daily, weekly, monthly, ...) |
| `crosstab_field` | No | If set, adds pivot columns |

```python
class SalesByCustomer(TabularReport, ReportEngineView):
    report_model = SalesLine
    date_field = "date_placed"
    group_by = "customer"
    columns = ["customer__name", "__total__", "__balance__"]
    parameter_spec = ParameterSet(
        DateRangeParam(name="date_range", start_field="date_placed"),
        FKFilterParam(name="product", model_field="product"),
    )
```

### SummaryReport & DetailedReport

Marker subclasses of `TabularReport`:

- **SummaryReport** — Signals aggregation-only mode (no detail rows).
- **DetailedReport** — Signals no-aggregation mode (list view, every row shown).

```python
class SalesSummary(SummaryReport, ReportEngineView):
    report_model = SalesLine
    group_by = "product"
    columns = ["product__name", "__total__"]
```

```python
class TransactionList(DetailedReport, ReportEngineView):
    report_model = SalesLine
    columns = ["date_placed", "customer__name", "value", "quantity"]
```

### CrosstabReport

2D pivot table. Requires `crosstab_field` and `crosstab_columns`.

| Attribute | Required | Description |
|-----------|----------|-------------|
| `crosstab_field` | Yes | FK or char field to pivot on (e.g. "product") |
| `crosstab_columns` | Yes | Computation fields per crosstab cell |
| `crosstab_ids` | No | Restrict to specific IDs |
| `crosstab_compute_remainder` | No | Include "other" column (default: True) |
| `crosstab_precomputed` | No | Read pre-aggregated values from DB |

```python
class RegionByProduct(CrosstabReport, ReportEngineView):
    report_model = SalesLine
    date_field = "date_placed"
    group_by = "region"
    crosstab_field = "product"
    crosstab_columns = ["__total__"]
    columns = ["region__name"]
```

### TimeSeriesReport

Chronological buckets. Requires `time_series_pattern`, `time_series_columns`, and `date_field`.

| Attribute | Required | Description |
|-----------|----------|-------------|
| `time_series_pattern` | Yes | One of: daily, weekly, bi-weekly, monthly, quarterly, semiannually, annually, custom |
| `time_series_columns` | Yes | Computation fields per bucket |
| `date_field` | Yes | Model date field for partitioning |

```python
class MonthlyRevenue(TimeSeriesReport, ReportEngineView):
    report_model = SalesLine
    date_field = "date_placed"
    time_series_pattern = "monthly"
    time_series_columns = ["__total__"]
    columns = []
```

### DocumentReport

Header + lines layout for invoices, purchase orders, statements. Requires `header_model` and `line_columns`.

| Attribute | Required | Description |
|-----------|----------|-------------|
| `header_model` | Yes | Django model for the document header |
| `header_fields` | Yes | Field names to display in header grid |
| `line_columns` | Yes | Field names as columns in the lines table |
| `lines_related_name` | No | Related name on header for line items (default: "lines") |
| `line_total_fields` | No | Numeric fields to sum in footer |

```python
class InvoiceReport(DocumentReport, ReportEngineView):
    header_model = Invoice
    header_fields = ["invoice_number", "customer", "date", "due_date", "status"]
    lines_related_name = "lines"
    line_columns = ["item", "description", "quantity", "unit_price", "line_total"]
    line_total_fields = ["line_total", "quantity"]
```

Access via URL: `/invoice-report/?document_id=42` or by overriding `get()`.

### DrillDownReport

Hierarchical multi-level navigation. Requires a `hierarchy` list of `HierarchyLevel` dataclasses.

| Attribute | Required | Description |
|-----------|----------|-------------|
| `hierarchy` | Yes | List of `HierarchyLevel` defining each level |
| `max_depth` | No | Maximum drill-down depth (default: 5) |

**HierarchyLevel dataclass fields:**

| Field | Description |
|-------|-------------|
| `model` | Django model for this level |
| `display_field` | Field name shown in UI |
| `parent_field` | FK field pointing to parent level |
| `value_field` | Numeric field for aggregation (default: "pk") |
| `aggregation` | Aggregation name: sum, count, avg, min, max |
| `label` | Human-readable label |
| `columns` | Custom column list for this level |

```python
class SalesDrillDown(DrillDownReport, ReportEngineView):
    hierarchy = [
        HierarchyLevel(model=Region, display_field="name"),
        HierarchyLevel(model=Branch, display_field="name", parent_field="region"),
        HierarchyLevel(
            model=SalesPerson,
            display_field="name",
            parent_field="branch",
            value_field="total_sales",
            aggregation="sum",
        ),
    ]
```

---

## Parameter System

Parameters define filter inputs for reports. Each report type has a `parameter_spec` — a `ParameterSet` of parameter instances.

### Built-in Parameter Types

| Parameter | Form Field | Use Case |
|-----------|-----------|----------|
| `DateRangeParam(name, start_field, end_field)` | Two DateTimeFields | Date-range filtering |
| `FKFilterParam(name, model_field, multiple)` | ModelMultipleChoiceField | FK-based filtering |
| `DocumentParam(name, model)` | ModelChoiceField | Single document selection |
| `ChoiceParam(name, choices, multiple)` | ChoiceField | Static choice filtering |
| `QueryParam(name, saved_query_id)` | ModelChoiceField or CharField | Workflow engine SavedQuery |

### DateRangeParam

```python
DateRangeParam(
    name="date_range",          # used as logical name
    start_field="date_placed",  # model field for __gte filter
    end_field="date_placed",    # model field for __lte filter
    required=False,
)
```

### FKFilterParam

```python
FKFilterParam(
    name="customer",            # form field name
    model_field="customer",     # FK field path on report model
    multiple=True,              # multi-select vs single-select
)
```

Traversing FK fields are supported: `model_field="customer__region"`.

### DocumentParam

```python
DocumentParam(
    name="document_id",
    model=Invoice,              # model for choices
    lookup_field="pk",          # value field
    required=True,
)
```

### QueryParam (Workflow Engine Integration)

When `enezaworkflowengine` is installed, shows available `SavedQuery` records. When not installed, degrades to a text field.

```python
QueryParam(
    name="saved_query_id",
    workflow_name="sales_filter",  # optional: filter queries by workflow
    saved_query_id=5,              # optional: fixed query (no form field shown)
)
```

### Custom Parameters

Subclass `BaseParameter` to create custom parameter types:

```python
from enezareporting.parameters import BaseParameter

class StatusParam(BaseParameter):
    def get_form_field(self):
        return forms.ChoiceField(
            choices=[("open", "Open"), ("closed", "Closed")],
            required=self.required,
            label=self.label,
        )

    def get_filter_q(self, cleaned_data):
        val = cleaned_data.get(self.name)
        if val:
            return Q(status=val)
        return None
```

---

## Generators

Generators produce the actual report data. Each report type has a corresponding generator class.

### TabularReportGenerator

`enezareporting.generators.tabular.TabularReportGenerator`

Produces tabular data with optional group_by, time-series, and crosstab.

```python
gen = TabularReportGenerator(
    report_model=SalesLine,
    columns=["item_description", "__total__"],
    group_by="item_code",
    start_date=start,
    end_date=end,
    date_field="date_placed",
)
data = gen.get_report_data()          # list of dicts
columns = gen.get_columns_data()      # column metadata
full = gen.get_full_response()        # {data, columns, metadata, chart_settings}
```

### DocumentReportGenerator

`enezareporting.generators.document.DocumentReportGenerator`

```python
gen = DocumentReportGenerator(
    header_model=Invoice,
    lines_related_name="lines",
    header_fields=["invoice_number", "customer"],
    line_columns=["item", "quantity", "line_total"],
    line_total_fields=["line_total"],
)
result = gen.get_report_data(document_id=42)
# result = {
#     "header": {"invoice_number": {"label": "Invoice #", "value": "INV-001"}, ...},
#     "lines": [{"item": "Widget", "quantity": 5, "line_total": 100}, ...],
#     "totals": {"line_total": 350},
# }
```

### DrillDownReportGenerator

`enezareporting.generators.drilldown.DrillDownReportGenerator`

```python
gen = DrillDownReportGenerator(
    hierarchy=[
        HierarchyLevel(model=Region, display_field="name"),
        HierarchyLevel(model=Branch, display_field="name", parent_field="region"),
    ],
)
result = gen.get_report_data(level_index=0)           # root level
result = gen.get_report_data(level_index=1, path_ids=[1])  # branches in region 1

# Check if a row can be drilled into:
can = gen.can_drill_down(level_index=0, row_id=1)
```

### Using Generators Directly

You can use generators outside of views — in management commands, API endpoints, or background tasks:

```python
from enezareporting.generators.tabular import TabularReportGenerator

def export_sales_report():
    gen = TabularReportGenerator(
        report_model=SalesLine,
        columns=["item_description", "__total__"],
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        date_field="date_placed",
    )
    return gen.get_report_data()
```

---

## Views

### ReportEngineView (Recommended)

The new unified view base class. Use with multiple inheritance:

```python
class MyReport(TabularReport, ReportEngineView):
    report_model = SalesLine
    columns = [...]
    parameter_spec = ParameterSet(...)
```

`ReportEngineView` automatically:
1. Resolves the report type from the class MRO
2. Builds the correct form from `parameter_spec`
3. Instantiates the correct generator
4. Adds type-specific context (document_header, drilldown_breadcrumb, etc.)

### Legacy Views (Backward Compatible)

These continue to work and are not deprecated:

| View | Use Case |
|------|----------|
| `ReportView` | Standard report with inline form |
| `ModalReportView` | Report with right-side modal filter |
| `ListReportView` | Flat list view (no aggregation) |
| `ReportViewBase` | Bare base class (customize everything) |

Legacy views use `report_form_factory()` for form building — still functional.

### View Class Attributes

| Attribute | Description |
|-----------|-------------|
| `report_title` | Display title (defaults to class name) |
| `report_slug` | URL/identifier slug |
| `template_name` | Template path |
| `use_modal_filter` | Use right-side modal instead of inline form |
| `auto_load` | Auto-load data on page open |
| `chart_settings` | List of Chart configs |
| `company_name` | Company name for print header |
| `currency` | Currency code for print header |

---

## Templates

All reports render through `eneza_reporting/base.html` → `eneza_reporting/report.html`. The unified layout provides:
- Top toolbar (zoom, print, export, theme toggle)
- Left sidebar (export options, document info / data stats)
- A4 page content area with dark surround

### Template Blocks

| Block | Used By |
|-------|---------|
| `document_report_content` | DocumentReport — header grid + lines table + totals |
| `drilldown_report_content` | DrillDownReport — breadcrumb + drill-down table |
| `content` (default) | Tabular/Crosstab/TimeSeries — standard data table |

### Override Partials

Override these templates in your project to customize appearance:

| Template | Purpose |
|----------|---------|
| `eneza_reporting/print_report_header.html` | Header with company name, date range, document ref |
| `eneza_reporting/print_report_footer.html` | Footer with confidentiality notice |
| `eneza_reporting/document_report.html` | Document report content block |
| `eneza_reporting/drilldown_report.html` | Drill-down report content block |
| `eneza_reporting/leftsidebar.html` | Sidebar with export actions and info |

### Template Tags

```djangotemplate
{% load eneza_reporting_tags %}

{# Get a widget for a report #}
{% get_widget_from_url url_name="my_report" title="Sales" %}

{# Get a dict value by key #}
{{ my_dict|get_item:"key_name" }}

{# Get a list from QueryDict #}
{{ request.GET|get_list:"path" }}
```

---

## Settings

Configure via `ENEZA_REPORTING_SETTINGS` in Django settings:

```python
ENEZA_REPORTING_SETTINGS = {
    "QUERY_INTEGRATION_ENABLED": True,     # Enable workflow engine SavedQuery integration
    "DRILLDOWN_MAX_DEPTH": 5,              # Max drill-down levels
    "DRILLDOWN_TEMPLATE": "",              # Custom drill-down template override
    "DOCUMENT_TEMPLATE": "",               # Custom document template override
    "DOCUMENT_DEFAULTS": {
        "company_name": "My Company Ltd.",
        "currency": "USD",
        "footer_text": "Confidential",
    },
    "DEFAULT_START_DATE_TIME": datetime(2024, 1, 1),
    "DEFAULT_END_DATE_TIME": datetime.now(),
    "CHARTS": {
        "highcharts": {
            "entryPoint": "$.eneza_reporting.highcharts.displayChart",
            "js": ("https://cdn.jsdelivr.net/npm/highcharts@11/highcharts.js",),
        },
    },
    "MESSAGES": {
        "total": "Total",
        "export_to_csv": "Export to CSV",
        "print_report": "Print",
    },
    "REPORT_VIEW_ACCESS_FUNCTION": "enezareporting.helpers.user_test_function",
}
```

---

## Migration Guide

### From Legacy ReportView to ReportEngineView

**Before (old API):**

```python
from enezareporting.views import ReportView
from enezareporting.fields import ComputationField
from django.db.models import Sum

class SalesReport(ReportView):
    report_model = SalesLine
    date_field = "date_placed"
    group_by = "item_code"
    columns = [
        "item_description",
        ComputationField.create(Sum, "value", name="total_sales", verbose_name="Total Sales"),
    ]
```

**After (new API):**

```python
from enezareporting.report_types import TabularReport
from enezareporting.parameters import ParameterSet, DateRangeParam, FKFilterParam
from enezareporting.views import ReportEngineView

class SalesReport(TabularReport, ReportEngineView):
    report_model = SalesLine
    date_field = "date_placed"
    group_by = "item_code"
    columns = [
        "item_description",
        "__total__",  # use registered computation field name
    ]
    parameter_spec = ParameterSet(
        DateRangeParam(name="date_range", start_field="date_placed"),
        FKFilterParam(name="customer", model_field="customer"),
    )
```

### Key Changes

| Old | New |
|-----|-----|
| Inherit `ReportView` | Inherit `ReportType` subclass + `ReportEngineView` |
| Form auto-built from FK fields | Form built from `parameter_spec` |
| `ComputationField.create(Sum, "value", ...)` | Use registered name `"__total__"` or import the field class |
| No parameter declaration | Declare `parameter_spec = ParameterSet(...)` |

### Backward Compatibility

All existing classes continue to work:
- `ReportView`, `ModalReportView`, `ListReportView` → unchanged
- `ReportGenerator`, `ListViewReportGenerator` → unchanged
- `ReportGeneratorAPI`, `Chart` → unchanged
- `ComputationField`, `field_registry` → unchanged
- All existing template paths and tag names → unchanged

---

## API Reference

### `parameters.py`

```
BaseParameter
├── DateRangeParam(name, start_field, end_field, required)
├── FKFilterParam(name, model_field, multiple, queryset_filter_func)
├── DocumentParam(name, model, lookup_field, display_field)
├── ChoiceParam(name, choices, multiple)
└── QueryParam(name, saved_query_id, workflow_name)

ParameterSet(*parameters)
    .get_form_class(report_model, initial) → Form class
    .get_filters(cleaned_data) → (Q, kw_filters)
    .get_initial() → dict
    .get_parameter(name) → BaseParameter
```

### `report_types.py`

```
ReportType (ABC)
├── DocumentReport
├── TabularReport
│   ├── SummaryReport
│   └── DetailedReport
├── CrosstabReport
├── TimeSeriesReport
└── DrillDownReport

HierarchyLevel(model, display_field, parent_field, value_field, aggregation, label, columns)
```

### `generators/`

```
generators.tabular.TabularReportGenerator
generators.crosstab.CrosstabReportGenerator
generators.time_series.TimeSeriesReportGenerator
generators.document.DocumentReportGenerator
generators.drilldown.DrillDownReportGenerator
```

### `views.py`

```
ReportEngineView  (new unified view)
ReportView        (legacy, backward compatible)
ModalReportView   (legacy, backward compatible)
ListReportView    (legacy, backward compatible)
ReportViewBase    (legacy, backward compatible)
```

---

## Examples

### Complete Invoice Report

```python
# myapp/reports.py
from enezareporting.report_types import DocumentReport
from enezareporting.parameters import ParameterSet, DocumentParam
from enezareporting.views import ReportEngineView
from myapp.models import Invoice, InvoiceLine

class InvoiceReport(DocumentReport, ReportEngineView):
    report_title = "Sales Invoice"
    header_model = Invoice
    header_fields = [
        "invoice_number", "customer", "date", "due_date",
        "status", "payment_terms",
    ]
    lines_related_name = "lines"
    line_columns = [
        "item_code", "description", "quantity",
        "unit_price", "discount_percent", "line_total",
    ]
    line_total_fields = ["line_total", "quantity"]
    parameter_spec = ParameterSet(
        DocumentParam(name="document_id", model=Invoice),
    )
```

```python
# myapp/urls.py
from django.urls import path
from myapp.reports import InvoiceReport

urlpatterns = [
    path("invoice/<int:document_id>/", InvoiceReport.as_view(), name="invoice_report"),
]
```

### Complete Drill-Down Report

```python
# myapp/reports.py
from enezareporting.report_types import DrillDownReport, HierarchyLevel
from enezareporting.views import ReportEngineView
from myapp.models import Region, Branch, SalesPerson

class SalesHierarchy(DrillDownReport, ReportEngineView):
    report_title = "Sales Hierarchy"
    max_depth = 3
    hierarchy = [
        HierarchyLevel(
            model=Region,
            display_field="name",
            label="Regions",
            columns=["name", "code"],
        ),
        HierarchyLevel(
            model=Branch,
            display_field="name",
            parent_field="region",
            label="Branches",
            columns=["name", "branch_code", "manager"],
        ),
        HierarchyLevel(
            model=SalesPerson,
            display_field="name",
            parent_field="branch",
            value_field="total_sales",
            aggregation="sum",
            label="Sales People",
            columns=["name", "email", "total_sales"],
        ),
    ]
```

### Using Computation Fields with the New API

```python
from enezareporting.report_types import TabularReport
from enezareporting.views import ReportEngineView
from enezareporting.fields import ComputationField
from django.db.models import Sum, Avg

# Registered computation fields (use by name):
columns = ["__total__", "__balance__", "__debit__", "__credit__"]

# Custom computation fields (use the class directly):
class AvgOrderValue(ComputationField):
    name = "__avg_order__"
    verbose_name = "Avg Order Value"
    calculation_method = Avg
    calculation_field = "value"

# Or create on the fly:
TotalWeight = ComputationField.create(Sum, "weight", name="total_weight", verbose_name="Total Weight")
```
