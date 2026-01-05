using System;
using System.Runtime;
using System.Collections.ObjectModel;
using System.Collections.Generic;
using System.Collections;
using UnityEngine;
using System.Diagnostics;

using Object = System.Object;

#if UNITY_64
using Unity.Profiling;
#endif

public class FunctorComparer<T> : IComparer<T>
{
    Comparison<T> comparison;

    public FunctorComparer(Comparison<T> comparison)
    {
        this.comparison = comparison;
    }

    public int Compare(T x, T y)
    {
        return comparison(x, y);
    }
}

// Implements a variable-size MyList that uses an array of objects to store the
// elements. A MyList has a capacity, which is the allocated length
// of the internal array. As elements are added to a MyList, the capacity
// of the MyList is automatically increased as required by reallocating the
// internal array.
//
public class MyList<T> : IList<T>, System.Collections.IList, IReadOnlyList<T>
{
    private const int _defaultCapacity = 4;
    private T[] _items;
    private int _size = 0;
    static readonly T[] _emptyArray = new T[0];

    public MyList()
    {
        //PrintStackTrace();
        _items = _emptyArray;
    }

    public MyList(int capacity)
    {
        if (capacity == 0)
            _items = _emptyArray;
        else
            _items = new T[capacity];
    }

    void PrintStackTrace(string prefix)
    {
        StackTrace stackTrace = new StackTrace();
        UnityEngine.Debug.Log(prefix + stackTrace.ToString());
    }

    // Constructs a MyList, copying the contents of the given collection. The
    // size and capacity of the new list will both be equal to the size of the
    // given collection.
    //
    public MyList(IEnumerable<T> collection)
    {
        //PrintStackTrace();
        ICollection<T> c = collection as ICollection<T>;
        if (c != null)
        {
            int count = c.Count;
            if (count == 0)
            {
                _items = _emptyArray;
            }
            else
            {
                _items = new T[count];
                c.CopyTo(_items, 0);
                _size = count;
            }
        }
        else
        {
            _size = 0;
            _items = _emptyArray;
            // This enumerable could be empty.  Let Add allocate a new array, if needed.
            // Note it will also go to _defaultCapacity first, not 1, then 2, etc.

            using (IEnumerator<T> en = collection.GetEnumerator())
            {
                while (en.MoveNext())
                {
                    Add(en.Current);
                }
            }
        }
    }

    // Gets and sets the capacity of this list.  The capacity is the size of
    // the internal array used to hold items.  When set, the internal
    // array of the list is reallocated to the given capacity.
    //
    public int Capacity
    {
        get { return _items.Length; }
        set
        {
            if (value != _items.Length)
            {
                if (value > 0)
                {
                    T[] newItems = new T[value];
                    if (_size > 0)
                    {
                        Array.Copy(_items, 0, newItems, 0, _size);
                    }
                    _items = newItems;
                }
                else
                {
                    _items = _emptyArray;
                }
            }
        }
    }

    // Read-only property describing how many elements are in the MyList.
    public int Count
    {
        get { return _size; }
    }

    bool System.Collections.IList.IsFixedSize
    {
        get { return false; }
    }

    // Is this MyList read-only?
    bool ICollection<T>.IsReadOnly
    {
        get { return false; }
    }

    bool System.Collections.IList.IsReadOnly
    {
        get { return false; }
    }

    // Is this MyList synchronized (thread-safe)?
    bool System.Collections.ICollection.IsSynchronized
    {
        get { return false; }
    }

    // Synchronization root for this object.
    Object System.Collections.ICollection.SyncRoot
    {
        get { return null; }
    }

    // Sets or Gets the element at the given index.
    //
    public T this[int index]
    {
        get { return _items[index]; }
        set { _items[index] = value; }
    }

    public T Last
    {
        ////[IgnoredByDeepProfilerAttribute]
        get { return _items[_size - 1]; }
    }

    ////[IgnoredByDeepProfilerAttribute]
    private static bool IsCompatibleObject(object value)
    {
        // Non-null values are fine.  Only accept nulls if T is a class or Nullable<U>.
        // Note that default(T) is not equal to null for value types except when T is Nullable<U>.
        return ((value is T) || (value == null && default(T) == null));
    }

