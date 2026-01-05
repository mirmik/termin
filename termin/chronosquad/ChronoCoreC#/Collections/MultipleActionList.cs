using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using System;
using UnityEngine;
using Unity.VisualScripting;

#if UNITY_64
using Unity.Profiling;
#endif

public class IgnoreRefflectionAttribute : Attribute { }

abstract public class BasicMultipleAction
{
    static public long TotalCardsCounter = 0;

    protected long start_step;
    protected long finish_step;

    public BasicMultipleAction() { }

    public BasicMultipleAction(long start_step, long finish_step)
    {
        this.start_step = start_step;
        this.finish_step = finish_step;
        TotalCardsCounter++;
    }

    public override string ToString()
    {
        return string.Format(
            "type: {2}, start_step: {0}, finish_step: {1}",
            start_step,
            finish_step,
            GetType().Name
        );
    }

    public string info()
    {
        return SimpleJsonParser.SerializeTrent(ToTrent());
    }

    public void ShiftByStart(long g)
    {
        var offset = g - start_step;

        if (start_step != long.MinValue)
            start_step += offset;

        if (finish_step != long.MaxValue)
            finish_step += offset;
    }

    public void SetStartStep(long step)
    {
        start_step = step;
    }

    public void SetFinishStep(long step)
    {
        finish_step = step;
    }

    public float StartTime => start_step / Utility.GAME_GLOBAL_FREQUENCY;
    public float FinishTime => finish_step / Utility.GAME_GLOBAL_FREQUENCY;

    public long StartStep => start_step;
    public long FinishStep => finish_step;

    public Dictionary<string, object> ToTrent()
    {
        var fields = FieldScanner.GetFieldsFromType(GetType());
        var result = new Dictionary<string, object>();
        result["type"] = GetType().Name;
        foreach (var field in fields)
        {
            bool has_ignore_attribute =
                field.GetCustomAttribute<IgnoreRefflectionAttribute>() != null;
            if (has_ignore_attribute)
                continue;
            var value = field.GetValue(this);
            result[field.Name] = value;
        }
        return result;
    }

    static public BasicMultipleAction CreateFromTrent(Dictionary<string, object> data)
    {
        var type = Type.GetType((string)data["type"]);
        var fields = FieldScanner.GetFieldsFromType(type);
        var obj = (BasicMultipleAction)Activator.CreateInstance(type);
        foreach (var field in fields)
        {
            var value = data[field.Name];
            var field_type = field.FieldType;
            var converted_value = Convert.ChangeType(value, field_type);
            field.SetValue(obj, converted_value);
        }
        return obj;
    }

    public MyList<FieldInfo> GetFields()
    {
        return FieldScanner.GetFieldsFromType(GetType());
    }

    // TODO: Ближе к релизу рефлексию убрать, переделать через виртуальные методы.
    // public virtual Int64 HashCode()
    // {
    // 	var fields = FieldScanner.GetFieldsFromType(GetType());
    // 	long hash = GetType().Name.GetHashCode();
    // 	foreach (var field in fields)
    // 	{
    // 		var value = field.GetValue(this);
    // 		if (value == null)
    // 			continue;
    // 		hash = (hash * 13) ^ value.GetHashCode();
    // 	}
    // 	return hash;
    // }

    public abstract Int64 HashCode();

    public override int GetHashCode()
    {
        return (int)HashCode();
    }

    // TODO: Ближе к релизу рефлексию убрать, переделать через виртуальные методы.
    public bool IsEqual(BasicMultipleAction other)
    {
        var type = GetType();
        var other_type = other.GetType();
        if (type != other_type)
            return false;

        var fields = GetFields();
        var other_fields = other.GetFields();

        if (fields.Count != other_fields.Count)
            return false;

        for (int i = 0; i < fields.Count; i++)
        {
            var field = fields[i];
            var other_field = other_fields[i];

            var value = field.GetValue(this);
            var other_value = other_field.GetValue(other);

            if (value == null && other_value == null)
                continue;

            if (value == null || other_value == null)
                return false;

            if (!value.Equals(other_value))
                return false;
        }

        return true;
    }
}

