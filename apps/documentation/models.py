from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .fields import EncryptedTextField


class DocumentationSource(models.Model):
    class SourceType(models.TextChoices):
        LOCAL = "LOCAL", "Local Filesystem"
        GITHUB = "GITHUB", "GitHub"

    name = models.CharField(
        max_length=200,
        verbose_name="name",
    )
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        verbose_name="source type",
    )
    enabled = models.BooleanField(
        default=True,
        verbose_name="enabled",
    )
    last_sync_status = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="last sync status",
    )
    last_sync_error = models.TextField(
        blank=True,
        verbose_name="last sync error",
    )
    last_sync_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="last sync at",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="created at",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="updated at",
    )

    class Meta:
        verbose_name = "documentation source"
        verbose_name_plural = "documentation sources"

    def __str__(self):
        return self.name


class LocalDocumentationSource(models.Model):
    source = models.OneToOneField(
        DocumentationSource,
        on_delete=models.CASCADE,
        related_name="local",
        verbose_name="source",
    )
    root_path = models.CharField(
        max_length=500,
        verbose_name="root path",
    )

    class Meta:
        verbose_name = "local documentation source"
        verbose_name_plural = "local documentation sources"

    def __str__(self):
        return self.root_path


class GitHubCredential(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name="name",
    )
    token = EncryptedTextField(
        blank=True,
        verbose_name="token",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="created at",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="updated at",
    )

    class Meta:
        verbose_name = "GitHub credential"
        verbose_name_plural = "GitHub credentials"

    def __str__(self):
        return self.name


class GitHubDocumentationSource(models.Model):
    source = models.OneToOneField(
        DocumentationSource,
        on_delete=models.CASCADE,
        related_name="github",
        verbose_name="source",
    )
    credential = models.ForeignKey(
        "GitHubCredential",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="github_sources",
        verbose_name="credential",
    )
    owner = models.CharField(
        max_length=100,
        verbose_name="owner",
    )
    repository = models.CharField(
        max_length=200,
        verbose_name="repository",
    )
    branch = models.CharField(
        max_length=200,
        default="main",
        verbose_name="branch",
    )
    root_path = models.CharField(
        max_length=500,
        default="docs",
        verbose_name="root path",
    )
    enabled = models.BooleanField(
        default=True,
        verbose_name="enabled",
    )
    last_sync_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="last sync at",
    )
    last_commit_sha = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="last commit sha",
    )

    class Meta:
        verbose_name = "GitHub documentation source"
        verbose_name_plural = "GitHub documentation sources"

    def __str__(self):
        return f"{self.owner}/{self.repository}"


class DocumentationSite(models.Model):
    class Icon(models.TextChoices):
        LAYERS = "layers", "Layers"
        CODE = "code", "Code"
        TERMINAL = "terminal", "Terminal"
        SHIELD = "shield", "Shield"
        DATABASE = "database", "Database"
        GLOBE = "globe", "Globe"
        CARD = "card", "Card"
        BOX = "box", "Box"

    name = models.CharField(
        max_length=200,
        verbose_name="name",
    )
    slug = models.SlugField(
        unique=True,
        verbose_name="slug",
    )
    description = models.TextField(
        blank=True,
        verbose_name="description",
    )
    category = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="category",
    )
    icon = models.CharField(
        max_length=20,
        choices=Icon.choices,
        default=Icon.LAYERS,
        verbose_name="icon",
    )
    source = models.ForeignKey(
        DocumentationSource,
        on_delete=models.PROTECT,
        related_name="sites",
        verbose_name="source",
    )
    logo = models.ImageField(
        upload_to="documentation/logos/",
        blank=True,
        null=True,
        verbose_name="logo",
    )
    featured = models.BooleanField(
        default=False,
        verbose_name="featured",
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="order",
    )
    enabled = models.BooleanField(
        default=True,
        verbose_name="enabled",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="created at",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="updated at",
    )

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "documentation site"
        verbose_name_plural = "documentation sites"

    def __str__(self):
        return self.name


class DocumentationSearchDocument(models.Model):
    source = models.ForeignKey(
        DocumentationSource,
        on_delete=models.CASCADE,
        related_name="search_documents",
        verbose_name="source",
    )
    path = models.CharField(
        max_length=1000,
        verbose_name="path",
    )
    title = models.CharField(
        max_length=500,
        verbose_name="title",
    )
    description = models.TextField(
        blank=True,
        verbose_name="description",
    )
    content = models.TextField(
        blank=True,
        verbose_name="content",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="updated at",
    )

    class Meta:
        verbose_name = "documentation search document"
        verbose_name_plural = "documentation search documents"
        ordering = ["path"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "path"],
                name="unique_source_path",
            ),
        ]

    def __str__(self):
        return self.path


