---
menu name: Architecture
position: 1
---

## Enezaframework Low-Code Framework: Technical Guide

**Project Theme:** To provide a low-code framework for Django that simplifies the development of CRUD (Create, Read, Update, Delete) activities within an Django system, making system  implementation easier and faster for Small to Medium Enterprises (SMEs).

This technical guide outlines the architecture, structure, and components of the Enezaframework framework. It is designed to be understood by both AI and human developers for coding applications on top of this framework.

**Core Technologies:**
* **Backend:** Django
* **Frontend:** Tailwind CSS, HTMX, Alpine.js

### 1. System Architecture

The Enezaframework system follows a modular Django architecture, emphasizing clean development practices. The project is primarily divided into three types of apps:

* **`enezacommon` App:**
    * Contains essential models and choice model definitions (e.g., for dropdowns) that are universally required by other apps within the system.
    * Crucially, this app is designed to be independent of other business-logic apps, with its only dependency being the `Enezaframework` itself.
    * Examples: `Business` model, `Person` model, `VendorType` choices, `CustomerType` choices.

* **`Enezaframework` App:**
    * This is the heart of the low-code framework.
    * It defines base models that encapsulate common fields and functionalities.
    * It provides a suite of generic base views that handle most CRUD operations with minimal custom code.
    * All other apps in the system will heavily rely on and inherit from the components defined in `Enezaframework`.

* **`Other Apps` (Business Logic Apps):**
    * These apps implement the specific business functionalities of the any system.
    * They are typically organized around data models rather than high-level functionalities.
    * Examples: `generalledger`, `accountpayable`, `expensereporting`, `inventorymanagement`.
    * These apps will contain their own models (inheriting from `Enezaframework` base models) and views (inheriting from `Enezaframework` base views).

### 2. Standardized App Structure

To ensure manageability and maintainability, each business logic app within Enezaframework should adhere to the following structure:

* **`migrations/`:**
    * Standard Django migrations folder.
    * Manages database schema changes for the models defined within the app.
    * `__init__.py`

* **`models/`:**
    * This is a folder that contain all Django model definitions specific to the app.
    * Each model should ideally be in its own Python file (e.g., `customertable.py`, `vendortable.py`).
    * The `models/__init__.py` file **must** import all models from their respective files. This allows for cleaner imports, such as: `from accountpayable import *`.

