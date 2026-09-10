---
menu name: Party System
position: 5
---

# Generic Party System — Developer Guide

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start: Creating a Party-Based Model](#quick-start-creating-a-party-based-model)
4. [What the Framework Handles Automatically](#what-the-framework-handles-automatically)
5. [View Layer: What You Do and Do Not Need](#view-layer-what-you-do-and-do-not-need)
6. [Party Inline System](#party-inline-system)
7. [Party-Bridge Pattern (One-to-One Inlines)](#party-bridge-pattern-one-to-one-inlines)
8. [Template Context Variables](#template-context-variables)
9. [Migration Considerations](#migration-considerations)
10. [Complete Example: Vendor Model](#complete-example-vendor-model)
11. [Reference: PartyModelMixin API](#reference-partymodelmixin-api)

---

## Overview

The Generic Party System eliminates boilerplate when creating party-based models — models like Customer, Vendor, Contact, or any entity that needs address, contact information, and person/organization profile data.

**Before (old way):**
- Manually define `party = ForeignKey(Party, ...)` on every model
- Manually implement `get_inline_related_objects()` in every detail view to expose Address, ContactInformation, Person/Business inlines
- Manually implement `get_related_object_id()` to resolve Person/Business IDs via the Party
- Manually handle Party creation logic
- ~80+ lines of repeated boilerplate per party-based model

**After (new way):**
- Add `PartyModelMixin` to your model, define `party_category` and `get_party_defaults()`
- The framework auto-creates the backing `Party` record on first save
- Party inlines (Address, ContactInformation, Person/Business) appear automatically on the detail page — no view override needed
- The `party` field is automatically hidden from forms
- ~15 lines of model configuration total

---

## Architecture

```
PartyModelMixin (abstract Django model)
  Provides: party FK, party_category=None, get_party_defaults()

Signals (enezaframework/signals.py)
  post_save → auto-create Party for PartyModelMixin instances

BaseDetailView (enezaframework/views/base.py)
  Auto-detects party-based model
  Auto-injects party inlines: Address, ContactInformation, Person/Business
  Adds party_object to template context

InlineMixin (enezaframework/views/mixins.py)
  Handles is_party_inline flag
  Resolves related_object_id via party chain

BaseInlineOneToOneDetailView (enezaframework/views/baseinline.py)
  Party-bridge auto-detection (_is_party_bridge)
  Resolves Person/Business through parent.party
```

**Data flow on save:**
```
User saves Contact (party_category='PRS')
  → post_save signal fires
  → detects PartyModelMixin, party_category != None
  → Party.objects.create(party_type='PRS', display_name=..., is_active=True)
  → Contact.party = party; Contact.save(update_fields=['party'])
  → Party post_save signal fires (enezacommon/signals.py)
  → Person.objects.get_or_create(party=party)  ← auto-creates Person profile
```

---

## Quick Start: Creating a Party-Based Model

### Step 1: Define the Model

```python
# myapp/models/customer.py
from django.db import models
from enezaframework.models import EnezaMaster, PartyModelMixin
from enezacommon.models.choices import PartyCategory

class Customer(PartyModelMixin, EnezaMaster):       # ← Note: PartyModelMixin FIRST
    customer_no = models.CharField(max_length=50)
    customer_type = models.CharField(               # ← Must be PartyCategory choices
        max_length=5, choices=PartyCategory.choices, verbose_name="Customer Type"
    )
    # ... your other fields ...

    sequence_field_name = 'customer_no'
    document_name = 'CUSTOMER'                       # If using sequences

    @property
    def party_category(self):                        # ← REQUIRED property
        """Return the PartyCategory for this model."""
        return self.customer_type

    def get_party_defaults(self):                    # ← Override to customize display_name
        """Return defaults for the auto-created Party (entity is auto-included from base)."""
        defaults = super().get_party_defaults()
        defaults['display_name'] = self.customer_no or 'Customer'
        return defaults

    def __str__(self):
        if self.party and self.party.display_name:
            return self.party.display_name
        return self.customer_no or ''

    class Meta:
        db_table = 'customer'
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
```

**Three requirements:**
1. Inherit from `PartyModelMixin` (must come **before** `EnezaMaster` in MRO)
2. Implement `party_category` property → returns a `PartyCategory` value (`'PRS'` or `'ORG'`)
3. Optionally override `get_party_defaults()` → calls `super()` and customizes `display_name`; the base class auto-includes `entity` from the model instance

### Step 2: Define Views

```python
# myapp/views/customer_views.py
from enezaframework.views import (
    BaseListView, BaseDetailView, BaseCreateView, BaseDeleteView,
)
from enezaframework.utils import auto_url_register
from myapp.models import Customer

@auto_url_register
class CustomerListView(BaseListView):
    model = Customer

    def set_list_fields(self):
        return ['customer_no', 'party', 'customer_type', 'name']

    def set_search_fields(self):
        return ['customer_no', 'name']


@auto_url_register
class CustomerDetailView(BaseDetailView):
    model = Customer

    def detail_ui_view(self):
        return [
            {
                'name': 'Basic Information',
                'icon': 'Home',
                'Fieldcolumns': [
                    {'fields': ['customer_no', 'customer_type']},
                    {'fields': ['name', 'email']},
                ],
                # NOTE: Do NOT include 'party' in Fieldcolumns — it is auto-hidden
            },
        ]
```

**That is it.** The detail page will now show Address, ContactInformation, and Person/Business inlines automatically — no `get_inline_related_objects()` override needed.

---

## What the Framework Handles Automatically

| Concern | Handled By | Mechanism |
|---------|-----------|-----------|
| `party` ForeignKey field | `PartyModelMixin` | Abstract model contributes `party` FK to child |
| Party auto-creation on save | `enezaframework.signals` | `post_save` receiver checks `isinstance(instance, PartyModelMixin)` |
| Person/Business profile auto-creation | `enezacommon.signals` | `Party` `post_save` signal (existing) |
| Party inlines on detail page | `BaseDetailView._get_party_inline_objects()` | Auto-injects Address + ContactInformation + (Person or Business) |
| `party_object` in template context | `BaseDetailView.get_context_data()` | `context['party_object'] = getattr(self.object, 'party', None)` |
| `is_party_inline` flag on inline items | `BaseDetailView._get_party_inline_objects()` | Flag added to each inline dict |
| Party PK in inline URLs | `detail_partial.html` | Template checks `inline_item.is_party_inline` → uses `party_object.pk` |
| `party` field hidden from forms | `UiMixin.get_form_class()` | Auto-excludes `party` for models with FK to Party |
| Related-object resolution (one-to-one) | `BaseInlineOneToOneDetailView._is_party_bridge()` | Auto-detects party chain: parent → parent.party → profile |

---

## View Layer: What You Do and Do Not Need

**You DO need to define:**
- List view with `set_list_fields()` and `set_search_fields()`
- Detail view with `detail_ui_view()` → form field layout
- Create view with `detail_ui_view()` → form field layout
- Delete view (trivial, just `model = ...`)

**You do NOT need to define:**
- `get_inline_related_objects()` — handled by `BaseDetailView`
- `get_related_object_id()` — handled by `InlineMixin` for party inlines
- Any logic to create/link the Party — handled by signals

**You MAY optionally define:**
- Additional non-party inlines (override `get_inline_related_objects()`, call `super()` to get party inlines, then append your own)
- Inline detail views for Person/Business (for backward compatibility with old URLs)

---

## Party Inline System

When a model inherits from `PartyModelMixin`, its detail page automatically displays:

### Static Inlines (always shown)
| Inline | Model | Relation | Template |
|--------|-------|----------|----------|
| Address | `Address` | FK to Party (`addresses`) | `inline_list_add_con_partial.html` |
| Contact Information | `ContactInformation` | FK to Party (`contact_information`) | `inline_list_add_con_partial.html` |

### Conditional Inlines (shown based on `party_type`)
| Party Type | Inline | Model | Relation |
|-----------|--------|-------|----------|
| `PRS` (Person) | Personal Details | `Person` | OneToOne to Party (`person_profile`) |
| `ORG` (Organization) | Business Details | `Business` | OneToOne to Party (`business_profile`) |

These inlines use the Party views (`PartyAddresslistView`, `PartyContactInformationlistView`, `PartyPersonView`, `PartyBusinessView`) — the `parent_model` is `Party`, and `main_object_pk` is the Party's primary key.

---

## Party-Bridge Pattern (One-to-One Inlines)

For backward compatibility or custom one-to-one inline views where `parent_model` is your party-based model (not Party itself), `BaseInlineOneToOneDetailView` provides automatic party-bridge resolution.

**Auto-detection:** `_is_party_bridge()` returns `True` when:
1. The inline model (e.g., `Person`) has a `party` FK to `Party`
2. The parent model (e.g., `Customer`) has a `party` FK to `Party`

When a bridge is detected, the base class automatically:
- `find_field_by_related_name()` → returns `'party'`
- `get_object()` → resolves: `parent_instance.party` → `model.objects.get(party=...)`
- `form_valid()` → sets `form.instance.party = parent_instance.party`

**Minimal inline view example:**
```python
@auto_url_register
class CustomerPersonInlineDetailView(BaseInlineOneToOneDetailView):
    model = Person
    parent_model = Customer
    related_name = 'person_profile'

    def detail_ui_view(self):
        return [{
            'name': 'Personal Information',
            'icon': 'Home',
            'Fieldcolumns': [
                {'fields': ['first_name', 'middle_name', 'last_name']},
                {'fields': ['birthday', 'email']},
            ],
        }]
```

No `find_field_by_related_name()`, `get_object()`, or `form_valid()` overrides needed — the base class handles everything via party-bridge detection.

---

## Template Context Variables

### In `detail_partial.html` (parent detail page)
| Variable | Description |
|----------|-------------|
| `party_object` | The `Party` instance (or `None` if no party linked) |
| `party_object.pk` | Party primary key — used in inline HTMX URLs for party inlines |
| `object.id` | Parent model primary key — used for non-party inline URLs |

### In party inline templates (loaded via HTMX)
| Variable | Description |
|----------|-------------|
| `party_object` | The `Party` instance (resolved from `main_object_pk` by base inline views) |
| `party_object.pk` | Party PK — used in form actions, detail links, delete links |
| `main_object_pk` | Raw query parameter (kept for backward compatibility) |

### Key template change
Previously all inlines used `{{main_object_pk}}` from the inline view context. Party inlines now use `{{party_object.pk}}` — the Party object is resolved by `BaseInlineListView`, `BaseInlineDetailView`, and `BaseInlineCreateView` when `parent_model == Party`.

---

## Migration Considerations

### New party-based models
When creating a **new** model with `PartyModelMixin`, run `makemigrations` normally — Django will create the `party_id` column automatically.

### Migrating existing models to use PartyModelMixin
If converting an existing model (like the `Contact` pilot):

1. Add `PartyModelMixin` to the model's base classes
2. Remove the manual `party = ForeignKey(Party, ...)` line
3. Add `party_category` property and optionally override `get_party_defaults()` method
4. Run `makemigrations` — Django may generate separate remove+add migrations
5. **Verify the migration does NOT drop the column** — you need only an `AlterField` to update the `related_name`
6. If Django generates `RemoveField` + `AddField`, delete those and create a manual `AlterField`:

```python
# Manual migration — only changes related_name, no DB column change
migrations.AlterField(
    model_name='contact',
    name='party',
    field=models.ForeignKey(
        blank=True, null=True,
        on_delete=django.db.models.deletion.PROTECT,
        related_name='%(class)s_party',    # ← new related_name
        to='enezacommon.party',
        verbose_name='Party',
    ),
),
```

The old `related_name` (e.g., `master_contacts`) changes to `%(class)s_party` which resolves to the model name (e.g., `contact_party`). This is a metadata-only change — no SQL is executed.

---

## Complete Example: Vendor Model

```python
# accountpayable/models/vendortable.py
from django.db import models
from enezaframework.models import EnezaMaster, PartyModelMixin
from enezacommon.models.choices import PartyCategory

class VendorTable(PartyModelMixin, EnezaMaster):
    vendorno = models.CharField(max_length=50, verbose_name="Vendor No")
    searchname = models.CharField(max_length=255, verbose_name="Search Name")
    vendortype = models.CharField(
        max_length=5, choices=PartyCategory.choices, verbose_name="Vendor Type"
    )
    blocked = models.BooleanField(default=False)

    sequence_field_name = 'vendorno'
    document_name = 'VENDOR'

    @property
    def party_category(self):
        return self.vendortype

    def get_party_defaults(self):
        defaults = super().get_party_defaults()
        defaults['display_name'] = self.searchname or self.vendorno or 'Vendor'
        defaults['is_active'] = not self.blocked
        return defaults

    def __str__(self):
        if self.party and self.party.display_name:
            return self.party.display_name
        return self.searchname or 'Vendor'

    class Meta:
        db_table = 'vendor'
        verbose_name = "Vendor"
        verbose_name_plural = "Vendors"
```

```python
# accountpayable/views/vendor_views.py
from enezaframework.views import (
    BaseListView, BaseDetailView, BaseCreateView, BaseDeleteView,
)
from enezaframework.utils import auto_url_register
from accountpayable.models import VendorTable

@auto_url_register
class VendorTableListView(BaseListView):
    model = VendorTable

    def set_list_fields(self):
        return ['vendorno', 'party', 'vendortype', 'searchname', 'blocked']

    def set_search_fields(self):
        return ['vendorno', 'searchname']


@auto_url_register
class VendorTableDetailView(BaseDetailView):
    model = VendorTable

    def detail_ui_view(self):
        return [
            {
                'name': 'Vendor Information',
                'icon': 'Home',
                'Fieldcolumns': [
                    {'fields': ['vendorno', 'vendortype']},
                    {'fields': ['searchname', 'blocked']},
                ],
            },
        ]
    # No get_inline_related_objects() needed — party inlines auto-injected
    # No get_related_object_id() needed — resolved via party chain


@auto_url_register
class VendorTableCreateView(BaseCreateView):
    model = VendorTable

    def detail_ui_view(self):
        return [
            {
                'name': 'Vendor Information',
                'icon': 'Home',
                'Fieldcolumns': [
                    {'fields': ['vendorno', 'vendortype']},
                    {'fields': ['searchname', 'blocked']},
                ],
            },
        ]


@auto_url_register
class VendorTableDeleteView(BaseDeleteView):
    model = VendorTable
```

---

## Reference: PartyModelMixin API

| Attribute / Method | Type | Description |
|-------------------|------|-------------|
| `party` | `ForeignKey` | Auto-provided FK to `Party` (`null=True, blank=True, on_delete=PROTECT`) |
| `party_category` | `property` | **Must override.** Returns `'PRS'` or `'ORG'` (PartyCategory). Determines Person vs Business profile. |
| `party_related_name` | `class attr` | Optional. Override the FK reverse name. Default: `'%(class)s_party'` |
| `get_party_defaults()` | `method` | **May override.** Returns dict for `Party.objects.create()`. Override to customize `display_name` — call `super()` to inherit auto-included `entity` and `party_type`. |
| `_resolve_party_related_name()` | `classmethod` | Returns the resolved related_name. Internal use. |

### MRO Ordering

```python
class YourModel(PartyModelMixin, EnezaMaster):   # ← PartyModelMixin FIRST
```

Place `PartyModelMixin` before `EnezaMaster` to ensure the `party` FK is contributed correctly via Django's abstract model field resolution.

### Signal Chain

```
YourModel.save() (created=True)
  → auto_create_party_for_party_model  (enezaframework/signals.py)
    → Party.objects.create(party_type=..., display_name=..., is_active=True)
    → your_model.party = party; your_model.save(update_fields=['party'])
  → create_org_or_person_profile       (enezacommon/signals.py)
    → Person.objects.get_or_create(party=party)   OR
    → Business.objects.get_or_create(party=party)
```