class DocumentationChunk(models.Model):
    source = models.ForeignKey(
        DocumentationSource,
        on_delete=models.CASCADE,
        related_name="search_chunks",
        verbose_name="source",
    )
    path = models.CharField(
        max_length=1000,
        verbose_name="path",
    )
    ordinal = models.PositiveIntegerField(
        default=0,
        verbose_name="ordinal",
    )
    heading = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="heading",
    )
    content = models.TextField(
        blank=True,
        verbose_name="content",
    )
    embedding = models.BinaryField(
        null=True,
        blank=True,
        verbose_name="embedding",
    )
    token_count = models.PositiveIntegerField(
        default=0,
        verbose_name="token count",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="updated at",
    )

    class Meta:
        verbose_name = "documentation chunk"
        verbose_name_plural = "documentation chunks"
        ordering = ["path", "ordinal"]
        indexes = [
            models.Index(
                fields=["source", "path"],
                name="doc_chunk_source_path_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "path", "ordinal"],
                name="unique_chunk_source_path_ordinal",
            ),
        ]

    def __str__(self):
        return f"{self.path}#{self.ordinal}"


class DocumentationNode(models.Model):
    class NodeType(models.TextChoices):
        SECTION = "section", "Section"
        GROUP = "group", "Group"

    class AccessLevel(models.TextChoices):
        PUBLIC = "public", "Public"
        PRIVATE = "private", "Private"

    site = models.ForeignKey(
        DocumentationSite,
        on_delete=models.CASCADE,
        related_name="nodes",
        verbose_name="site",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="parent",
    )
    type = models.CharField(
        max_length=20,
        choices=NodeType.choices,
        verbose_name="type",
    )
    title = models.CharField(
        max_length=300,
        verbose_name="title",
    )
    path = models.CharField(
        max_length=1000,
        blank=True,
        verbose_name="folder path",
        help_text="Folder path relative to the provider root (section/group nodes).",
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="order",
    )
    access = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.PUBLIC,
        verbose_name="access",
        help_text="Public = visible to everyone; Private = signed-in users only.",
    )
    enabled = models.BooleanField(
        default=True,
        verbose_name="enabled",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="created at",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="updated at",
    )

    class Meta:
        verbose_name = "documentation node"
        verbose_name_plural = "documentation nodes"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class HomePage(models.Model):
    brand_name = models.CharField(
        max_length=100,
        default="Enezadocs",
        verbose_name="brand name",
    )
    hero_eyebrow = models.CharField(
        max_length=100,
        default="Documentation hub",
        verbose_name="hero eyebrow",
    )
    hero_title = models.CharField(
        max_length=300,
        default="Every Eneza product, documented in one place.",
        verbose_name="hero title",
    )
    hero_subtitle = models.TextField(
        blank=True,
        verbose_name="hero subtitle",
    )
    cta_title = models.CharField(
        max_length=200,
        default="Can't find what you need?",
        verbose_name="cta title",
    )
    cta_subtitle = models.TextField(
        blank=True,
        verbose_name="cta subtitle",
    )
    footer_tagline = models.TextField(
        blank=True,
        verbose_name="footer tagline",
    )
    latest_release = models.CharField(
        max_length=50,
        default="v1.0",
        verbose_name="latest release",
    )
    quick_install_title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="quick install title",
    )
    quick_install_description = models.TextField(
        blank=True,
        verbose_name="quick install description",
    )
    quick_install_code = models.TextField(
        blank=True,
        verbose_name="quick install code",
    )
    quick_install_bullets = models.TextField(
        blank=True,
        verbose_name="quick install bullets",
        help_text="One bullet per line.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="created at",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="updated at",
    )

    class Meta:
        verbose_name = "home page"
        verbose_name_plural = "home page"

    def __str__(self):
        return self.brand_name

    @classmethod
    def load(cls):
        home, _ = cls.objects.get_or_create(pk=1)
        return home


