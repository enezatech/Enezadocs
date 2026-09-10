---
menu name: Sequence Generation
position: 6
---

# Eneza Framework Sequence Generation — Developer Guide

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Sequence Configuration Model](#sequence-configuration-model)
5. [Defining Custom Document and Module Choices](#defining-custom-document-and-module-choices)
6. [Using SequenceMixin in Models](#using-sequencemixin-in-models)
7. [Setting Up Sequences in Admin](#setting-up-sequences-in-admin)
8. [Template Integration](#template-integration)
9. [Settings Configuration](#settings-configuration)
10. [Best Practices](#best-practices)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The Eneza Framework provides a flexible sequence generation system that allows you to automatically generate unique document numbers for your models. The system supports configurable prefixes, delimiters, number lengths, and per-entity sequences.

**Key Features:**
- Automatic sequence generation for model fields
- Configurable prefixes, delimiters, and number formats
- Multi-entity support with separate sequences per entity
- Pluggable choice system for documents and modules
- Automatic increment of sequence numbers

**Use Cases:**
- Invoice numbers (INV-0001, INV-0002, ...)
- Purchase orders (PO-2024-001, PO-2024-002, ...)
- Customer codes (CUST-001, CUST-002, ...)
- Vendor numbers (VEND-001, VEND-002, ...)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ SequenceMixin (enezaframework/services/Mixin.py)     │
│ - generate_sequence() method                        │
│ - Automatic save() hook                           │
│ - Field assignment logic                          │
├─────────────────────────────────────────────────────┤
│ Base Models with Sequence Support                   │
│ - EnezaMaster → includes SequenceMixin            │
│ - EnezaDocument → includes SequenceMixin          │
│ - EnezaGeneral → does NOT include SequenceMixin   │
├─────────────────────────────────────────────────────┤
│ SequenceConfig (enezaframework/models/enezasequence.py) │
│ - Stores sequence configuration per document type │
│ - Tracks next number to use                       │
│ - Configurable prefix, delimiter, length         │
├─────────────────────────────────────────────────────┤
│ Choice System (enezaframework/models/choices.py)     │
│ - get_number_sequences_choices() → pluggable docs │
│ - get_modules_choices() → pluggable modules     │
│ - Default choices fallback                       │
├─────────────────────────────────────────────────────┤
│ Model Integration                                 │
│ - Inherit EnezaMaster/EnezaDocument              │
│ - Define sequence_field_name                     │
│ - Define document_name                           │
└─────────────────────────────────────────────────────┘
```

---

## Quick Start

### Step 1: Define Your Model (SequenceMixin Already Included)

```python
from enezaframework.models import EnezaMaster
from your_project.choices import YourDocumentTypes

class Customer(EnezaMaster):
    customer_code = models.CharField(max_length=50, null=True, blank=True)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    
    # Required: field that will store the sequence
    sequence_field_name = 'customer_code'
    
    # Required: document type identifier
    document_name = YourDocumentTypes.CUSTOMER
    
    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
    
    def __str__(self):
        return self.customer_code or self.name
```

### Step 2: Configure Document Types (Optional)

```python
# your_project/choices.py
from django.db import models

class YourDocumentTypes(models.TextChoices):
    CUSTOMER = 'CUST', "Customer"
    VENDOR = 'VEND', "Vendor"
    INVOICE = 'INV', "Invoice"
    PURCHASE_ORDER = 'PO', "Purchase Order"
```

### Step 3: Configure in Settings

```python
# settings.py
YOUR_PACKAGE_NUMBER_SEQUENCE_DOCUMENT = 'your_project.choices.YourDocumentTypes'
YOUR_PACKAGE_MODULES = 'your_project.choices.YourModules'
```

### Step 4: Set Up Sequence Configuration

In the admin interface, create a new Sequence Configuration:
- **Document**: Customer
- **Prefix**: CUST
- **Delimiter**: -
- **Number Length**: 4
- **Active**: Yes
- **Module**: CRM

Result: First Customer will get CUST-0001, next will be CUST-0002, etc.

---

## Sequence Configuration Model

### Model Definition

The `SequenceConfig` model stores all the configuration needed for sequence generation:

```python
class SequenceConfig(EnezaModel):
    documents = models.CharField(
        max_length=50,
        null=False,
        choices=get_number_sequences_choices().choices,
        help_text="Choose the model for this sequence configuration."
    )
    prefix = models.CharField(
        max_length=10,
        null=False,
        help_text="Prefix like 'IV', 'CR', etc."
    )
    delimiter = models.CharField(
        max_length=1,
        default='-',
        help_text="Delimiter like '-', '_', etc."
    )
    number_length = models.PositiveIntegerField(
        default=4,
        null=False,
        help_text="Length of the number sequence (e.g., 4 for '0001')."
    )
    active = models.BooleanField(default=False)
    nextnumber = models.PositiveIntegerField(
        default=1,
        help_text="Next number for the sequence."
    )
    modules = models.CharField(
        max_length=50,
        null=False,
        choices=get_modules_choices().choices,
        help_text="Choose the module for this sequence configuration."
    )
    entity = models.ForeignKey(
        Entity, 
        on_delete=models.PROTECT, 
        blank=True, 
        null=True,
        help_text="Entity to which this sequence configuration belongs."
    )
```

### Key Fields

| Field | Purpose | Example |
|-------|---------|---------|
| `documents` | Document type identifier | CUSTOMER, INVOICE, VENDOR |
| `prefix` | Alpha prefix for sequence | CUST, INV, PO |
| `delimiter` | Character between prefix and number | -, _, / |
| `number_length` | Width of numeric portion | 4 → 0001, 6 → 000001 |
| `active` | Whether this config is usable | Only one can be active per document |
| `nextnumber` | Next number to assign | Incremented after each use |
| `modules` | Module category for organization | CRM, FINANCE, INVENTORY |
| `entity` | Multi-tenant support | Separate sequences per company |

### Unique Constraint

The model includes a unique constraint to ensure only one active sequence per document type:
```python
constraints = [
    models.UniqueConstraint(
        fields=['documents', 'active'], 
        name='unique_model_name_active'
    )
]
```

---

## Defining Custom Document and Module Choices

### Document Types

The system uses a pluggable choice system that allows you to define your own document types:

```python
# your_project/choices.py
from django.db import models

class YourDocumentTypes(models.TextChoices):
    CUSTOMER = 'CUST', "Customer"
    VENDOR = 'VEND', "Vendor"
    INVOICE = 'INV', "Invoice"
    PURCHASE_ORDER = 'PO', "Purchase Order"
    QUOTATION = 'QT', "Quotation"
    DELIVERY_NOTE = 'DN', "Delivery Note"
```

### Module Categories

```python
# your_project/choices.py
class YourModules(models.TextChoices):
    CRM = 'CRM', "Customer Relationship Management"
    FINANCE = 'FIN', "Finance"
    INVENTORY = 'INV', "Inventory Management"
    PURCHASING = 'PUR', "Purchasing"
    SALES = 'SAL', "Sales"
```

### Settings Configuration

```python
# settings.py
YOUR_PACKAGE_NUMBER_SEQUENCE_DOCUMENT = 'your_project.choices.YourDocumentTypes'
YOUR_PACKAGE_MODULES = 'your_project.choices.YourModules'
```

### Default Fallback

If no custom choices are defined in settings, the system falls back to default choices defined in `enezaframework/models/choices.py` with warning messages.

---

## Using SequenceMixin in Models

### Basic Implementation

```python
from enezaframework.models import EnezaMaster
from your_project.choices import YourDocumentTypes

class Invoice(EnezaMaster):
    invoice_number = models.CharField(max_length=50, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    
    # Required: specify which field stores the sequence
    sequence_field_name = 'invoice_number'
    
    # Required: specify document type for sequence lookup
    document_name = YourDocumentTypes.INVOICE
    
    class Meta:
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
```

### Multiple Sequence Fields

**Important Note: Multiple sequence fields per model are not currently supported by the standard SequenceMixin implementation.** 

The Eneza Framework's SequenceMixin is designed to work with a single sequence field per model, identified by the `sequence_field_name` attribute. Attempting to configure multiple sequence fields in the standard way will not work correctly.

**Current Limitation:**
- Only one sequence field can be automatically managed per model
- The `sequence_field_name` attribute can only point to a single field
- The auto-generation hook only handles one field

**Workaround Options:**

If you need multiple sequential fields, you would need to implement custom sequence logic by overriding the save method. However, this is complex because the SequenceMixin already implements save() logic:

```python
class ComplexDocument(EnezaMaster):
    primary_seq = models.CharField(max_length=50, null=True, blank=True)
    secondary_seq = models.CharField(max_length=50, null=True, blank=True)
    
    # This approach won't work well with multiple sequences
    # because the mixin only handles one sequence_field_name
    sequence_field_name = 'primary_seq'
    document_name = YourDocumentTypes.COMPLEX_DOC
    
    def save(self, *args, **kwargs):
        # Get the current state of the object to avoid conflicts
        is_new = self._state.adding  # Check if this is a new object
        
        # Let the parent class (which includes SequenceMixin) handle the primary sequence
        # We need to be careful here to avoid conflicts with the mixin's save method
        
        # The standard save will handle primary_seq through the mixin
        super().save(*args, **kwargs)
        
        # If you need a secondary sequence, you'd need to update it after the first save
        if is_new and not self.secondary_seq:
            # Generate secondary sequence after the initial save
            secondary_config = SequenceConfig.objects.filter(
                documents=YourDocumentTypes.SECONDARY_DOC,
                active=True
            ).first()
            
            if secondary_config:
                formatted_num = f"{secondary_config.nextnumber:0{secondary_config.number_length}d}"
                self.secondary_seq = f"{secondary_config.prefix}{secondary_config.delimiter}{formatted_num}"
                
                # Update the config number
                secondary_config.nextnumber += 1
                secondary_config.save()
                
                # Update only the secondary_seq field
                super().save(update_fields=['secondary_seq'])
```

**Important Considerations for Multiple Sequences:**
- The standard SequenceMixin only supports one sequence field per model
- Overriding save() to add multiple sequences requires careful coordination to avoid conflicts
- Sequence number incrementing could be inconsistent in concurrent environments
- The complexity makes this approach error-prone

**Recommended Approach:**
- Use only one sequence field per model following the standard pattern
- For related sequential data, consider separate models or computed fields
- If multiple sequences are absolutely required, create a custom mixin that extends SequenceMixin
- Consider if multiple sequence fields are truly necessary - often a single well-designed sequence meets the requirements

### Custom Sequence Generation Logic

You can override the `generate_sequence` method for custom logic:

```python
class YearlyInvoice(EnezaMaster):
    invoice_number = models.CharField(max_length=50, null=True, blank=True)
    year = models.IntegerField()
    
    sequence_field_name = 'invoice_number'
    document_name = YourDocumentTypes.YEARLY_INVOICE
```

---

## Setting Up Sequences in Admin

### Creating Sequence Configuration

1. Navigate to **System Administrator** → **Number Sequences**
2. Click **Create New** or **Edit Existing**
3. Fill in the configuration:

**Basic Settings:**
- **Document**: Select your document type (Customer, Invoice, etc.)
- **Module**: Select the module category
- **Active**: Check this to make it the active sequence for this document type

**Format Settings:**
- **Prefix**: Alphanumeric prefix (CUST, INV, PO, etc.)
- **Delimiter**: Character between prefix and number (-, _, /, etc.)
- **Number Length**: Number of digits (4 → 0001, 6 → 000001)

**Entity Settings:**
- **Entity**: Select specific entity (leave blank for all entities)

### Managing Sequences

- Only one sequence per document type can be active at a time
- Inactive sequences can be kept as historical records
- To change sequence format, deactivate old one and create new one
- Resetting `nextnumber` allows reusing sequence numbers (be careful!)

### Example Configurations

| Document | Prefix | Delimiter | Length | Format Example | Notes |
|----------|--------|-----------|--------|----------------|-------|
| Customer | CUST | - | 4 | CUST-0001 | Start at 1 |
| Invoice | INV | - | 5 | INV-00001 | Start at 1001 for existing customers |
| Purchase Order | PO | / | 3 | PO/001 | Short format for POs |
| Employee | EMP | - | 4 | EMP-0001 | HR module |

---

## Template Integration

### Displaying Sequence Format Preview

The `SequenceConfig` model includes a helper method:

```python
def get_sequence_format(self):
    formatted_number = '#' * self.number_length  # Use '#' to represent number length
    return f"{self.prefix}{self.delimiter}{formatted_number}"
```

This returns a preview like "CUST-####" or "INV-#####" for UI display.

### Admin Template Helpers

In admin interfaces, you can show the expected format:

```html
<!-- In sequence admin template -->
<div class="sequence-preview">
    <strong>Expected Format:</strong>
    <code>{{ sequence_config.get_sequence_format }}</code>
</div>
```

### Form Validation

The system automatically validates that the sequence field gets populated before saving:

```python
# In save() method
if not getattr(self, sequence_field_name, None):
    sequence_value = self.generate_sequence()
    setattr(self, sequence_field_name, sequence_value)
```

---

## Settings Configuration

### Project-Level Customization

```python
# settings.py
# Custom document types for sequence generation
YOUR_PACKAGE_NUMBER_SEQUENCE_DOCUMENT = 'myproject.choices.CustomDocumentTypes'

# Custom module categories
YOUR_PACKAGE_MODULES = 'myproject.choices.CustomModules'
```

### Default Values

If settings are not provided, the system uses defaults from `enezaframework/models/choices.py`:

```python
# Default document types include:
- AUDIT_REPORT, BANK, BANK_DEPOSIT_SLIP, BANK_JOURNAL, etc.
- CUSTOMER, VENDOR, INVOICE, PURCHASE_ORDER, etc.
- EMPLOYEE, EXPENSE, INVENTORY, etc.

# Default modules include:
- GENERAL_LEDGER, ACCOUNTS_PAYABLE, ACCOUNTS_RECEIVABLE
- CUSTOMER_ENGAGEMENT, FIXED_ASSETS, INVENTORY_MANAGEMENT
- PAYROLL, CASH_MANAGEMENT, etc.
```

### Warning Messages

When custom choices cannot be imported, the system shows warnings:

```
WARNING: Could not import myapp.choices.projectSequencesDocument: No module named 'myapp.choices'. Using default choices.
```

---

## Best Practices

### 2. Choose the Right Base Model

The Eneza Framework provides several base models that already include SequenceMixin:

- **EnezaMaster**: For master data records (customers, vendors, products, etc.)
- **EnezaDocument**: For document records (invoices, orders, etc.)
- **EnezaGeneral**: For general records without sequence

**Models with Sequence Support:**
```python
from enezaframework.models import EnezaMaster, EnezaDocument

class Customer(EnezaMaster):  # ← Already includes SequenceMixin
    customer_code = models.CharField(max_length=50, null=True, blank=True)
    sequence_field_name = 'customer_code'
    document_name = YourDocumentTypes.CUSTOMER

class Invoice(EnezaDocument):  # ← Already includes SequenceMixin
    invoice_number = models.CharField(max_length=50, null=True, blank=True)
    sequence_field_name = 'invoice_number'
    document_name = YourDocumentTypes.INVOICE
```

**Models without Sequence Support:**
```python
from enezaframework.models import EnezaGeneral

class Setting(EnezaGeneral):  # ← Does not include SequenceMixin
    name = models.CharField(max_length=100)
    value = models.TextField()
    # No sequence generation needed
```

### 3. Proper Model Declaration

When creating models that need sequence generation, remember:

1. **DO NOT** inherit from SequenceMixin separately - it's already included in EnezaMaster and EnezaDocument
2. **DO** inherit from EnezaMaster for master data or EnezaDocument for document data
3. **DO** define both `sequence_field_name` and `document_name`
4. **DO** ensure the sequence field is nullable (`null=True, blank=True`)

**Correct:**
```python
class Product(EnezaMaster):  # ← Proper inheritance
    product_code = models.CharField(max_length=50, null=True, blank=True)
    name = models.CharField(max_length=200)
    
    sequence_field_name = 'product_code'  # ← Required
    document_name = YourDocumentTypes.PRODUCT  # ← Required
```

**Incorrect:**
```python
class Product(SequenceMixin, EnezaMaster):  # ← Don't double-inherit
    # This could cause issues with the MRO (Method Resolution Order)
```

### 2. Use Meaningful Prefixes

Choose prefixes that are:
- Short but meaningful (3-6 characters)
- Consistent across your system
- Unique per document type
- Easy to understand for end users

```
Good: CUST, INV, PO, SO, EMP
Bad: C, I, P, S, E
```

### 3. Plan Number Lengths Carefully

Consider your volume:
- 4 digits: 0001-9999 (10K records)
- 5 digits: 00001-99999 (100K records)
- 6 digits: 000001-999999 (1M records)

### 4. Test Sequence Roll-Over

Test what happens when sequences reach their maximum:
```python
# If number_length=4, test what happens at 9999
# Should roll over to 10000 or reset appropriately
```

### 5. Handle Concurrent Access

The current implementation is thread-safe for single-server deployments but may need additional locking for high-concurrency scenarios.

### 6. Backup Sequence Numbers

Include `nextnumber` in your backup strategy to prevent duplicate sequences after restore.

### 7. Monitor Sequence Usage

Track which sequences are approaching their limits:

```python
# Admin dashboard showing sequence utilization
def sequence_health_check():
    configs = SequenceConfig.objects.filter(active=True)
    for config in configs:
        utilization = (config.nextnumber - 1) / (10 ** config.number_length)
        if utilization > 0.9:  # 90% utilized
            print(f"Warning: {config} is {utilization:.1%} utilized")
```

---

## Troubleshooting

### Common Issues

**Issue**: Sequence field remains empty after saving
**Cause**: Missing `sequence_field_name` or `document_name` definition
**Solution**: Ensure both attributes are set in your model

```python
class MyModel(EnezaMaster):  # ← Already includes SequenceMixin
    my_field = models.CharField(max_length=50, null=True, blank=True)
    
    sequence_field_name = 'my_field'  # ← Required
    document_name = MyDocumentTypes.MY_TYPE  # ← Required
```

**Issue**: Double inheritance causing MRO problems
**Cause**: Inheriting SequenceMixin separately when using EnezaMaster/EnezaDocument
**Solution**: Use only EnezaMaster or EnezaDocument (they already include SequenceMixin)

```python
# Correct
class MyModel(EnezaMaster):
    # ...

# Incorrect - causes MRO issues
class MyModel(SequenceMixin, EnezaMaster):
    # ...
```

**Issue**: "No Sequence configuration found" error
**Cause**: No active sequence configuration exists for the document type
**Solution**: Create an active sequence configuration in admin

**Issue**: Duplicate sequence numbers
**Cause**: Multiple active configurations for same document type
**Solution**: Ensure only one active configuration per document type

**Issue**: Format mismatch (e.g., "CUST-1" instead of "CUST-0001")
**Cause**: Wrong number_length setting
**Solution**: Adjust number_length in sequence configuration

### Debugging Steps

1. **Check Model Definition**
   ```python
   print(MyModel.sequence_field_name)  # Should return field name
   print(MyModel.document_name)       # Should return document type
   ```

2. **Check Configuration**
   ```python
   from enezaframework.models.enezasequence import SequenceConfig
   
   config = SequenceConfig.objects.filter(
       documents=MyModel.document_name,
       active=True
   ).first()
   
   print(config)  # Should return configuration object
   ```

3. **Check Field Assignment**
   ```python
   obj = MyModel()
   obj.save()
   print(obj.my_field)  # Should contain generated sequence
   ```

### Error Messages

**"No Sequence configuration found for model 'X'"**
- Check that sequence configuration exists and is active
- Verify document type matches between model and config

**"Failed to generate sequence for field 'Y' in model 'X'"**
- Check that the field exists and is nullable
- Verify sequence generation logic is working

### Performance Considerations

- Each save() operation performs one SELECT and one UPDATE
- For bulk operations, consider generating sequences in advance
- Monitor sequence table performance as it's updated on every save

### Migration Considerations

When migrating existing data to use sequences:
1. Add sequence field with `null=True`
2. Populate existing records with manual sequences
3. Set up sequence configuration with appropriate `nextnumber`
4. Add `sequence_field_name` and `document_name` to model
5. Handle existing records specially in save() method