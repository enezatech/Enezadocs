import re
import shutil
from pathlib import Path

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    DocumentationNode,
    DocumentationSearchDocument,
    DocumentationSite,
    DocumentationSource,
    FeaturedSite,
    GitHubCredential,
    GitHubDocumentationSource,
    HomePage,
    HomeUpdate,
    LocalDocumentationSource,
    MCPToken,
    MCPServer,
    QuickPath,
)
from .services.factory import get_provider
from .services.mcp_tokens import generate_token, hash_token
from .services.structure import rebuild_from_provider_tree
from .services.sync import sync_source


@admin.action(description="Sync documentation")
def sync_documentation(modeladmin, request, queryset):
    for source in queryset:
        sync_source(source)
    modeladmin.message_user(request, "Documentation sync complete.")


@admin.action(description="Import navigation structure from provider")
def import_structure(modeladmin, request, queryset):
    total = 0
    errors = []
    for site in queryset:
        try:
            provider = get_provider(site.source)
            count = rebuild_from_provider_tree(site, provider.get_tree())
            total += count
        except Exception as exc:
            errors.append(f"{site.slug}: {exc}")
    message = f"Imported {total} navigation nodes."
    if errors:
        message += " Errors: " + "; ".join(errors)
    modeladmin.message_user(request, message)


class LocalDocumentationSourceForm(forms.ModelForm):
    class Meta:
        model = LocalDocumentationSource
        fields = ("root_path",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["root_path"].disabled = True


class LocalDocumentationSourceInline(admin.StackedInline):
    model = LocalDocumentationSource
    form = LocalDocumentationSourceForm
    extra = 0


class GitHubDocumentationSourceInline(admin.StackedInline):
    model = GitHubDocumentationSource
    extra = 0


class GitHubCredentialForm(forms.ModelForm):
    token = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        label="Token",
        help_text="Leave blank to keep the existing token.",
    )

    class Meta:
        model = GitHubCredential
        fields = ("name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.token:
            self.fields["token"].widget.attrs["placeholder"] = "blank keeps current token"

    def save(self, commit=True):
        instance = super().save(commit=False)
        token = self.cleaned_data.get("token")
        if token:
            instance.token = token
        if commit:
            instance.save()
        return instance


@admin.register(GitHubCredential)
class GitHubCredentialAdmin(admin.ModelAdmin):
    form = GitHubCredentialForm
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)


@admin.register(DocumentationSource)
class DocumentationSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "source_type", "enabled", "last_sync_status", "last_sync_at")
    list_filter = ("source_type", "enabled")
    search_fields = ("name",)
    readonly_fields = ("last_sync_status", "last_sync_error", "last_sync_at")
    inlines = [LocalDocumentationSourceInline, GitHubDocumentationSourceInline]
    actions = [sync_documentation]


@admin.register(DocumentationSite)
class DocumentationSiteAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "category", "icon", "featured", "order", "source", "enabled")
    list_filter = ("category", "featured", "enabled")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("category", "icon", "featured", "order")
    actions = [import_structure]


NODE_FOLDER_TYPES = (
    DocumentationNode.NodeType.SECTION,
    DocumentationNode.NodeType.GROUP,
)


def _is_local_node(node):
    if node.type not in NODE_FOLDER_TYPES:
        return False
    site = node.site
    if site is None or site.source is None:
        return False
    return site.source.source_type == DocumentationSource.SourceType.LOCAL


def _local_root(site):
    try:
        config = site.source.local
    except LocalDocumentationSource.DoesNotExist:
        raise ValidationError("Local source has no root path configured.")
    return Path(config.root_path).expanduser().resolve()


def _resolve_target(root, path):
    clean = (path or "").strip("/\\")
    if not clean:
        raise ValidationError({"path": "A folder path is required."})
    target = (root / clean).resolve()
    if target == root or root not in target.parents:
        raise ValidationError({"path": "Path escapes the documentation root."})
    return target


_UNSAFE_FOLDER_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _folder_name_from_title(title):
    """Turn a node title into a safe folder name, keeping case and spaces."""
    name = _UNSAFE_FOLDER_CHARS.sub("", title or "")
    name = name.strip().strip(".")
    return name.strip() or "untitled"


def _auto_node_path(title, parent):
    """Derive a folder path from the node title and its parent's path."""
    name = _folder_name_from_title(title)
    parent_path = (getattr(parent, "path", "") or "").strip("/\\")
    return f"{parent_path}/{name}" if parent_path else name


