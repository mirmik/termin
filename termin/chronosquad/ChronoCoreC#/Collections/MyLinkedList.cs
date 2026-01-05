using System;
using System.Collections.Generic;
using System.Security.Permissions;

#if UNITY_64
using Unity.Profiling;
#endif

public class MyLinkedList<T>
    : ICollection<T>,
        System.Collections.ICollection,
        IReadOnlyCollection<T>
{
    // This MyLinkedList is a doubly-Linked circular list.
    internal MyLinkedListNode<T> head;
    internal int count;

    public MyLinkedList() { }

    public MyLinkedList(IEnumerable<T> collection)
    {
        if (collection == null)
        {
            throw new ArgumentNullException("collection");
        }

        foreach (T item in collection)
        {
            AddLast(item);
        }
    }

    public int Count
    {
        get { return count; }
    }

    public MyLinkedListNode<T> First
    {
        get { return head; }
    }

    public MyLinkedListNode<T> Last
    {
        get { return head == null ? null : head.prev; }
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
    public MyLinkedListNode<T> AddAfter(MyLinkedListNode<T> node, T value)
    {
        ValidateNode(node);
        MyLinkedListNode<T> result = new MyLinkedListNode<T>(node.list, value);
        InternalInsertNodeBefore(node.next, result);
        return result;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void AddAfter(MyLinkedListNode<T> node, MyLinkedListNode<T> newNode)
    {
        ValidateNode(node);
        ValidateNewNode(newNode);
        InternalInsertNodeBefore(node.next, newNode);
        newNode.list = this;
    }

    //[IgnoredByDeepProfilerAttribute]
    public MyLinkedListNode<T> AddBefore(MyLinkedListNode<T> node, T value)
    {
        ValidateNode(node);
        MyLinkedListNode<T> result = new MyLinkedListNode<T>(node.list, value);
        InternalInsertNodeBefore(node, result);
        if (node == head)
        {
            head = result;
        }
        return result;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void AddBefore(MyLinkedListNode<T> node, MyLinkedListNode<T> newNode)
    {
        ValidateNode(node);
        ValidateNewNode(newNode);
        InternalInsertNodeBefore(node, newNode);
        newNode.list = this;
        if (node == head)
        {
            head = newNode;
        }
    }

    //[IgnoredByDeepProfilerAttribute]
    public MyLinkedListNode<T> AddFirst(T value)
    {
        MyLinkedListNode<T> result = new MyLinkedListNode<T>(this, value);
        if (head == null)
        {
            InternalInsertNodeToEmptyList(result);
        }
        else
        {
            InternalInsertNodeBefore(head, result);
            head = result;
        }
        return result;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void AddFirst(MyLinkedListNode<T> node)
    {
        ValidateNewNode(node);

        if (head == null)
        {
            InternalInsertNodeToEmptyList(node);
        }
        else
        {
            InternalInsertNodeBefore(head, node);
            head = node;
        }
        node.list = this;
    }

    //[IgnoredByDeepProfilerAttribute]
    public MyLinkedListNode<T> AddLast(T value)
    {
        MyLinkedListNode<T> result = new MyLinkedListNode<T>(this, value);
        if (head == null)
        {
            InternalInsertNodeToEmptyList(result);
        }
        else
        {
            InternalInsertNodeBefore(head, result);
        }
        return result;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void AddLast(MyLinkedListNode<T> node)
    {
        ValidateNewNode(node);

        if (head == null)
        {
            InternalInsertNodeToEmptyList(node);
        }
        else
        {
            InternalInsertNodeBefore(head, node);
        }
        node.list = this;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void Clear()
    {
        MyLinkedListNode<T> current = head;
        while (current != null)
        {
            MyLinkedListNode<T> temp = current;
            current = current.Next; // use Next the instead of "next", otherwise it will loop forever
            temp.Invalidate();
        }

        head = null;
        count = 0;
    }

    //[IgnoredByDeepProfilerAttribute]
    public bool Contains(T value)
    {
        return Find(value) != null;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void CopyTo(T[] array, int index)
    {
        MyLinkedListNode<T> node = head;
        if (node != null)
        {
            do
            {
                array[index++] = node.item;
                node = node.next;
            } while (node != head);
        }
    }

    //[IgnoredByDeepProfilerAttribute]
    public MyLinkedListNode<T> Find(T value)
    {
        MyLinkedListNode<T> node = head;
        EqualityComparer<T> c = EqualityComparer<T>.Default;
        if (node != null)
        {
            if (value != null)
            {
                do
                {
                    if (c.Equals(node.item, value))
                    {
                        return node;
                    }
                    node = node.next;
                } while (node != head);
            }
            else
            {
                do
                {
                    if (node.item == null)
                    {
                        return node;
                    }
                    node = node.next;
                } while (node != head);
            }
        }
        return null;
    }

    //[IgnoredByDeepProfilerAttribute]
    public MyLinkedListNode<T> FindLast(T value)
    {
        if (head == null)
            return null;

        MyLinkedListNode<T> last = head.prev;
        MyLinkedListNode<T> node = last;
        EqualityComparer<T> c = EqualityComparer<T>.Default;
        if (node != null)
        {
            if (value != null)
            {
                do
                {
                    if (c.Equals(node.item, value))
                    {
                        return node;
                    }

                    node = node.prev;
                } while (node != last);
            }
            else
            {
                do
                {
                    if (node.item == null)
                    {
                        return node;
                    }
                    node = node.prev;
                } while (node != last);
            }
        }
        return null;
    }

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
        MyLinkedListNode<T> node = Find(value);
        if (node != null)
        {
            InternalRemoveNode(node);
            return true;
        }
        return false;
    }

    //[IgnoredByDeepProfilerAttribute]
    public void Remove(MyLinkedListNode<T> node)
    {
        ValidateNode(node);
        InternalRemoveNode(node);
    }

    //[IgnoredByDeepProfilerAttribute]
    public void RemoveFirst()
    {
        if (head == null)
        {
            throw new InvalidOperationException("");
        }
        InternalRemoveNode(head);
    }

    //[IgnoredByDeepProfilerAttribute]
    public void RemoveLast()
    {
        if (head == null)
        {
            throw new InvalidOperationException("");
        }
        InternalRemoveNode(head.prev);
    }

    //[IgnoredByDeepProfilerAttribute]
    private void InternalInsertNodeBefore(MyLinkedListNode<T> node, MyLinkedListNode<T> newNode)
    {
        newNode.next = node;
        newNode.prev = node.prev;
        node.prev.next = newNode;
        node.prev = newNode;
        count++;
    }

    //[IgnoredByDeepProfilerAttribute]
    private void InternalInsertNodeToEmptyList(MyLinkedListNode<T> newNode)
    {
        newNode.next = newNode;
        newNode.prev = newNode;
        head = newNode;
        count++;
    }

    //[IgnoredByDeepProfilerAttribute]
    internal void InternalRemoveNode(MyLinkedListNode<T> node)
    {
        if (node.next == node)
        {
            head = null;
        }
        else
        {
            node.next.prev = node.prev;
            node.prev.next = node.next;
            if (head == node)
            {
                head = node.next;
            }
        }
        node.Invalidate();
        count--;
    }

    //[IgnoredByDeepProfilerAttribute]
    internal void ValidateNewNode(MyLinkedListNode<T> node)
    {
        if (node == null)
        {
            throw new ArgumentNullException("node");
        }

        if (node.list != null)
        {
            throw new InvalidOperationException("");
        }
    }

    //[IgnoredByDeepProfilerAttribute]
    internal void ValidateNode(MyLinkedListNode<T> node)
    {
        if (node == null)
        {
            throw new ArgumentNullException("node");
        }

        if (node.list != this)
        {
            throw new InvalidOperationException("");
        }
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
        T[] tArray = array as T[];
        if (tArray != null)
        {
            CopyTo(tArray, index);
        }
        else
        {
            //
            // Catch the obvious case assignment will fail.
            // We can found all possible problems by doing the check though.
            // For example, if the element type of the Array is derived from T,
            // we can't figure out if we can successfully copy the element beforehand.
            //
            Type targetType = array.GetType().GetElementType();
            Type sourceType = typeof(T);

            object[] objects = array as object[];
            MyLinkedListNode<T> node = head;
            try
            {
                if (node != null)
                {
                    do
                    {
                        objects[index++] = node.item;
                        node = node.next;
                    } while (node != head);
                }
            }
            catch (ArrayTypeMismatchException)
            {
                //	throw new ArgumentException(SR.GetString(SR.Invalid_Array_Type));
            }
        }
    }

    //[IgnoredByDeepProfilerAttribute]
    System.Collections.IEnumerator System.Collections.IEnumerable.GetEnumerator()
    {
        return GetEnumerator();
    }

    public struct Enumerator : IEnumerator<T>, System.Collections.IEnumerator
    {
        private MyLinkedList<T> list;
        private MyLinkedListNode<T> node;
        private T current;
        private int index;

        internal Enumerator(MyLinkedList<T> list)
        {
            this.list = list;
            node = list.head;
            current = default(T);
            index = 0;
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
            if (node == null)
            {
                index = list.Count + 1;
                return false;
            }

            ++index;
            current = node.item;
            node = node.next;
            if (node == list.head)
            {
                node = null;
            }
            return true;
        }

        //[IgnoredByDeepProfilerAttribute]
        void System.Collections.IEnumerator.Reset()
        {
            current = default(T);
            node = list.head;
            index = 0;
        }

        //[IgnoredByDeepProfilerAttribute]
        public void Dispose() { }
    }
}

public sealed class MyLinkedListNode<T>
{
    internal MyLinkedList<T> list;
    internal MyLinkedListNode<T> next;
    internal MyLinkedListNode<T> prev;
    internal T item;

    public MyLinkedListNode(T value)
    {
        this.item = value;
    }

    internal MyLinkedListNode(MyLinkedList<T> list, T value)
    {
        this.list = list;
        this.item = value;
    }

    public MyLinkedList<T> MyList
    {
        get { return list; }
    }

    public MyLinkedListNode<T> Next
    {
        get { return next == null || next == list.head ? null : next; }
    }

    public MyLinkedListNode<T> Previous
    {
        get { return prev == null || this == list.head ? null : prev; }
    }

    public T Value
    {
        get { return item; }
        set { item = value; }
    }

    //[IgnoredByDeepProfilerAttribute]
    internal void Invalidate()
    {
        list = null;
        next = null;
        prev = null;
    }
}
