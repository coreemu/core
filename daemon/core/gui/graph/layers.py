import tkinter as tk
from functools import partial
from typing import TYPE_CHECKING, Dict, Iterable, Set

from core.gui import themes

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.graph import CanvasGraph


class LayersMenu(tk.Menu):
    def __init__(self, master: tk.BaseWidget, app: "Application", item: int) -> None:
        super().__init__(master)
        themes.style_menu(self)
        self.app: "Application" = app
        self.item: int = item
        self.buttons: Dict[str, tk.BooleanVar] = {}
        self.draw()

    def draw(self) -> None:
        for name in self.app.canvas.layers.names():
            value = self.app.canvas.layers.in_layer(name, self.item)
            var = tk.BooleanVar(value=value)
            self.buttons[name] = var
            self.add_checkbutton(
                label=name, variable=var, command=partial(self.click_layer, name)
            )

    def click_layer(self, name):
        value = self.buttons[name].get()
        if value:
            self.app.canvas.layers.add_item(name, self.item)
        else:
            self.app.canvas.layers.delete_item(name, self.item)


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
        for item in items:
            self.canvas.itemconfig(item, state=tk.NORMAL)

    def in_layer(self, name: str, item: int) -> bool:
        return item in self.layers.get(name, set())

    def add_item(self, name: str, item: int) -> None:
        if name in self.layers:
            self.layers[name].add(item)
            if name in self.hidden:
                self.canvas.itemconfig(item, state=tk.HIDDEN)

    def delete_item(self, name: str, item: int) -> None:
        if name in self.layers:
            self.layers[name].remove(item)
            hidden_items = self.all_hidden()
            if item not in hidden_items:
                self.canvas.itemconfig(item, state=tk.NORMAL)

    def toggle_layer(self, name: str) -> None:
        items = self.layers[name]
        if name in self.hidden:
            self.hidden.remove(name)
            hidden_items = self.all_hidden()
            items -= hidden_items
            for item in items:
                self.canvas.itemconfig(item, state=tk.NORMAL)
        else:
            self.hidden.add(name)
            for item in items:
                self.canvas.itemconfig(item, state=tk.HIDDEN)

    def all_hidden(self) -> Set[int]:
        items = set()
        for name in self.hidden:
            items |= self.layers[name]
        return items