def _create_node_folder(node):
    root = _local_root(node.site)
    if not root.is_dir():
        raise ValidationError({"path": f"Documentation root does not exist: {root}"})
    target = _resolve_target(root, node.path)
    target.mkdir(parents=True, exist_ok=True)


def _has_other_node_for_folder(node, target, exclude_ids=frozenset()):
    others = DocumentationNode.objects.filter(
        site__source=node.site.source,
        type__in=NODE_FOLDER_TYPES,
    ).exclude(pk__in=set(exclude_ids) | {node.pk})
    for other in others:
        try:
            if _resolve_target(_local_root(other.site), other.path) == target:
                return True
        except ValidationError:
            continue
    return False


def _delete_node_folder(node, exclude_ids=frozenset()):
    """Remove the node's folder and its content.

    Returns a warning string when removal is deliberately skipped (missing
    path, root target, or a folder shared with another node); returns None when
    the folder was removed or no filesystem action applies. Real filesystem
    errors (e.g. permission denied) propagate so the caller can block the DB
    delete. ``exclude_ids`` lists nodes being deleted in the same batch so they
    are not treated as other owners of the folder.
    """
    if not _is_local_node(node):
        return None
    try:
        root = _local_root(node.site)
        target = _resolve_target(root, node.path)
    except ValidationError as exc:
        return "; ".join(exc.messages)
    if _has_other_node_for_folder(node, target, exclude_ids):
        return f"Folder {target} is shared with another node; it was kept on disk."
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()
    return None


class DocumentationNodeAdminForm(forms.ModelForm):
    class Meta:
        model = DocumentationNode
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "path" in self.fields:
            self.fields["path"].required = False
            self.fields["path"].help_text = (
                "Leave blank to derive the folder path from the title and parent."
            )

    def clean(self):
        cleaned = super().clean()
        site = cleaned.get("site")
        node_type = cleaned.get("type")
        title = (cleaned.get("title") or "").strip()
        if site is not None and node_type in NODE_FOLDER_TYPES:
            path = (cleaned.get("path") or "").strip("/\\")
            if not path and title:
                path = _auto_node_path(title, cleaned.get("parent"))
                cleaned["path"] = path
            if path and self.instance.pk is None:
                probe = DocumentationNode(
                    site=site,
                    type=node_type,
                    path=path,
                )
                if _is_local_node(probe):
                    try:
                        _create_node_folder(probe)
                    except ValidationError:
                        raise
                    except OSError as exc:
                        raise ValidationError(
                            {"path": f"Could not create folder: {exc}"},
                        )
        return cleaned


@admin.register(DocumentationNode)
class DocumentationNodeAdmin(admin.ModelAdmin):
    form = DocumentationNodeAdminForm
    list_display = ("site", "title", "type", "path", "parent", "access", "order", "enabled")
    list_filter = ("site", "type", "access", "enabled")
    search_fields = ("title", "path")
    list_editable = ("access", "order", "enabled")

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        if obj is not None:
            site = getattr(obj, "site", None)
            if site is not None and "parent" in form.base_fields:
                form.base_fields["parent"].queryset = DocumentationNode.objects.filter(
                    site=site,
                )
        return form

    def delete_model(self, request, obj):
        warning = _delete_node_folder(obj)
        if warning:
            self.message_user(request, warning, messages.WARNING)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        ids = set(queryset.values_list("pk", flat=True))
        warnings = []
        for obj in queryset:
            warning = _delete_node_folder(obj, exclude_ids=ids)
            if warning:
                warnings.append(f"{obj}: {warning}")
        if warnings:
            self.message_user(request, " ".join(warnings), messages.WARNING)
        super().delete_queryset(request, queryset)


@admin.register(DocumentationSearchDocument)
class DocumentationSearchDocumentAdmin(admin.ModelAdmin):
    list_display = ("path", "title", "source")
    list_filter = ("source",)
    search_fields = ("title", "path", "content")


