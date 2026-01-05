using System;
using System.Collections;
using System.Diagnostics;
using System.Collections.Generic;

internal static partial class HashHelpers
{
    public const uint HashCollisionThreshold = 100;

    // This is the maximum prime smaller than Array.MaxLength.
    public const int MaxPrimeArrayLength = 0x7FFFFFC3;

    public const int HashPrime = 101;

    // Table of prime numbers to use as hash table sizes.
    // A typical resize algorithm would pick the smallest prime number in this array
    // that is larger than twice the previous capacity.
    // Suppose our Hashtable currently has capacity x and enough elements are added
    // such that a resize needs to occur. Resizing first computes 2x then finds the
    // first prime in the table greater than 2x, i.e. if primes are ordered
    // p_1, p_2, ..., p_i, ..., it finds p_n such that p_n-1 < 2x < p_n.
    // Doubling is important for preserving the asymptotic complexity of the
    // hashtable operations such as add.  Having a prime guarantees that double
    // hashing does not lead to infinite loops.  IE, your hash function will be
    // h1(key) + i*h2(key), 0 <= i < size.  h2 and the size must be relatively prime.
    // We prefer the low computation costs of higher prime numbers over the increased
    // memory allocation of a fixed prime number i.e. when right sizing a HashSet.
    internal static List<int> Primes = new List<int>()
    {
        3,
        7,
        11,
        17,
        23,
        29,
        37,
        47,
        59,
        71,
        89,
        107,
        131,
        163,
        197,
        239,
        293,
        353,
        431,
        521,
        631,
        761,
        919,
        1103,
        1327,
        1597,
        1931,
        2333,
        2801,
        3371,
        4049,
        4861,
        5839,
        7013,
        8419,
        10103,
        12143,
        14591,
        17519,
        21023,
        25229,
        30293,
        36353,
        43627,
        52361,
        62851,
        75431,
        90523,
        108631,
        130363,
        156437,
        187751,
        225307,
        270371,
        324449,
        389357,
        467237,
        560689,
        672827,
        807403,
        968897,
        1162687,
        1395263,
        1674319,
        2009191,
        2411033,
        2893249,
        3471899,
        4166287,
        4999559,
        5999471,
        7199369
    };

    public static bool IsPrime(int candidate)
    {
        if ((candidate & 1) != 0)
        {
            int limit = (int)Math.Sqrt(candidate);
            for (int divisor = 3; divisor <= limit; divisor += 2)
            {
                if ((candidate % divisor) == 0)
                    return false;
            }
            return true;
        }
        return candidate == 2;
    }

    public static int GetPrime(int min)
    {
        foreach (int prime in Primes)
        {
            if (prime >= min)
                return prime;
        }

        // Outside of our predefined table. Compute the hard way.
        for (int i = (min | 1); i < int.MaxValue; i += 2)
        {
            if (IsPrime(i) && ((i - 1) % HashPrime != 0))
                return i;
        }
        return min;
    }

    // Returns size of hashtable to grow to.
    public static int ExpandPrime(int oldSize)
    {
        int newSize = 2 * oldSize;

        // Allow the hashtables to grow to maximum possible size (~2G elements) before encountering capacity overflow.
        // Note that this check works even when _items.Length overflowed thanks to the (uint) cast
        if ((uint)newSize > MaxPrimeArrayLength && MaxPrimeArrayLength > oldSize)
        {
            return MaxPrimeArrayLength;
        }

        return GetPrime(newSize);
    }

    /// <summary>Returns approximate reciprocal of the divisor: ceil(2**64 / divisor).</summary>
    /// <remarks>This should only be used on 64-bit.</remarks>
    public static ulong GetFastModMultiplier(uint divisor) => ulong.MaxValue / divisor + 1;

    /// <summary>Performs a mod operation using the multiplier pre-computed with <see cref="GetFastModMultiplier"/>.</summary>
    /// <remarks>This should only be used on 64-bit.</remarks>
    public static uint FastMod(uint value, uint divisor, ulong multiplier)
    {
        uint highbits = (uint)(((((multiplier * value) >> 32) + 1) * divisor) >> 32);
        return highbits;
    }
}