    Object System.Collections.IList.this[int index]
    {
        get { return this[index]; }
        set { this[index] = (T)value; }
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Adds the given object to the end of this list. The size of the list is
    // increased by one. If required, the capacity of the list is doubled
    // before adding the new element.
    //
    public void Add(T item)
    {
        if (_size == _items.Length)
            EnsureCapacity(_size + 1);
        _items[_size++] = item;
    }

    ////[IgnoredByDeepProfilerAttribute]
    int System.Collections.IList.Add(Object item)
    {
        Add((T)item);
        return Count - 1;
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Adds the elements of the given collection to the end of this list. If
    // required, the capacity of the list is increased to twice the previous
    // capacity or the new size, whichever is larger.
    //
    public void AddRange(IEnumerable<T> collection)
    {
        InsertRange(_size, collection);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public ReadOnlyCollection<T> AsReadOnly()
    {
        return new ReadOnlyCollection<T>(this);
    }

    // Searches a section of the list for a given element using a binary search
    // algorithm. Elements of the list are compared to the search value using
    // the given IComparer interface. If comparer is null, elements of
    // the list are compared to the search value using the IComparable
    // interface, which in that case must be implemented by all elements of the
    // list and the given search value. This method assumes that the given
    // section of the list is already sorted; if this is not the case, the
    // result will be incorrect.
    //
    // The method returns the index of the given value in the list. If the
    // list does not contain the given value, the method returns a negative
    // integer. The bitwise complement operator (~) can be applied to a
    // negative result to produce the index of the first element (if any) that
    // is larger than the given search value. This is also the index at which
    // the search value should be inserted into the list in order for the list
    // to remain sorted.
    //
    // The method uses the Array.BinarySearch method to perform the
    // search.
    //
    public int BinarySearch(int index, int count, T item, IComparer<T> comparer)
    {
        return Array.BinarySearch<T>(_items, index, count, item, comparer);
    }

    public int BinarySearch(T item)
    {
        return BinarySearch(0, Count, item, null);
    }

    public int BinarySearch(T item, IComparer<T> comparer)
    {
        return BinarySearch(0, Count, item, comparer);
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Clears the contents of MyList.
    public void Clear()
    {
        if (_size > 0)
        {
            Array.Clear(_items, 0, _size); // Don't need to doc this but we clear the elements so that the gc can reclaim the references.
            _size = 0;
        }
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Contains returns true if the specified element is in the MyList.
    // It does a linear, O(n) search.  Equality is determined by calling
    // item.Equals().
    //
    public bool Contains(T item)
    {
        if ((Object)item == null)
        {
            for (int i = 0; i < _size; i++)
                if ((Object)_items[i] == null)
                    return true;
            return false;
        }
        else
        {
            EqualityComparer<T> c = EqualityComparer<T>.Default;
            for (int i = 0; i < _size; i++)
            {
                if (c.Equals(_items[i], item))
                    return true;
            }
            return false;
        }
    }

    ////[IgnoredByDeepProfilerAttribute]
    bool System.Collections.IList.Contains(Object item)
    {
        if (IsCompatibleObject(item))
        {
            return Contains((T)item);
        }
        return false;
    }

    public MyList<TOutput> ConvertAll<TOutput>(Converter<T, TOutput> converter)
    {
        MyList<TOutput> list = new MyList<TOutput>(_size);
        for (int i = 0; i < _size; i++)
        {
            list._items[i] = converter(_items[i]);
        }
        list._size = _size;
        return list;
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Copies this MyList into array, which must be of a
    // compatible array type.
    //
    public void CopyTo(T[] array)
    {
        CopyTo(array, 0);
    }

    // Copies this MyList into array, which must be of a
    // compatible array type.
    //
    void System.Collections.ICollection.CopyTo(Array array, int arrayIndex)
    {
        Array.Copy(_items, 0, array, arrayIndex, _size);
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Copies a section of this list to the given array at the given index.
    //
    // The method uses the Array.Copy method to copy the elements.
    //
    public void CopyTo(int index, T[] array, int arrayIndex, int count)
    {
        // Delegate rest of error checking to Array.Copy.
        Array.Copy(_items, index, array, arrayIndex, count);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public void CopyTo(T[] array, int arrayIndex)
    {
        // Delegate rest of error checking to Array.Copy.
        Array.Copy(_items, 0, array, arrayIndex, _size);
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Ensures that the capacity of this list is at least the given minimum
    // value. If the currect capacity of the list is less than min, the
    // capacity is increased to twice the current capacity or to min,
    // whichever is larger.
    private void EnsureCapacity(int min)
    {
        if (_items.Length < min)
        {
            int newCapacity = _items.Length == 0 ? _defaultCapacity : _items.Length * 2;
            if (newCapacity < min)
                newCapacity = min;
            Capacity = newCapacity;

#if UNITY_64
            //PrintStackTrace("EnsureCapacity ->");
#endif
        }
    }

    ////[IgnoredByDeepProfilerAttribute]
    public bool Exists(Predicate<T> match)
    {
        return FindIndex(match) != -1;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public T Find(Predicate<T> match)
    {
        for (int i = 0; i < _size; i++)
        {
            if (match(_items[i]))
            {
                return _items[i];
            }
        }
        return default(T);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public MyList<T> FindAll(Predicate<T> match)
    {
        MyList<T> list = new MyList<T>();
        for (int i = 0; i < _size; i++)
        {
            if (match(_items[i]))
            {
                list.Add(_items[i]);
            }
        }
        return list;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public int FindIndex(Predicate<T> match)
    {
        return FindIndex(0, _size, match);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public int FindIndex(int startIndex, Predicate<T> match)
    {
        return FindIndex(startIndex, _size - startIndex, match);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public int FindIndex(int startIndex, int count, Predicate<T> match)
    {
        int endIndex = startIndex + count;
        for (int i = startIndex; i < endIndex; i++)
        {
            if (match(_items[i]))
                return i;
        }
        return -1;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public T FindLast(Predicate<T> match)
    {
        for (int i = _size - 1; i >= 0; i--)
        {
            if (match(_items[i]))
            {
                return _items[i];
            }
        }
        return default(T);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public int FindLastIndex(Predicate<T> match)
    {
        return FindLastIndex(_size - 1, _size, match);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public int FindLastIndex(int startIndex, Predicate<T> match)
    {
        return FindLastIndex(startIndex, startIndex + 1, match);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public int FindLastIndex(int startIndex, int count, Predicate<T> match)
    {
        int endIndex = startIndex - count;
        for (int i = startIndex; i > endIndex; i--)
        {
            if (match(_items[i]))
            {
                return i;
            }
        }
        return -1;
    }

    ////[IgnoredByDeepProfilerAttribute]
    public void ForEach(Action<T> action)
    {
        for (int i = 0; i < _size; i++)
        {
            action(_items[i]);
        }
    }

    public void ReSize(int newSize)
    {
        if (_size == newSize)
            return;

        if (newSize < _size)
        {
            Array.Clear(_items, newSize, _size - newSize);
        }
        else if (newSize > _size)
        {
            if (newSize > _items.Length)
                EnsureCapacity(newSize);
        }
        _size = newSize;
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Returns an enumerator for this list with the given
    // permission for removal of elements. If modifications made to the list
    // while an enumeration is in progress, the MoveNext and
    // GetObject methods of the enumerator will throw an exception.
    //
    public Enumerator GetEnumerator()
    {
        return new Enumerator(this);
    }

    ////[IgnoredByDeepProfilerAttribute]
    /// <internalonly/>
    IEnumerator<T> IEnumerable<T>.GetEnumerator()
    {
#if UNITY_64
        UnityEngine.Debug.Assert(
            false,
            "This function is not expected to be called as we implement the non-generic IEnumerable interface"
        );
#endif
        return new Enumerator(this);
    }

    ////[IgnoredByDeepProfilerAttribute]
    System.Collections.IEnumerator System.Collections.IEnumerable.GetEnumerator()
    {
#if UNITY_64
        UnityEngine.Debug.Assert(
            false,
            "This function is not expected to be called as we implement the non-generic IEnumerable interface"
        );
#endif
        return new Enumerator(this);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public MyList<T> GetRange(int index, int count)
    {
        MyList<T> list = new MyList<T>(count);
        Array.Copy(_items, index, list._items, 0, count);
        list._size = count;
        return list;
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Returns the index of the first occurrence of a given value in a range of
    // this list. The list is searched forwards from beginning to end.
    // The elements of the list are compared to the given value using the
    // Object.Equals method.
    //
    // This method uses the Array.IndexOf method to perform the
    // search.
    //
    public int IndexOf(T item)
    {
        return Array.IndexOf(_items, item, 0, _size);
    }

    ////[IgnoredByDeepProfilerAttribute]
    int System.Collections.IList.IndexOf(Object item)
    {
        if (IsCompatibleObject(item))
        {
            return IndexOf((T)item);
        }
        return -1;
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Returns the index of the first occurrence of a given value in a range of
    // this list. The list is searched forwards, starting at index
    // index and ending at count number of elements. The
    // elements of the list are compared to the given value using the
    // Object.Equals method.
    //
    // This method uses the Array.IndexOf method to perform the
    // search.
    //
    public int IndexOf(T item, int index)
    {
        return Array.IndexOf(_items, item, index, _size - index);
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Returns the index of the first occurrence of a given value in a range of
    // this list. The list is searched forwards, starting at index
    // index and upto count number of elements. The
    // elements of the list are compared to the given value using the
    // Object.Equals method.
    //
    // This method uses the Array.IndexOf method to perform the
    // search.
    //
    public int IndexOf(T item, int index, int count)
    {
        return Array.IndexOf(_items, item, index, count);
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Inserts an element into this list at a given index. The size of the list
    // is increased by one. If required, the capacity of the list is doubled
    // before inserting the new element.
    //
    public void Insert(int index, T item)
    {
        if (_size == _items.Length)
            EnsureCapacity(_size + 1);
        if (index < _size)
        {
            Array.Copy(_items, index, _items, index + 1, _size - index);
        }
        _items[index] = item;
        _size++;
    }

    void System.Collections.IList.Insert(int index, Object item)
    {
        Insert(index, (T)item);
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Inserts the elements of the given collection at a given index. If
    // required, the capacity of the list is increased to twice the previous
    // capacity or the new size, whichever is larger.  Ranges may be added
    // to the end of the list by setting index to the MyList's size.
    //
    public void InsertRange(int index, IEnumerable<T> collection)
    {
        ICollection<T> c = collection as ICollection<T>;
        if (c != null)
        { // if collection is ICollection<T>
            int count = c.Count;
            if (count > 0)
            {
                EnsureCapacity(_size + count);
                if (index < _size)
                {
                    Array.Copy(_items, index, _items, index + count, _size - index);
                }

                // If we're inserting a MyList into itself, we want to be able to deal with that.
                if (this == c)
                {
                    // Copy first part of _items to insert location
                    Array.Copy(_items, 0, _items, index, index);
                    // Copy last part of _items back to inserted location
                    Array.Copy(_items, index + count, _items, index * 2, _size - index);
                }
                else
                {
                    T[] itemsToInsert = new T[count];
                    c.CopyTo(itemsToInsert, 0);
                    itemsToInsert.CopyTo(_items, index);
                }
                _size += count;
            }
        }
        else
        {
            using (IEnumerator<T> en = collection.GetEnumerator())
            {
                while (en.MoveNext())
                {
                    Insert(index++, en.Current);
                }
            }
        }
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Returns the index of the last occurrence of a given value in a range of
    // this list. The list is searched backwards, starting at the end
    // and ending at the first element in the list. The elements of the list
    // are compared to the given value using the Object.Equals method.
    //
    // This method uses the Array.LastIndexOf method to perform the
    // search.
    //
    public int LastIndexOf(T item)
    {
        if (_size == 0)
        { // Special case for empty list
            return -1;
        }
        else
        {
            return LastIndexOf(item, _size - 1, _size);
        }
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Returns the index of the last occurrence of a given value in a range of
    // this list. The list is searched backwards, starting at index
    // index and ending at the first element in the list. The
    // elements of the list are compared to the given value using the
    // Object.Equals method.
    //
    // This method uses the Array.LastIndexOf method to perform the
    // search.
    //
    public int LastIndexOf(T item, int index)
    {
        return LastIndexOf(item, index, index + 1);
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Returns the index of the last occurrence of a given value in a range of
    // this list. The list is searched backwards, starting at index
    // index and upto count elements. The elements of
    // the list are compared to the given value using the Object.Equals
    // method.
    //
    // This method uses the Array.LastIndexOf method to perform the
    // search.
    //
    public int LastIndexOf(T item, int index, int count)
    {
        if (_size == 0)
        { // Special case for empty list
            return -1;
        }
        return Array.LastIndexOf(_items, item, index, count);
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Removes the element at the given index. The size of the list is
    // decreased by one.
    //
    public bool Remove(T item)
    {
        int index = IndexOf(item);
        if (index >= 0)
        {
            RemoveAt(index);
            return true;
        }

        return false;
    }

    void System.Collections.IList.Remove(Object item)
    {
        if (IsCompatibleObject(item))
        {
            Remove((T)item);
        }
    }

    ////[IgnoredByDeepProfilerAttribute]
    // This method removes all items which matches the predicate.
    // The complexity is O(n).
    public int RemoveAll(Predicate<T> match)
    {
        int freeIndex = 0; // the first free slot in items array

        // Find the first item which needs to be removed.
        while (freeIndex < _size && !match(_items[freeIndex]))
            freeIndex++;
        if (freeIndex >= _size)
            return 0;

        int current = freeIndex + 1;
        while (current < _size)
        {
            // Find the first item which needs to be kept.
            while (current < _size && match(_items[current]))
                current++;

            if (current < _size)
            {
                // copy item to the free slot.
                _items[freeIndex++] = _items[current++];
            }
        }

        Array.Clear(_items, freeIndex, _size - freeIndex);
        int result = _size - freeIndex;
        _size = freeIndex;
        return result;
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Removes the element at the given index. The size of the list is
    // decreased by one.
    //
    public void RemoveAt(int index)
    {
        _size--;
        if (index < _size)
        {
            Array.Copy(_items, index + 1, _items, index, _size - index);
        }
        _items[_size] = default(T);
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Removes a range of elements from this list.
    //
    public void RemoveRange(int index, int count)
    {
        if (count > 0)
        {
            int i = _size;
            _size -= count;
            if (index < _size)
            {
                Array.Copy(_items, index + count, _items, index, _size - index);
            }
            Array.Clear(_items, _size, count);
        }
    }

    // Reverses the elements in this list.
    public void Reverse()
    {
        Reverse(0, Count);
    }

    // Reverses the elements in a range of this list. Following a call to this
    // method, an element in the range given by index and count
    // which was previously located at index i will now be located at
    // index index + (index + count - i - 1).
    //
    // This method uses the Array.Reverse method to reverse the
    // elements.
    //
    public void Reverse(int index, int count)
    {
        Array.Reverse(_items, index, count);
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Sorts the elements in this list.  Uses the default comparer and
    // Array.Sort.
    public void Sort()
    {
        Sort(0, Count, null);
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Sorts the elements in this list.  Uses Array.Sort with the
    // provided comparer.
    public void Sort(IComparer<T> comparer)
    {
        Sort(0, Count, comparer);
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Sorts the elements in a section of this list. The sort compares the
    // elements to each other using the given IComparer interface. If
    // comparer is null, the elements are compared to each other using
    // the IComparable interface, which in that case must be implemented by all
    // elements of the list.
    //
    // This method uses the Array.Sort method to sort the elements.
    //
    public void Sort(int index, int count, IComparer<T> comparer)
    {
        Array.Sort<T>(_items, index, count, comparer);
    }

    ////[IgnoredByDeepProfilerAttribute]
    public void Sort(Comparison<T> comparison)
    {
        if (_size > 0)
        {
            IComparer<T> comparer = new FunctorComparer<T>(comparison);
            Array.Sort(_items, 0, _size, comparer);
        }
    }

    // public void Sort(Comparison<T> comparison) {
    //     if( _size > 0) {
    //         //IComparer<T> comparer = new Array.FunctorComparer<T>(comparison);
    //         //Array.Sort(_items, 0, _size, comparer);
    //         Array.Sort(_items, 0, _size, comparison);
    //     }
    // }

    ////[IgnoredByDeepProfilerAttribute]
    // ToArray returns a new Object array containing the contents of the MyList.
    // This requires copying the MyList, which is an O(n) operation.
    public T[] ToArray()
    {
        T[] array = new T[_size];
        Array.Copy(_items, 0, array, 0, _size);
        return array;
    }

    ////[IgnoredByDeepProfilerAttribute]
    // Sets the capacity of this list to the size of the list. This method can
    // be used to minimize a list's memory overhead once it is known that no
    // new elements will be added to the list. To completely clear a list and
    // release all memory referenced by the list, execute the following
    // statements:
    //
    // list.Clear();
    // list.TrimExcess();
    //
    public void TrimExcess()
    {
        int threshold = (int)(((double)_items.Length) * 0.9);
        if (_size < threshold)
        {
            Capacity = _size;
        }
    }

    public bool TrueForAll(Predicate<T> match)
    {
        for (int i = 0; i < _size; i++)
        {
            if (!match(_items[i]))
            {
                return false;
            }
        }
        return true;
    }

    [Serializable]
    public struct Enumerator : IEnumerator<T>, System.Collections.IEnumerator
    {
        private MyList<T> list;
        private int index;
        private T current;

        internal Enumerator(MyList<T> list)
        {
            this.list = list;
            index = 0;
            current = default(T);
        }

        ////[IgnoredByDeepProfilerAttribute]
        public void Dispose() { }

        ////[IgnoredByDeepProfilerAttribute]
        public bool MoveNext()
        {
            if ((uint)index < (uint)list._size)
            {
                current = list._items[index];
                index++;
                return true;
            }
            return MoveNextRare();
        }

        ////[IgnoredByDeepProfilerAttribute]
        private bool MoveNextRare()
        {
            index = list._size + 1;
            current = default(T);
            return false;
        }

        public T Current
        {
            get { return current; }
        }

        Object System.Collections.IEnumerator.Current
        {
            get { return Current; }
        }

        void System.Collections.IEnumerator.Reset()
        {
            index = 0;
            current = default(T);
        }
    }
}
