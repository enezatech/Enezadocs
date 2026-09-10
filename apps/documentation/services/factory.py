from documentation.models import DocumentationSource

from .base import DocumentationProvider
from .filesystem import LocalDocumentationProvider
from .github import GitHubDocumentationProvider
from .s3 import S3DocumentationProvider, s3_enabled


def get_provider(source: DocumentationSource) -> DocumentationProvider:
    if source.source_type == DocumentationSource.SourceType.LOCAL:
        if s3_enabled():
            return S3DocumentationProvider(source)
        return LocalDocumentationProvider(source.local)
    if source.source_type == DocumentationSource.SourceType.GITHUB:
        return GitHubDocumentationProvider(source.github)
    raise ValueError(f"Unsupported source type: {source.source_type}")
