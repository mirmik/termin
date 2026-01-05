using System;
using System.Collections.Generic;
using UnityEngine;

public class ComponentCollection
{
    ObjectOfTimeline _owner;
    public MyList<ItemComponent> Components = new MyList<ItemComponent>();
    int _non_started = 0;

    public ComponentCollection(ObjectOfTimeline newowner)
    {
        _owner = newowner;
    }

    public ComponentCollection() { }

    public ObjectOfTimeline Owner
    {
        get { return _owner; }
        set { SetOwner(value); }
    }

    public void SetOwner(ObjectOfTimeline newowner)
    {
        _owner = newowner;
        foreach (var component in Components)
        {
            component.Owner = newowner;
        }
    }

    public ComponentCollection(ComponentCollection other, ObjectOfTimeline newowner)
    {
        foreach (var component in other.Components)
        {
            AddComponent(component.Copy(newowner));
        }
    }

    public void Promote(long local_step)
    {
        if (_non_started > 0)
        {
            foreach (var component in Components)
            {
                component.InvokeStart();
            }
            _non_started = 0;
        }

        foreach (var component in Components)
        {
            component.Promote(local_step);
        }
    }

    public void StartPhase()
    {
        foreach (var component in Components)
        {
            component.InvokeStart();
        }
        _non_started = 0;
    }

    public void Execute(long timeline_step, long local_step)
    {
        foreach (var component in Components)
        {
            component.Execute(timeline_step, local_step);
        }
    }

    public void AddComponent(ItemComponent component)
    {
        Components.Add(component);
        component.OnAdd();
        _non_started++;
    }

    public T AddComponent<T>(ObjectOfTimeline owner) where T : ItemComponent, new()
    {
        var component = new T();
        component.Owner = owner;
        Components.Add(component);
        component.OnAdd();
        _non_started++;
        return component;
    }

    public void RemoveComponent(ItemComponent component)
    {
        Components.Remove(component);
    }

    public bool HasComponent<T>() where T : ItemComponent
    {
        foreach (var component in Components)
        {
            if (component is T)
            {
                return true;
            }
        }
        return false;
    }

    public T GetComponent<T>() where T : ItemComponent
    {
        foreach (var component in Components)
        {
            if (component is T)
            {
                return component as T;
            }
        }
        return null;
    }
}
