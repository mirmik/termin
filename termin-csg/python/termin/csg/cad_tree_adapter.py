"""tcgui tree adapter helpers for standalone CSG CAD."""

from __future__ import annotations

from tcgui.widgets.label import Label
from tcgui.widgets.tree import TreeNode, TreeWidget

from termin.csg.document_tree_model import DocumentTreeNode
from termin.csg.operation_specs import BOOLEAN_OPERATION_KINDS
from termin.csg.procedural_document import ProceduralMeshDocument


def to_tree_node(source: DocumentTreeNode) -> TreeNode:
    label = Label()
    label.text = source.text
    label.color = (0.70, 0.74, 0.80, 1.0)
    node = TreeNode(label)
    node.data = (source.kind, source.item_id)
    node.csg_document_node = source
    node.expanded = True
    for child in source.children:
        node.add_node(to_tree_node(child))
    return node


def restore_tree_selection(tree: TreeWidget, roots: list[TreeNode], selection: tuple[str, str] | None) -> None:
    for root in roots:
        selected = find_tree_node(root, selection)
        if selected is not None:
            tree.selected_node = selected
            selected._selected = True
            return


def find_tree_node(root: TreeNode, data: tuple[str, str] | None) -> TreeNode | None:
    if data is None:
        return None
    if root.data == data:
        return root
    for child in root.subnodes:
        found = find_tree_node(child, data)
        if found is not None:
            return found
    return None


def tree_node_data(node: TreeNode | None) -> tuple[str, str] | None:
    if node is None:
        return None
    data = node.data
    if not isinstance(data, tuple) or len(data) != 2:
        return None
    return (str(data[0]), str(data[1]))


def tree_node_model(node: TreeNode | None) -> DocumentTreeNode | None:
    if node is None:
        return None
    try:
        model = node.csg_document_node
    except AttributeError:
        return None
    if not isinstance(model, DocumentTreeNode):
        return None
    return model


def boolean_operation_id_for_tree_node(document: ProceduralMeshDocument, node: TreeNode | None) -> str:
    model = tree_node_model(node)
    if model is None or not model.accepts_drop_inside:
        return ""
    operation = document.find_operation(model.item_id)
    if operation is None or operation.kind not in BOOLEAN_OPERATION_KINDS:
        return ""
    return operation.id


def boolean_parent_id_for_tree_node(document: ProceduralMeshDocument, node: TreeNode | None) -> str:
    model = tree_node_model(node)
    if model is None or not model.is_boolean_input:
        return ""
    parent_operation = document.find_operation(model.parent_operation_id)
    if parent_operation is None:
        return ""
    if model.input_index < 0 or model.input_index >= len(parent_operation.inputs):
        return ""
    return parent_operation.id


__all__ = [
    "boolean_operation_id_for_tree_node",
    "boolean_parent_id_for_tree_node",
    "find_tree_node",
    "restore_tree_selection",
    "to_tree_node",
    "tree_node_data",
    "tree_node_model",
]
