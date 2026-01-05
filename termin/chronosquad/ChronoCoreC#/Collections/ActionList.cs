using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using System;

#if UNITY_64
using UnityEngine;
using Unity.Profiling;
#endif

public class ActionList<T> where T : BasicMultipleAction
{
    // MyList<T> _active_states = new MyList<T>();
    // LinkedListMAL<T> list_sorted_by_start_step = new LinkedListMAL<T>();
    // LinkedListNodeMAL<T> _current_by_start_step;
    // long _promotion_step = 0;
    // public MyList<T> BonusAdded = new MyList<T>();
    // public Dictionary<Int64, T> _hashes = new Dictionary<Int64, T>();

    // MyList<T> removed_precreated = new MyList<T>();
    // MyList<T> added_precreated = new MyList<T>();

    LinkedListMAL<T> list_sorted_by_start_step;
    LinkedListNodeMAL<T> _current_by_start_step;
    long _promotion_step;

    //public MyList<T> BonusAdded;
    public MyList<T> LateAdd = new MyList<T>();
    public Dictionary<Int64, T> _hashes;

    MyList<T> _active_states_temporary;
    MyList<T> removed_precreated;
    MyList<T> added_precreated;

    public bool HasHash(Int64 hash)
    {
        return _hashes.ContainsKey(hash);
    }

    public T CurrentState()
    {
        if (_current_by_start_step == list_sorted_by_start_step.NoneNode())
            return null;

        if (_current_by_start_step.StartStep > _promotion_step)
            return null;

        if (_current_by_start_step.FinishStep < _promotion_step)
            return null;

        return _current_by_start_step.Value;
    }

    public LinkedListNodeMAL<T> CurrentByStartStepNode
    {
        get { return _current_by_start_step; }
        set { _current_by_start_step = value; }
    }

    public Dictionary<Int64, T> Hashes
    {
        get { return _hashes; }
        set { _hashes = value; }
    }

    public string FullInfo()
    {
        string result = "";
        foreach (var item in list_sorted_by_start_step)
        {
            result += item.ToString() + "\n";
        }
        return result;
    }

    // public MyList<T> ActiveStatesList
    // {
    // 	get { return _active_states; }
    // 	set { _active_states = value; }
    // }

    public void StepForwardFork()
    {
        _current_by_start_step = _current_by_start_step.StepForwardFork();
    }

    public void StepForwardForkAlternate()
    {
        _current_by_start_step = _current_by_start_step.StepForwardForkAlternate();
    }

    public void StepBackwardFork()
    {
        _current_by_start_step = _current_by_start_step.StepBackwardFork();
    }

    public void StepBackwardForkAlternate()
    {
        _current_by_start_step = _current_by_start_step.StepBackwardForkAlternate();
    }

    public LinkedListNodeMAL<T> Last
    {
        get
        {
            if (list_sorted_by_start_step.Count == 0)
                return null;
            return list_sorted_by_start_step.Last;
        }
    }

    public LinkedListNodeMAL<T> First
    {
        get
        {
            if (list_sorted_by_start_step.Count == 0)
                return null;
            return list_sorted_by_start_step.First;
        }
    }

    //[IgnoredByDeepProfilerAttribute]
    // public MyList<T> AsList()
    // {
    // 	var result = new MyList<T>();
    // 	foreach (var item in list_sorted_by_start_step)
    // 	{
    // 		result.Add(item);
    // 	}
    // 	return result;
    // }

    //[IgnoredByDeepProfilerAttribute]
    // public MyList<T> GetList()
    // {
    // 	return AsList();
    // }

