---
menu name: Eneza CLI Framework
position: 3
---

# Eneza CLI Framework — Developer Guide

## Table of Contents
1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Command Reference](#command-reference)
5. [Project Structure](#project-structure)
6. [App Structure](#app-structure)
7. [Menu Configuration](#menu-configuration)
8. [URL Configuration](#url-configuration)
9. [Dynamic URL Registration](#dynamic-url-registration)
10. [Best Practices](#best-practices)

---

## Overview

The Eneza CLI (Command Line Interface) framework provides a streamlined way to create Eneza-based Django projects and applications with pre-configured settings, app structures, and integrations. The CLI automates the creation of projects and apps following Eneza framework conventions, eliminating repetitive setup tasks.

**Features:**
- `eneza startproject` - Creates a new Eneza-based Django project
- `eneza startapp` - Creates a new app with Eneza framework structure
- Pre-configured settings with all Eneza dependencies
- Integrated menu system with icons and navigation
- Dynamic URL registration support
- Standardized app structure with models/ and views/ directories

---

## Installation

### Prerequisites
- Python 3.8+
- Django 5.0+

### Create Virtual Environment
```bash
# Create a virtual environment
python -m venv eneza-env

# Activate the virtual environment
# On Windows:
eneza-env\Scripts\activate
# On macOS/Linux:
source eneza-env/bin/activate
```

### Install Eneza Framework
The Eneza CLI tool is included as part of the enezaframework package:

```bash
# Install from PyPI (when published)
pip install enezaframework

# Or install from source (development)
pip install -e .
```

After installation, the `eneza` command will be available globally when the virtual environment is activated.

---

## Quick Start

### Create a New Project
```bash
eneza startproject myproject
```

This creates a new project with:
- Complete Eneza framework settings
- Core app with standard structure
- Pre-configured URLs with all required endpoints
- Media file serving configuration

### Navigate and Run
```bash
cd myproject
python manage.py runserver
```

### Create a New App
```bash
python -m eneza startapp myapp
eneza startapp myapp --project-dir .
```

This creates an app with:
- Standard Django app structure
- Models and views directories
- Menu configuration with icons
- Dynamic URL registration
- Dashboard view with template

---

## Command Reference

### `python -m eneza startproject <project_name>`

Creates a new Eneza-based Django project.

**Arguments:**
- `<project_name>` - Name of the project to create

**Generated structure:**
```
project_name/
├── manage.py
├── project_name/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── core/
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── models/
    │   └── __init__.py
    ├── views/
    │   └── __init__.py
    ├── urls.py
    ├── tests.py
    └── migrations/
        └── __init__.py
```

### `python -m eneza startapp <app_name>`

Creates a new app with Eneza framework structure.

**Arguments:**
- `<app_name>` - Name of the app to create

**Options:**
- `--project-dir` - Project directory (default: current directory)

**Generated structure:**
```
app_name/
├── __init__.py
├── admin.py
├── apps.py
├── models/
│   ├── __init__.py
│   └── appname_models.py (sample model)
├── views/
│   ├── __init__.py
│   └── dashboards.py (dashboard view)
├── urls.py
├── tests.py
└── migrations/
    └── __init__.py
```

---

## Project Structure

### Generated Settings Configuration

The generated project includes comprehensive settings pre-configured with:

**Essential Apps:**
- `daphne`, `channels` for WebSocket support
- `unfold` admin with extensions
- `django.contrib.*` standard apps
- `enezaframework` and related apps
- Third-party packages like `widget_tweaks`, `simple_history`

**Middleware Stack:**
- Security and session middleware
- Custom Eneza middleware
- Authentication middleware
- History tracking middleware

**URL Configuration:**
The generated `urls.py` includes all required endpoints:

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('administration/', include('enezaadminstrator.urls')),
    path('', include('enezacommon.urls', namespace='enezacommon')),
    path('workflow/', include('enezaworkflowengine.urls', namespace='enezaworkflowengine')),
    path('communication/', include('enezacommunication.urls', namespace='enezacommunication')),
    path('reporting/', include('enezareporting.urls')),
    path('accounts/', include('allauth.urls')),
    path('', include('core.urls')),  # Core app URLs
]
```

**Static and Media Files:**
- Static files configured for development and production
- Media file serving with security checks
- Upload path configurations

---

## App Structure

### Standard Directory Layout

Each app created with `eneza startapp` follows this structure:

```
myapp/
├── __init__.py
├── admin.py          # Register models
├── apps.py          # App configuration with menu system
├── models/          # Model definitions
│   ├── __init__.py
│   └── myapp_models.py
├── views/           # View definitions
│   ├── __init__.py
│   └── dashboards.py
├── urls.py          # URL patterns with dynamic registration
├── tests.py         # Test cases
└── migrations/      # Database migrations
    └── __init__.py
```

### App Configuration (`apps.py`)

Each app includes comprehensive menu configuration:

```python
class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'
    menu_verbose_name = 'My App'
    app_entry_menu = 'myapp:myapp_dashboard'  # Dashboard as entry point
    app_icon = 'app-placeholder-icon'        # Replace with actual icon
    menu_position = 10

    menus = [
        {
            'fasttab': 'myapp',
            'name': 'General',
            'icon': 'common-module',
            'menuitems': [
                {
                    'url': f'{name}:myapp_dashboard',
                    'name': 'My App Dashboard',
                    'icon': 'vendor-icon',
                },
                {
                    'url': f'{name}:myapp_list',
                    'name': 'My App',
                    'icon': 'vendor-icon',
                },
            ],
        },
        {
            'fasttab': 'myappdocument',
            'name': 'Documents',
            'icon': 'common-module',
            'menuitems': [
                {
                    'url': f'{name}:myappdocument_list',
                    'name': 'My App Documents',
                    'icon': 'vendor-icon',
                },
            ],
        },
        # Additional sections: Reports, Setup
    ]
```

### Sample Model (`models/myapp_models.py`)

Each app includes a sample model demonstrating Eneza framework integration:

```python
from django.db import models
from enezaframework.utils import auto_url_register

@auto_url_register
class MyAppModel(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "My App Item"
        verbose_name_plural = "My App Items"
    
    def __str__(self):
        return self.name
```

### Dashboard View (`views/dashboards.py`)

Each app includes a dashboard view:

```python
from django.shortcuts import render
from django.views.generic import View

class MyAppDashboard(View):
    def get(self, request):
        return render(request, 'components/common/app_dashboard.html')
```

---

## Menu Configuration

### Menu Structure

The Eneza framework supports complex menu structures with the following hierarchy:

- **Fast Tabs**: Logical groupings of related menu items
- **Menu Items**: Individual navigation items with icons and URLs

### Fast Tab Categories

Each app includes these standard fast tab categories:

1. **General**: Dashboard and main entity lists
2. **Documents**: Document-related functionality
3. **Reports**: Reporting and analytics
4. **Setup**: Configuration and setup options

### Icon Integration

Icons are loaded using the Eneza framework's icon system:

```python
from enezaframework.utils import load_icon

app_icon = load_icon('building-library')
```

Icons are expected to be SVG files located in `static/assets/icons/`.

---

## URL Configuration

### Dynamic URL Registration

Each app uses dynamic URL registration through the `enezaframework.utils.get_registered_urls()` function:

```python
from django.urls import path
from . import views
from .views import MyAppDashboard
from enezaframework.utils import get_registered_urls, URL_REGISTRY

app_name = 'myapp'

dynamic_urls = get_registered_urls(app_name)

urlpatterns = [
    path('', MyAppDashboard.as_view(), name='myapp_dashboard'),  # Dashboard as default
    *dynamic_urls,
]
```

### Auto-URL Registration

Views can be automatically registered using the `@auto_url_register` decorator:

```python
from enezaframework.utils import auto_url_register
from enezaframework.views import BaseListView, BaseDetailView

@auto_url_register
class MyAppListView(BaseListView):
    model = MyAppModel
    
    def set_list_fields(self):
        return ['name', 'description', 'created_at']

@auto_url_register
class MyAppDetailView(BaseDetailView):
    model = MyAppModel
    
    def detail_ui_view(self):
        return [
            {
                'name': 'Basic Information',
                'icon': 'Home',
                'Fieldcolumns': [
                    {'fields': ['name', 'description']},
                ],
            },
        ]
```

The decorator automatically generates standard CRUD URLs:
- `myapp:myapp_list` → `/myapp/`
- `myapp:myapp_create` → `/myapp/create/`
- `myapp:myapp_detail` → `/myapp/<pk>/`
- `myapp:myapp_update` → `/myapp/<pk>/update/`
- `myapp:myapp_delete` → `/myapp/<pk>/delete/`

---

## Dynamic URL Registration

### How It Works

The `get_registered_urls()` function scans the URL registry for views belonging to a specific app:

```python
def get_registered_urls(app_name='enezaframework'):
    """
    Generate URLs for all views in the URL_REGISTRY that belong to a specific app.
    """
    urlpatterns = []

    for view_class in URL_REGISTRY:
        # Check if the view belongs to the specified app
        module_name = view_class.__module__
        if app_name not in module_name:
            continue  # Skip views not in the target app

        # Generate URL patterns based on view type
        # ... URL generation logic
    return urlpatterns
```

### Supported View Types

The system supports various view types with automatic URL pattern generation:

- `list` - List views: `/myapp/`
- `detail` - Detail views: `/myapp/<pk>/`
- `create` - Create views: `/myapp/create/`
- `delete` - Delete views: `/myapp/<pk>/delete/`
- `action` - Action views: `/myapp/action/<pk>/`
- `parameter` - Parameter views: `/myapp/`
- `Dashboard` - Dashboard views: `/myapp/dashboard/`
- `autocomplete` - Autocomplete views: `/myapp/autocomplete/`
- `workflow` - Workflow views: `/myapp/workflow/<pk>/`
- `document_report` - Document reports: `/myapp/report/<pk>/`

---

## Best Practices

### Naming Conventions

- Use underscore_case for app names: `customer_management`, `inventory_system`
- Use PascalCase for model names: `Customer`, `InventoryItem`
- Use descriptive names for views: `CustomerListView`, `InventoryReportView`

### App Organization

- Place business logic models in the main app directory
- Use the `models/` directory for complex model organizations
- Use the `views/` directory for organizing related views
- Keep `admin.py`, `apps.py`, `tests.py` in the main app directory

### Menu Configuration

- Use meaningful fast tab names that group related functionality
- Include icons that visually represent the functionality
- Organize menu items logically within each fast tab
- Use consistent naming conventions across all apps

### Dynamic URL Registration

- Always use the `@auto_url_register` decorator for CRUD views
- Follow the Eneza framework's view class hierarchies
- Implement required methods like `set_list_fields()` and `detail_ui_view()`
- Test URL generation to ensure proper routing

### Testing

- Create comprehensive tests for all views
- Test URL resolution and access
- Validate form submissions and data processing
- Include integration tests that cover the menu system

---

## Troubleshooting

### Common Issues

**Issue**: App not appearing in admin menu
**Solution**: Verify that the app is registered in `INSTALLED_APPS` and has proper menu configuration in `apps.py`

**Issue**: URLs not resolving
**Solution**: Check that views are decorated with `@auto_url_register` and that the app's URLs are included in the main project URLs

**Issue**: Dashboard not loading
**Solution**: Verify that the dashboard view is properly configured and that the template exists at `components/common/app_dashboard.html`

### Debugging Tips

- Use `python manage.py show_urls` to verify generated URL patterns
- Check the Django admin interface to ensure apps are properly registered
- Test individual views directly to isolate issues
- Review the logs for any import or configuration errors

---

## Extending the Framework

### Custom App Templates

To extend the CLI with custom app templates:

1. Modify the template files in `eneza/templates/app/`
2. Update the replacement logic in `eneza/cli.py`
3. Test the new templates with the CLI commands

### Additional App Configurations

Custom menu items and configurations can be added by extending the `apps.py` template and updating the replacement patterns in the CLI code.

### Advanced Features

The framework supports advanced features like:
- Multi-image upload fields
- Dynamic form layouts
- Report generation
- Workflow integration
- Real-time notifications