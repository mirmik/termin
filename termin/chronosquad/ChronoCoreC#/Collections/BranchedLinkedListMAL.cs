// 	using System;
// 	using System.Collections.Generic;
// 	using System.Security.Permissions;

// 	#if UNITY_64
// 	using Unity.Profiling;
// 	using UnityEngine;
// 	#endif

// 	public struct BranchedLinkedListMAL<T>:
// 		//ICollection<T>,
// 		System.Collections.ICollection,
// 		IReadOnlyCollection<T>
// 		where T: BasicMultipleAction
// 	{
// 		// This BranchedLinkedListMAL is a doubly-Linked circular list.
// 		internal BranchedLinkedListNodeMAL<T> head;
// 		internal int count;

// 		public BranchedLinkedListMAL(bool stub)
// 		{
// 			count = 0;
// 			head = null;
// 			AddTerminators();
// 		}

// 		public BranchedLinkedListNodeMAL<T> NoneNode()
// 		{
// 			return head;
// 		}

// 		// public BranchedLinkedListMAL(IEnumerable<T> collection)
// 		// {
// 		// 	head = collection.head;
// 		// 	count = collection.count;
// 		// }

// 		public void AddTerminators()
// 		{
// 			Debug.Assert(head == null);
// 			BranchedLinkedListNodeMAL<T> maxnode = new BranchedLinkedListNodeMAL<T>(null, long.MaxValue, long.MaxValue);
// 			BranchedLinkedListNodeMAL<T> minnode = new BranchedLinkedListNodeMAL<T>(null, long.MinValue, long.MinValue);
// 			maxnode.next = null;
// 			maxnode.prev = minnode;
// 			minnode.next = maxnode;
// 			minnode.prev = null;
// 			head = minnode;
// 		}

// 		public ForkNode<T> AddForkAfter(BranchedLinkedListNodeMAL<T> node, long step, bool positive)
// 		{
// 			var entrance = new BranchEntrance<T>();
// 			entrance.StartStep = step;
// 			entrance.FinishStep = step;

// 			var fork = new ForkNode<T>();
// 			fork.branchEntrance = entrance;
// 			fork.StartStep = step;
// 			fork.FinishStep = step;
// 			AddAfter(node, fork);

// 			if (positive)
// 			{
// 				var terminator = new BranchedLinkedListNodeMAL<T>(null, long.MaxValue, long.MaxValue);
// 				terminator.next = null;
// 				terminator.prev = entrance;
// 				entrance.next = terminator;
// 				entrance.prev = fork;
// 			}
// 			else
// 			{
// 				var terminator = new BranchedLinkedListNodeMAL<T>(null, long.MinValue, long.MinValue);
// 				terminator.next = fork.next;
// 				terminator.prev = null;
// 				entrance.next = fork;
// 				entrance.prev = terminator;
// 			}

// 			return fork;
// 		}

// 		public int Count {
// 			get { return count;}
// 		}

// 		public BranchedLinkedListNodeMAL<T> First {
// 			get { return head;}
// 		}

// 		// public BranchedLinkedListNodeMAL<T> Last {
// 		// 	get { return head.prev;}
// 		// }

// 		// bool ICollection<T>.IsReadOnly {
// 		// 	get { return false; }
// 		// }

// 		// void ICollection<T>.Add(T value) {
// 		// 	AddLast(value);
// 		// }

// 		public BranchedLinkedListNodeMAL<T> AddAfter(BranchedLinkedListNodeMAL<T> node, T value) {
// 			BranchedLinkedListNodeMAL<T> result = new BranchedLinkedListNodeMAL<T>(value);
// 			InternalInsertNodeAfter(node, result);
// 			return result;
// 		}

// 		public void AddAfter(BranchedLinkedListNodeMAL<T> node, BranchedLinkedListNodeMAL<T> newNode) {
// 			InternalInsertNodeAfter(node, newNode);
// 			//newNode.list = this;
// 		}

// 		public BranchedLinkedListNodeMAL<T> AddBefore(BranchedLinkedListNodeMAL<T> node, T value) {
// 			BranchedLinkedListNodeMAL<T> result = new BranchedLinkedListNodeMAL<T>(value);
// 			InternalInsertNodeBefore(node, result);
// 			// if ( node == head) {
// 			// 	head = result;
// 			// }
// 			return result;
// 		}

// 		public void AddBefore(BranchedLinkedListNodeMAL<T> node, BranchedLinkedListNodeMAL<T> newNode) {
// 			InternalInsertNodeBefore(node, newNode);
// 			//newNode.list = this;
// 			// if ( node == head) {
// 			// 	head = newNode;
// 			// }
// 		}



// 		public BranchedLinkedListNodeMAL<T> AddFirst(T value) {
// 			BranchedLinkedListNodeMAL<T> result = new BranchedLinkedListNodeMAL<T>(value);
// 			head = result;
// 			return result;
// 		}

// 		// public void AddFirst(BranchedLinkedListNodeMAL<T> node) {
// 		// 		InternalInsertNodeAfter( head, node);
// 		// }