class MCPTokenInline(admin.TabularInline):
    model = MCPToken
    extra = 0
    fields = ("name", "prefix", "allow_private", "enabled", "last_used_at")
    readonly_fields = ("name", "prefix", "allow_private", "enabled", "last_used_at")
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(MCPServer)
class MCPServerAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "site", "section", "group", "enabled")
    list_filter = ("site", "enabled")
    search_fields = ("name", "slug", "site__name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MCPTokenInline]

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        if obj is not None and obj.site_id:
            nodes = DocumentationNode.objects.filter(site=obj.site)
            if "section" in form.base_fields:
                form.base_fields["section"].queryset = nodes.filter(
                    type=DocumentationNode.NodeType.SECTION,
                )
            if "group" in form.base_fields:
                form.base_fields["group"].queryset = nodes.filter(
                    type=DocumentationNode.NodeType.GROUP,
                )
        return form


@admin.register(MCPToken)
class MCPTokenAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "prefix",
        "server",
        "allow_private",
        "enabled",
        "last_used_at",
    )
    list_filter = ("server", "allow_private", "enabled")
    search_fields = ("name", "prefix", "server__name")
    autocomplete_fields = ("server",)
    exclude = ("token",)
    readonly_fields = (
        "prefix",
        "token_hash",
        "token_value",
        "last_used_at",
        "created_at",
        "updated_at",
    )
    actions = ("reveal_token", "regenerate_token")

    @admin.display(description="Bearer token")
    def token_value(self, obj):
        if obj is None or not obj.pk:
            return "Generated automatically when you save."
        if not obj.token:
            return mark_safe(
                "Not stored. Use <strong>Regenerate bearer token</strong> to "
                "issue a new one.",
            )
        return format_html(
            '<input type="text" value="{}" readonly '
            'style="width: 32rem; font-family: monospace;" /> '
            '<button type="button" '
            'onclick="navigator.clipboard.writeText('
            "this.previousElementSibling.value)\">Copy</button>",
            obj.token,
        )

    @admin.action(description="Reveal bearer token")
    def reveal_token(self, request, queryset):
        for token in queryset:
            if token.token:
                self.message_user(
                    request,
                    f"{token.name}: {token.token}",
                    messages.WARNING,
                )
            else:
                self.message_user(
                    request,
                    f"{token.name}: not stored; regenerate to reveal.",
                    messages.ERROR,
                )

    @admin.action(description="Regenerate bearer token")
    def regenerate_token(self, request, queryset):
        for token in queryset:
            raw, prefix = generate_token()
            token.prefix = prefix
            token.token_hash = hash_token(raw)
            token.token = raw
            token.save(
                update_fields=["prefix", "token_hash", "token", "updated_at"],
            )
            self.message_user(
                request,
                f"{token.name} new bearer token: {raw}",
                messages.WARNING,
            )

    def save_model(self, request, obj, form, change):
        raw_token = ""
        if not change:
            raw_token, prefix = generate_token()
            obj.prefix = prefix
            obj.token_hash = hash_token(raw_token)
            obj.token = raw_token
        super().save_model(request, obj, form, change)
        if raw_token:
            self.message_user(
                request,
                f"MCP token for '{obj.name}': {raw_token}",
                messages.WARNING,
            )


class QuickPathInline(admin.TabularInline):
    model = QuickPath
    extra = 1


class FeaturedSiteInline(admin.TabularInline):
    model = FeaturedSite
    extra = 1
    autocomplete_fields = ("site",)


class HomeUpdateInline(admin.TabularInline):
    model = HomeUpdate
    extra = 1
    autocomplete_fields = ("site",)


@admin.register(HomePage)
class HomePageAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Branding", {"fields": ("brand_name",)}),
        ("Hero", {"fields": ("hero_eyebrow", "hero_title", "hero_subtitle")}),
        (
            "Quick install",
            {
                "fields": (
                    "quick_install_title",
                    "quick_install_description",
                    "quick_install_code",
                    "quick_install_bullets",
                )
            },
        ),
        ("Call to action", {"fields": ("cta_title", "cta_subtitle")}),
        ("Footer", {"fields": ("footer_tagline",)}),
        ("Stats", {"fields": ("latest_release",)}),
    )
    inlines = [QuickPathInline, FeaturedSiteInline, HomeUpdateInline]

    def has_add_permission(self, request):
        return not HomePage.objects.exists()


@admin.register(QuickPath)
class QuickPathAdmin(admin.ModelAdmin):
    list_display = ("label", "query", "home", "order")
    list_editable = ("order",)
    search_fields = ("label", "query")


@admin.register(FeaturedSite)
class FeaturedSiteAdmin(admin.ModelAdmin):
    list_display = ("site", "title", "order", "home")
    list_editable = ("order",)
    autocomplete_fields = ("site",)


@admin.register(HomeUpdate)
class HomeUpdateAdmin(admin.ModelAdmin):
    list_display = ("text", "site", "published_at")
    list_filter = ("site",)
    autocomplete_fields = ("site",)
