import tkinter as tk
from typing import TYPE_CHECKING, Dict, Iterable, Set

if TYPE_CHECKING:
    from core.gui.graph.graph import CanvasGraph


class CanvasLayers:
    def __init__(self, canvas: "CanvasGraph"):
        self.canvas: "CanvasGraph" = canvas
        self.layers: Dict[str, Set[int]] = {}
        self.hidden: Set[str] = set()

    def names(self) -> Iterable[str]:
        return self.layers.keys()

    def add_layer(self, name: str) -> bool:
        if name in self.layers:
            return False
        else:
            self.layers[name] = set()
            return True

    def delete_layer(self, name: str) -> None:
        items = self.layers.pop(name, set())
        hidden_items = self.all_hidden()
        items -= hidden_items
        self.canvas.config(items, state=tk.NORMAL)

    def add_item(self, name: str, item: int) -> None:
        if name in self.layers:
            self.layers[name].add(item)
            if name in self.hidden:
                self.canvas.config(item, state=tk.HIDDEN)

    def delete_item(self, name: str, item: int) -> None:
        if name in self.layers:
            self.layers[name].remove(item)
            hidden_items = self.all_hidden()
            if item not in hidden_items:
                self.canvas.config(item, state=tk.NORMAL)

    def toggle_layer(self, name: str) -> None:
        items = self.layers[name]
        if name in self.hidden:
            self.hidden.remove(name)
            hidden_items = self.all_hidden()
            items -= hidden_items
            self.canvas.config(items, state=tk.NORMAL)
        else:
            self.hidden.add(name)
            self.canvas.config(items, state=tk.HIDDEN)

    def all_hidden(self) -> Set[int]:
        items = set()
        for name in self.hidden:
            items |= self.layers[name]
        return items