// 	// //[IgnoredByDeepProfilerAttribute]
// 	// 	public BranchedLinkedListNodeMAL<T> AddLast(T value) {
// 	// 		BranchedLinkedListNodeMAL<T> result = new BranchedLinkedListNodeMAL<T>(value);
// 	// 			InternalInsertNodeBefore( head, result);
// 	// 		return result;
// 	// 	}

// 	// //[IgnoredByDeepProfilerAttribute]
// 	// 	public void AddLast(BranchedLinkedListNodeMAL<T> node) {
// 	// 			InternalInsertNodeBefore( head, node);
// 	// 	}

// 		public void Clear() {
// 			BranchedLinkedListNodeMAL<T> current = head.next;
// 			while (current != head ) {
// 				BranchedLinkedListNodeMAL<T> temp = current;
// 				current = current.next;   // use Next the instead of "next", otherwise it will loop forever
// 				temp.Invalidate();
// 			}

// 			head.next = head;
// 			head.prev = head;
// 			count = 0;
// 		}

// 		public bool Contains(T value) {
// 			return false;
// 			//return Find(value) != null;
// 		}

// 		public void CopyTo( T[] array, int index) {
// 			BranchedLinkedListNodeMAL<T> node = head.next;
// 			if (node != head) {
// 				do {
// 					array[index++] = node.item;
// 					node = node.next;
// 				} while (node != head);
// 			}
// 		}

// 		public BranchedLinkedListNodeMAL<T> Find(T value) {
// 			// BranchedLinkedListNodeMAL<T> node = head;
// 			// EqualityComparer<T> c = EqualityComparer<T>.Default;
// 			// if (node != null) {
// 			// 	if (value != null) {
// 			// 		do {
// 			// 			if (c.Equals(node.item, value)) {
// 			// 				return node;
// 			// 			}
// 			// 			node = node.next;
// 			// 		} while (node != head);
// 			// 	}
// 			// 	else {
// 			// 		do {
// 			// 			if (node.item == null) {
// 			// 				return node;
// 			// 			}
// 			// 			node = node.next;
// 			// 		} while (node != head);
// 			// 	}
// 			// }
// 			return null;
// 		}

// 	// //[IgnoredByDeepProfilerAttribute]
// 	// 	public BranchedLinkedListNodeMAL<T> FindLast(T value) {
// 	// 		if ( head == null) return null;

// 	// 		BranchedLinkedListNodeMAL<T> last = head.prev;
// 	// 		BranchedLinkedListNodeMAL<T> node = last;
// 	// 		EqualityComparer<T> c = EqualityComparer<T>.Default;
// 	// 		if (node != null) {
// 	// 			if (value != null) {
// 	// 				do {
// 	// 					if (c.Equals(node.item, value)) {
// 	// 						return node;
// 	// 					}

// 	// 					node = node.prev;
// 	// 				} while (node != last);
// 	// 			}
// 	// 			else {
// 	// 				do {
// 	// 					if (node.item == null) {
// 	// 						return node;
// 	// 					}
// 	// 					node = node.prev;
// 	// 				} while (node != last);
// 	// 			}
// 	// 		}
// 	// 		return null;
// 	// 	}

// 		public Enumerator GetEnumerator() {
// 			return new Enumerator(this);
// 		}

// 		IEnumerator<T> IEnumerable<T>.GetEnumerator() {
// 			return GetEnumerator();
// 		}

// 		public bool Remove(T value) {
// 			throw new NotImplementedException();
// 			//return false;
// 		}

// 		public void Remove(BranchedLinkedListNodeMAL<T> node) {
// 			InternalRemoveNode(node);
// 		}

// 	//[IgnoredByDeepProfilerAttribute]
// 		public void RemoveFirst() {
// 			if ( head == head.next) { throw new InvalidOperationException(""); }
// 			InternalRemoveNode(head.next);
// 		}

// 		public void RemoveLast() {
// 			if ( head == head.prev) { throw new InvalidOperationException(""); }
// 			InternalRemoveNode(head.prev);
// 		}

// 		private void InternalInsertNodeBefore(BranchedLinkedListNodeMAL<T> node, BranchedLinkedListNodeMAL<T> newNode) {
// 			newNode.next = node;
// 			newNode.prev = node.prev;
// 			node.prev.next = newNode;
// 			node.prev = newNode;
// 			count++;
// 		}

// 		private void InternalInsertNodeAfter(BranchedLinkedListNodeMAL<T> node, BranchedLinkedListNodeMAL<T> newNode) {
// 			newNode.prev = node;
// 			newNode.next = node.next;
// 			node.next.prev = newNode;
// 			node.next = newNode;
// 			count++;
// 		}


// 		internal void InternalRemoveNode(BranchedLinkedListNodeMAL<T> node) {
// 			if (node == head) {
// 				throw new InvalidOperationException("");
// 			}

// 			node.prev.next = node.next;
// 			node.next.prev = node.prev;

// 			node.Invalidate();
// 			count--;
// 		}

// 		bool System.Collections.ICollection.IsSynchronized {
// 			get { return false;}
// 		}

// 		object System.Collections.ICollection.SyncRoot  {
// 			get {
// 				return null;
// 			}
// 		}

