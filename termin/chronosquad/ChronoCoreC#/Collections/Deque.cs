// using System;
// using System.Collections.Generic;


// public class DequeBlockStorage<T>
// {
// 	public T[] data;
// 	public int sptr;
// 	public int eptr;

// 	public DequeBlockStorage(int size)
// 	{
// 		data = new T[size];
// 	}

// 	public void AddBack(T item)
// 	{
// 		data[eptr++] = item;
// 	}

// 	public void RemoveBack()
// 	{
// 		eptr--;
// 	}

// 	public void SetBlock(DequeBlock<T> block)
// 	{
// 		node = block.node;
// 	}

// 	public void Remove(int index)
// 	{
// 		Array.Copy(data, index + 1, data, index, eptr - index - 1);
// 		eptr--;
// 	}

// 	public T this[int index]
// 	{
// 		get
// 		{
// 			return data[index];
// 		}
// 		set
// 		{
// 			data[index] = value;
// 		}
// 	}
// }

// public class DequeBlock<T>
// {
// 	public DequeBlockStorage<T> storage;



// 	public DequeBlock(int size)
// 	{
// 		storage = new DequeBlockStorage<T>(size);
// 	}

// 	public T this[int index]
// 	{
// 		get
// 		{
// 			return storage[index];
// 		}
// 	}

// }

// public class DequeNode<T>
// {
// 	public DequeBlock<T> block;
// 	public int index;

// 	public DequeNode(DequeBlock<T> block, int index)
// 	{
// 		this.block = block;
// 		this.index = index;
// 	}

// 	public void RemoveThis()
// 	{
// 		block.Remove(index);
// 	}

// 	public T Value
// 	{
// 		get
// 		{
// 			return block[index];
// 		}
// 	}
// }

// public class Deque<T>
// {
// 	int blockSize = 168;
// 	LinkedList<DequeBlock<T>> blocks;
// 	int _size = 0;

// 	public Deque()
// 	{
// 		blocks = new LinkedList<DequeBlock<T>>();
// 	}

// 	public Deque(Deque<T> other)
// 	{
// 		blockSize = other.blockSize;
// 		blocks = new LinkedList<DequeBlock<T>>();
// 		foreach (var block in other.blocks)
// 		{
// 			var new_block = new DequeBlock<T>(blockSize);
// 			new_block.sptr = block.sptr;
// 			new_block.eptr = block.eptr;
// 			Array.Copy(block.data, new_block.data, blockSize);
// 			blocks.AddLast(new_block);
// 		}
// 		_size = other._size;
// 	}

// 	public void Add(T item)
// 	{
// 		if (blocks.Count == 0 || blocks.Last.Value.eptr == blockSize)
// 		{
// 			blocks.AddLast(new DequeBlock<T>(blockSize));
// 		}

// 		blocks.Last.Value.AddBack(item);
// 		_size++;
// 	}

// 	public int Count => _size;

// 	public DequeNode<T> First
// 	{
// 		get
// 		{
// 			return new DequeNode<T>(blocks.First.Value, 0);
// 		}
// 	}

// 	public void Remove(DequeNode<T> item)
// 	{
// 		item.RemoveThis();
// 	}

// 	public DequeNode<T> Last
// 	{
// 		get
// 		{
// 			return new DequeNode<T>(blocks.Last.Value, blocks.Last.Value.eptr - 1);
// 		}
// 	}

// 	// enumerator for foreach
// 	public IEnumerator<T> GetEnumerator()
// 	{
// 		foreach (var block in blocks)
// 		{
// 			for (int i = 0; i < block.eptr; i++)
// 			{
// 				yield return block.data[i];
// 			}
// 		}
// 	}

// }