    public long CurrentPromoteStep
    {
        set { _promotion_step = value; }
        get { return _promotion_step; }
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

    //[IgnoredByDeepProfilerAttribute]
    public T CurrentByStartStep()
    {
        if (_current_by_start_step == list_sorted_by_start_step.NoneNode())
            return null;
        return _current_by_start_step.Value;
    }

    //[IgnoredByDeepProfilerAttribute]
    // public T LastActive()
    // {
    // 	if (_active_states.Count == 0)
    // 		return null;
    // 	return _active_states[_active_states.Count - 1];
    // }

    //[IgnoredByDeepProfilerAttribute]
    // public T FirstActive()
    // {
    // 	if (_active_states.Count == 0)
    // 		return null;
    // 	return _active_states[0];
    // }

    //[IgnoredByDeepProfilerAttribute]
    public T Current()
    {
        if (_current_by_start_step == list_sorted_by_start_step.NoneNode())
            return null;

        return _current_by_start_step.Value;
    }

    //[IgnoredByDeepProfilerAttribute]
    public LinkedListNodeMAL<T> CurrentNode()
    {
        return _current_by_start_step;
    }

    // //[IgnoredByDeepProfilerAttribute]
    // public T Next()
    // {
    // 	if (_current_by_start_step == null)
    // 		return null;
    // 	if (_current_by_start_step.Next == null)
    // 		return null;
    // 	return _current_by_start_step.Next.Value;
    // }

    //[IgnoredByDeepProfilerAttribute]
    public LinkedListNodeMAL<T> NextNode()
    {
        if (_current_by_start_step == list_sorted_by_start_step.NoneNode())
            return null;
        if (_current_by_start_step.Next == list_sorted_by_start_step.NoneNode())
            return null;
        return _current_by_start_step.Next;
    }

    // //[IgnoredByDeepProfilerAttribute]
    // public LinkedListNodeMAL<T> PreviousNode()
    // {
    // 	if (_current_by_start_step == null)
    // 		return null;
    // 	if (_current_by_start_step.Previous == null)
    // 		return null;
    // 	return _current_by_start_step.Previous;
    // }

    //[IgnoredByDeepProfilerAttribute]
    public void RemoveLast()
    {
        Remove(Last.Value);
    }

    //[IgnoredByDeepProfilerAttribute]
    public T Previous()
    {
        if (_current_by_start_step == list_sorted_by_start_step.NoneNode())
            return null;
        if (_current_by_start_step.Previous == list_sorted_by_start_step.NoneNode())
            return null;
        return _current_by_start_step.Previous.Value;
    }

    //[IgnoredByDeepProfilerAttribute]
    public MyList<T> AsListByStart()
    {
        var result = new MyList<T>();
        foreach (var item in list_sorted_by_start_step)
        {
            result.Add(item);
        }
        return result;
    }

    public MyList<T> AllNextAsList()
    {
        var iterator = _current_by_start_step;
        var result = new MyList<T>();
        do
        {
            iterator = iterator.Next;
            if (iterator == list_sorted_by_start_step.NoneNode())
                break;
            result.Add(iterator.Value);
        } while (true);
        return result;
    }

    public ActionList(bool stub)
    {
        list_sorted_by_start_step = new LinkedListMAL<T>(true);
        _current_by_start_step = list_sorted_by_start_step.NoneNode();

        _active_states_temporary = new MyList<T>();
        _promotion_step = long.MinValue;
        //BonusAdded = new MyList<T>();
        _hashes = new Dictionary<Int64, T>();

        removed_precreated = new MyList<T>();
        added_precreated = new MyList<T>();
    }

    public ActionList(ActionList<T> other)
    {
        list_sorted_by_start_step = new LinkedListMAL<T>(other.list_sorted_by_start_step);
        _current_by_start_step = list_sorted_by_start_step.NoneNode();
        _promotion_step = other._promotion_step;
        _hashes = new Dictionary<Int64, T>(other._hashes);
        LateAdd = new MyList<T>(other.LateAdd);

        //BonusAdded = new MyList<T>(other.BonusAdded);

        _active_states_temporary = new MyList<T>();
        removed_precreated = new MyList<T>();
        added_precreated = new MyList<T>();

        PromoteWithoutExecution(_promotion_step);
    }

    LinkedListNodeMAL<T> FindInStartList(T state)
    {
        var current = list_sorted_by_start_step.First;
        while (current != list_sorted_by_start_step.NoneNode())
        {
            if (current.Value == state)
                return current;
            current = current.Next;
        }
        return list_sorted_by_start_step.NoneNode();

        // var current = _current_by_start_step;
        // while (current != list_sorted_by_start_step.NoneNode())
        // {
        // 	if (current.Value == state)
        // 		return current;
        // 	if (current.Value.StartStep >= state.StartStep)
        // 		current = current.Previous;
        // 	else
        // 		current = current.Next;
        // }
        // return list_sorted_by_start_step.NoneNode();
    }

    public LinkedListNodeMAL<T> NullNode()
    {
        return list_sorted_by_start_step.NoneNode();
    }

    void RemoveInStartList(T state)
    {
        var node = FindInStartList(state);
        if (node == list_sorted_by_start_step.NoneNode())
        {
            Debug.LogError(
                "RemoveInStartList: node == list_sorted_by_start_step.NoneNode():"
                    + state.ToString()
            );

            var current = list_sorted_by_start_step.First;
            while (current != list_sorted_by_start_step.NoneNode())
            {
                Debug.LogError("List: " + current.Value.ToString());
                current = current.Next;
            }

            return;
        }
        list_sorted_by_start_step.Remove(node);
    }

    //[IgnoredByDeepProfilerAttribute]
    public void Remove(T state)
    {
        if (_hashes.Count != list_sorted_by_start_step.Count)
        {
            //Debug.LogError($"hashes count {_hashes.Count} != list_sorted_by_start_step.Count {list_sorted_by_start_step.Count}");
        }

        if (_current_by_start_step != list_sorted_by_start_step.NoneNode())
            if (_current_by_start_step.Value == state)
                _current_by_start_step = _current_by_start_step.Previous;

        RemoveInStartList(state);

        // if (_active_states.Contains(state))
        // 	_active_states.Remove(state);

        // if (BonusAdded.Contains(state))
        // 	BonusAdded.Remove(state);
        if (LateAdd.Contains(state))
            LateAdd.Remove(state);

        _hashes.Remove(state.HashCode());
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

    public T Find(Type type, long start_step)
    {
        var current = list_sorted_by_start_step.First;
        while (current != list_sorted_by_start_step.NoneNode())
        {
            if ((current.Value.GetType() == type) && (current.Value.StartStep == start_step))
                return current.Value;
            current = current.Next;
        }
        return null;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void Remove(Type type, long start_step)
    {
        var state = Find(type, start_step);
        if (state != null)
        {
            Remove(state);
            return;
        }
    }

    //[IgnoredByDeepProfilerAttribute]
    public int CountOfCards()
    {
        return list_sorted_by_start_step.Count;
    }

    //[IgnoredByDeepProfilerAttribute]
    T AddToActiveStates(T state)
    {
        _active_states_temporary.Add(state);
        return state;
    }

    //[IgnoredByDeepProfilerAttribute]
    public LinkedListNodeMAL<T> CurrentByStart()
    {
        return _current_by_start_step;
    }

    // //[IgnoredByDeepProfilerAttribute]
    // public MyList<T> ActiveStates()
    // {
    // 	return _active_states;
    // }

    //[IgnoredByDeepProfilerAttribute]
    // public T FirstActiveState()
    // {
    // 	if (_active_states.Count == 0)
    // 		return null;
    // 	return _active_states[0];
    // }

    //[IgnoredByDeepProfilerAttribute]
    // public T LastActiveState()
    // {
    // 	if (_active_states.Count == 0)
    // 		return null;
    // 	return _active_states[_active_states.Count - 1];
    // }

    Predicate<T> predicate = null;

    //[IgnoredByDeepProfilerAttribute]
    // public MyList<T> DecimateActiveStates(long current_step)
    // {
    // 	if (predicate == null)
    // 		predicate = (x) => removed_precreated.Contains(x);

    // 	removed_precreated.Clear();
    // 	foreach (var state in _active_states)
    // 	{
    // 		if (state.FinishStep < current_step || state.StartStep > current_step)
    // 		{
    // 			removed_precreated.Add(state);
    // 		}
    // 	}

    // 	if (removed_precreated.Count != 0) {
    // 		_active_states.RemoveAll(predicate);
    // 	}

    // 	return removed_precreated;
    // }

    bool ContainsHash(T state, MyList<T> list)
    {
        foreach (var item in list)
        {
            if (item.HashCode() == state.HashCode())
                return true;
        }
        return false;
    }

    public MyList<T> DecimateAllActiveStatesExceptCurrentIfActive(long current_step)
    {
        if (predicate == null)
            predicate = (x) => ContainsHash(x, removed_precreated);

        removed_precreated.Clear();
        var current = _current_by_start_step;
        foreach (var state in _active_states_temporary)
        {
            if (current == null)
            {
                removed_precreated.Add(state);
            }
            else
            {
                if (state != current.Value)
                {
                    removed_precreated.Add(state);
                }
                else if (state.FinishStep < current_step || state.StartStep > current_step)
                {
                    removed_precreated.Add(state);
                }
            }
        }

        if (removed_precreated.Count != 0)
        {
            _active_states_temporary.RemoveAll(predicate);
        }

        Debug.Assert(_active_states_temporary.Count <= 1);

        return removed_precreated;
    }

    // //[IgnoredByDeepProfilerAttribute]
    // private LinkedListNode<T> PromoteListToIII(
    // 	LinkedListNode<T> current,
    // 	LinkedList<T> list,
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

    //[IgnoredByDeepProfilerAttribute]
    private LinkedListNodeMAL<T> PromoteListToIII_A(
        LinkedListNodeMAL<T> current,
        ref LinkedListMAL<T> list,
        MyList<T> added,
        bool add_to_active_states,
        long current_step
    )
    {
        // if (list.Count == 0)
        // 	return null;
        var next = current == list_sorted_by_start_step.NoneNode() ? list.First : current.Next;

        while (next != list_sorted_by_start_step.NoneNode() && next.StartStep <= current_step)
        {
            if (add_to_active_states)
                added.Add(AddToActiveStates(next.Value));
            current = next;
            next = next.Next;
        }

        while (
            current != list_sorted_by_start_step.NoneNode() && !(current.StartStep <= current_step)
        )
        {
            if (add_to_active_states)
                added.Add(AddToActiveStates(current.Value));
            current = current.Previous;
        }
        return current;
    }

    // //[IgnoredByDeepProfilerAttribute]
    // 	private LinkedListNode<T> PromoteListToIII_B(
    // 	LinkedListNode<T> current,
    // 	LinkedList<T> list,
    // 	MyList<T> added,
    // 	bool add_to_active_states,
    // 	long current_step
    // )
    // {
    // 	// if (list.Count == 0)
    // 	// 	return null;
    // 	var next = current == null ? list.First : current.Next;

    // 	while (next != null && next.Value.FinishStep >= current_step)
    // 	{
    // 		if (add_to_active_states)
    // 			added.Add(AddToActiveStates(next.Value));
    // 		current = next;
    // 		next = next.Next;
    // 	}

    // 	while (current != null && !(current.Value.FinishStep >= current_step))
    // 	{
    // 		if (add_to_active_states)
    // 			added.Add(AddToActiveStates(current.Value));
    // 		current = current.Previous;
    // 	}
    // 	return current;
    // }

    //[IgnoredByDeepProfilerAttribute]
    public string CurrentIndexes()
    {
        return string.Format(
            "CurrentByStart: {0}",
            CurrentByStart() == list_sorted_by_start_step.NoneNode()
                ? "null"
                : CurrentByStart().Value.ToString()
        );
    }

    //[IgnoredByDeepProfilerAttribute]
    private MyList<T> PromoteListToSide(long current_step, bool add_forward_pass)
    {
        bool is_forward_pass = add_forward_pass;
        added_precreated.Clear();
        _current_by_start_step = PromoteListToIII_A(
            _current_by_start_step,
            ref list_sorted_by_start_step,
            added_precreated,
            add_forward_pass,
            current_step
        );
        _promotion_step = current_step;
        return added_precreated;
    }

    //[IgnoredByDeepProfilerAttribute]
    void PromoteWithoutExecution(long current_step)
    {
        PromoteListToSide(current_step, false);
    }

    //[IgnoredByDeepProfilerAttribute]
    void AddSortedToList(LinkedListNodeMAL<T> reference, T state)
    {
        Debug.Assert(state != null);

        if (reference == list_sorted_by_start_step.NoneNode())
            if (list_sorted_by_start_step.First == list_sorted_by_start_step.NoneNode())
            {
                list_sorted_by_start_step.AddFirst(state);
                return;
            }
            else
            {
                reference = list_sorted_by_start_step.First;
            }

        LinkedListNodeMAL<T> current = reference;

        if (state.StartStep < reference.StartStep)
        {
            while (
                current.prev != list_sorted_by_start_step.NoneNode()
                && !(current.prev.StartStep < state.StartStep)
            )
            {
                current = current.prev;
            }
            list_sorted_by_start_step.AddBefore(current, state);
        }
        else
        {
            while (
                current.next != list_sorted_by_start_step.NoneNode()
                && current.Next.StartStep < state.StartStep
            )
            {
                current = current.next;
            }
            list_sorted_by_start_step.AddAfter(current, state);
        }
    }

    public void Clean()
    {
        _hashes.Clear();
        list_sorted_by_start_step.Clear();
        _current_by_start_step = list_sorted_by_start_step.NoneNode();
    }

    public bool Add(T state)
    {
        if (Utility.CARDS_DEBUG_MODE)
            Debug.Log($"Add {state.info()}");

        Debug.Assert(state.StartStep > long.MinValue + 1000);
        Debug.Assert(state.FinishStep > long.MinValue + 1000);

        Debug.Assert(state.StartStep < long.MaxValue - 1000);
        //Debug.Assert(state.FinishStep < long.MaxValue - 1000);

        if (_hashes.ContainsKey(state.HashCode()))
        {
            return false;
        }
        LateAdd.Add(state);
        return true;
    }

    //[IgnoredByDeepProfilerAttribute]
    public bool L_Add(T state)
    {
        if (_hashes.Count != list_sorted_by_start_step.Count)
        {
            //Debug.LogError($"hashes count {_hashes.Count} != list_sorted_by_start_step.Count {list_sorted_by_start_step.Count}");
        }

        if (_hashes.ContainsKey(state.HashCode()))
        {
            return false;
        }

        AddSortedToList(_current_by_start_step, state);
        // if (_promotion_step >= state.StartStep && _promotion_step <= state.FinishStep)
        // 	BonusAdded.Add(state);

        _hashes.Add(state.HashCode(), state);

        PromoteWithoutExecution(_promotion_step);
        return true;
    }

    //[IgnoredByDeepProfilerAttribute]
    // public void Replace(T oldstate, T newstate)
    // {
    // 	//bool is_bonus_added_contains = BonusAdded.Contains(oldstate);

    // 	Remove(oldstate);
    // 	L_Add(newstate);

    // 	// if (!is_bonus_added_contains && BonusAdded.Contains(newstate))
    // 	// 	BonusAdded.Remove(newstate);
    // }

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

    //[IgnoredByDeepProfilerAttribute]
    public long FirstStepInStartList()
    {
        if (list_sorted_by_start_step.Count == 0)
            return long.MaxValue;
        return list_sorted_by_start_step.First.StartStep;
    }

    //[IgnoredByDeepProfilerAttribute]
    public long LastStepInStartList()
    {
        if (list_sorted_by_start_step.Count == 0)
            return long.MinValue;
        return list_sorted_by_start_step.Last.StartStep;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void Invalidate()
    {
        list_sorted_by_start_step.Clear();
        _current_by_start_step = null;
        //_active_states.Clear();
        //BonusAdded.Clear();
        _hashes.Clear();
    }

    //[IgnoredByDeepProfilerAttribute]
    public void DropToCurrentState(
        LinkedListNodeMAL<T> current,
        //Func<bool> invalidate_condition,
        ref MyList<T> list_of_removed
    )
    {
        // if (invalidate_condition())
        // {
        // 	list_of_removed = AsList();
        // 	Invalidate();
        // 	return;
        // }

        while (current.Next != list_sorted_by_start_step.NoneNode())
        {
            var last = list_sorted_by_start_step.Last;
            list_sorted_by_start_step.RemoveLast();

            var state = last.Value;
            if (state != null)
            {
                list_of_removed.Add(state);
                _hashes.Remove(state.HashCode());
            }
            // if (_active_states.Contains(state))
            // 	_active_states.Remove(state);

            // if (BonusAdded.Contains(state))
            // 	BonusAdded.Remove(state);
        }
    }

    //[IgnoredByDeepProfilerAttribute]
    public MyList<T> DropToCurrentState()
    {
        removed_precreated.Clear();
        DropToCurrentState(
            _current_by_start_step,
            //() => _promotion_step < FirstStepInStartList(),
            ref removed_precreated
        );
        return removed_precreated;
    }

    //[IgnoredByDeepProfilerAttribute]
    public MyList<T> DropToCurrentStateInverted()
    {
        removed_precreated.Clear();
        return removed_precreated;
    }

    //[IgnoredByDeepProfilerAttribute]
    void BonusApplyAndClear(ref MyList<T> added, MyList<T> bonus)
    {
        if (bonus.Count == 0)
            return;

        foreach (var ev in bonus)
        {
            if (!_active_states_temporary.Contains(ev))
            {
                added.Add(AddToActiveStates(ev));
            }
        }
    }

    //[IgnoredByDeepProfilerAttribute]
    public long PromoteStep()
    {
        return _promotion_step;
    }

    void ResetActiveStates()
    {
        _active_states_temporary.Clear();
        if (CurrentState() != null)
            _active_states_temporary.Add(CurrentState());
    }

    MyList<T> _BonusAdded = new MyList<T>();

    //[IgnoredByDeepProfilerAttribute]
    public void PromoteList(
        long step,
        out MyList<T> added,
        out MyList<T> goned,
        out TimeDirection direction
    )
    {
        ResetActiveStates();
        _BonusAdded.Clear();
        foreach (var state in LateAdd)
        {
            L_Add(state);

            if (_promotion_step >= state.StartStep && _promotion_step <= state.FinishStep)
                _BonusAdded.Add(state);
        }
        LateAdd.Clear();

        direction = step > _promotion_step ? TimeDirection.Forward : TimeDirection.Backward;

        if (direction == TimeDirection.Forward)
            added = PromoteListToSide(step, true);
        else
            added = PromoteListToSide(step, false);

        BonusApplyAndClear(ref added, _BonusAdded);

        goned = DecimateAllActiveStatesExceptCurrentIfActive(step);
        //goned = DecimateActiveStates(step);
        _promotion_step = step;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void Promote(long step, out MyList<T> added, out MyList<T> goned)
    {
        TimeDirection direction;
        PromoteList(step, out added, out goned, out direction);
    }

    //[IgnoredByDeepProfilerAttribute]
    public void PromoteList(long step, out MyList<T> added, out MyList<T> goned)
    {
        TimeDirection direction;
        PromoteList(step, out added, out goned, out direction);
    }

    //[IgnoredByDeepProfilerAttribute]
    public void Promote(
        long step,
        out MyList<T> added,
        out MyList<T> goned,
        out TimeDirection direction
    )
    {
        PromoteList(step, out added, out goned, out direction);
    }

    //[IgnoredByDeepProfilerAttribute]
    public void UpdatePresentState(long current_step, out MyList<T> goned)
    {
        MyList<T> added;
        TimeDirection direction;
        PromoteList(current_step, out added, out goned, out direction);
    }

    public int Count
    {
        get { return list_sorted_by_start_step.Count + LateAdd.Count; }
    }

    // public int ActiveCount
    // {
    // 	get { return _active_states.Count; }
    // }

    //[IgnoredByDeepProfilerAttribute]
    public void RemoveByHashCode(Int64 hash)
    {
        var state = _hashes[hash];
        Remove(state);
    }

    //[IgnoredByDeepProfilerAttribute]
    public bool ContainsHash(T state)
    {
        return _hashes.ContainsKey(state.HashCode());
    }

    //[IgnoredByDeepProfilerAttribute]
    public bool ContainsHash(long hash)
    {
        return _hashes.ContainsKey(hash);
    }

    //[IgnoredByDeepProfilerAttribute]
    public bool IsEqual(ActionList<T> other)
    {
        if (Count != other.Count)
            return false;

        // var this_list = AsList();
        // var other_list = other.AsList();

        // for (int i = 0; i < this_list.Count; i++)
        // {
        // 	if (!this_list[i].IsEqual(other_list[i]))
        // 		return false;
        // }

        return true;
    }

    //[IgnoredByDeepProfilerAttribute]
    Dictionary<string, object> SerializeCardDictionary(Dictionary<long, T> cards)
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();
        foreach (var card in cards)
        {
            dict.Add(card.Key.ToString(), card.Value.ToTrent());
        }
        return dict;
    }

    //[IgnoredByDeepProfilerAttribute]
    MyList<object> SerializeHashList(ref LinkedListMAL<T> cards)
    {
        MyList<object> list = new MyList<object>();
        foreach (var card in cards)
        {
            list.Add(card.HashCode());
        }
        return list;
    }

    //[IgnoredByDeepProfilerAttribute]
    MyList<object> SerializeHashList(MyList<T> cards)
    {
        MyList<object> list = new MyList<object>();
        foreach (var card in cards)
        {
            list.Add(card.HashCode());
        }
        return list;
    }

    //[IgnoredByDeepProfilerAttribute]
    public Dictionary<string, object> ToTrent()
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();

        dict.Add("cards", SerializeCardDictionary(Hashes));
        dict.Add("by_start_step", SerializeHashList(ref list_sorted_by_start_step));
        //dict.Add("by_finish_step", SerializeHashList(ByFinishStep));
        //dict.Add("active_states", SerializeHashList(ActiveStatesList));
        dict.Add(
            "current_by_start_step",
            CurrentByStartStepNode == list_sorted_by_start_step.NoneNode()
                ? "null"
                : CurrentByStartStepNode.Value.HashCode().ToString()
        );
        dict.Add("current_promote_step", CurrentPromoteStep);

        return dict;
    }

    //[IgnoredByDeepProfilerAttribute]
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

    //[IgnoredByDeepProfilerAttribute]
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

    //[IgnoredByDeepProfilerAttribute]
    public static MyList<T> DeserializeHashList(Dictionary<long, T> cards, MyList<object> list)
    {
        MyList<T> result = new MyList<T>();
        foreach (var card in list)
        {
            result.Add(cards[(long)card]);
        }
        return result;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void FromTrent(Dictionary<string, object> dict)
    {
        _hashes = DeserializeCardDictionary(dict["cards"] as Dictionary<string, object>);
        list_sorted_by_start_step = DeserializeHashLinkedList(
            _hashes,
            dict["by_start_step"] as MyList<object>
        );
        //ActiveStatesList = DeserializeHashList(_hashes, dict["active_states"] as MyList<object>);
        //BonusAdded = DeserializeHashList(_hashes, dict["bonus_added"] as MyList<object>);
        CurrentPromoteStep = (long)dict["current_promote_step"];
    }

    //[IgnoredByDeepProfilerAttribute]
    public static ActionList<T> CreateFromTrent(Dictionary<string, object> data)
    {
        var result = new ActionList<T>(true);
        result.FromTrent(data);
        return result;
    }
}