public class MultipleActionList<T> where T : BasicMultipleAction
{
    MyList<T> _active_states;
    LinkedListMAL<T> list_sorted_by_start_step;
    LinkedListMAL<T> list_sorted_by_finish_step;
    LinkedListNodeMAL<T> _current_by_start_step;
    LinkedListNodeMAL<T> _current_by_finish_step;
    long _promotion_step;
    public MyList<T> BonusAdded;
    public Dictionary<Int64, T> _hashes;

    ///////

    MyList<T> removed_precreated;
    MyList<T> added_precreated;

    //////


    ////[IgnoredByDeepProfilerAttribute]
    public bool HasHash(Int64 hash)
    {
        return _hashes.ContainsKey(hash);
    }

    public LinkedListNodeMAL<T> CurrentByStartStepNode
    {
        get { return _current_by_start_step; }
        set { _current_by_start_step = value; }
    }

    public LinkedListNodeMAL<T> CurrentByFinishStepNode
    {
        get { return _current_by_finish_step; }
        set { _current_by_finish_step = value; }
    }

    public Dictionary<Int64, T> Hashes
    {
        get { return _hashes; }
        set { _hashes = value; }
    }

    public string Info()
    {
        string str = "";
        var lst = AsList();
        str += $"Count: {lst.Count}\n";
        foreach (var item in lst)
        {
            str += item.info() + "\n";
        }
        return str;
    }

    // public LinkedListMAL<T> ByStartStep
    // {
    // 	get { return list_sorted_by_start_step; }
    // 	set { list_sorted_by_start_step = value; }
    // }

    // public LinkedListMAL<T> ByFinishStep
    // {
    // 	get { return list_sorted_by_finish_step; }
    // 	set { list_sorted_by_finish_step = value; }
    // }

    public MyList<T> ActiveStatesList
    {
        get { return _active_states; }
        set { _active_states = value; }
    }

    // public LinkedListNodeMAL<T> Last
    // {
    // 	get
    // 	{
    // 		if (list_sorted_by_start_step.Count == 0)
    // 			return null;
    // 		return list_sorted_by_start_step.Last;
    // 	}
    // }

    // public LinkedListNodeMAL<T> First
    // {
    // 	get
    // 	{
    // 		if (list_sorted_by_start_step.Count == 0)
    // 			return null;
    // 		return list_sorted_by_start_step.First;
    // 	}
    // }

    ////[IgnoredByDeepProfilerAttribute]
    // public MyList<T> AsList()
    // {
    // 	var result = new MyList<T>();
    // 	foreach (var item in list_sorted_by_start_step)
    // 	{
    // 		result.Add(item);
    // 	}
    // 	return result;
    // }

    // ////[IgnoredByDeepProfilerAttribute]
    // public MyList<T> GetList()
    // {
    // 	return AsList();
    // }

    public long CurrentPromoteStep
    {
        set { _promotion_step = value; }
        get { return _promotion_step; }
    }

