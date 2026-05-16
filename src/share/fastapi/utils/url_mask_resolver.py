import re
from collections.abc import Sequence
from typing import Any

from starlette.routing import BaseRoute, Route
from starlette.types import ASGIApp


class _TrieNode:
    __slots__ = ('children', 'dynamic_child', 'mask')

    def __init__(self):
        self.children: dict[str, _TrieNode] = {}
        self.dynamic_child: tuple[str, _TrieNode] | None = None
        self.mask: str | None = None


class UrlMaskResolver:
    def __init__(self, app: ASGIApp):
        routes = self._find_routes(app)
        self._root = _TrieNode()
        for route in routes:
            if isinstance(route, Route):
                url_mask = re.sub(r'\{(\w+)\}', r'<\1>', route.path)
                self._insert(route.path, url_mask)

    def _insert(self, path: str, url_mask: str) -> None:
        node = self._root
        for segment in path.strip('/').split('/'):
            if segment.startswith('{') and segment.endswith('}'):
                if node.dynamic_child is None:
                    node.dynamic_child = (segment[1:-1], _TrieNode())
                node = node.dynamic_child[1]  # ty: ignore[not-subscriptable]
            else:
                if segment not in node.children:
                    node.children[segment] = _TrieNode()
                node = node.children[segment]
        node.mask = url_mask

    @staticmethod
    def _find_routes(app: ASGIApp) -> Sequence[BaseRoute]:
        current: Any = app
        while current:
            if hasattr(current, 'routes'):
                return current.routes  # ty: ignore[invalid-return-type]
            current = getattr(current, 'app', None)
        return []

    def resolve(self, url_path: str) -> str:
        node = self._root
        for segment in url_path.strip('/').split('/'):
            if segment in node.children:
                node = node.children[segment]
            elif node.dynamic_child is not None:
                node = node.dynamic_child[1]
            else:
                return url_path
        return node.mask or url_path