// 		void System.Collections.ICollection.CopyTo(Array  array, int index) {
// 			// T[] tArray = array as T[];
// 			// if (tArray != null) {
// 			// 	CopyTo(tArray, index);
// 			// }
// 			// else {
// 			// 	//
// 			// 	// Catch the obvious case assignment will fail.
// 			// 	// We can found all possible problems by doing the check though.
// 			// 	// For example, if the element type of the Array is derived from T,
// 			// 	// we can't figure out if we can successfully copy the element beforehand.
// 			// 	//
// 			// 	Type targetType = array.GetType().GetElementType();
// 			// 	Type sourceType = typeof(T);


// 			// 	object[] objects = array as object[];
// 			// 		BranchedLinkedListNodeMAL<T> node = head;
// 			// 	try {
// 			// 		if (node != null) {
// 			// 			do {
// 			// 				objects[index++] = node.item;
// 			// 				node = node.next;
// 			// 			} while (node != head);
// 			// 		}
// 			// 	}
// 			// 	catch(ArrayTypeMismatchException) {
// 			// 	//	throw new ArgumentException(SR.GetString(SR.Invalid_Array_Type));
// 			// 	}
// 			// }
// 			throw new NotImplementedException();
// 		}

// 		System.Collections.IEnumerator System.Collections.IEnumerable.GetEnumerator() {
// 			return GetEnumerator();
// 		}

// 		public struct Enumerator : IEnumerator<T>, System.Collections.IEnumerator
// 		{
// 			private BranchedLinkedListMAL<T> list;
// 			private BranchedLinkedListNodeMAL<T> node;
// 			private T current;
// 			//private int index;

// 			internal Enumerator(BranchedLinkedListMAL<T> list) {
// 				this.list = list;
// 				node = list.head;
// 				current = default(T);
// 			}


// 			public T Current {
// 				get { return current;}
// 			}

// 			object System.Collections.IEnumerator.Current {
// 				get {
// 					return current;
// 				}
// 			}

// 			public bool MoveNext() {
// 				if (node.next != list.head) {
// 					node = node.next;
// 					current = node.item;
// 					//index++;
// 					return true;
// 				}
// 				else {
// 					current = default(T);
// 					//index = list.Count + 1;
// 					return false;
// 				}
// 			}

// 			void System.Collections.IEnumerator.Reset() {
// 				current = default(T);
// 				node = list.head;
// 				//index = 0;
// 			}

// 			public void Dispose() {
// 			}

// 		}

// 	}

// 	public class BranchedLinkedListNodeMAL<T> where T: BasicMultipleAction
// 	 {
// 		//internal BranchedLinkedListMAL<T> list;
// 		//internal BranchedLinkedListNodeMAL<T> head;
// 		internal BranchedLinkedListNodeMAL<T> next;
// 		internal BranchedLinkedListNodeMAL<T> prev;
// 		internal T item;

// 		public long StartStep;
// 		public long FinishStep;

// 		public BranchedLinkedListNodeMAL(T value) {
// 			this.item = value;
// 			StartStep = value.StartStep;
// 			FinishStep = value.FinishStep;
// 		}

// 		public BranchedLinkedListNodeMAL(
// 			T item,
// 			long StartStep,
// 			long FinishStep)
// 		{
// 			this.item = item;
// 			this.StartStep = StartStep;
// 			this.FinishStep = FinishStep;
// 		}


// 		// internal BranchedLinkedListNodeMAL(T value) {
// 		// 	//this.list = list;
// 		// //	this.head = list;
// 		// 	this.item = value;
// 		// 	StartStep = value.StartStep;
// 		// 	FinishStep = value.FinishStep;
// 		// }
// 		internal BranchedLinkedListNodeMAL() {
// 		//	this.head = list;
// 			this.next = null;
// 			this.prev = null;
// 			this.item = null;
// 		}

// 		// internal BranchedLinkedListNodeMAL() {
// 		// //	this.head = this;
// 		// 	this.next = this;
// 		// 	this.prev = this;
// 		// 	this.item = null;
// 		// }

// 		internal void Init(BranchedLinkedListNodeMAL<T> list) {
// 		//	this.head = list;
// 			this.next = list;
// 			this.prev = list;
// 			this.item = null;
// 		}

// 		// public BranchedLinkedListMAL<T> MyList {
// 		// 	get { return list;}
// 		// }

// 		public BranchedLinkedListNodeMAL<T> Next {
// 			get { return next;}
// 		}

// 		public BranchedLinkedListNodeMAL<T> Previous {
// 			get { return prev;}
// 		}

// 		public T Value {
// 			get { return item;}
// 			set { item = value;}
// 		}

// 		internal void Invalidate() {
// 		//	head = null;
// 			next = null;
// 			prev = null;
// 		}
// 	}


// public class ForkNode<T> : BranchedLinkedListNodeMAL<T> where T : BasicMultipleAction
// {
// 	public BranchEntrance<T> branchEntrance;
// }

// public class BranchEntrance<T> : BranchedLinkedListNodeMAL<T> where T : BasicMultipleAction
// {

// }
