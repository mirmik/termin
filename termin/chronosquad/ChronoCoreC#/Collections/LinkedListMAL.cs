using System;
using System.Collections.Generic;
using System.Security.Permissions;

#if UNITY_64
using Unity.Profiling;
using UnityEngine;
#endif

public struct LinkedListMAL<T>
    : ICollection<T>,
        System.Collections.ICollection,
        IReadOnlyCollection<T> where T : BasicMultipleAction
{
    // This LinkedListMAL is a doubly-Linked circular list.
    internal LinkedListNodeMAL<T> head;
    internal int count;

    // LinkedListNodeMAL<T> minimal_terminator = null;
    // LinkedListNodeMAL<T> maximal_terminator = null;

    public LinkedListMAL(bool stub)
    {
        count = 0;
        head = new LinkedListNodeMAL<T>();
        //AddTerminators();
    }

    public LinkedListMAL(IEnumerable<T> collection)
    {
        count = 0;
        head = new LinkedListNodeMAL<T>();
        //AddTerminators();

        foreach (T item in collection)
        {
            if (item != null)
                AddLast(item);
        }
    }

    // public void AddTerminators()
    // {
    //     Debug.Assert(head == null);
    //     LinkedListNodeMAL<T> maxnode = new LinkedListNodeMAL<T>(null, long.MaxValue, long.MaxValue);
    //     LinkedListNodeMAL<T> minnode = new LinkedListNodeMAL<T>(null, long.MinValue, long.MinValue);
    //     //maxnode.next = null;
    //     maxnode.next = minnode;
    //     maxnode.prev = minnode;
    //     minnode.next = maxnode;
    //     //minnode.prev = null;
    //     minnode.prev = maxnode;
    //     head = minnode;

    //     minimal_terminator = minnode;
    //     maximal_terminator = maxnode;
    // }

    // public LinkedListNodeMAL<T> MinimalTerminator => minimal_terminator;
    // public LinkedListNodeMAL<T> MaximalTerminator => maximal_terminator;

    public LinkedListNodeMAL<T> NoneNode()
    {
        return head;
    }

    public ForkNode<T> AddForkAfter(LinkedListNodeMAL<T> node, long step, bool positive)
    {
        var entrance = new BranchEntrance<T>();
        entrance.StartStep = step;
        entrance.FinishStep = step;

        var fork = new ForkNode<T>();
        fork.branchEntrance = entrance;
        fork.StartStep = step;
        fork.FinishStep = step;
        AddAfter(node, fork);

        if (positive)
        {
            var terminator = new LinkedListNodeMAL<T>(null, long.MaxValue, long.MaxValue);
            terminator.next = null;
            terminator.prev = entrance;
            entrance.next = terminator;
            entrance.prev = fork;
        }
        else
        {
            var terminator = new LinkedListNodeMAL<T>(null, long.MinValue, long.MinValue);
            terminator.next = fork.next;
            terminator.prev = null;
            entrance.next = fork;
            entrance.prev = terminator;
        }

        return fork;
    }

    public int Count
    {
        get { return count; }
    }

    public LinkedListNodeMAL<T> First
    {
        get { return head.next; }
    }

    public LinkedListNodeMAL<T> Last
    {
        get { return head.prev; }
    }

    bool ICollection<T>.IsReadOnly
    {
        get { return false; }
    }

    void ICollection<T>.Add(T value)
    {
        AddLast(value);
    }

    //[IgnoredByDeepProfilerAttribute]
    public LinkedListNodeMAL<T> AddAfter(LinkedListNodeMAL<T> node, T value)
    {
        LinkedListNodeMAL<T> result = new LinkedListNodeMAL<T>(node.head, value);
        InternalInsertNodeAfter(node, result);
        return result;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void AddAfter(LinkedListNodeMAL<T> node, LinkedListNodeMAL<T> newNode)
    {
        InternalInsertNodeAfter(node, newNode);
        //newNode.list = this;
    }

    //[IgnoredByDeepProfilerAttribute]
    public LinkedListNodeMAL<T> AddBefore(LinkedListNodeMAL<T> node, T value)
    {
        LinkedListNodeMAL<T> result = new LinkedListNodeMAL<T>(node.head, value);
        InternalInsertNodeBefore(node, result);
        // if ( node == head) {
        // 	head = result;
        // }
        return result;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void AddBefore(LinkedListNodeMAL<T> node, LinkedListNodeMAL<T> newNode)
    {
        InternalInsertNodeBefore(node, newNode);
        //newNode.list = this;
        // if ( node == head) {
        // 	head = newNode;
        // }
    }

    //[IgnoredByDeepProfilerAttribute]
    public LinkedListNodeMAL<T> AddFirst(T value)
    {
        if (value == null)
        {
            throw new ArgumentNullException("value");
        }
        LinkedListNodeMAL<T> result = new LinkedListNodeMAL<T>(head, value);
        InternalInsertNodeAfter(head, result);
        return result;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void AddFirst(LinkedListNodeMAL<T> node)
    {
        InternalInsertNodeAfter(head, node);
    }

    //[IgnoredByDeepProfilerAttribute]
    public LinkedListNodeMAL<T> AddLast(T value)
    {
        if (value == null)
        {
            throw new ArgumentNullException("value");
        }
        LinkedListNodeMAL<T> result = new LinkedListNodeMAL<T>(head, value);
        InternalInsertNodeBefore(head, result);
        return result;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void AddLast(LinkedListNodeMAL<T> node)
    {
        InternalInsertNodeBefore(head, node);
    }

    //[IgnoredByDeepProfilerAttribute]
    public void Clear()
    {
        LinkedListNodeMAL<T> current = head.next;
        while (current != head)
        {
            LinkedListNodeMAL<T> temp = current;
            current = current.next; // use Next the instead of "next", otherwise it will loop forever
            temp.Invalidate();
        }

        head.next = head;
        head.prev = head;
        count = 0;
    }

    //[IgnoredByDeepProfilerAttribute]
    public bool Contains(T value)
    {
        return false;
        //return Find(value) != null;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void CopyTo(T[] array, int index)
    {
        LinkedListNodeMAL<T> node = head.next;
        if (node != head)
        {
            do
            {
                array[index++] = node.item;
                node = node.next;
            } while (node != head);
        }
    }

    //[IgnoredByDeepProfilerAttribute]
    public LinkedListNodeMAL<T> Find(T value)
    {
        // LinkedListNodeMAL<T> node = head;
        // EqualityComparer<T> c = EqualityComparer<T>.Default;
        // if (node != null) {
        // 	if (value != null) {
        // 		do {
        // 			if (c.Equals(node.item, value)) {
        // 				return node;
        // 			}
        // 			node = node.next;
        // 		} while (node != head);
        // 	}
        // 	else {
        // 		do {
        // 			if (node.item == null) {
        // 				return node;
        // 			}
        // 			node = node.next;
        // 		} while (node != head);
        // 	}
        // }
        return null;
    }

    // //[IgnoredByDeepProfilerAttribute]
    // 	public LinkedListNodeMAL<T> FindLast(T value) {
    // 		if ( head == null) return null;

    // 		LinkedListNodeMAL<T> last = head.prev;
    // 		LinkedListNodeMAL<T> node = last;
    // 		EqualityComparer<T> c = EqualityComparer<T>.Default;
    // 		if (node != null) {
    // 			if (value != null) {
    // 				do {
    // 					if (c.Equals(node.item, value)) {
    // 						return node;
    // 					}

    // 					node = node.prev;
    // 				} while (node != last);
    // 			}
    // 			else {
    // 				do {
    // 					if (node.item == null) {
    // 						return node;
    // 					}
    // 					node = node.prev;
    // 				} while (node != last);
    // 			}
    // 		}
    // 		return null;
    // 	}

    //[IgnoredByDeepProfilerAttribute]
    public Enumerator GetEnumerator()
    {
        return new Enumerator(this);
    }

    IEnumerator<T> IEnumerable<T>.GetEnumerator()
    {
        return GetEnumerator();
    }

    //[IgnoredByDeepProfilerAttribute]
    public bool Remove(T value)
    {
        throw new NotImplementedException();
        //return false;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void Remove(LinkedListNodeMAL<T> node)
    {
        InternalRemoveNode(node);
    }

    //[IgnoredByDeepProfilerAttribute]
    public void RemoveFirst()
    {
        if (head == head.next)
        {
            throw new InvalidOperationException("");
        }
        InternalRemoveNode(head.next);
    }

    //[IgnoredByDeepProfilerAttribute]
    public void RemoveLast()
    {
        if (head == head.prev)
        {
            throw new InvalidOperationException("");
        }
        InternalRemoveNode(head.prev);
    }

    //[IgnoredByDeepProfilerAttribute]
    private void InternalInsertNodeBefore(LinkedListNodeMAL<T> node, LinkedListNodeMAL<T> newNode)
    {
        newNode.next = node;
        newNode.prev = node.prev;
        node.prev.next = newNode;
        node.prev = newNode;
        if (newNode.Value != null)
            count++;
    }

    //[IgnoredByDeepProfilerAttribute]
    private void InternalInsertNodeAfter(LinkedListNodeMAL<T> node, LinkedListNodeMAL<T> newNode)
    {
        newNode.prev = node;
        newNode.next = node.next;
        node.next.prev = newNode;
        node.next = newNode;
        if (newNode.Value != null)
            count++;
    }

    //[IgnoredByDeepProfilerAttribute]
    internal void InternalRemoveNode(LinkedListNodeMAL<T> node)
    {
        if (node == head)
        {
            throw new InvalidOperationException("");
        }

        if (node.prev != null)
            node.prev.next = node.next;

        if (node.next != null)
            node.next.prev = node.prev;

        if (node.Value != null)
            count--;
        node.Invalidate();
    }

    bool System.Collections.ICollection.IsSynchronized
    {
        get { return false; }
    }

    object System.Collections.ICollection.SyncRoot
    {
        get { return null; }
    }

    //[IgnoredByDeepProfilerAttribute]
    void System.Collections.ICollection.CopyTo(Array array, int index)
    {
        // T[] tArray = array as T[];
        // if (tArray != null) {
        // 	CopyTo(tArray, index);
        // }
        // else {
        // 	//
        // 	// Catch the obvious case assignment will fail.
        // 	// We can found all possible problems by doing the check though.
        // 	// For example, if the element type of the Array is derived from T,
        // 	// we can't figure out if we can successfully copy the element beforehand.
        // 	//
        // 	Type targetType = array.GetType().GetElementType();
        // 	Type sourceType = typeof(T);


        // 	object[] objects = array as object[];
        // 		LinkedListNodeMAL<T> node = head;
        // 	try {
        // 		if (node != null) {
        // 			do {
        // 				objects[index++] = node.item;
        // 				node = node.next;
        // 			} while (node != head);
        // 		}
        // 	}
        // 	catch(ArrayTypeMismatchException) {
        // 	//	throw new ArgumentException(SR.GetString(SR.Invalid_Array_Type));
        // 	}
        // }
        throw new NotImplementedException();
    }

    //[IgnoredByDeepProfilerAttribute]
    System.Collections.IEnumerator System.Collections.IEnumerable.GetEnumerator()
    {
        return GetEnumerator();
    }

    public struct Enumerator : IEnumerator<T>, System.Collections.IEnumerator
    {
        private LinkedListMAL<T> list;
        private LinkedListNodeMAL<T> node;
        private T current;

        //private int index;

        internal Enumerator(LinkedListMAL<T> list)
        {
            this.list = list;
            node = list.head;
            current = default(T);
        }

        public T Current
        {
            get { return current; }
        }

        object System.Collections.IEnumerator.Current
        {
            get { return current; }
        }

        //[IgnoredByDeepProfilerAttribute]
        public bool MoveNext()
        {
            if (node.next != list.head)
            {
                node = node.next;
                current = node.item;
                //index++;
                return true;
            }
            else
            {
                current = default(T);
                //index = list.Count + 1;
                return false;
            }
        }

        //[IgnoredByDeepProfilerAttribute]
        void System.Collections.IEnumerator.Reset()
        {
            current = default(T);
            node = list.head;
            //index = 0;
        }

        //[IgnoredByDeepProfilerAttribute]
        public void Dispose() { }
    }
}

// public class Terminator : BasicMultipleAction
// {
// 	public Terminator() : base(long.MinValue, long.MaxValue) {}
// 	public Terminator(long s, long f) : base(s, f) {}
// 	public override long HashCode() { return 0; }
// 	public override string ToString() { return "Terminator(" + StartStep.ToString() + "," + FinishStep.ToString() + ")"; }
// }

public class LinkedListNodeMAL<T> where T : BasicMultipleAction
{
    //internal LinkedListMAL<T> list;
    internal LinkedListNodeMAL<T> head;
    internal LinkedListNodeMAL<T> next;
    internal LinkedListNodeMAL<T> prev;
    internal T item;

    public long StartStep;
    public long FinishStep;

    public LinkedListNodeMAL(T value)
    {
        this.item = value;
        StartStep = value.StartStep;
        FinishStep = value.FinishStep;
    }

    public LinkedListNodeMAL(T item, long StartStep, long FinishStep)
    {
        this.item = item;
        this.StartStep = StartStep;
        this.FinishStep = FinishStep;
    }

    internal LinkedListNodeMAL(LinkedListNodeMAL<T> list, T value)
    {
        //this.list = list;
        this.head = list;
        this.item = value;
        StartStep = value.StartStep;
        FinishStep = value.FinishStep;
    }

    internal LinkedListNodeMAL(LinkedListNodeMAL<T> list)
    {
        this.head = list;
        this.next = list;
        this.prev = list;
        this.item = null;
    }

    internal LinkedListNodeMAL()
    {
        this.head = this;
        this.next = this;
        this.prev = this;
        this.item = null;
    }

    internal void Init(LinkedListNodeMAL<T> list)
    {
        this.head = list;
        this.next = list;
        this.prev = list;
        this.item = null;
    }

    public LinkedListNodeMAL<T> StepForwardFork()
    {
        var fork_node = next;
        return fork_node;
    }

    public LinkedListNodeMAL<T> StepBackwardFork()
    {
        var fork_node = this;
        return fork_node.prev;
    }

    public LinkedListNodeMAL<T> StepForwardForkAlternate()
    {
        var fork_node = next;
        return (fork_node as ForkNode<T>).branchEntrance;
    }

    public LinkedListNodeMAL<T> StepBackwardForkAlternate()
    {
        var entrance = this as BranchEntrance<T>;
        var fork_node = entrance.prev;
        return fork_node.prev;
    }

    // public LinkedListMAL<T> MyList {
    // 	get { return list;}
    // }

    public LinkedListNodeMAL<T> Next
    {
        get { return next; }
    }

    public LinkedListNodeMAL<T> Previous
    {
        get { return prev; }
    }

    public T Value
    {
        get { return item; }
        set { item = value; }
    }

    //[IgnoredByDeepProfilerAttribute]
    internal void Invalidate()
    {
        head = null;
        next = null;
        prev = null;
    }
}

// public class BranchNode<T> : LinkedListNodeMAL<T> where T : BasicMultipleAction
// {

// }

// public class BranchEntrance<T> : LinkedListNodeMAL<T> where T : BasicMultipleAction
// {

// }

public class ForkNode<T> : LinkedListNodeMAL<T> where T : BasicMultipleAction
{
    public BranchEntrance<T> branchEntrance;
    public ObjectId fork_id;
}

public class BranchEntrance<T> : LinkedListNodeMAL<T> where T : BasicMultipleAction { }
