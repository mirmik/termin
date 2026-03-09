using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Windows;
using System.Windows.Controls;
using Termin.Native;

namespace SceneApp.Controls;

public partial class HierarchyPanel : UserControl
{
    private Scene? _scene;

    public event EventHandler<TcEntityId>? SelectionChanged;

    public HierarchyPanel()
    {
        InitializeComponent();
    }

    public Scene? Scene
    {
        get => _scene;
        set
        {
            _scene = value;
            Refresh();
        }
    }

    public void Refresh()
    {
        var nodes = new ObservableCollection<EntityNode>();

        if (_scene != null)
        {
            // Collect all entities first
            var allEntities = new List<Entity>(_scene.Entities.GetAllEntities());

            // Get all root entities (entities without parent)
            foreach (var entity in allEntities)
            {
                var parent = entity.Parent;
                if (!parent.IsValid)
                {
                    nodes.Add(CreateNode(entity, allEntities));
                }
            }
        }

        EntityTree.ItemsSource = nodes;
    }

    private EntityNode CreateNode(Entity entity, List<Entity> allEntities)
    {
        var node = new EntityNode
        {
            Id = entity.Id,
            Name = entity.Name ?? "(unnamed)"
        };

        // Add children
        foreach (var child in allEntities)
        {
            var parent = child.Parent;
            if (parent.IsValid && parent.Id.Index == entity.Id.Index && parent.Id.Generation == entity.Id.Generation)
            {
                node.Children.Add(CreateNode(child, allEntities));
            }
        }

        return node;
    }

    private void EntityTree_SelectedItemChanged(object sender, RoutedPropertyChangedEventArgs<object> e)
    {
        if (e.NewValue is EntityNode node)
        {
            SelectionChanged?.Invoke(this, node.Id);
        }
        else
        {
            SelectionChanged?.Invoke(this, TcEntityId.Invalid);
        }
    }
}

public class EntityNode
{
    public TcEntityId Id { get; set; }
    public string Name { get; set; } = "";
    public ObservableCollection<EntityNode> Children { get; } = new();
}