* **`templates/`:**
    * This is a folder Contains Django templates specific to the app.
    * **Note:** Most apps are not expected to have their own extensive set of templates. The `Enezaframework` provides generic templates that are reused by the base views. Custom templates should only be created if there's a unique presentational requirement not covered by the framework.
    * App-specific templates would typically reside in a subdirectory named after the app (e.g., `accountpayable/

* **`views/`:**
    * This is a folder that contain all Django view definitions for the app.
    * Each view or a closely related set of views can be in its own Python file (e.g., `customerviews.py`, `vendorviews.py`).
    * The `views/__init__.py` file **must** import all views from their respective files. This allows for cleaner imports, such as: `from .customerviews import *`.

* **`requirements/`:**
    * Contains Product Requirement Documents (PRD.md) or other detailed requirement specifications for the app. This helps in understanding the app's purpose and functionality.

* **`apps.py`:**
    * This file plays a crucial role in defining the app's presence in the ERP system's navigation menu.
    * It contains a `menus` list (a JSON-like Python list of dictionaries) that the main template system uses to render navigation links.

    **Menu Definition (`menus` list in `apps.py`):**
    ```python
    # In your app's apps.py (e.g., common/apps.py or accountpayable/apps.py)
        from enezaframework.utils import load_icon # Helper to load SVG icons
        from django.apps import AppConfig
        
        class CrmConfig(AppConfig):
            default_auto_field = 'django.db.models.BigAutoField'
            name = 'crm' # App name, e.g., 'common'

            menus = [
                {
                    'fasttab': 'common_setup', # A unique key for a group of related menu items (fast tab)
                    'name': 'Common Setup',    # Display name for the fast tab
                    'icon': load_icon('settings_icon'), # Icon for the fast tab (ensure 'settings_icon.svg' is in static/assets/icons/)
                    'menuitems': [
                        {
                            'url': f'{name}:country_list', # URL name: app_name:url_pattern_name (e.g., common:country_list)
                                                        # Often model name in lowercase + _list or _create
                            'name': 'Countries',          # Display name for the menu item
                            'icon': load_icon('flag_icon'), # Icon for the menu item
                        },
                        {
                            'url': f'{name}:custtable_list',
                            'name': 'Customers',
                            'icon': load_icon('handshake'),
                        },
                        # Add more menu items for this fast tab
                    ],
                },
                {
                    'fasttab': 'another_group',
                    'name': 'Another Group',
                    'icon': load_icon('another_icon'),
                    'menuitems': [
                        # ... menu items ...
                    ],
                }
                # Add more fast tabs as needed for the app
            ]
    ```
    * `fasttab`: A logical grouping of menu items.
    * `name`: The display name for the fast tab or menu item.
    * `icon`: An icon loaded using `load_icon('icon_name')`. Icons are expected to be SVG files located in `static/assets/icons/`. The `load_icon` function likely reads the SVG content.
    * `menuitems`: A list of individual menu links within a fast tab.
    * `url`: The Django URL name to navigate to. It typically follows the pattern `app_name:url_name`. For views generated by `Enezaframework`, `url_name` is often automatically derived from the model name (e.g., `country_list`, `country_detail`, `country_create`).

### 3. Enezaframework Architecture

#### 3.1. Enezaframework Models

The `Enezaframework` provides a set of base abstract models. Your application-specific models should inherit from these to gain common fields and behaviors. All these models are "Entity Specific," meaning they are designed to be used in the context of a specific `Entity` (company/organization) within the ERP, unless otherwise stated.

* **`EnezaModel(models.Model)`:**
    * The most fundamental base model in the framework.
    * Defines commonly needed fields such as:
        * `created_at`, `updated_at` (timestamps)
        * `created_by`, `updated_by` (user tracking)
        * `entity` (ForeignKey to the `Entity` model, establishing multi-tenancy or company separation)
        * `is_active` (boolean for soft deletes or status)
    * This model itself might not always be "Entity Specific" if used for global, non-company-related data. However, its children usually are.
    * *Abstract Model*: Yes (typically)

* **`EnezaMaster(EnezaModel, SequenceMixin)`:**
    * Inherits from `EnezaModel` and a `SequenceMixin`.
    * The `SequenceMixin`  provides functionality for auto-generating sequential IDs (e.g., CUST0001, VEND0002) based on predefined sequences for that entity.
    * Intended for defining master records like `Customer`, `Vendor`, `Item`, `BankAccount`. These are core data entities that are referenced by transactions.
    * Entity Specific: Yes.

* **`EnezaMasterDetail(EnezaModel)`:**
    * Inherits from `EnezaModel`.
    * Used for defining detailed information related to a master record, typically in a one-to-one relationship.
    * This helps keep the main master table cleaner by offloading less frequently accessed or more extensive details to a separate table.
    * Example: `CustomerDetails` linked to `Customer` (EnezaMaster), `VendorTableDetails` linked to `VendorTable` (EnezaMaster).
    * Entity Specific: Yes.
    *  a signal is defined and used  to create the reocred in the child that inherit from EnezaMasterDetail for consistence  

* **`EnezaTransactionalTable(EnezaModel, SequenceMixin)`:**
    * Inherits from `EnezaModel` and `SequenceMixin`.
    * Designed for the header part of transactional documents.
    * Examples: `SalesInvoiceHeader`, `PurchaseOrderHeader`, `JournalBatch`.
    * The `SequenceMixin` provides document numbering.
    * Entity Specific: Yes.

* **`EnezaTransactionalLines(EnezaModel)`:**
    * Inherits from `EnezaModel`.
    * Used for the line items of transactional documents.
    * Typically has a one-to-many relationship with an `EnezaTransactionalTable` model (e.g., `SalesInvoiceLine` linked to `SalesInvoiceHeader`).
    * Entity Specific: Yes.

* **`EnezaSetup(EnezaModel)`:**
    * Inherits from `EnezaModel`.
    * Intended for models that define setup or configuration data for the application.
    * These records control how other parts of the system behave.
    * Examples: `LedgerSetup`, `PaymentTerms`, `PostingGroup`, `Currency`.
    * Entity Specific: Often yes, but some setups might be global.

* **`Entity(models.Model)`:** (Likely defined in `Common` or `Enezaframework`)
    * This is a central model representing a legal entity (company, organization, or individual if operating as such) for which financial transactions are recorded.
    * Most other data within the ERP (master records, transactions, setups) will be linked to an `Entity` record. This allows the ERP to be used by multiple companies or branches if needed.

#### 3.2. Enezaframework Base Views

The `Enezaframework` provides a rich set of class-based views that significantly reduce the amount of boilerplate code needed for common CRUD operations. These views come with pre-defined templates and expect certain attributes to be set in the child class.

##### 3.2.1. Core Base Views

These are the foundational views for most CRUD operations.

* **`BaseListView(ListView)`:**
    * Inherits from Django's generic `ListView`.
    * Used to display a list of records for any model.
    * **Template:** Uses a generic list template provided by `Enezaframework`. Child views generally do not need to define `template_name`.
    * **Required attributes in child view:**
        * `model`: The Django model to display (e.g., `model = Country`).
        * define a method with A list of model field names to be displayed as columns in the list view e.g.
  
    ```python
            def set_list_fields(self):
                list_fields = ['code', 'description']
                return list_fields
    ```

**Optional attributes in child view:**
  * A method that have a list of model field names that the generic   template will use to provide search/filtering capabilities e.g. 
  
    ```python

        def set_search_fields(self):
            search_fields = ['code', 'description']
            return search_fields

    ````
* 
* **`BaseDetailView(DetailView)`:**
    * Inherits from Django's generic `DetailView`.
    * Used to display the details of a single record and typically handles updates (GET and POST/PUT for editing).
    * **Template:** Uses a generic detail/form template provided by `Enezaframework`.
    * **Required attributes in child view:**
        * `model`: The Django model (e.g., `model = Country`).
    * **Key attribute for UI layout:**
    All detail and create views should have a `detail_ui_view` method that returns a list of dictionaries defining how fields are organized into tabs and columns on the detail/edit form.

    ```python

        def detail_ui_view(self):
            Fieldtabs = [
                {
                    'name': 'Basic Information',  # Display name of the tab
                    'icon': 'Home',             # Icon name (from static/assets/icons/) for the tab. All icon are found in static/icons
                    'disable_fields': ['code', 'name'], # List of fields to be read-only in this tab always
                    'disable_if': {             # Conditionally disable all fields in this tab
                        'field': 'postedstatus', # Model field to check
                        'value': 'POSTED',       # Value that triggers read-only
                    },
                    'headerpostion': 'header', # Optional: 'header' or 'lines', for BaseDocument views to place tab content.
                    'Fieldcolumns': [          # Defines columns within the tab
                        {
                            'fields': ['name', 'code'] # Simple field names (strings)
                        },
                        {
                            'fields': ['currency_code'] # Fields in the second column
                        },
                    ],
                },
                # More tabs...
            ]
            return Fieldtabs
    ```

#### 3.2.4. Extended Field Configuration for ManyToMany Fields

For ManyToMany fields that require TomSelect autocomplete functionality, you can use extended field configuration in the `detail_ui_view` method. This allows you to customize how the M2M field is rendered and which autocomplete endpoint to use.

**Simple Field Definition (String):**
When you specify a field as a simple string, the framework automatically:
- Detects if it's a ManyToMany field
- Generates the autocomplete URL as `{app_label}:{model_name}_autocomplete`
- Auto-detects the label field (priority: `first_name` → `name` → first CharField → `id`)

```python
'Fieldcolumns': [
    {'fields': ['name', 'assignee_users']}  # 'assignee_users' is M2M, auto-configured
]
```

**Extended Field Definition (Dict):**
For more control, use a dictionary to override specific settings:

```python
'Fieldcolumns': [
    {
        'fields': [
            'name',  # Simple field
            {
                'name': 'assignee_users',           # Field name (required)
                'autocomplete_url': 'myapp:custom_user_autocomplete',  # Optional: custom autocomplete URL
                'value_field': 'id',                # Optional: field to use as value (default: 'id')
                'label_field': 'text',              # Optional: field to display as label
                'search_fields': ['first_name', 'last_name'],  # Optional: fields to search
            }
        ]
    }
]
```

**Configuration Options:**
| Option             | Type   | Default        | Description                                          |
| ------------------ | ------ | -------------- | ---------------------------------------------------- |
| `name`             | string | (required)     | The model field name                                 |
| `autocomplete_url` | string | Auto-generated | Django URL name for autocomplete endpoint            |
| `value_field`      | string | `'id'`         | Field to use as the option value                     |
| `label_field`      | string | Auto-detected  | Field to display as the option label                 |
| `search_fields`    | list   | `[]`           | Fields to search when filtering autocomplete results |

**Example: Step Template with User Assignment**
```python
@auto_url_register
class StepTemplateDetailView(BaseInlineDetailView):
    model = StepTemplate
    parent_model = WorkflowTemplate
    related_name = 'steps'
    
    def detail_ui_view(self):
        Fieldtabs = [
            {
                'name': 'Step Information',
                'icon': 'Home',
                'Fieldcolumns': [
                    {'fields': ['order', 'name', 'step_type']},
                    {
                        'fields': [
                            'condition_expression',
                            {
                                'name': 'assignee_users',
                                'label_field': 'text',  # Use 'text' from autocomplete response
                            }
                        ]
                    },
                ],
            },
        ]
        return Fieldtabs
```

**Note:** The autocomplete URL follows the convention `{app_label}:{model_name}_autocomplete`. For the User model in `enezacommon`, this would be `enezacommon:user_autocomplete`. Make sure your autocomplete view is registered with this URL name.
* **Method for inline (related) objects:**
        * `get_inline_related_objects(self)`: Override this method to define related objects (one-to-many or one-to-one) that should be displayed/managed as "inlines" or related tabs on the detail page.
           
    ```python
            def get_inline_related_objects(self):
                inline_related_object = [
                    {
                        'name': 'State', # Internal name/key for the inline section
                        'caption': 'States', # Display caption for the inline tab/section
                        'model': 'state', # Lowercase model name of the related object (e.g., 'state' for State model)
                        'relation_name': 'state_country', # The 'related_name' attribute on the ForeignKey from the inline model to the parent model.
                        'position': 1, # Order of this inline tab
                        'active': 1, # Whether this inline is active (1 for active, 0 for inactive)
                        'icon': 'DocumentPlus', # Icon for the inline tab
                        'relation_type': 'one_to_many', # or 'one_to_one'
                        # For one_to_one, you might need different handling or specialized inline views.
                        # Add 'condition': some_value if this inline should only appear based on a parent object's field value
                    },
                ]
                return inline_related_object
    ```

* **`BaseCreateView(CreateView)`:**
    * Inherits from Django's generic `CreateView`.
    * Used to create new records for a model.
    * **Template:** Uses the same generic detail/form template as `BaseDetailView`.
    * **Required attributes in child view:**
        * `model`: The Django model.
        * `Fieldtabs`: Same structure as in `BaseDetailView` to define the form layout. `disable_fields` here might control fields that are auto-generated or set server-side on creation.

* **`BaseDeleteView(DeleteView)`:**
    * Inherits from Django's generic `DeleteView`.
    * Used to delete a record. Typically presents a confirmation page.
    * **Required attributes in child view:**
        * `model`: The Django model.
    * **Note:** The framework likely handles the success URL redirection automatically.

* **`BaseParameter(UpdateView)`:** (Likely an UpdateView or a custom view)
    * A specialized view for creating and updating a *single instance* model, often used for main application parameters or settings where only one record exists (or one per entity).
    * You might not need to create multiple views (List, Detail, Create) for such a model; `BaseParameter` handles both display and update.
    * Expects `model` and `Fieldtabs` to be defined.

* **`BaseAction(View)`:**
    * A special view that allows custom actions to be performed on a model instance. These actions appear as menu items or buttons on the detail or list views.
    * Examples: "Post Invoice", "Approve Expense", "Change Status".
    * The child view inheriting from `BaseAction` would define the logic for the action.
    * The child view must implement `process_action` action method that define all business logic. it expect the `pk` of the main model.
    * **Attribute in Detail Views to trigger actions:**
        * `action_list`: Defined in a `BaseDetailView` (or its children) to list actions available for that record.
  
        ```python
            # In a DetailView, e.g., CountryDetailView
            action_list = [
                {
                    'name': 'Print Name', # Display name of the action
                    'icon': 'DocumentPlus', # Icon for the action button/menu
                    'url': 'printname', # Partial URL component or identifier for this action.
                                       # The framework likely constructs the full URL: app_name:model_name_action_url
                    'confirm_message': "Are you sure you want to print this name?", # Optional confirmation
                }
            ]
        ```
        * When an action is invoked, it typically calls a corresponding method on a `BaseAction` child view called `process_action` , which needs to be implemented by the developer.

##### 3.2.2. Inline Views

These views operate similarly to the core base views but are designed to manage records that are "inline" or directly related (usually one-to-many or one-to-one) to a parent record. They are often rendered within the parent's detail page.

* `BaseInlineListView`
* `BaseInlineDetailView`
* `BaseInlineCreateView`
* `BaseInlineDeleteView`
* `BaseInlineOneToOneDetailView`: Specialized for displaying/editing a related object in a strict one-to-one relationship.
    * **Required attributes in child view:**
        * `model`: The inline model.
        * `parent_model`: The parent model class.
        * `related_name`: The `related_name` specified on the `ForeignKey` or `OneToOneField` from the inline model back to the parent.
        * `Fieldtabs`: For form layout.

##### 3.2.3. Specialized Base Views

These are further specializations of the core views, tailored for specific types of models or functionalities.

* **`BaseJournals` Views:** (`BaseJournalsListView`, `BaseJournalsDetailView`, `BaseJournalsCreateView`, `BaseJournalsDeleteView`)
    * Behave like the core base views but are specialized for models that inherit from a `JournalBatch` (or similar header-level journal model).

* **`BaseJournalsLines` Views:** (`BaseJournalsLinesListView`, `BaseJournalsLinesDetailView`, `BaseJournalsLinesCreateView`, `BaseJournalsLinesDeleteView`)
    * Support operations on models that inherit from a `JournalLine` (or similar line-level journal model), typically used as inlines for `BaseJournalsDetailView`.

* **`BaseSetup` Views:** (`BaseSetupsListview`, `BaseSetupsDetailView`, `BaseSetupsCreateView`, `BaseSetupsDeleteView`)
    * Behave like core base views but are specialized for models inheriting from `EnezaSetup`.
    * **Read-Only Variants:**
        * `BaseSetupsReadOnlyListView`
        * `BaseSetupsReadOnlyDetailView`
        * (`BaseSetupsReadOnlyCreateView` is less common but could mean pre-filled, non-editable creation).
        * These are likely used when setup data should be viewable but not modifiable by certain users or in certain contexts.

* **`BaseDocument` Views:** (`BaseSourceDocumentListView`, `BaseSourceDocumentDetailView`, `BaseSourceDocumentCreateView`, `BaseSourceDocumentDeleteView`)
    * Specialized for "source document" models (e.g., Sales Orders, Purchase Invoices) that might require a more complex layout, especially in the header section.
    * The `Fieldtabs` definition for these views can include an additional key: `'headerpostion': 'header'` or `'headerpostion': 'lines'`. This allows a tab's content to be specifically rendered in the "header" part of the document view or alongside "lines" if the template is structured that way.

#### 3.3. URL Registration with `@auto_url_register`

The framework provides a decorator `@auto_url_register` ( from `enezaframework.utils`).

```python
from enezaframework.utils import auto_url_register
from .models import Country

@auto_url_register
class CountryListView(BaseListView):
    model = Country
    def set_list_fields(self):
        list_fields = ['name', 'code']
        return list_fields


@auto_url_register
class CountryDetailView(BaseDetailView):
    model = Country
    # ... Fieldtabs and other attributes ...

@auto_url_register
class CountryCreateView(BaseCreateView):
    model = Country
    # ... Fieldtabs ...

@auto_url_register
class CountryDeleteView(BaseDeleteView):
    model = Country
```

* **Purpose:** This decorator automatically generates and registers standard Django URL patterns for the view it decorates.
* **Convention:** It likely creates URLs based on the model name and the view type. For example, for a `Country` model:
    * `CountryListView` -> `/countries/` (URL name: `app_name:country_list`)
    * `CountryCreateView` -> `/countries/create/` (URL name: `app_name:country_create`)
    * `CountryDetailView` -> `/countries/<pk>/` (URL name: `app_name:country_detail`)
    * `CountryDeleteView` -> `/countries/<pk>/delete/` (URL name: `app_name:country_delete`)
* This significantly reduces the need to manually define URLs in `urls.py` for every CRUD view. The app's `urls.py` might only need to include the auto-generated URLs from `enezaframework.urls` or a similar mechanism.

#### 3.4. Model-Level Image Size Definition

The Enezaframework includes a comprehensive image handling system that allows developers to define custom image sizes directly at the model level, providing a unified, user-friendly experience for uploading and previewing images across all CRUD operations. This enhancement is documented in detail in the [Feature Architecture: Image Size Definition](feature_architecture/feature_architecture_image_size_definition.md).

**Key Features:**
- **Model-Level Configuration**: Define image sizes directly in Django model field definitions
- **Unified Image Widget**: Single component handles both new uploads and existing image previews
- **Client-side Validation**: File size (2MB limit) and type validation (JPG, PNG, GIF)
- **Responsive Design**: Optimized display across all device sizes with mobile-specific sizing
- **Dynamic CSS Generation**: Automatic Tailwind CSS class generation from model configuration
- **Alpine.js Integration**: Reactive UI updates without page reloads
- **Backward Compatibility**: Existing implementations continue to work unchanged

**Core Components:**
- **`enezaframework/models/configurable_image_field.py`**: Custom ImageField class with size configuration support
- **`enezaframework/templatetags/form_extras.py`**: Template tags for image field detection and widget rendering
- **`enezaframework/templates/tags/image_upload.html`**: Main image upload template with preview functionality
- **Alpine.js Components**: Client-side reactivity for dynamic UI updates

**Model-Level Usage:**
```python
from enezaframework.models import ConfigurableImageField

class Profile(models.Model):
    avatar = ConfigurableImageField(
        upload_to='profile_images/',
        image_size_config={
            'max_height': 200,
            'max_width': 200,
            'mobile_max_height': 150,
            'mobile_max_width': 150,
        }
    )

    banner = ConfigurableImageField(
        upload_to='banner_images/',
        image_size_config={
            'max_height': 300,
            'max_width': 800,
            'mobile_max_height': 200,
            'mobile_max_width': 600,
        }
    )
```

**Template Integration:**
```html
{% load form_extras %}
{% if field|is_image_field %}
    {% image_upload_widget field %}
{% else %}
    <!-- Standard field rendering -->
{% endif %}
```

**Benefits of Model-Level Approach:**
- **Single Template, Multiple Models**: One template can serve multiple models with different image size requirements
- **Developer-Friendly**: Size configuration is co-located with field definition
- **Type Safety**: Configuration is validated at the model level
- **Consistency**: All instances of a model use the same size configuration
- **Maintainability**: Changes to image sizes only require model updates

For complete implementation details, technical specifications, and integration guidelines, refer to the [comprehensive feature architecture document](feature_architecture/feature_architecture_image_size_definition.md).

### 4. Implementing CRUD Operations: Examples

Let's illustrate with the provided `VendorTable` example from an `accountpayable` app.

#### 4.1. Models (Assumed)

First, you would have your models defined in `accountpayable/models/`:

* `vendortable.py` (for `VendorTable` master data)
* `vendortabledetails.py` (for `VendorTableDetails` one-to-one extension)
* `vendorpostinggroup.py`, `vendorgroup.py`, etc. (for setup data)
* And `common/models/` would have `Business`, `Person`.

```python
# Example: accountpayable/models/vendortable.py
from django.db import models
from enezaframework.models import EnezaMaster
from common.models import VendorType # Assuming VendorType is defined in common app

class VendorTable(EnezaMaster):
    vendorno = models.CharField(max_length=50, unique=True)
    searchname = models.CharField(max_length=255)
    vendortype = models.CharField(max_length=50, choices=VendorType.choices) # Example choice field
    vendorgroup = models.ForeignKey('VendorGroup', on_delete=models.PROTECT)
    blocked = models.BooleanField(default=False)
    responsibilitycenter = models.ForeignKey('common.ResponsibilityCenter', on_delete=models.SET_NULL, null=True, blank=True) # Example FK
    # ... other fields ...

    def __str__(self):
        return self.searchname

# Example: accountpayable/models/vendortabledetails.py
from django.db import models
from enezaframework.models import EnezaMasterDetail
from .vendortable import VendorTable

class VendorTableDetails(EnezaMasterDetail):
    vendortable = models.OneToOneField(VendorTable, on_delete=models.CASCADE, related_name='details')
    segment = models.CharField(max_length=100, null=True, blank=True)
    # ... many other detail fields from your example ...

    def __str__(self):
        return f"Details for {self.vendortable.searchname}"

# And so on for other models like VendorGroup, VendorPostingGroup, Business, Person.
```

#### 4.2. Views (`accountpayable/views/vendorviews.py`)

```python
from django.shortcuts import render, redirect
from django.contrib.contenttypes.models import ContentType

from enezaframework.views import (
    BaseListView, BaseDetailView, BaseCreateView, BaseDeleteView,
    BaseInlineOneToOneDetailView, BaseSetupsListview, BaseSetupsDetailView,
    BaseSetupsCreateView, BaseSetupsDeleteView
)
from enezaframework.utils import auto_url_register

from common.models import Business, Person, VendorType # Assuming VendorType defined here
from accountpayable.models import (
    VendorTable, VendorTableDetails, VendorPostingGroup, VendorGroup,
    VendorPriceGroup, VendorBranch
)
# from accountreceivables.models import Custtable # Not used in this snippet directly

# --- VendorTable CRUD ---
@auto_url_register
class VendorTableListView(BaseListView):
    model = VendorTable
    def set_list_fields(self):
        list_fields = ['vendorno', 'searchname', 'vendortype', 'vendorgroup', 'blocked']
        return list_fields
    def set_search_fields(self):
        search_fields = ['vendorno', 'searchname'] 
        return search_fields

@auto_url_register
class VendorTableDetailView(BaseDetailView):
    model = VendorTable
    Fieldtabs = [
        {
            'name': 'Basic Information',
            'icon': 'Home',
            'disable_fields': ['vendorno', 'blocked', 'vendortype'], # Fields to be read-only on edit
            'Fieldcolumns': [
                {'fields': ['vendorno', 'searchname', 'vendorgroup']},
                {'fields': ['vendortype', 'responsibilitycenter', 'blocked']},
            ],
        },
    ]

    def get_related_object_id(self, related_model_name_str):
        """
        Gets the PK of a related object, typically for a OneToOne relationship
        when the related object is linked via ContentType (GenericForeignKey) or a direct OneToOne.
        This is used by the framework to fetch the correct inline object for BaseInlineOneToOneDetailView.
        """
        related_object = None
        try:
            if related_model_name_str == 'VendorTableDetails':
                related_object = VendorTableDetails.objects.get(vendortable=self.object)
            elif self.object.vendortype == VendorType.ORGANIZATION and related_model_name_str == 'Business':
                content_type = ContentType.objects.get_for_model(self.model) # VendorTable
                related_object = Business.objects.get(content_type=content_type, object_id=self.object.id)
            elif self.object.vendortype == VendorType.PERSON and related_model_name_str == 'Person':
                content_type = ContentType.objects.get_for_model(self.model) # VendorTable
                related_object = Person.objects.get(content_type=content_type, object_id=self.object.id)

            return related_object.id if related_object else None
        except (Business.DoesNotExist, Person.DoesNotExist, VendorTableDetails.DoesNotExist):
            return None # Important to handle cases where the related object might not exist

    def get_inline_related_objects(self):
        """
        Defines which related objects (inlines) should be displayed on the VendorTable detail page.
        Some inlines are static (always show), some are conditional (based on VendorTable.vendortype).
        """
        static_inlines = [
            {
                'name': 'vendortabledetails_inline', # Unique key for this inline
                'caption': 'Vendor Table Details',
                'active': 1,
                'relation_type': 'one_to_one', # Indicates how it's related
                'model': 'VendorTableDetails', # The model name as a string
                'relation_name': 'details', # 'related_name' from VendorTableDetails.vendortable
                                            # OR a unique identifier if handled differently by framework for 1-to-1
                'position': 2,
                'icon': 'Folder',
                # 'view_name': 'accountpayable:vendortabledetails_detail' # Optional: if you need a custom inline view
            },
        ]

        conditional_inlines = []
        if hasattr(self.object, 'vendortype'): # Check if object is loaded (e.g., not in create view context yet)
            if self.object.vendortype == VendorType.ORGANIZATION:
                conditional_inlines.append({
                    'name': 'business_details_inline',
                    'caption': 'Business Details',
                    'active': 1,
                    'relation_type': 'one_to_one', # GenericForeignKey behaves like one_to_one here
                    'model': 'Business', # Common model
                    'relation_name': 'business_content_type', # Custom identifier for generic relation
                    'position': 1,
                    'icon': 'DocumentPlus',
                })
            elif self.object.vendortype == VendorType.PERSON:
                conditional_inlines.append({
                    'name': 'person_details_inline',
                    'caption': 'Personal Details',
                    'active': 1,
                    'relation_type': 'one_to_one',
                    'model': 'Person', # Common model
                    'relation_name': 'person_content_type', # Custom identifier
                    'position': 1,
                    'icon': 'DocumentPlus',
                })
        
        all_inlines = conditional_inlines + static_inlines
        # Sort by position if necessary, or the template handles it
        return sorted(all_inlines, key=lambda x: x.get('position', 99))


@auto_url_register
class VendorTableCreateView(BaseCreateView):
    model = VendorTable
    Fieldtabs = [ # Same Fieldtabs as DetailView, but 'disable_fields' might be different for creation
        {
            'name': 'Basic Information',
            'icon': 'Home',
            'disable_fields': ['vendorno'], # vendorno might be auto-generated
            'Fieldcolumns': [
                {'fields': ['searchname', 'vendorgroup', 'vendortype']}, # vendorno removed
                {'fields': ['responsibilitycenter', 'blocked']},
            ],
        },
    ]
    # Note: In create view, `get_inline_related_objects` might not show inlines until parent is saved.
    # HTMX can be used to load them dynamically after the initial save.

@auto_url_register
class VendorTableDeleteView(BaseDeleteView):
    model = VendorTable

# --- InlineOneToOneDetailViews for VendorTable's related objects ---
# These views are typically called by the framework when an inline tab is clicked
# on the VendorTableDetailView. The framework uses HTMX to load their content.

@auto_url_register # URL: .../vendortable/<pk>/business/
class VendorBusinessView(BaseInlineOneToOneDetailView):
    model = Business # The model for this inline view
    parent_model = VendorTable # The parent model this inline belongs to
    # 'related_name' here signifies how the BaseInlineOneToOneDetailView finds/updates the Business object
    # related to the VendorTable. For GenericForeignKey, this might be a convention.
    # It needs to align with how get_related_object_id in VendorTableDetailView identifies it.
    related_name = 'business_content_type' # Matches 'relation_name' in get_inline_related_objects
    template_name = 'enezaframework/includes/generic_form_tabs_content.html' # Or specific inline template

    Fieldtabs = [
        {
            'name': 'Business Information',
            'icon': 'Home',
            'Fieldcolumns': [
                {'fields': ['business_name']},
                {'fields': ['business_registration_number']},
            ],
        },
    ]

@auto_url_register # URL: .../vendortable/<pk>/person/
class VendorPersonView(BaseInlineOneToOneDetailView):
    model = Person
    parent_model = VendorTable
    related_name = 'person_content_type' # Matches 'relation_name'
    template_name = 'enezaframework/includes/generic_form_tabs_content.html'

    Fieldtabs = [
        {
            'name': 'Personal Information',
            'icon': 'Home',
            'Fieldcolumns': [
                {'fields': ['first_name', 'middle_name', 'last_name']},
                {'fields': ['birthday', 'email']},
            ],
        },
    ]

@auto_url_register # URL: .../vendortable/<pk>/vendortabledetails/
class VendorTableDetailsInlineView(BaseInlineOneToOneDetailView): # Renamed for clarity
    model = VendorTableDetails
    parent_model = VendorTable
    related_name = 'details' # This is the actual related_name on VendorTableDetails.vendortable
    template_name = 'enezaframework/includes/generic_form_tabs_content.html'

    Fieldtabs = [
        {'name': 'Purchase demographics', 'icon': 'Home', 'Fieldcolumns': [...]},
        {'name': 'Invoice and delivery', 'icon': 'Home', 'Fieldcolumns': [...]},
        # ... other tabs as per your example ...
    ]


# --- VendorPostingGroup (Setup Table) CRUD ---
@auto_url_register
class VendorPostingGroupListView(BaseSetupsListview): # Corrected class name from example
    model = VendorPostingGroup
    list_fields = ['code', 'description']
    search_fields = ['code', 'description']

@auto_url_register
class VendorPostingGroupDetailView(BaseSetupsDetailView): # Corrected class name
    model = VendorPostingGroup
    Fieldtabs = [
        {'name': 'Basic Information', 'icon': 'Home', 'Fieldcolumns': [{'fields': ['code']}, {'fields': ['description']}]},
        {'name': 'Summary Accounts', 'icon': 'Home', 'Fieldcolumns': [{'fields': ['payablesaccount']}, {'fields': ['prepaymentaccount']}]},
    ]

@auto_url_register
class VendorPostingGroupCreateView(BaseSetupsCreateView):
    model = VendorPostingGroup
    Fieldtabs = [ # Usually same as DetailView for setups
        {'name': 'Basic Information', 'icon': 'Home', 'Fieldcolumns': [{'fields': ['code']}, {'fields': ['description']}]},
        {'name': 'Summary Accounts', 'icon': 'Home', 'Fieldcolumns': [{'fields': ['payablesaccount']}, {'fields': ['prepaymentaccount']}]},
    ]

@auto_url_register
class VendorPostingGroupDeleteView(BaseSetupsDeleteView):
    model = VendorPostingGroup

# --- Implement similar views for VendorGroup, VendorPriceGroup, VendorBranch ---
# Example for VendorGroup:
@auto_url_register
class VendorGroupListView(BaseSetupsListview): # Corrected
    model = VendorGroup
    def set_list_fields(self):
        list_fields = ['code', 'description']
        return list_fields

    
    def set_search_fields(self):
        search_fields = ['code', 'description']
        return search_fields

class VendorGroupDetailView(BaseSetupsDetailView):  # Corrected
    model = VendorGroup
    Fieldtabs = [
        {
            'name': 'Basic Information',
            'icon': 'Home',
            'Fieldcolumns': [
                {'fields': ['code']},
                {'fields': ['description']}
            ]
        },
        {
            'name': 'Posting Group',
            'icon': 'Home',
            'Fieldcolumns': [
                {'fields': ['vendorpostinggroup']}
            ]
        }
    ]


@auto_url_register
class VendorGroupCreateView(BaseSetupsCreateView):
    model = VendorGroup
    Fieldtabs = [
        {
            'name': 'Basic Information',
            'icon': 'Home',
            'Fieldcolumns': [
                {'fields': ['code']},
                {'fields': ['description']}
            ]
        },
        {
            'name': 'Posting Group',
            'icon': 'Home',
            'Fieldcolumns': [
                {'fields': ['vendorpostinggroup']}
            ]
        }
    ]


@auto_url_register
class VendorGroupDeleteView(BaseSetupsDeleteView):
    model = VendorGroup
# ... and so on for VendorPriceGroup and VendorBranch ...
```

#### 4.3. App Configuration (`accountpayable/apps.py`)

```python
from django.apps import AppConfig
from enezaframework.utils import load_icon



class AccountpayableConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accountpayable'

    def ready(self):
        import accountpayable.signals

    menus = [
        {
            'fasttab': 'ap_masterdata',
            'name': 'AP Master Data',
            'icon': load_icon('users_icon'), # Ensure 'users_icon.svg' exists
            'menuitems': [
                {
                    'url': f'{name}:vendortable_list', # accountpayable:vendortable_list
                    'name': 'Vendors',
                    'icon': load_icon('vendor_icon'),
                },
                # Add other master data menu items if any
            ],
        },
        {
            'fasttab': 'ap_setup',
            'name': 'AP Setup',
            'icon': load_icon('settings_icon'),
            'menuitems': [
                {
                    'url': f'{name}:vendorpostinggroup_list',
                    'name': 'Vendor Posting Groups',
                    'icon': load_icon('posting_group_icon'),
                },
                {
                    'url': f'{name}:vendorgroup_list',
                    'name': 'Vendor Groups',
                    'icon': load_icon('group_icon'),
                },
                {
                    'url': f'{name}:vendorpricegroup_list',
                    'name': 'Vendor Price Groups',
                    'icon': load_icon('price_tag_icon'),
                },
                {
                    'url': f'{name}:vendorbranch_list',
                    'name': 'Vendor Branches',
                    'icon': load_icon('branch_icon'),
                },
            ],
        },
        # Add other fast tabs for transactions, reports etc.
    ]
```

### 5. Workflow Summary for Developers

1.  **Define Models:**
    * In your app's `models/` directory.
    * Inherit from the appropriate `Enezaframework` base models (`EnezaMaster`, `EnezaTransactionalTable`, `EnezaSetup`, etc.).
    * Ensure all models are imported in `models/__init__.py`.

2.  **Define Views:**
    * In your app's `views/` directory.
    * Inherit from the appropriate `Enezaframework` base views (`BaseListView`, `BaseDetailView`, etc.).
    * Decorate each view with `@auto_url_register`.
    * Set required attributes: `model`, `list_fields` (for list views), `Fieldtabs` (for detail/create views).
    * Implement `get_inline_related_objects()` in detail views if they have inline/related data.
    * Implement `get_related_object_id()` in detail views if they have conditional one-to-one inlines, especially those using `ContentType`.
    * Ensure all views are imported in `views/__init__.py`.

3.  **Define Menus:**
    * In your app's `app.py`, create/update the `menus` list to make your views accessible from the navigation.
    * Use `load_icon()` for icons (ensure SVG files are in `static/assets/icons/`).

4.  **Migrations:**
    * Run `python manage.py makemigrations your_app_name` and `python manage.py migrate`.

5.  **Templates (Optional):**
    * Only create custom templates in your app's `templates/` folder if the generic framework templates are insufficient.

6.  **URL Configuration (Minimal):**
    * The `@auto_url_register` should handle most URL creation. Your project's main `urls.py` will need to include a line that aggregates these auto-generated URLs, and your app's `urls.py` might be very minimal or only needed for highly custom URL patterns not covered by the decorator.

  

## 🛠️ Creating the `urls.py` – Developer Guidelines

When setting up the `urls.py` file in a Django app using **EnezaFramework**, follow this structure to combine both manually defined views and framework-generated routes(views with a decorator `@auto_url_register`).

### 1. **Start with Required Imports**

Import the necessary components:

```python
from . import views  # Access to the app’s views
from django.urls import path  # Django's path utility
from enezaframework.utils import get_registered_urls  # EnezaFramework dynamic URL loader
```

> 💡 The `get_registered_urls` function will fetch all the CRUD-style routes registered via the framework for this app.

---

### 2. **Set the App Name**

```python
app_name = 'cashandbankmanagement'
```

This is important for namespacing your URLs properly in templates and reverse lookups. Use the actual name of your Django app.

---

### 3. **Get Dynamic URLs from EnezaFramework**

```python
dynamic_urls = get_registered_urls(app_name)
```

This will return a list of automatically generated `path()` entries for all models registered through the framework. You don’t need to define URLs for standard CRUD operations manually if your model is registered.

---

### 4. **Define the URL Patterns**

```python
urlpatterns = [
    # Manually defined view (non-decorator-based)
    path('CashandBankDashboard', views.cashandbankdashboard, name='cashandbankdashboard'),

    # Insert all auto-generated URLs
    *dynamic_urls,
]
```

* Use `path()` for any views that aren’t handled by the framework (e.g., dashboards, reports).
* Use the unpacking operator `*` to include the dynamic list directly into `urlpatterns`.

---

### ✅ Notes

* If you skip `*dynamic_urls`, your app will miss all auto-generated CRUD endpoints.
* If you're using custom views that rely on decorators (e.g., permissions), ensure they’re defined manually like the example.
* This structure ensures a clean separation between manually defined views and framework-generated ones.


When setting up the `urls.py` file in a Django app using **EnezaFramework**, follow this structure to combine both manually defined views and framework-generated routes(views with a decorator `@auto_url_register`).


### 🛠️ Used base HTMl template – Developer Guidelines
The project was made from a HTML template and design found in  `vristo-html-template` folder in root of the project. You can get the design elements and app design as follows
* There is `chat app`, `mailbox app`,`To do list` ,`note` and `scrumboard`. No need to redo the UI for a similar fuctinonality just ,reuse where posible and concentrate with back end and reuse the design as as much as posible
* The template provide dashboard and chart widgets where posible reuse the design amd no need to introduce new widgets 
* The template files have a number of html element and Components  no need to renvent the wheel just reuse any component or elemet where posible
*  Always reuse the `css`and `js` that comes with the template they are found in `vristo-html-template/assets`

This low-code approach, centered around the `Enezaframework`'s base models and views, aims to dramatically speed up the development of standard ERP functionalities, allowing developers to focus on the unique business logic and more complex aspects of the system. The use of HTMX and Alpine.js by the framework likely enhances the user interface by providing dynamic interactions without full page reloads, further streamlining the user experience.