public class MyDictionary<TKey, TValue>
    : IDictionary<TKey, TValue>,
        IDictionary,
        IReadOnlyDictionary<TKey, TValue>
{
    private struct Entry
    {
        public int hashCode; // Lower 31 bits of hash code, -1 if unused
        public int next; // Index of next entry, -1 if last
        public TKey key; // Key of entry
        public TValue value; // Value of entry
    }

    private int[] buckets;
    private Entry[] entries;
    private int count;
    private int freeList;
    private int freeCount;
    private IEqualityComparer<TKey> comparer;
    private KeyCollection keys;
    private ValueCollection values;

    public MyDictionary() : this(0, null) { }

    public MyDictionary(int capacity) : this(capacity, null) { }

    public MyDictionary(IEqualityComparer<TKey> comparer) : this(0, comparer) { }

    public MyDictionary(int capacity, IEqualityComparer<TKey> comparer)
    {
        if (capacity > 0)
            Initialize(capacity);
        this.comparer = comparer ?? EqualityComparer<TKey>.Default;

#if FEATURE_CORECLR
        if (
            HashHelpers.s_UseRandomizedStringHashing && comparer == EqualityComparer<string>.Default
        )
        {
            this.comparer = (IEqualityComparer<TKey>)NonRandomizedStringEqualityComparer.Default;
        }
#endif // FEATURE_CORECLR
    }

    public MyDictionary(IDictionary<TKey, TValue> dictionary) : this(dictionary, null) { }

    public MyDictionary(IDictionary<TKey, TValue> dictionary, IEqualityComparer<TKey> comparer)
        : this(dictionary != null ? dictionary.Count : 0, comparer)
    {
        foreach (KeyValuePair<TKey, TValue> pair in dictionary)
        {
            Add(pair.Key, pair.Value);
        }
    }

    public IEqualityComparer<TKey> Comparer
    {
        get { return comparer; }
    }

    public override string ToString()
    {
        string result = "{";
        foreach (var pair in this)
        {
            result += pair.Key.ToString() + ": " + pair.Value.ToString() + ", ";
        }
        result += "}";
        return result;
    }

    public int Count
    {
        get { return count - freeCount; }
    }

    public KeyCollection Keys
    {
        get
        {
            if (keys == null)
                keys = new KeyCollection(this);
            return keys;
        }
    }

    ICollection<TKey> IDictionary<TKey, TValue>.Keys
    {
        get
        {
            if (keys == null)
                keys = new KeyCollection(this);
            return keys;
        }
    }

    IEnumerable<TKey> IReadOnlyDictionary<TKey, TValue>.Keys
    {
        get
        {
            if (keys == null)
                keys = new KeyCollection(this);
            return keys;
        }
    }

    public ValueCollection Values
    {
        get
        {
            if (values == null)
                values = new ValueCollection(this);
            return values;
        }
    }

    ICollection<TValue> IDictionary<TKey, TValue>.Values
    {
        get
        {
            if (values == null)
                values = new ValueCollection(this);
            return values;
        }
    }

    IEnumerable<TValue> IReadOnlyDictionary<TKey, TValue>.Values
    {
        get
        {
            if (values == null)
                values = new ValueCollection(this);
            return values;
        }
    }

    public TValue this[TKey key]
    {
        get
        {
            int i = FindEntry(key);
            if (i >= 0)
                return entries[i].value;
            return default(TValue);
        }
        set { Insert(key, value, false); }
    }

    public void Add(TKey key, TValue value)
    {
        Insert(key, value, true);
    }

    void ICollection<KeyValuePair<TKey, TValue>>.Add(KeyValuePair<TKey, TValue> keyValuePair)
    {
        Add(keyValuePair.Key, keyValuePair.Value);
    }

    bool ICollection<KeyValuePair<TKey, TValue>>.Contains(KeyValuePair<TKey, TValue> keyValuePair)
    {
        int i = FindEntry(keyValuePair.Key);
        if (i >= 0 && EqualityComparer<TValue>.Default.Equals(entries[i].value, keyValuePair.Value))
        {
            return true;
        }
        return false;
    }

    bool ICollection<KeyValuePair<TKey, TValue>>.Remove(KeyValuePair<TKey, TValue> keyValuePair)
    {
        int i = FindEntry(keyValuePair.Key);
        if (i >= 0 && EqualityComparer<TValue>.Default.Equals(entries[i].value, keyValuePair.Value))
        {
            Remove(keyValuePair.Key);
            return true;
        }
        return false;
    }

    public void Clear()
    {
        if (count > 0)
        {
            for (int i = 0; i < buckets.Length; i++)
                buckets[i] = -1;
            Array.Clear(entries, 0, count);
            freeList = -1;
            count = 0;
            freeCount = 0;
        }
    }

    public bool ContainsKey(TKey key)
    {
        return FindEntry(key) >= 0;
    }

    public bool ContainsValue(TValue value)
    {
        if (value == null)
        {
            for (int i = 0; i < count; i++)
            {
                if (entries[i].hashCode >= 0 && entries[i].value == null)
                    return true;
            }
        }
        else
        {
            EqualityComparer<TValue> c = EqualityComparer<TValue>.Default;
            for (int i = 0; i < count; i++)
            {
                if (entries[i].hashCode >= 0 && c.Equals(entries[i].value, value))
                    return true;
            }
        }
        return false;
    }

    private void CopyTo(KeyValuePair<TKey, TValue>[] array, int index)
    {
        int count = this.count;
        Entry[] entries = this.entries;
        for (int i = 0; i < count; i++)
        {
            if (entries[i].hashCode >= 0)
            {
                array[index++] = new KeyValuePair<TKey, TValue>(entries[i].key, entries[i].value);
            }
        }
    }

    public Enumerator GetEnumerator()
    {
        return new Enumerator(this, Enumerator.KeyValuePair);
    }

    IEnumerator<KeyValuePair<TKey, TValue>> IEnumerable<KeyValuePair<TKey, TValue>>.GetEnumerator()
    {
        return new Enumerator(this, Enumerator.KeyValuePair);
    }

    // 		[System.Security.SecurityCritical]  // auto-generated_required
    // 		public virtual void GetObjectData(SerializationInfo info, StreamingContext context) {
    // 			if (info==null) {
    // 				ThrowHelper.ThrowArgumentNullException(ExceptionArgument.info);
    // 			}
    // 			info.AddValue(VersionName, version);

    // #if FEATURE_RANDOMIZED_STRING_HASHING
    // 			info.AddValue(ComparerName, HashHelpers.GetEqualityComparerForSerialization(comparer), typeof(IEqualityComparer<TKey>));
    // #else
    // 			info.AddValue(ComparerName, comparer, typeof(IEqualityComparer<TKey>));
    // #endif

    // 			info.AddValue(HashSizeName, buckets == null ? 0 : buckets.Length); //This is the length of the bucket array.
    // 			if( buckets != null) {
    // 				KeyValuePair<TKey, TValue>[] array = new KeyValuePair<TKey, TValue>[Count];
    // 				CopyTo(array, 0);
    // 				info.AddValue(KeyValuePairsName, array, typeof(KeyValuePair<TKey, TValue>[]));
    // 			}
    // 		}

    private int FindEntry(TKey key)
    {
        if (buckets != null)
        {
            int hashCode = comparer.GetHashCode(key) & 0x7FFFFFFF;
            for (int i = buckets[hashCode % buckets.Length]; i >= 0; i = entries[i].next)
            {
                if (entries[i].hashCode == hashCode && comparer.Equals(entries[i].key, key))
                    return i;
            }
        }
        return -1;
    }

    private void Initialize(int capacity)
    {
        int size = HashHelpers.GetPrime(capacity);
        buckets = new int[size];
        for (int i = 0; i < buckets.Length; i++)
            buckets[i] = -1;
        entries = new Entry[size];
        freeList = -1;
    }

    private void Insert(TKey key, TValue value, bool add)
    {
        if (buckets == null)
            Initialize(0);
        int hashCode = comparer.GetHashCode(key) & 0x7FFFFFFF;
        int targetBucket = hashCode % buckets.Length;

#if FEATURE_RANDOMIZED_STRING_HASHING
        int collisionCount = 0;
#endif

        for (int i = buckets[targetBucket]; i >= 0; i = entries[i].next)
        {
            if (entries[i].hashCode == hashCode && comparer.Equals(entries[i].key, key))
            {
                entries[i].value = value;

                return;
            }

#if FEATURE_RANDOMIZED_STRING_HASHING
            collisionCount++;
#endif
        }
        int index;
        if (freeCount > 0)
        {
            index = freeList;
            freeList = entries[index].next;
            freeCount--;
        }
        else
        {
            if (count == entries.Length)
            {
                Resize();
                targetBucket = hashCode % buckets.Length;
            }
            index = count;
            count++;
        }

        entries[index].hashCode = hashCode;
        entries[index].next = buckets[targetBucket];
        entries[index].key = key;
        entries[index].value = value;
        buckets[targetBucket] = index;

#if FEATURE_RANDOMIZED_STRING_HASHING

#if FEATURE_CORECLR
			// In case we hit the collision threshold we'll need to switch to the comparer which is using randomized string hashing
			// in this case will be EqualityComparer<string>.Default.
			// Note, randomized string hashing is turned on by default on coreclr so EqualityComparer<string>.Default will 
			// be using randomized string hashing

			if (collisionCount > HashHelpers.HashCollisionThreshold && comparer == NonRandomizedStringEqualityComparer.Default) 
			{
				comparer = (IEqualityComparer<TKey>) EqualityComparer<string>.Default;
				Resize(entries.Length, true);
			}
#else
        if (
            collisionCount > HashHelpers.HashCollisionThreshold
            && HashHelpers.IsWellKnownEqualityComparer(comparer)
        )
        {
            comparer = (IEqualityComparer<TKey>)HashHelpers.GetRandomizedEqualityComparer(comparer);
            Resize(entries.Length, true);
        }
#endif // FEATURE_CORECLR

#endif
    }

    private void Resize()
    {
        Resize(HashHelpers.ExpandPrime(count), false);
    }

    private void Resize(int newSize, bool forceNewHashCodes)
    {
        int[] newBuckets = new int[newSize];
        for (int i = 0; i < newBuckets.Length; i++)
            newBuckets[i] = -1;
        Entry[] newEntries = new Entry[newSize];
        Array.Copy(entries, 0, newEntries, 0, count);
        if (forceNewHashCodes)
        {
            for (int i = 0; i < count; i++)
            {
                if (newEntries[i].hashCode != -1)
                {
                    newEntries[i].hashCode = (comparer.GetHashCode(newEntries[i].key) & 0x7FFFFFFF);
                }
            }
        }
        for (int i = 0; i < count; i++)
        {
            if (newEntries[i].hashCode >= 0)
            {
                int bucket = newEntries[i].hashCode % newSize;
                newEntries[i].next = newBuckets[bucket];
                newBuckets[bucket] = i;
            }
        }
        buckets = newBuckets;
        entries = newEntries;
    }

    public bool Remove(TKey key)
    {
        if (buckets != null)
        {
            int hashCode = comparer.GetHashCode(key) & 0x7FFFFFFF;
            int bucket = hashCode % buckets.Length;
            int last = -1;
            for (int i = buckets[bucket]; i >= 0; last = i, i = entries[i].next)
            {
                if (entries[i].hashCode == hashCode && comparer.Equals(entries[i].key, key))
                {
                    if (last < 0)
                    {
                        buckets[bucket] = entries[i].next;
                    }
                    else
                    {
                        entries[last].next = entries[i].next;
                    }
                    entries[i].hashCode = -1;
                    entries[i].next = freeList;
                    entries[i].key = default(TKey);
                    entries[i].value = default(TValue);
                    freeList = i;
                    freeCount++;

                    return true;
                }
            }
        }
        return false;
    }

    public bool TryGetValue(TKey key, out TValue value)
    {
        int i = FindEntry(key);
        if (i >= 0)
        {
            value = entries[i].value;
            return true;
        }
        value = default(TValue);
        return false;
    }

    // This is a convenience method for the internal callers that were converted from using Hashtable.
    // Many were combining key doesn't exist and key exists but null value (for non-value types) checks.
    // This allows them to continue getting that behavior with minimal code delta. This is basically
    // TryGetValue without the out param
    internal TValue GetValueOrDefault(TKey key)
    {
        int i = FindEntry(key);
        if (i >= 0)
        {
            return entries[i].value;
        }
        return default(TValue);
    }

    bool ICollection<KeyValuePair<TKey, TValue>>.IsReadOnly
    {
        get { return false; }
    }

    void ICollection<KeyValuePair<TKey, TValue>>.CopyTo(
        KeyValuePair<TKey, TValue>[] array,
        int index
    )
    {
        CopyTo(array, index);
    }

    void ICollection.CopyTo(Array array, int index)
    {
        KeyValuePair<TKey, TValue>[] pairs = array as KeyValuePair<TKey, TValue>[];
        if (pairs != null)
        {
            CopyTo(pairs, index);
        }
        else if (array is DictionaryEntry[])
        {
            DictionaryEntry[] dictEntryArray = array as DictionaryEntry[];
            Entry[] entries = this.entries;
            for (int i = 0; i < count; i++)
            {
                if (entries[i].hashCode >= 0)
                {
                    dictEntryArray[index++] = new DictionaryEntry(entries[i].key, entries[i].value);
                }
            }
        }
        else
        {
            object[] objects = array as object[];

            int count = this.count;
            Entry[] entries = this.entries;
            for (int i = 0; i < count; i++)
            {
                if (entries[i].hashCode >= 0)
                {
                    objects[index++] = new KeyValuePair<TKey, TValue>(
                        entries[i].key,
                        entries[i].value
                    );
                }
            }
        }
    }

    IEnumerator IEnumerable.GetEnumerator()
    {
        return new Enumerator(this, Enumerator.KeyValuePair);
    }

    bool ICollection.IsSynchronized
    {
        get { return false; }
    }

    object ICollection.SyncRoot
    {
        get { return null; }
    }

    bool IDictionary.IsFixedSize
    {
        get { return false; }
    }

    bool IDictionary.IsReadOnly
    {
        get { return false; }
    }

    ICollection IDictionary.Keys
    {
        get { return (ICollection)Keys; }
    }

    ICollection IDictionary.Values
    {
        get { return (ICollection)Values; }
    }

    object IDictionary.this[object key]
    {
        get
        {
            if (IsCompatibleKey(key))
            {
                int i = FindEntry((TKey)key);
                if (i >= 0)
                {
                    return entries[i].value;
                }
            }
            return null;
        }
        set
        {
            TKey tempKey = (TKey)key;
            this[tempKey] = (TValue)value;
        }
    }

    private static bool IsCompatibleKey(object key)
    {
        return (key is TKey);
    }

    void IDictionary.Add(object key, object value)
    {
        TKey tempKey = (TKey)key;

        Add(tempKey, (TValue)value);
    }

    bool IDictionary.Contains(object key)
    {
        if (IsCompatibleKey(key))
        {
            return ContainsKey((TKey)key);
        }

        return false;
    }

    IDictionaryEnumerator IDictionary.GetEnumerator()
    {
        return new Enumerator(this, Enumerator.DictEntry);
    }

    void IDictionary.Remove(object key)
    {
        if (IsCompatibleKey(key))
        {
            Remove((TKey)key);
        }
    }

    [Serializable]
    public struct Enumerator : IEnumerator<KeyValuePair<TKey, TValue>>, IDictionaryEnumerator
    {
        private MyDictionary<TKey, TValue> dictionary;
        private int index;
        private KeyValuePair<TKey, TValue> current;
        private int getEnumeratorRetType; // What should Enumerator.Current return?

        internal const int DictEntry = 1;
        internal const int KeyValuePair = 2;

        internal Enumerator(MyDictionary<TKey, TValue> dictionary, int getEnumeratorRetType)
        {
            this.dictionary = dictionary;
            index = 0;
            this.getEnumeratorRetType = getEnumeratorRetType;
            current = new KeyValuePair<TKey, TValue>();
        }

        public bool MoveNext()
        {
            // Use unsigned comparison since we set index to dictionary.count+1 when the enumeration ends.
            // dictionary.count+1 could be negative if dictionary.count is Int32.MaxValue
            while ((uint)index < (uint)dictionary.count)
            {
                if (dictionary.entries[index].hashCode >= 0)
                {
                    current = new KeyValuePair<TKey, TValue>(
                        dictionary.entries[index].key,
                        dictionary.entries[index].value
                    );
                    index++;
                    return true;
                }
                index++;
            }

            index = dictionary.count + 1;
            current = new KeyValuePair<TKey, TValue>();
            return false;
        }

        public KeyValuePair<TKey, TValue> Current
        {
            get { return current; }
        }

        public void Dispose() { }

        object IEnumerator.Current
        {
            get
            {

                if (getEnumeratorRetType == DictEntry)
                {
                    return new System.Collections.DictionaryEntry(current.Key, current.Value);
                }
                else
                {
                    return new KeyValuePair<TKey, TValue>(current.Key, current.Value);
                }
            }
        }

        void IEnumerator.Reset()
        {
            index = 0;
            current = new KeyValuePair<TKey, TValue>();
        }

        DictionaryEntry IDictionaryEnumerator.Entry
        {
            get
            {

                return new DictionaryEntry(current.Key, current.Value);
            }
        }

        object IDictionaryEnumerator.Key
        {
            get { return current.Key; }
        }

        object IDictionaryEnumerator.Value
        {
            get { return current.Value; }
        }
    }

    public sealed class KeyCollection : ICollection<TKey>, ICollection, IReadOnlyCollection<TKey>
    {
        private MyDictionary<TKey, TValue> dictionary;

        public KeyCollection(MyDictionary<TKey, TValue> dictionary)
        {
            this.dictionary = dictionary;
        }

        public Enumerator GetEnumerator()
        {
            return new Enumerator(dictionary);
        }

        public void CopyTo(TKey[] array, int index)
        {
            int count = dictionary.count;
            Entry[] entries = dictionary.entries;
            for (int i = 0; i < count; i++)
            {
                if (entries[i].hashCode >= 0)
                    array[index++] = entries[i].key;
            }
        }

        public int Count
        {
            get { return dictionary.Count; }
        }

        bool ICollection<TKey>.IsReadOnly
        {
            get { return true; }
        }

        void ICollection<TKey>.Add(TKey item)
        {
            //ThrowHelper.ThrowNotSupportedException(ExceptionResource.NotSupported_KeyCollectionSet);
        }

        void ICollection<TKey>.Clear()
        {
            //ThrowHelper.ThrowNotSupportedException(ExceptionResource.NotSupported_KeyCollectionSet);
        }

        bool ICollection<TKey>.Contains(TKey item)
        {
            return dictionary.ContainsKey(item);
        }

        bool ICollection<TKey>.Remove(TKey item)
        {
            //ThrowHelper.ThrowNotSupportedException(ExceptionResource.NotSupported_KeyCollectionSet);
            return false;
        }

        IEnumerator<TKey> IEnumerable<TKey>.GetEnumerator()
        {
            return new Enumerator(dictionary);
        }

        IEnumerator IEnumerable.GetEnumerator()
        {
            return new Enumerator(dictionary);
        }

        void ICollection.CopyTo(Array array, int index)
        {
            TKey[] keys = array as TKey[];
            if (keys != null)
            {
                CopyTo(keys, index);
            }
            else
            {
                object[] objects = array as object[];

                int count = dictionary.count;
                Entry[] entries = dictionary.entries;
                for (int i = 0; i < count; i++)
                {
                    if (entries[i].hashCode >= 0)
                        objects[index++] = entries[i].key;
                }
            }
        }

        bool ICollection.IsSynchronized
        {
            get { return false; }
        }

        Object ICollection.SyncRoot
        {
            get { return ((ICollection)dictionary).SyncRoot; }
        }

        [Serializable]
        public struct Enumerator : IEnumerator<TKey>, System.Collections.IEnumerator
        {
            private MyDictionary<TKey, TValue> dictionary;
            private int index;
            private TKey currentKey;

            internal Enumerator(MyDictionary<TKey, TValue> dictionary)
            {
                this.dictionary = dictionary;
                index = 0;
                currentKey = default(TKey);
            }

            public void Dispose() { }

            public bool MoveNext()
            {
                while ((uint)index < (uint)dictionary.count)
                {
                    if (dictionary.entries[index].hashCode >= 0)
                    {
                        currentKey = dictionary.entries[index].key;
                        index++;
                        return true;
                    }
                    index++;
                }

                index = dictionary.count + 1;
                currentKey = default(TKey);
                return false;
            }

            public TKey Current
            {
                get { return currentKey; }
            }

            Object System.Collections.IEnumerator.Current
            {
                get
                {

                    return currentKey;
                }
            }

            void System.Collections.IEnumerator.Reset()
            {
                index = 0;
                currentKey = default(TKey);
            }
        }
    }

    public sealed class ValueCollection
        : ICollection<TValue>,
            ICollection,
            IReadOnlyCollection<TValue>
    {
        private MyDictionary<TKey, TValue> dictionary;

        public ValueCollection(MyDictionary<TKey, TValue> dictionary)
        {
            this.dictionary = dictionary;
        }

        public Enumerator GetEnumerator()
        {
            return new Enumerator(dictionary);
        }

        public void CopyTo(TValue[] array, int index)
        {
            int count = dictionary.count;
            Entry[] entries = dictionary.entries;
            for (int i = 0; i < count; i++)
            {
                if (entries[i].hashCode >= 0)
                    array[index++] = entries[i].value;
            }
        }

        public int Count
        {
            get { return dictionary.Count; }
        }

        bool ICollection<TValue>.IsReadOnly
        {
            get { return true; }
        }

        void ICollection<TValue>.Add(TValue item)
        {
            //ThrowHelper.ThrowNotSupportedException(ExceptionResource.NotSupported_ValueCollectionSet);
        }

        bool ICollection<TValue>.Remove(TValue item)
        {
            //ThrowHelper.ThrowNotSupportedException(ExceptionResource.NotSupported_ValueCollectionSet);
            return false;
        }

        void ICollection<TValue>.Clear()
        {
            //ThrowHelper.ThrowNotSupportedException(ExceptionResource.NotSupported_ValueCollectionSet);
        }

        bool ICollection<TValue>.Contains(TValue item)
        {
            return dictionary.ContainsValue(item);
        }

        IEnumerator<TValue> IEnumerable<TValue>.GetEnumerator()
        {
            return new Enumerator(dictionary);
        }

        IEnumerator IEnumerable.GetEnumerator()
        {
            return new Enumerator(dictionary);
        }

        void ICollection.CopyTo(Array array, int index)
        {
            TValue[] values = array as TValue[];
            if (values != null)
            {
                CopyTo(values, index);
            }
            else
            {
                object[] objects = array as object[];

                int count = dictionary.count;
                Entry[] entries = dictionary.entries;
                for (int i = 0; i < count; i++)
                {
                    if (entries[i].hashCode >= 0)
                        objects[index++] = entries[i].value;
                }
            }
        }

        bool ICollection.IsSynchronized
        {
            get { return false; }
        }

        Object ICollection.SyncRoot
        {
            get { return ((ICollection)dictionary).SyncRoot; }
        }

        [Serializable]
        public struct Enumerator : IEnumerator<TValue>, System.Collections.IEnumerator
        {
            private MyDictionary<TKey, TValue> dictionary;
            private int index;
            private TValue currentValue;

            internal Enumerator(MyDictionary<TKey, TValue> dictionary)
            {
                this.dictionary = dictionary;
                index = 0;
                currentValue = default(TValue);
            }

            public void Dispose() { }

            public bool MoveNext()
            {
                while ((uint)index < (uint)dictionary.count)
                {
                    if (dictionary.entries[index].hashCode >= 0)
                    {
                        currentValue = dictionary.entries[index].value;
                        index++;
                        return true;
                    }
                    index++;
                }
                index = dictionary.count + 1;
                currentValue = default(TValue);
                return false;
            }

            public TValue Current
            {
                get { return currentValue; }
            }

            Object System.Collections.IEnumerator.Current
            {
                get
                {

                    return currentValue;
                }
            }

            void System.Collections.IEnumerator.Reset()
            {
                index = 0;
                currentValue = default(TValue);
            }
        }
    }
}