class QuickPath(models.Model):
    home = models.ForeignKey(
        HomePage,
        on_delete=models.CASCADE,
        related_name="quick_paths",
        verbose_name="home page",
    )
    label = models.CharField(
        max_length=200,
        verbose_name="label",
    )
    query = models.CharField(
        max_length=200,
        verbose_name="query",
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="order",
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "quick path"
        verbose_name_plural = "quick paths"

    def __str__(self):
        return self.label


class FeaturedSite(models.Model):
    home = models.ForeignKey(
        HomePage,
        on_delete=models.CASCADE,
        related_name="featured_sites",
        verbose_name="home page",
    )
    site = models.ForeignKey(
        DocumentationSite,
        on_delete=models.CASCADE,
        related_name="featured_entries",
        verbose_name="site",
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="title",
    )
    subtitle = models.TextField(
        blank=True,
        verbose_name="subtitle",
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="order",
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "featured site"
        verbose_name_plural = "featured sites"

    def __str__(self):
        return self.title or self.site.name


class HomeUpdate(models.Model):
    home = models.ForeignKey(
        HomePage,
        on_delete=models.CASCADE,
        related_name="updates",
        verbose_name="home page",
    )
    site = models.ForeignKey(
        DocumentationSite,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updates",
        verbose_name="site",
    )
    text = models.CharField(
        max_length=500,
        verbose_name="text",
    )
    published_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="published at",
    )

    class Meta:
        ordering = ["-published_at"]
        verbose_name = "home update"
        verbose_name_plural = "home updates"

    def __str__(self):
        return self.text


class MCPServer(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name="name",
    )
    slug = models.SlugField(
        unique=True,
        verbose_name="slug",
        help_text="URL segment for the endpoint, addressed as MCP_PATH/<slug>/.",
    )
    description = models.TextField(
        blank=True,
        verbose_name="description",
    )
    site = models.ForeignKey(
        DocumentationSite,
        on_delete=models.CASCADE,
        related_name="mcp_servers",
        verbose_name="site",
    )
    section = models.ForeignKey(
        DocumentationNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="section",
        help_text="Optional top-level section node; empty grants the whole site.",
    )
    group = models.ForeignKey(
        DocumentationNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="group",
        help_text="Optional group node inside the section; empty grants the whole section.",
    )
    enabled = models.BooleanField(
        default=True,
        verbose_name="enabled",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="created at",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="updated at",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "MCP server"
        verbose_name_plural = "MCP servers"

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.section_id is not None:
            if self.section.type != DocumentationNode.NodeType.SECTION:
                raise ValidationError(
                    {"section": "The selected node is not a section."},
                )
            if self.site_id is not None and self.section.site_id != self.site_id:
                raise ValidationError(
                    {"section": "The section belongs to a different site."},
                )
            if not (self.section.path or "").strip():
                raise ValidationError(
                    {"section": "The section has no folder path and cannot scope a server."},
                )
        if self.group_id is not None:
            if self.group.type != DocumentationNode.NodeType.GROUP:
                raise ValidationError(
                    {"group": "The selected node is not a group."},
                )
            if self.site_id is not None and self.group.site_id != self.site_id:
                raise ValidationError(
                    {"group": "The group belongs to a different site."},
                )
            if not (self.group.path or "").strip():
                raise ValidationError(
                    {"group": "The group has no folder path and cannot scope a server."},
                )
        if self.section_id is not None and self.group_id is not None:
            section_path = (self.section.path or "").strip("/")
            group_path = (self.group.path or "").strip("/")
            if section_path and not (
                group_path == section_path
                or group_path.startswith(section_path + "/")
            ):
                raise ValidationError(
                    {"group": "The group is not inside the selected section."},
                )


class MCPToken(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name="name",
    )
    prefix = models.CharField(
        max_length=16,
        unique=True,
        verbose_name="prefix",
        help_text="Short, non-secret prefix used to identify the token.",
    )
    token_hash = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="token hash",
        help_text="SHA-256 hash of the token; used to authenticate requests.",
    )
    token = EncryptedTextField(
        blank=True,
        default="",
        verbose_name="token",
        help_text="Encrypted copy of the raw token so an admin can re-copy it.",
    )
    server = models.ForeignKey(
        "MCPServer",
        on_delete=models.CASCADE,
        related_name="tokens",
        verbose_name="server",
    )
    allow_private = models.BooleanField(
        default=False,
        verbose_name="allow private",
        help_text="When enabled, this token may read private content inside its scope.",
    )
    enabled = models.BooleanField(
        default=True,
        verbose_name="enabled",
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="last used at",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="created at",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="updated at",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "MCP token"
        verbose_name_plural = "MCP tokens"

    def __str__(self):
        return f"{self.name} ({self.prefix})"