    ////[IgnoredByDeepProfilerAttribute]
    public T CurrentByStartStep()
    {
        if (_current_by_start_step == list_sorted_by_start_step.NoneNode())
            return null;
        return _current_by_start_step.Value;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public T CurrentByFinishStep()
    {
        if (_current_by_finish_step == list_sorted_by_finish_step.NoneNode())
            return null;
        return _current_by_finish_step.Value;
    }

    // ////[IgnoredByDeepProfilerAttribute]
    // public T LastActive()
    // {
    // 	if (_active_states.Count == 0)
    // 		return null;
    // 	return _active_states[_active_states.Count - 1];
    // }

    // ////[IgnoredByDeepProfilerAttribute]
    // public T FirstActive()
    // {
    // 	if (_active_states.Count == 0)
    // 		return null;
    // 	return _active_states[0];
    // }

    // ////[IgnoredByDeepProfilerAttribute]
    // public T Current()
    // {
    // 	if (_current_by_start_step == null)
    // 		return null;

    // 	return _current_by_start_step.Value;
    // }

    // ////[IgnoredByDeepProfilerAttribute]
    // public LinkedListNodeMAL<T> CurrentNode()
    // {
    // 	return _current_by_start_step;
    // }

    // ////[IgnoredByDeepProfilerAttribute]
    // public T Next()
    // {
    // 	if (_current_by_start_step == null)
    // 		return null;
    // 	if (_current_by_start_step.Next == null)
    // 		return null;
    // 	return _current_by_start_step.Next.Value;
    // }

    // ////[IgnoredByDeepProfilerAttribute]
    // public LinkedListNodeMAL<T> NextNode()
    // {
    // 	if (_current_by_start_step == null)
    // 		return null;
    // 	if (_current_by_start_step.Next == null)
    // 		return null;
    // 	return _current_by_start_step.Next;
    // }

    // ////[IgnoredByDeepProfilerAttribute]
    // public LinkedListNodeMAL<T> PreviousNode()
    // {
    // 	if (_current_by_start_step == null)
    // 		return null;
    // 	if (_current_by_start_step.Previous == null)
    // 		return null;
    // 	return _current_by_start_step.Previous;
    // }

    // ////[IgnoredByDeepProfilerAttribute]
    // public void RemoveLast()
    // {
    // 	Remove(Last.Value);
    // }

    // ////[IgnoredByDeepProfilerAttribute]
    // public T Previous()
    // {
    // 	if (_current_by_start_step == null)
    // 		return null;
    // 	if (_current_by_start_step.Previous == null)
    // 		return null;
    // 	return _current_by_start_step.Previous.Value;
    // }

    ////[IgnoredByDeepProfilerAttribute]
    public MyList<T> AsListByFinish()
    {
        var result = new MyList<T>();
        foreach (var item in list_sorted_by_finish_step)
        {
            result.Add(item);
        }
        return result;
    }

    // ////[IgnoredByDeepProfilerAttribute]
    // public MyList<T> AsListByStart()
    // {
    // 	var result = new MyList<T>();
    // 	foreach (var item in list_sorted_by_start_step)
    // 	{
    // 		result.Add(item);
    // 	}
    // 	return result;
    // }

    // ////[IgnoredByDeepProfilerAttribute]
    // public bool IsValid()
    // {
    // 	return list_sorted_by_start_step.Count == list_sorted_by_finish_step.Count
    // 		&& list_sorted_by_finish_step.Count == _hashes.Count;
    // }

    public MultipleActionList(bool stub)
    {
        list_sorted_by_start_step = new LinkedListMAL<T>(true);
        list_sorted_by_finish_step = new LinkedListMAL<T>(true);
        _current_by_start_step = list_sorted_by_start_step.NoneNode();
        _current_by_finish_step = list_sorted_by_finish_step.NoneNode();

        Debug.Assert(_current_by_start_step != null);
        Debug.Assert(_current_by_finish_step != null);

        _active_states = new MyList<T>();
        _promotion_step = 0;
        BonusAdded = new MyList<T>();
        _hashes = new Dictionary<Int64, T>();
        added_precreated = new MyList<T>();
        removed_precreated = new MyList<T>();
    }

    public MultipleActionList(MultipleActionList<T> other)
    {
        _active_states = new MyList<T>(other._active_states);
        list_sorted_by_start_step = new LinkedListMAL<T>(other.list_sorted_by_start_step);
        list_sorted_by_finish_step = new LinkedListMAL<T>(other.list_sorted_by_finish_step);

        _current_by_start_step = list_sorted_by_start_step.NoneNode();
        _current_by_finish_step = list_sorted_by_finish_step.NoneNode();

        _promotion_step = other._promotion_step;
        _hashes = new Dictionary<Int64, T>(other._hashes);

        BonusAdded = new MyList<T>(other.BonusAdded);
        added_precreated = new MyList<T>();
        removed_precreated = new MyList<T>();

        PromoteWithoutExecution(_promotion_step);
    }

    public MyList<T> AsList()
    {
        var result = new MyList<T>();
        foreach (var item in list_sorted_by_start_step)
        {
            result.Add(item);
        }
        return result;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public void Remove(T state)
    {
        if (_current_by_start_step != list_sorted_by_start_step.NoneNode())
            if (_current_by_start_step.Value == state)
                _current_by_start_step = _current_by_start_step.Previous;

        if (_current_by_finish_step != list_sorted_by_finish_step.NoneNode())
            if (_current_by_finish_step.Value == state)
                _current_by_finish_step = _current_by_finish_step.Previous;

        list_sorted_by_start_step.Remove(state);
        list_sorted_by_finish_step.Remove(state);

        if (_active_states.Contains(state))
            _active_states.Remove(state);

        if (BonusAdded.Contains(state))
            BonusAdded.Remove(state);

        //Debug.Assert(_hashes.ContainsKey(state.HashCode()));
        _hashes.Remove(state.HashCode());

        Debug.Assert(_hashes.Count == list_sorted_by_start_step.Count);
    }

    // public void ReAdd(T state, long current_step)
    // {
    // 	Remove(state);
    // 	Add(state);

    // 	CheckValidity();
    // }

    ////[IgnoredByDeepProfilerAttribute]
    public int CountOfCards()
    {
        return list_sorted_by_start_step.Count;
    }

    ////[IgnoredByDeepProfilerAttribute]
    T AddToActiveStates(T state)
    {
        //Debug.Assert(HasHash(state.HashCode()));
        _active_states.Add(state);
        return state;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public LinkedListNodeMAL<T> CurrentByStart()
    {
        if (_current_by_start_step == list_sorted_by_start_step.NoneNode())
            return null;
        return _current_by_start_step;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public LinkedListNodeMAL<T> CurrentByFinish()
    {
        if (_current_by_finish_step == list_sorted_by_finish_step.NoneNode())
            return null;
        return _current_by_finish_step;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public MyList<T> ActiveStates()
    {
        return _active_states;
    }

    // ////[IgnoredByDeepProfilerAttribute]
    // public T FirstActiveState()
    // {
    // 	if (_active_states.Count == 0)
    // 		return null;
    // 	return _active_states[0];
    // }

    // ////[IgnoredByDeepProfilerAttribute]
    // public T LastActiveState()
    // {
    // 	if (_active_states.Count == 0)
    // 		return null;
    // 	return _active_states[_active_states.Count - 1];
    // }


    Predicate<T> predicate = null;

    ////[IgnoredByDeepProfilerAttribute]
    public MyList<T> DecimateActiveStates(long current_step)
    {
        if (predicate == null)
            predicate = (x) => removed_precreated.Contains(x);

        // int _active_states_capacity = _active_states.Capacity;
        // int _removed_precreated_capacity = removed_precreated.Capacity;

        removed_precreated.Clear();
        foreach (var state in _active_states)
        {
            if (state == null)
                continue;

            if (state.FinishStep < current_step || state.StartStep > current_step)
                removed_precreated.Add(state);
        }

        var rp = removed_precreated;
        _active_states.RemoveAll(predicate);

        // if (_active_states_capacity != _active_states.Capacity)
        // {
        // 	Debug.Log($"_active_states_capacity {_active_states_capacity} != _active_states.Capacity {_active_states.Capacity}");
        // }

        // if (_removed_precreated_capacity != removed_precreated.Capacity)
        // {
        // 	Debug.Log($"_removed_precreated_capacity {_removed_precreated_capacity} != removed_precreated.Capacity {removed_precreated.Capacity}");
        // }

        return removed_precreated;
    }

    // ////[IgnoredByDeepProfilerAttribute]
    // private LinkedListNodeMAL<T> PromoteListToIII(
    // 	LinkedListNodeMAL<T> current,
    // 	LinkedListMAL<T> list,
    // 	MyList<T> added,
    // 	bool add_to_active_states,
    // 	Func<T, bool> less_or_equal
    // )
    // {
    // 	// if (list.Count == 0)
    // 	// 	return null;
    // 	var next = current == null ? list.First : current.Next;

    // 	while (next != null && less_or_equal(next.Value))
    // 	{
    // 		if (add_to_active_states)
    // 			added.Add(AddToActiveStates(next.Value));
    // 		current = next;
    // 		next = next.Next;
    // 	}

    // 	while (current != null && !less_or_equal(current.Value))
    // 	{
    // 		if (add_to_active_states)
    // 			added.Add(AddToActiveStates(current.Value));
    // 		current = current.Previous;
    // 	}
    // 	return current;
    // }

    ////[IgnoredByDeepProfilerAttribute]
    private LinkedListNodeMAL<T> PromoteListToIII_A(
        LinkedListNodeMAL<T> current,
        LinkedListMAL<T> list,
        MyList<T> added,
        bool add_to_active_states,
        long current_step
    )
    {
        // if (list.Count == 0)
        // 	return null;
        var next = current.next;

        while (next != list.NoneNode() && next.StartStep <= current_step)
        {
            if (add_to_active_states)
                added.Add(AddToActiveStates(next.Value));
            current = next;
            next = next.next;
        }

        while (current != list.NoneNode() && !(current.StartStep <= current_step))
        {
            if (add_to_active_states)
                added.Add(AddToActiveStates(current.Value));
            current = current.prev;
        }
        return current;
    }

    ////[IgnoredByDeepProfilerAttribute]
    private LinkedListNodeMAL<T> PromoteListToIII_B(
        LinkedListNodeMAL<T> current,
        LinkedListMAL<T> list,
        MyList<T> added,
        bool add_to_active_states,
        long current_step
    )
    {
        // if (list.Count == 0)
        // 	return null;
        var next = current.next;

        while (next != list.NoneNode() && next.FinishStep >= current_step)
        {
            if (add_to_active_states)
                added.Add(AddToActiveStates(next.Value));
            current = next;
            next = next.next;
        }

        while (current != list.NoneNode() && !(current.FinishStep >= current_step))
        {
            if (add_to_active_states)
                added.Add(AddToActiveStates(current.Value));
            current = current.prev;
        }
        return current;
    }

    ////[IgnoredByDeepProfilerAttribute]
    private MyList<T> PromoteListToSide(
        long current_step,
        bool add_forward_pass,
        bool add_backward_pass
    )
    {
        added_precreated.Clear();

        _current_by_start_step = PromoteListToIII_A(
            _current_by_start_step,
            list_sorted_by_start_step,
            added_precreated,
            add_forward_pass,
            current_step
        );

        _current_by_finish_step = PromoteListToIII_B(
            _current_by_finish_step,
            list_sorted_by_finish_step,
            added_precreated,
            add_backward_pass,
            current_step
        );

        _promotion_step = current_step;
        return added_precreated;
    }

    ////[IgnoredByDeepProfilerAttribute]
    void PromoteWithoutExecution(long current_step)
    {
        PromoteListToSide(current_step, false, false);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public LinkedListMAL<T> GetListSortedByStartStep()
    {
        return list_sorted_by_start_step;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public LinkedListMAL<T> GetListSortedByFinishStep()
    {
        return list_sorted_by_finish_step;
    }

    ////[IgnoredByDeepProfilerAttribute]
    void AddSortedToList(
        ref LinkedListMAL<T> list,
        LinkedListNodeMAL<T> reference,
        T state,
        Func<LinkedListNodeMAL<T>, long, bool> less,
        long state_step
    )
    {
        if (reference == list.NoneNode())
            if (list.First == list.NoneNode())
            {
                list.AddFirst(state);
                return;
            }
            else
            {
                reference = list.First;
            }

        LinkedListNodeMAL<T> current = reference;
        //LinkedListNodeMAL<T> added_node = null;

        if (!less(reference, state_step))
        {
            while (current.Previous != list.NoneNode() && !less(current.Previous, state_step))
            {
                current = current.Previous;
            }
            list.AddBefore(current, state);
        }
        else
        {
            while (current.Next != list.NoneNode() && less(current.Next, state_step))
            {
                current = current.Next;
            }
            list.AddAfter(current, state);
        }
    }

    public void Clean()
    {
        _active_states.Clear();
        BonusAdded.Clear();
        _hashes.Clear();
        list_sorted_by_start_step.Clear();
        list_sorted_by_finish_step.Clear();
        _current_by_start_step = list_sorted_by_start_step.NoneNode();
        _current_by_finish_step = list_sorted_by_finish_step.NoneNode();
    }

    ////[IgnoredByDeepProfilerAttribute]
    public bool Add(T state)
    {
        if (Utility.CARDS_DEBUG_MODE)
            Debug.Log($"Add {state.info()}");

        if (
            state.StartStep < long.MinValue + 1000
            || state.FinishStep < long.MinValue + 1000
            || state.StartStep > long.MaxValue - 1000
            || state.FinishStep > long.MaxValue - 1000
        )
        {
            Debug.LogError($"Wrong start or finish step in {state.info()}");
        }

        if (_hashes.Count != list_sorted_by_start_step.Count)
        {
            //Debug.LogError($"hashes count {_hashes.Count} != list_sorted_by_start_step.Count {list_sorted_by_start_step.Count}");
        }

        if (_hashes.ContainsKey(state.HashCode()))
            return false;

        var stateStartStep = state.StartStep;
        var stateFinishStep = state.FinishStep;

        AddSortedToList(
            ref list_sorted_by_start_step,
            _current_by_start_step,
            state,
            (a, state_step) => a.StartStep < state_step,
            stateStartStep
        );
        AddSortedToList(
            ref list_sorted_by_finish_step,
            _current_by_finish_step,
            state,
            (a, state_step) => a.FinishStep > state_step,
            stateFinishStep
        );
        if (_promotion_step >= state.StartStep && _promotion_step <= state.FinishStep)
            BonusAdded.Add(state);

        _hashes.Add(state.HashCode(), state);

        PromoteWithoutExecution(_promotion_step);
        return true;
    }

    ////[IgnoredByDeepProfilerAttribute]
    // public void Replace(T oldstate, T newstate)
    // {
    // 	bool is_bonus_added_contains = BonusAdded.Contains(oldstate);

    // 	Remove(oldstate);
    // 	Add(newstate);

    // 	if (!is_bonus_added_contains && BonusAdded.Contains(newstate))
    // 		BonusAdded.Remove(newstate);
    // }

    ////[IgnoredByDeepProfilerAttribute]
    public void AddLast(T state)
    {
        Add(state);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public int ByStartIteratorPosition()
    {
        if (_current_by_start_step == list_sorted_by_start_step.NoneNode())
            return -1;
        int i = 0;
        var current = list_sorted_by_start_step.First;
        for (
            ;
            current != list_sorted_by_start_step.NoneNode() && current != _current_by_start_step;
            i++
        )
        {
            current = current.next;
        }
        return i;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public int ByFinishIteratorPosition()
    {
        if (_current_by_finish_step == list_sorted_by_finish_step.NoneNode())
            return -1;
        int i = 0;
        var current = list_sorted_by_finish_step.First;
        for (
            ;
            current != list_sorted_by_finish_step.NoneNode() && current != _current_by_finish_step;
            i++
        )
        {
            current = current.next;
        }
        return i;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public long FirstStepInStartList()
    {
        if (list_sorted_by_start_step.Count == 0)
            return long.MaxValue;
        return list_sorted_by_start_step.First.Value.StartStep;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public long LastStepInStartList()
    {
        if (list_sorted_by_start_step.Count == 0)
            return long.MinValue;
        return list_sorted_by_start_step.Last.Value.StartStep;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public long LastStepInFinishList()
    {
        if (list_sorted_by_finish_step.Count == 0)
            return long.MinValue;
        return list_sorted_by_finish_step.First.Value.FinishStep;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public long FirstStepInFinishList()
    {
        if (list_sorted_by_finish_step.Count == 0)
            return long.MaxValue;
        return list_sorted_by_finish_step.Last.Value.FinishStep;
    }

    // ////[IgnoredByDeepProfilerAttribute]
    // public void Invalidate()
    // {
    // 	list_sorted_by_start_step.Clear();
    // 	list_sorted_by_finish_step.Clear();
    // 	_current_by_finish_step = null;
    // 	_current_by_start_step = null;
    // 	_active_states.Clear();
    // 	BonusAdded.Clear();
    // 	_hashes.Clear();
    // }

    ////[IgnoredByDeepProfilerAttribute]
    public LinkedListNodeMAL<T> DropToCurrentState(
        ref LinkedListMAL<T> list,
        LinkedListNodeMAL<T> current,
        ref LinkedListMAL<T> other_list,
        LinkedListNodeMAL<T> other_current,
        //Func<bool> invalidate_condition,
        ref MyList<T> list_of_removed
    )
    {
        // if (invalidate_condition())
        // {
        // 	list_of_removed = AsList();
        // 	Invalidate();
        // 	return null;
        // }

        while (current.Next != list.NoneNode())
        {
            var last = list.Last;
            list.RemoveLast();

            var state = last.Value;

            if (state != null)
            {
                list_of_removed.Add(state);
                _hashes.Remove(state.HashCode());

                if (_active_states.Contains(state))
                    _active_states.Remove(state);

                if (BonusAdded.Contains(state))
                    BonusAdded.Remove(state);
            }

            var iterator = other_list.First;
            while (iterator.Value != state)
            {
                iterator = iterator.Next;
            }

            if (other_current == iterator)
                other_current = iterator.Next;

            other_list.Remove(iterator);
        }

        return other_current;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public long PromotionStep()
    {
        return _promotion_step;
    }

    MyList<T> list_of_removed_precreated = new MyList<T>();

    ////[IgnoredByDeepProfilerAttribute]
    public MyList<T> DropToCurrentState()
    {
        list_of_removed_precreated.Clear();
        _current_by_finish_step = DropToCurrentState(
            ref list_sorted_by_start_step,
            _current_by_start_step,
            ref list_sorted_by_finish_step,
            _current_by_finish_step,
            //() => _promotion_step < FirstStepInStartList(),
            ref list_of_removed_precreated
        );
        return list_of_removed_precreated;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public MyList<T> DropToCurrentStateInverted()
    {
        list_of_removed_precreated.Clear();
        _current_by_start_step = DropToCurrentState(
            ref list_sorted_by_finish_step,
            _current_by_finish_step,
            ref list_sorted_by_start_step,
            _current_by_start_step,
            //() => _promotion_step > LastStepInFinishList(),
            ref list_of_removed_precreated
        );
        return list_of_removed_precreated;
    }

    ////[IgnoredByDeepProfilerAttribute]
    void BonusApplyAndClear(ref MyList<T> added)
    {
        if (BonusAdded.Count == 0)
            return;

        foreach (var ev in BonusAdded)
        {
            if (!_active_states.Contains(ev))
                added.Add(AddToActiveStates(ev));
        }
        BonusAdded.Clear();
    }

    ////[IgnoredByDeepProfilerAttribute]
    public long PromoteStep()
    {
        return _promotion_step;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public void PromoteList(
        long step,
        out MyList<T> added,
        out MyList<T> goned,
        out TimeDirection direction
    )
    {
        // var added_capacity = added_precreated.Capacity;
        // var goned_capacity = removed_precreated.Capacity;

        direction = step > _promotion_step ? TimeDirection.Forward : TimeDirection.Backward;

        // if (Timeline.direction_check_enabled)
        // {
        // 	if (direction == Timeline.direction)
        // 		Debug.Assert(direction == Timeline.direction);
        // }

        if (direction == TimeDirection.Forward)
            added = PromoteListToSide(step, true, false);
        else
            added = PromoteListToSide(step, false, true);

        BonusApplyAndClear(ref added);

        goned = DecimateActiveStates(step);
        _promotion_step = step;

        // if (added_capacity != added_precreated.Capacity)
        // {
        // 	Debug.Log($"added_capacity {added_capacity} != added_precreated.Capacity {added_precreated.Capacity}");
        // }

        // if (goned_capacity != removed_precreated.Capacity)
        // {
        // 	Debug.Log($"goned_capacity {goned_capacity} != removed_precreated.Capacity {removed_precreated.Capacity}");
        // }
    }

    ////[IgnoredByDeepProfilerAttribute]
    public void Promote(long step, out MyList<T> added, out MyList<T> goned)
    {
        TimeDirection direction;
        PromoteList(step, out added, out goned, out direction);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public void PromoteList(long step, out MyList<T> added, out MyList<T> goned)
    {
        TimeDirection direction;
        PromoteList(step, out added, out goned, out direction);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public void Promote(
        long step,
        out MyList<T> added,
        out MyList<T> goned,
        out TimeDirection direction
    )
    {
        PromoteList(step, out added, out goned, out direction);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public void UpdatePresentState(long current_step, out MyList<T> goned)
    {
        MyList<T> added;
        TimeDirection direction;
        PromoteList(current_step, out added, out goned, out direction);
    }

    public int Count
    {
        get { return list_sorted_by_start_step.Count; }
    }

    public int ActiveCount
    {
        get { return _active_states.Count; }
    }

    ////[IgnoredByDeepProfilerAttribute]
    public void RemoveByHashCode(Int64 hash)
    {
        var state = _hashes[hash];
        Remove(state);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public bool ContainsHash(T state)
    {
        return _hashes.ContainsKey(state.HashCode());
    }

    ////[IgnoredByDeepProfilerAttribute]
    public bool ContainsHash(long hash)
    {
        return _hashes.ContainsKey(hash);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public bool IsEqual(MultipleActionList<T> other)
    {
        if (Count != other.Count)

            return false;

        // TODO

        // var this_list = AsList();
        // var other_list = other.AsList();

        // for (int i = 0; i < this_list.Count; i++)
        // {
        // 	if (!this_list[i].IsEqual(other_list[i]))
        // 		return false;
        // }

        return true;
    }

    ////[IgnoredByDeepProfilerAttribute]
    Dictionary<string, object> SerializeCardDictionary(Dictionary<long, T> cards)
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();
        foreach (var card in cards)
        {
            dict.Add(card.Key.ToString(), card.Value.ToTrent());
        }
        return dict;
    }

    ////[IgnoredByDeepProfilerAttribute]
    MyList<object> SerializeHashList(ref LinkedListMAL<T> cards)
    {
        MyList<object> list = new MyList<object>();
        foreach (var card in cards)
        {
            list.Add(card.HashCode());
        }
        return list;
    }

    ////[IgnoredByDeepProfilerAttribute]
    MyList<object> SerializeHashList(MyList<T> cards)
    {
        MyList<object> list = new MyList<object>();
        foreach (var card in cards)
        {
            list.Add(card.HashCode());
        }
        return list;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public Dictionary<string, object> ToTrent()
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();

        dict.Add("cards", SerializeCardDictionary(Hashes));
        dict.Add("by_start_step", SerializeHashList(ref list_sorted_by_start_step));
        dict.Add("by_finish_step", SerializeHashList(ref list_sorted_by_finish_step));
        dict.Add("active_states", SerializeHashList(ActiveStatesList));
        dict.Add("bonus_added", SerializeHashList(BonusAdded));
        dict.Add(
            "current_by_start_step",
            CurrentByStartStepNode == list_sorted_by_start_step.NoneNode()
                ? "null"
                : CurrentByStartStepNode.Value.HashCode().ToString()
        );
        dict.Add(
            "current_by_finish_step",
            CurrentByFinishStepNode == list_sorted_by_finish_step.NoneNode()
                ? "null"
                : CurrentByFinishStepNode.Value.HashCode().ToString()
        );
        dict.Add("current_promote_step", CurrentPromoteStep);

        return dict;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public static Dictionary<long, T> DeserializeCardDictionary(Dictionary<string, object> dict)
    {
        Dictionary<long, T> cards = new Dictionary<long, T>();
        foreach (var card in dict)
        {
            cards.Add(
                long.Parse(card.Key),
                BasicMultipleAction.CreateFromTrent(card.Value as Dictionary<string, object>) as T
            );
        }
        return cards;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public static LinkedListMAL<T> DeserializeHashLinkedList(
        Dictionary<long, T> cards,
        MyList<object> list
    )
    {
        LinkedListMAL<T> result = new LinkedListMAL<T>();
        foreach (var card in list)
        {
            result.AddLast(cards[(long)card]);
        }
        return result;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public static MyList<T> DeserializeHashList(Dictionary<long, T> cards, MyList<object> list)
    {
        MyList<T> result = new MyList<T>();
        foreach (var card in list)
        {
            result.Add(cards[(long)card]);
        }
        return result;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public void FromTrent(Dictionary<string, object> dict)
    {
        _hashes = DeserializeCardDictionary(dict["cards"] as Dictionary<string, object>);
        list_sorted_by_start_step = DeserializeHashLinkedList(
            _hashes,
            dict["by_start_step"] as MyList<object>
        );
        list_sorted_by_finish_step = DeserializeHashLinkedList(
            _hashes,
            dict["by_finish_step"] as MyList<object>
        );
        ActiveStatesList = DeserializeHashList(_hashes, dict["active_states"] as MyList<object>);
        BonusAdded = DeserializeHashList(_hashes, dict["bonus_added"] as MyList<object>);
        //event_line.MyList.CurrentByStartStepNode = DeserializeCurrent(event_line.MyList.Hashes, dict["current_by_start_step"] as string);
        //event_line.MyList.CurrentByFinishStepNode = DeserializeCurrent(event_line.MyList.Hashes, dict["current_by_finish_step"] as string);
        CurrentPromoteStep = (long)dict["current_promote_step"];
    }

    ////[IgnoredByDeepProfilerAttribute]
    public static MultipleActionList<T> CreateFromTrent(Dictionary<string, object> data)
    {
        var result = new MultipleActionList<T>(true);
        result.FromTrent(data);
        return result;
    }
}
